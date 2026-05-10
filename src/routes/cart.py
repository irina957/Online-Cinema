from typing import cast
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import SQLAlchemyError

from src.database.session import get_db
from src.database.models.accounts import User, UserGroupEnum
from src.database.models.movies import Movie
from src.database.models.cart import Cart, CartItem, MoviePurchase
from src.schemas.cart import CartSchema, CartItemSchema, MessageResponseSchema
from src.security.dependencies import get_current_user
from src.security.roles import RoleChecker

router = APIRouter(prefix="/cart", tags=["Cart"])


async def get_or_create_cart(user_id: int, db: AsyncSession) -> Cart:
    result = await db.execute(select(Cart).where(Cart.user_id == user_id))
    cart = result.scalar_one_or_none()
    if not cart:
        cart = Cart(user_id=user_id)
        db.add(cart)
        await db.commit()
        await db.refresh(cart)
    return cart


@router.get("/", response_model=CartSchema)
async def get_cart(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_or_create_cart(cast(int, current_user.id), db)

    result = await db.execute(
        select(Cart)
        .options(
            selectinload(Cart.items)
            .selectinload(CartItem.movie)
            .selectinload(Movie.genres)
        )
        .where(Cart.user_id == current_user.id)
    )
    return result.scalar_one()


@router.post("/add/{movie_id}/", response_model=CartItemSchema, status_code=201)
async def add_to_cart(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    movie = await db.get(Movie, movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found.")

    already_purchased = await db.execute(
        select(MoviePurchase).where(
            MoviePurchase.user_id == current_user.id,
            MoviePurchase.movie_id == movie_id,
        )
    )
    if already_purchased.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="You already own this movie.")

    cart = await get_or_create_cart(cast(int, current_user.id), db)

    existing = await db.execute(
        select(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.movie_id == movie_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Movie already in cart.")

    try:
        item = CartItem(cart_id=cast(int, cart.id), movie_id=movie_id)
        db.add(item)
        await db.commit()
        await db.refresh(item)
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error adding movie to cart.")

    result = await db.execute(
        select(CartItem)
        .options(selectinload(CartItem.movie).selectinload(Movie.genres))
        .where(CartItem.id == item.id)
    )
    return result.scalar_one()


@router.delete("/remove/{movie_id}/", response_model=MessageResponseSchema)
async def remove_from_cart(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cart = await get_or_create_cart(cast(int, current_user.id), db)

    result = await db.execute(
        select(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.movie_id == movie_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Movie not in cart.")

    await db.delete(item)
    await db.commit()
    return MessageResponseSchema(message="Movie removed from cart.")


@router.delete("/clear/", response_model=MessageResponseSchema)
async def clear_cart(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cart = await get_or_create_cart(cast(int, current_user.id), db)

    await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
    await db.commit()

    return MessageResponseSchema(message="Cart cleared successfully.")


@router.get("/admin/", response_model=list[CartSchema])
async def get_all_carts(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(RoleChecker([UserGroupEnum.ADMIN, UserGroupEnum.MODERATOR])),
):
    result = await db.execute(
        select(Cart).options(
            selectinload(Cart.items)
            .selectinload(CartItem.movie)
            .selectinload(Movie.genres)
        )
    )
    return result.scalars().all()


@router.post("/checkout/", response_model=MessageResponseSchema)
async def checkout(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Cart)
        .options(selectinload(Cart.items))
        .where(Cart.user_id == current_user.id)
    )
    cart = result.scalar_one_or_none()

    if not cart or not cart.items:
        raise HTTPException(status_code=400, detail="Cart is empty.")

    try:
        for item in cart.items:
            purchase = MoviePurchase(
                user_id=cast(int, current_user.id),
                movie_id=item.movie_id,
            )
            db.add(purchase)

        await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error during checkout.")

    return MessageResponseSchema(message="Purchase successful! Enjoy your movies.")
