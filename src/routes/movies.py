from typing import cast
from fastapi import APIRouter, Depends, status, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import SQLAlchemyError

from src.database.session import get_db
from src.database.models.accounts import User, UserGroupEnum
from src.database.models.movies import (
    Movie,
    Genre,
    Star,
    Director,
    Certification,
    MovieLike,
    MovieComment,
    MovieFavorite,
    MovieRating,
    movie_genres,
)
from src.schemas.movies import (
    MovieListSchema,
    MovieDetailSchema,
    MovieCreateSchema,
    MovieUpdateSchema,
    MovieLikeSchema,
    MovieLikeResponseSchema,
    MovieCommentCreateSchema,
    MovieCommentSchema,
    MovieRatingSchema,
    MovieRatingResponseSchema,
    GenreWithCountSchema,
    GenreSchema,
    GenreCreateSchema,
    StarSchema,
    StarCreateSchema,
    DirectorSchema,
    DirectorCreateSchema,
    CertificationSchema,
    CertificationCreateSchema,
    MovieFavoriteResponseSchema,
)
from src.security.dependencies import get_current_user
from src.security.roles import RoleChecker

router = APIRouter(prefix="/movies", tags=["Movies"])


@router.post("/", response_model=MovieDetailSchema, status_code=status.HTTP_201_CREATED)
async def create_movie(
    data: MovieCreateSchema,
    db: AsyncSession = Depends(get_db),
    moderator: User = Depends(
        RoleChecker([UserGroupEnum.MODERATOR, UserGroupEnum.ADMIN])
    ),
) -> MovieDetailSchema:
    cert = await db.get(Certification, data.certification_id)
    if not cert:
        raise HTTPException(status_code=404, detail="Certification not found.")

    try:
        movie = Movie(
            name=data.name,
            year=data.year,
            time=data.time,
            imdb=data.imdb,
            votes=data.votes,
            meta_score=data.meta_score,
            gross=data.gross,
            description=data.description,
            price=data.price,
            certification_id=data.certification_id,
        )
        db.add(movie)
        await db.flush()

        if data.genre_ids:
            genres = await db.execute(select(Genre).where(Genre.id.in_(data.genre_ids)))
            movie.genres = list(genres.scalars().all())

        if data.star_ids:
            stars = await db.execute(select(Star).where(Star.id.in_(data.star_ids)))
            movie.stars = list(stars.scalars().all())

        if data.director_ids:
            directors = await db.execute(
                select(Director).where(Director.id.in_(data.director_ids))
            )
            movie.directors = list(directors.scalars().all())

        await db.commit()
        await db.refresh(movie)

    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error creating movie.")

    result = await db.execute(
        select(Movie)
        .options(
            selectinload(Movie.genres),
            selectinload(Movie.stars),
            selectinload(Movie.directors),
            selectinload(Movie.certification),
        )
        .where(Movie.id == movie.id)
    )
    return result.scalar_one()


@router.patch("/{movie_id}/", response_model=MovieDetailSchema)
async def update_movie(
    movie_id: int,
    data: MovieUpdateSchema,
    db: AsyncSession = Depends(get_db),
    moderator: User = Depends(
        RoleChecker([UserGroupEnum.MODERATOR, UserGroupEnum.ADMIN])
    ),
) -> MovieDetailSchema:
    result = await db.execute(
        select(Movie)
        .options(
            selectinload(Movie.genres),
            selectinload(Movie.stars),
            selectinload(Movie.directors),
            selectinload(Movie.certification),
        )
        .where(Movie.id == movie_id)
    )
    movie = result.scalar_one_or_none()

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found.")

    update_data = data.model_dump(exclude_unset=True)

    if "genre_ids" in update_data:
        genres = await db.execute(
            select(Genre).where(Genre.id.in_(update_data.pop("genre_ids")))
        )
        movie.genres = list(genres.scalars().all())

    if "star_ids" in update_data:
        stars = await db.execute(
            select(Star).where(Star.id.in_(update_data.pop("star_ids")))
        )
        movie.stars = list(stars.scalars().all())

    if "director_ids" in update_data:
        directors = await db.execute(
            select(Director).where(Director.id.in_(update_data.pop("director_ids")))
        )
        movie.directors = list(directors.scalars().all())

    for key, value in update_data.items():
        setattr(movie, key, value)

    try:
        await db.commit()
        await db.refresh(movie)
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error updating movie.")

    return movie


@router.delete("/{movie_id}/", response_model=dict)
async def delete_movie(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
    moderator: User = Depends(
        RoleChecker([UserGroupEnum.MODERATOR, UserGroupEnum.ADMIN])
    ),
):
    result = await db.execute(select(Movie).where(Movie.id == movie_id))
    movie = result.scalar_one_or_none()

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found.")

    # TODO: перевірити що фільм не куплений

    try:
        await db.delete(movie)
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error deleting movie.")

    return {"message": "Movie deleted successfully."}


@router.get("/genres/", response_model=list[GenreWithCountSchema])
async def get_genres(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Genre.id, Genre.name, func.count(Movie.id).label("movie_count"))
        .outerjoin(movie_genres, Genre.id == movie_genres.c.genre_id)
        .outerjoin(Movie, Movie.id == movie_genres.c.movie_id)
        .group_by(Genre.id)
        .order_by(Genre.name)
    )
    rows = result.all()
    return [
        GenreWithCountSchema(id=row.id, name=row.name, movie_count=row.movie_count)
        for row in rows
    ]


@router.post(
    "/genres/", response_model=GenreSchema, status_code=status.HTTP_201_CREATED
)
async def create_genre(
    data: GenreCreateSchema,
    db: AsyncSession = Depends(get_db),
    moderator: User = Depends(
        RoleChecker([UserGroupEnum.MODERATOR, UserGroupEnum.ADMIN])
    ),
):
    existing = await db.execute(select(Genre).where(Genre.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Genre already exists.")
    genre = Genre(name=data.name)
    db.add(genre)
    await db.commit()
    await db.refresh(genre)
    return genre


@router.delete("/genres/{genre_id}/", response_model=dict)
async def delete_genre(
    genre_id: int,
    db: AsyncSession = Depends(get_db),
    moderator: User = Depends(
        RoleChecker([UserGroupEnum.MODERATOR, UserGroupEnum.ADMIN])
    ),
):
    genre = await db.get(Genre, genre_id)
    if not genre:
        raise HTTPException(status_code=404, detail="Genre not found.")
    await db.delete(genre)
    await db.commit()
    return {"message": "Genre deleted successfully."}


@router.get("/genres/{genre_id}/movies/", response_model=list[MovieListSchema])
async def get_movies_by_genre(
    genre_id: int,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
):
    genre = await db.get(Genre, genre_id)
    if not genre:
        raise HTTPException(status_code=404, detail="Genre not found.")

    query = (
        select(Movie)
        .options(
            selectinload(Movie.genres),
            selectinload(Movie.certification),
        )
        .where(Movie.genres.any(Genre.id == genre_id))
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/stars/", response_model=StarSchema, status_code=status.HTTP_201_CREATED)
async def create_star(
    data: StarCreateSchema,
    db: AsyncSession = Depends(get_db),
    moderator: User = Depends(
        RoleChecker([UserGroupEnum.MODERATOR, UserGroupEnum.ADMIN])
    ),
):
    existing = await db.execute(select(Star).where(Star.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Star already exists.")
    star = Star(name=data.name)
    db.add(star)
    await db.commit()
    await db.refresh(star)
    return star


@router.delete("/stars/{star_id}/", response_model=dict)
async def delete_star(
    star_id: int,
    db: AsyncSession = Depends(get_db),
    moderator: User = Depends(
        RoleChecker([UserGroupEnum.MODERATOR, UserGroupEnum.ADMIN])
    ),
):
    star = await db.get(Star, star_id)
    if not star:
        raise HTTPException(status_code=404, detail="Star not found.")
    await db.delete(star)
    await db.commit()
    return {"message": "Star deleted successfully."}


@router.post(
    "/directors/", response_model=DirectorSchema, status_code=status.HTTP_201_CREATED
)
async def create_director(
    data: DirectorCreateSchema,
    db: AsyncSession = Depends(get_db),
    moderator: User = Depends(
        RoleChecker([UserGroupEnum.MODERATOR, UserGroupEnum.ADMIN])
    ),
):
    existing = await db.execute(select(Director).where(Director.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Director already exists.")
    director = Director(name=data.name)
    db.add(director)
    await db.commit()
    await db.refresh(director)
    return director


@router.delete("/directors/{director_id}/", response_model=dict)
async def delete_director(
    director_id: int,
    db: AsyncSession = Depends(get_db),
    moderator: User = Depends(
        RoleChecker([UserGroupEnum.MODERATOR, UserGroupEnum.ADMIN])
    ),
):
    director = await db.get(Director, director_id)
    if not director:
        raise HTTPException(status_code=404, detail="Director not found.")
    await db.delete(director)
    await db.commit()
    return {"message": "Director deleted successfully."}


@router.post(
    "/certifications/",
    response_model=CertificationSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_certification(
    data: CertificationCreateSchema,
    db: AsyncSession = Depends(get_db),
    moderator: User = Depends(
        RoleChecker([UserGroupEnum.MODERATOR, UserGroupEnum.ADMIN])
    ),
):
    existing = await db.execute(
        select(Certification).where(Certification.name == data.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Certification already exists.")
    cert = Certification(name=data.name)
    db.add(cert)
    await db.commit()
    await db.refresh(cert)
    return cert


@router.get("/certifications/", response_model=list[CertificationSchema])
async def get_certifications(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Certification).order_by(Certification.name))
    return result.scalars().all()


@router.get("/favorites/", response_model=list[MovieListSchema])
async def get_favorites(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    search: str | None = Query(None),
    year_from: int | None = Query(None),
    year_to: int | None = Query(None),
    imdb_min: float | None = Query(None, ge=0, le=10),
    sort_by: str = Query("id", pattern="^(id|name|year|imdb|price)$"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
):
    query = (
        select(Movie)
        .options(
            selectinload(Movie.genres),
            selectinload(Movie.certification),
        )
        .join(MovieFavorite, MovieFavorite.movie_id == Movie.id)
        .where(MovieFavorite.user_id == current_user.id)
    )

    if search:
        query = query.where(
            Movie.name.ilike(f"%{search}%") | Movie.description.ilike(f"%{search}%")
        )
    if year_from:
        query = query.where(Movie.year >= year_from)
    if year_to:
        query = query.where(Movie.year <= year_to)
    if imdb_min:
        query = query.where(Movie.imdb >= imdb_min)

    sort_column = getattr(Movie, sort_by)
    query = query.order_by(sort_column.desc() if order == "desc" else sort_column.asc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/", response_model=list[MovieListSchema])
async def get_movies(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    search: str | None = Query(None),
    year_from: int | None = Query(None),
    year_to: int | None = Query(None),
    imdb_min: float | None = Query(None, ge=0, le=10),
    genre_id: int | None = Query(None),
    sort_by: str = Query("id", pattern="^(id|name|year|imdb|price)$"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
):
    query = select(Movie).options(
        selectinload(Movie.genres),
        selectinload(Movie.certification),
    )

    if search:
        query = (
            query.outerjoin(Movie.stars)
            .outerjoin(Movie.directors)
            .where(
                Movie.name.ilike(f"%{search}%")
                | Movie.description.ilike(f"%{search}%")
                | Star.name.ilike(f"%{search}%")
                | Director.name.ilike(f"%{search}%")
            )
            .distinct()
        )

    if year_from:
        query = query.where(Movie.year >= year_from)
    if year_to:
        query = query.where(Movie.year <= year_to)
    if imdb_min:
        query = query.where(Movie.imdb >= imdb_min)
    if genre_id:
        query = query.where(Movie.genres.any(Genre.id == genre_id))

    sort_column = getattr(Movie, sort_by)
    if order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{movie_id}/", response_model=MovieDetailSchema)
async def get_movie(movie_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Movie)
        .options(
            selectinload(Movie.genres),
            selectinload(Movie.stars),
            selectinload(Movie.directors),
            selectinload(Movie.certification),
        )
        .where(Movie.id == movie_id)
    )
    movie = result.scalar_one_or_none()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found.")
    return movie


@router.post("/{movie_id}/like/", response_model=MovieLikeResponseSchema)
async def like_movie(
    movie_id: int,
    data: MovieLikeSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    movie = await db.get(Movie, movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found.")

    result = await db.execute(
        select(MovieLike).where(
            MovieLike.movie_id == movie_id,
            MovieLike.user_id == current_user.id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.is_like = data.is_like
    else:
        db.add(
            MovieLike(
                movie_id=movie_id,
                user_id=cast(int, current_user.id),
                is_like=data.is_like,
            )
        )

    await db.commit()

    likes = await db.execute(
        select(func.count()).where(
            MovieLike.movie_id == movie_id, MovieLike.is_like == True
        )
    )
    dislikes = await db.execute(
        select(func.count()).where(
            MovieLike.movie_id == movie_id, MovieLike.is_like == False
        )
    )
    return MovieLikeResponseSchema(
        likes=likes.scalar_one(),
        dislikes=dislikes.scalar_one(),
    )


@router.post("/{movie_id}/rate/", response_model=MovieRatingResponseSchema)
async def rate_movie(
    movie_id: int,
    data: MovieRatingSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    movie = await db.get(Movie, movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found.")

    result = await db.execute(
        select(MovieRating).where(
            MovieRating.movie_id == movie_id,
            MovieRating.user_id == current_user.id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.rating = data.rating
    else:
        db.add(
            MovieRating(
                movie_id=movie_id,
                user_id=cast(int, current_user.id),
                rating=data.rating,
            )
        )

    await db.commit()

    avg = await db.execute(
        select(func.avg(MovieRating.rating), func.count(MovieRating.id)).where(
            MovieRating.movie_id == movie_id
        )
    )
    row = avg.one()
    return MovieRatingResponseSchema(
        average_rating=round(float(row[0]), 2),
        total_ratings=row[1],
    )


@router.post(
    "/{movie_id}/comments/", response_model=MovieCommentSchema, status_code=201
)
async def add_comment(
    movie_id: int,
    data: MovieCommentCreateSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    movie = await db.get(Movie, movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found.")

    if data.parent_id is not None and data.parent_id > 0:
        parent = await db.get(MovieComment, data.parent_id)
        if not parent or parent.movie_id != movie_id:
            raise HTTPException(status_code=404, detail="Parent comment not found.")

    comment = MovieComment(
        movie_id=movie_id,
        user_id=cast(int, current_user.id),
        content=data.content,
        parent_id=data.parent_id,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment


@router.get("/{movie_id}/comments/", response_model=list[MovieCommentSchema])
async def get_comments(movie_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MovieComment)
        .options(selectinload(MovieComment.replies))
        .where(MovieComment.movie_id == movie_id, MovieComment.parent_id.is_(None))
        .order_by(MovieComment.created_at)
    )
    return result.scalars().all()


@router.post("/{movie_id}/favorites/", response_model=MovieFavoriteResponseSchema)
async def add_to_favorites(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    movie = await db.get(Movie, movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found.")

    existing = await db.execute(
        select(MovieFavorite).where(
            MovieFavorite.movie_id == movie_id,
            MovieFavorite.user_id == current_user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Movie already in favorites.")

    db.add(MovieFavorite(movie_id=movie_id, user_id=cast(int, current_user.id)))
    await db.commit()
    return MovieFavoriteResponseSchema(message="Movie added to favorites.")


@router.delete("/{movie_id}/favorites/", response_model=MovieFavoriteResponseSchema)
async def remove_from_favorites(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(MovieFavorite).where(
            MovieFavorite.movie_id == movie_id,
            MovieFavorite.user_id == current_user.id,
        )
    )
    favorite = result.scalar_one_or_none()
    if not favorite:
        raise HTTPException(status_code=404, detail="Movie not in favorites.")

    await db.delete(favorite)
    await db.commit()
    return MovieFavoriteResponseSchema(message="Movie removed from favorites.")
