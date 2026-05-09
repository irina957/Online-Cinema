from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.routes.accounts import router as accounts_router
from src.database.session import AsyncSessionLocal
from src.database.seed import seed_user_groups
from src.routes.movies import router as movies_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncSessionLocal() as db:
        await seed_user_groups(db)
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(accounts_router)
app.include_router(movies_router)


@app.get("/")
async def root():
    return {"message": "Hello World"}
