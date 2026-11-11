from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import close_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

    await close_database()


app = FastAPI(
    title=settings.APP_NAME,
    description="Tutova Tutoring Marketplace API",
    version="1.0.0",
    debug=settings.DEBUG,
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(
    api_router,
    prefix=settings.API_V1_PREFIX,
)


@app.get("/")
async def root():
    return {
        "success": True,
        "message": "Welcome to Tutova API",
        "version": "1.0.0",
    }
