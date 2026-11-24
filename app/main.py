from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import close_database
from app.core.dependencies import DBSession


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
    allow_origins=settings.cors_origins,
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



@app.get("/health", tags=["System"])
async def health():
    return {"success": True, "status": "healthy"}


@app.get("/ready", tags=["System"])
async def readiness(db: DBSession):
    await db.execute(text("SELECT 1"))
    return {"success": True, "status": "ready", "database": "connected"}
