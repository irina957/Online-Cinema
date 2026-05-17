import uuid as uuid_module
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy import (
    String,
    Float,
    Text,
    Numeric,
    ForeignKey,
    UniqueConstraint,
    Table,
    Column,
    Integer,
    DateTime,
    func,
    Boolean,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from src.database.session import Base

movie_genres = Table(
    "movie_genres",
    Base.metadata,
    Column("movie_id", Integer, ForeignKey("movies.id"), primary_key=True),
    Column("genre_id", Integer, ForeignKey("genres.id"), primary_key=True),
)

movie_stars = Table(
    "movie_stars",
    Base.metadata,
    Column("movie_id", Integer, ForeignKey("movies.id"), primary_key=True),
    Column("star_id", Integer, ForeignKey("stars.id"), primary_key=True),
)

movie_directors = Table(
    "movie_directors",
    Base.metadata,
    Column("movie_id", Integer, ForeignKey("movies.id"), primary_key=True),
    Column("director_id", Integer, ForeignKey("directors.id"), primary_key=True),
)


class Genre(Base):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    movies: Mapped[list["Movie"]] = relationship(
        secondary=movie_genres, back_populates="genres"
    )


class Star(Base):
    __tablename__ = "stars"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    movies: Mapped[list["Movie"]] = relationship(
        secondary=movie_stars, back_populates="stars"
    )


class Director(Base):
    __tablename__ = "directors"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    movies: Mapped[list["Movie"]] = relationship(
        secondary=movie_directors, back_populates="directors"
    )


class Certification(Base):
    __tablename__ = "certifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    movies: Mapped[list["Movie"]] = relationship(back_populates="certification")


class Movie(Base):
    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    uuid: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid_module.uuid4, unique=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    year: Mapped[int] = mapped_column(nullable=False)
    time: Mapped[int] = mapped_column(nullable=False)
    imdb: Mapped[float] = mapped_column(Float, nullable=False)
    votes: Mapped[int] = mapped_column(nullable=False)
    meta_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    gross: Mapped[float | None] = mapped_column(Float, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    certification_id: Mapped[int] = mapped_column(
        ForeignKey("certifications.id"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("name", "year", "time", name="uq_movie_name_year_time"),
    )

    certification: Mapped["Certification"] = relationship(back_populates="movies")
    genres: Mapped[list["Genre"]] = relationship(
        secondary=movie_genres, back_populates="movies"
    )
    stars: Mapped[list["Star"]] = relationship(
        secondary=movie_stars, back_populates="movies"
    )
    directors: Mapped[list["Director"]] = relationship(
        secondary=movie_directors, back_populates="movies"
    )

    likes: Mapped[list["MovieLike"]] = relationship(
        back_populates="movie", cascade="all, delete-orphan"
    )
    comments: Mapped[list["MovieComment"]] = relationship(
        back_populates="movie", cascade="all, delete-orphan"
    )
    favorites: Mapped[list["MovieFavorite"]] = relationship(
        back_populates="movie", cascade="all, delete-orphan"
    )
    ratings: Mapped[list["MovieRating"]] = relationship(
        back_populates="movie", cascade="all, delete-orphan"
    )


class MovieLike(Base):
    __tablename__ = "movie_likes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    is_like: Mapped[bool] = mapped_column(Boolean, nullable=False)

    __table_args__ = (
        UniqueConstraint("movie_id", "user_id", name="uq_movie_like_user"),
    )

    movie: Mapped["Movie"] = relationship(back_populates="likes")


class MovieComment(Base):
    __tablename__ = "movie_comments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("movie_comments.id", ondelete="CASCADE"), nullable=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    movie: Mapped["Movie"] = relationship(back_populates="comments")
    replies: Mapped[list["MovieComment"]] = relationship(back_populates="parent")
    parent: Mapped["MovieComment | None"] = relationship(
        back_populates="replies", remote_side="MovieComment.id"
    )


class MovieFavorite(Base):
    __tablename__ = "movie_favorites"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("movie_id", "user_id", name="uq_movie_favorite_user"),
    )

    movie: Mapped["Movie"] = relationship(back_populates="favorites")


class MovieRating(Base):
    __tablename__ = "movie_ratings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    rating: Mapped[int] = mapped_column(nullable=False)  # 1-10

    __table_args__ = (
        UniqueConstraint("movie_id", "user_id", name="uq_movie_rating_user"),
    )

    movie: Mapped["Movie"] = relationship(back_populates="ratings")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MovieCommentLike(Base):
    __tablename__ = "movie_comment_likes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    comment_id: Mapped[int] = mapped_column(
        ForeignKey("movie_comments.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("comment_id", "user_id", name="uq_comment_like_user"),
    )
