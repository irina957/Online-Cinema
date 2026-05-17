import secrets
import uuid
from typing import cast
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, status, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from src.database.models.movies import Notification
from schemas.movies import NotificationSchema
from src.security.roles import RoleChecker
from src.security.dependencies import get_current_user
from src.security.tokens import create_access_token, create_refresh_token
from src.database.session import get_db
from src.config.settings import settings
from src.tasks.accounts import send_activation_email
from src.tasks.accounts import send_reset_password_email
from src.database.models.accounts import (
    User,
    UserGroup,
    UserGroupEnum,
    ActivationToken,
    RefreshToken,
    PasswordResetToken,
    UserProfile,
)
from src.schemas.accounts import (
    UserRegistrationRequestSchema,
    UserRegistrationResponseSchema,
    MessageResponseSchema,
    UserActivationRequestSchema,
    UserActivationResendRequestSchema,
    UserLoginResponseSchema,
    UserLoginRequestSchema,
    PasswordResetCompleteRequestSchema,
    PasswordChangeRequestSchema,
    PasswordResetRequestSchema,
    UserProfileSchema,
    UserProfileUpdateSchema,
    TokenRefreshRequestSchema,
)

from src.security.passwords import hash_password
from storages.minio_client import delete_avatar, upload_avatar, get_avatar_url

router = APIRouter(prefix="/accounts", tags=["Accounts"])


@router.post(
    "/register/",
    response_model=UserRegistrationResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def register_user(
    user_data: UserRegistrationRequestSchema,
    db: AsyncSession = Depends(get_db),
) -> UserRegistrationResponseSchema:
    query_existing = select(User).where(User.email == str(user_data.email))
    res_existing = await db.execute(query_existing)

    if res_existing.scalars().first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A user with this email {user_data.email} already exists.",
        )

    query_group = select(UserGroup).where(UserGroup.name == UserGroupEnum.USER)
    res_group = await db.execute(query_group)
    target_group = res_group.scalars().first()

    if target_group is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Default user group not found.",
        )

    try:
        new_account = User(
            email=str(user_data.email),
            group_id=cast(int, target_group.id),
            is_active=False,
        )
        new_account.password = user_data.password
        db.add(new_account)
        await db.flush()
        new_profile = UserProfile(user_id=new_account.id)
        db.add(new_profile)

        activation_rec = ActivationToken(
            user_id=cast(int, new_account.id),
            token=secrets.token_urlsafe(),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        db.add(activation_rec)
        await db.commit()
        await db.refresh(new_account)
        send_activation_email.delay(str(new_account.email), activation_rec.token)
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during user creation.",
        )

    return UserRegistrationResponseSchema(
        id=cast(int, new_account.id), email=cast(str, new_account.email)
    )


@router.post("/activate/resend/", response_model=MessageResponseSchema)
async def resend_activation_token(
    data: UserActivationResendRequestSchema,
    db: AsyncSession = Depends(get_db),
) -> MessageResponseSchema:
    result = await db.execute(select(User).where(User.email == str(data.email)))
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User with this email not found.",
        )

    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already active.",
        )

    result = await db.execute(
        select(ActivationToken).where(ActivationToken.user_id == cast(int, user.id))
    )
    old_token = result.scalars().first()
    if old_token:
        await db.delete(old_token)

    try:
        new_expiry = cast(datetime, datetime.now(timezone.utc) + timedelta(hours=24))

        new_token = ActivationToken(
            user_id=cast(int, user.id),
            token=secrets.token_urlsafe(),
            expires_at=new_expiry,
        )
        db.add(new_token)
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while resending activation token.",
        )

    return MessageResponseSchema(message="Activation token resent successfully.")


@router.get("/activate/")
async def activate_user_by_link(
    email: str,
    token: str,
    db: AsyncSession = Depends(get_db),
) -> MessageResponseSchema:
    data = UserActivationRequestSchema(email=email, token=token)
    return await activate_user(data=data, db=db)


@router.post("/activate/", response_model=MessageResponseSchema)
async def activate_user(
    data: UserActivationRequestSchema,
    db: AsyncSession = Depends(get_db),
) -> MessageResponseSchema:
    result = await db.execute(select(User).where(User.email == str(data.email)))
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email or activation token.",
        )

    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email or activation token.",
        )

    result = await db.execute(
        select(ActivationToken).where(
            ActivationToken.user_id == cast(int, user.id),
            ActivationToken.token == str(data.token),
        )
    )
    activation_token = result.scalars().first()

    if not activation_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid activation token.",
        )

    expiry = cast(datetime, activation_token.expires_at)
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)

    if expiry < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Activation token has expired.",
        )

    try:
        user.is_active = True
        await db.delete(activation_token)
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during account activation.",
        )

    return MessageResponseSchema(message="Account activated successfully.")


@router.post("/login/", response_model=UserLoginResponseSchema)
async def login_user(
    user_data: UserLoginRequestSchema,
    db: AsyncSession = Depends(get_db),
) -> UserLoginResponseSchema:
    result = await db.execute(select(User).where(User.email == str(user_data.email)))
    user = result.scalars().first()

    if not user or not user.verify_password(user_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not activated.",
        )

    user_id = cast(int, user.id)
    print(f"DEBUG: functions are: {create_access_token}, {create_refresh_token}")
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    result = await db.execute(
        select(RefreshToken).where(RefreshToken.user_id == user_id)
    )
    old_token = result.scalars().first()
    if old_token:
        await db.delete(old_token)

    try:
        expiry = cast(
            datetime,
            datetime.now(timezone.utc)
            + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
        )

        new_refresh_token = RefreshToken(
            user_id=user_id,
            token=refresh_token,
            expires_at=expiry,
        )
        db.add(new_refresh_token)
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during login.",
        )

    return UserLoginResponseSchema(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


@router.post("/refresh/", response_model=UserLoginResponseSchema)
async def refresh_access_token(
    data: TokenRefreshRequestSchema,
    db: AsyncSession = Depends(get_db),
) -> UserLoginResponseSchema:
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token == data.refresh_token)
    )
    db_token = result.scalars().first()

    if not db_token or db_token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        )

    user_id = cast(int, db_token.user_id)
    new_access = create_access_token(user_id)
    new_refresh = create_refresh_token(user_id)

    await db.delete(db_token)

    new_db_token = RefreshToken(
        user_id=user_id,
        token=new_refresh,
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(new_db_token)
    await db.commit()

    return UserLoginResponseSchema(
        access_token=new_access, refresh_token=new_refresh, token_type="bearer"
    )


@router.post("/logout/", response_model=MessageResponseSchema)
async def logout_user(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponseSchema:
    try:
        result = await db.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == cast(int, current_user.id)
            )
        )
        tokens = result.scalars().all()

        for token in tokens:
            await db.delete(token)

        await db.commit()
        return MessageResponseSchema(
            message="Successfully logged out and tokens revoked."
        )

    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during logout.",
        )


@router.get("/admin/users/", response_model=list[UserRegistrationResponseSchema])
async def list_all_users(
    admin: User = Depends(RoleChecker([UserGroupEnum.ADMIN])),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User))
    users = result.scalars().all()
    return users


@router.patch("/admin/activate/{user_id}/", response_model=MessageResponseSchema)
async def admin_activate_user(
    user_id: int,
    admin: User = Depends(RoleChecker([UserGroupEnum.ADMIN])),
    db: AsyncSession = Depends(get_db),
) -> MessageResponseSchema:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = True

    token_result = await db.execute(
        select(ActivationToken).where(ActivationToken.user_id == user_id)
    )
    token = token_result.scalars().first()
    if token:
        await db.delete(token)

    await db.commit()
    return MessageResponseSchema(
        message=f"User {user.email} has been manually activated."
    )


@router.patch("/admin/change-group/{user_id}/", response_model=MessageResponseSchema)
async def change_user_group(
    user_id: int,
    new_group_name: UserGroupEnum,
    admin: User = Depends(RoleChecker([UserGroupEnum.ADMIN])),
    db: AsyncSession = Depends(get_db),
) -> MessageResponseSchema:
    user_query = await db.execute(select(User).where(User.id == user_id))
    user = user_query.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    group_query = await db.execute(
        select(UserGroup).where(UserGroup.name == new_group_name)
    )
    group = group_query.scalars().first()

    if not group:
        raise HTTPException(status_code=404, detail="Target group not found")

    user.group_id = cast(int, group.id)
    await db.commit()

    return MessageResponseSchema(
        message=f"User {user.email} role updated to {new_group_name.value}"
    )


@router.post("/password-reset/request/", response_model=MessageResponseSchema)
async def request_password_reset(
    data: PasswordResetRequestSchema, db: AsyncSession = Depends(get_db)
) -> MessageResponseSchema:
    result = await db.execute(select(User).where(User.email == str(data.email)))
    user = result.scalars().first()

    if not user or not user.is_active:
        return MessageResponseSchema(
            message="If the email is registered, a reset link has been sent."
        )

    try:
        old_tokens_query = await db.execute(
            select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
        )
        old_tokens = old_tokens_query.scalars().all()
        for t in old_tokens:
            await db.delete(t)

        token_str = secrets.token_urlsafe()
        reset_token = PasswordResetToken(
            user_id=cast(int, user.id),
            token=token_str,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(reset_token)
        await db.commit()
        send_reset_password_email.delay(str(user.email), token_str)
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error processing password reset.")

    return MessageResponseSchema(message="Reset link has been sent to your email.")


@router.post("/password-reset/confirm/", response_model=MessageResponseSchema)
async def confirm_password_reset(
    data: PasswordResetCompleteRequestSchema,
    db: AsyncSession = Depends(get_db),
) -> MessageResponseSchema:
    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token == data.token)
    )
    reset_token = result.scalars().first()

    if not reset_token or reset_token.expires_at.replace(
        tzinfo=timezone.utc
    ) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired token.")

    user_result = await db.execute(select(User).where(User.id == reset_token.user_id))
    user = user_result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    try:
        user.password = data.new_password

        await db.delete(reset_token)

        refresh_tokens = await db.execute(
            select(RefreshToken).where(RefreshToken.user_id == user.id)
        )
        for rt in refresh_tokens.scalars().all():
            await db.delete(rt)

        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error updating password.")

    return MessageResponseSchema(message="Password reset successful.")


@router.post("/password-change/", response_model=MessageResponseSchema)
async def change_password(
    data: PasswordChangeRequestSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponseSchema:
    if not current_user.verify_password(data.old_password):
        raise HTTPException(status_code=400, detail="Incorrect old password.")

    try:
        current_user.password = data.new_password
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error updating password.")

    return MessageResponseSchema(message="Password changed successfully.")


@router.patch("/me/avatar/", response_model=UserProfileSchema)
async def upload_my_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfileSchema:
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = result.scalars().first()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found.")

    if profile.avatar:
        delete_avatar(profile.avatar)

    file_data = await file.read()
    filename = f"{uuid.uuid4()}{file.filename[file.filename.rfind('.'):]}"

    upload_avatar(file_data, filename, file.content_type or "image/jpeg")

    profile.avatar = filename

    try:
        await db.commit()
        await db.refresh(profile)
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error updating avatar.")

    profile_data = UserProfileSchema.model_validate(profile)
    return profile_data


@router.get("/me/avatar/")
async def get_my_avatar(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = result.scalars().first()

    if not profile or not profile.avatar:
        raise HTTPException(status_code=404, detail="Avatar not found.")

    url = get_avatar_url(profile.avatar)
    return {"avatar_url": url}


@router.get("/me/", response_model=UserProfileSchema)
async def get_my_profile(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> UserProfileSchema:
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = result.scalars().first()

    if not profile:
        profile = UserProfile(user_id=current_user.id)
        db.add(profile)
        await db.commit()
        await db.refresh(profile)

    return profile


@router.patch("/me/", response_model=UserProfileSchema)
async def update_my_profile(
    data: UserProfileUpdateSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfileSchema:
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = result.scalars().first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(profile, key, value)

    try:
        await db.commit()
        await db.refresh(profile)
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error updating profile")

    return profile


@router.get("/notifications/", response_model=list[NotificationSchema])
async def get_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
    )
    return result.scalars().all()


@router.patch(
    "/notifications/{notification_id}/read/", response_model=NotificationSchema
)
async def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found.")

    notification.is_read = True
    await db.commit()
    await db.refresh(notification)
    return notification
