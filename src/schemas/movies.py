from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field
from typing import Optional


class GenreSchema(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class StarSchema(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class DirectorSchema(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class CertificationSchema(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class MovieListSchema(BaseModel):
    id: int
    uuid: UUID
    name: str
    year: int
    time: int
    imdb: float
    price: Optional[Decimal] = None
    genres: list[GenreSchema] = []
    certification: CertificationSchema

    model_config = {"from_attributes": True}


class MovieDetailSchema(MovieListSchema):
    votes: int
    meta_score: Optional[float] = None
    gross: Optional[float] = None
    description: str
    directors: list[DirectorSchema] = []
    stars: list[StarSchema] = []

    model_config = {"from_attributes": True}


class MovieCreateSchema(BaseModel):
    name: str = Field(max_length=250)
    year: int
    time: int
    imdb: float = Field(ge=0, le=10)
    votes: int = Field(ge=0)
    meta_score: Optional[float] = None
    gross: Optional[float] = None
    description: str
    price: Optional[Decimal] = None
    certification_id: int
    genre_ids: list[int] = []
    star_ids: list[int] = []
    director_ids: list[int] = []


class MovieUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, max_length=250)
    year: Optional[int] = None
    time: Optional[int] = None
    imdb: Optional[float] = Field(None, ge=0, le=10)
    votes: Optional[int] = Field(None, ge=0)
    meta_score: Optional[float] = None
    gross: Optional[float] = None
    description: Optional[str] = None
    price: Optional[Decimal] = None
    certification_id: Optional[int] = None
    genre_ids: Optional[list[int]] = None
    star_ids: Optional[list[int]] = None
    director_ids: Optional[list[int]] = None


class MovieLikeSchema(BaseModel):
    is_like: bool


class MovieLikeResponseSchema(BaseModel):
    likes: int
    dislikes: int


class MovieCommentCreateSchema(BaseModel):
    content: str = Field(min_length=1, max_length=1000)
    parent_id: Optional[int] = Field(None, gt=0)


class MovieCommentSchema(BaseModel):
    id: int
    user_id: int
    content: str
    parent_id: Optional[int] = None
    replies: list["MovieCommentSchema"] = []

    model_config = {"from_attributes": True}


class MovieRatingSchema(BaseModel):
    rating: int = Field(ge=1, le=10)


class MovieRatingResponseSchema(BaseModel):
    average_rating: float
    total_ratings: int


class MovieFavoriteResponseSchema(BaseModel):
    message: str


class GenreWithCountSchema(BaseModel):
    id: int
    name: str
    movie_count: int


class GenreCreateSchema(BaseModel):
    name: str = Field(max_length=100)


class StarCreateSchema(BaseModel):
    name: str = Field(max_length=100)


class DirectorCreateSchema(BaseModel):
    name: str = Field(max_length=100)


class CertificationCreateSchema(BaseModel):
    name: str = Field(max_length=100)
