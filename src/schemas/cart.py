from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel
from typing import Optional
from src.schemas.movies import GenreSchema


class CartItemMovieSchema(BaseModel):
    id: int
    name: str
    year: int
    price: Optional[Decimal] = None
    genres: list[GenreSchema] = []

    model_config = {"from_attributes": True}


class CartItemSchema(BaseModel):
    id: int
    movie: CartItemMovieSchema
    added_at: datetime

    model_config = {"from_attributes": True}


class CartSchema(BaseModel):
    id: int
    items: list[CartItemSchema] = []

    model_config = {"from_attributes": True}


class MessageResponseSchema(BaseModel):
    message: str
