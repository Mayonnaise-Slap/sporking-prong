import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_db, init_db
from app.middleware import AuthMiddleware, LoggingMiddleware
from app.routers.auth import router as auth_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="sporking-prong", lifespan=lifespan)

app.add_middleware(AuthMiddleware)
app.add_middleware(LoggingMiddleware)

app.include_router(auth_router)


@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict:
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}
