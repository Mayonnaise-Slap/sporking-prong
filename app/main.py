import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_db, init_db
from app.middleware import AuthMiddleware, LoggingMiddleware
from app.routers.assignments import router as assignments_router
from app.routers.auth import router as auth_router
from app.routers.comments import comment_router
from app.routers.comments import router as comments_router
from app.routers.grading import router as grading_router
from app.routers.submissions import router as submissions_router
from app.routers.submissions import submission_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="sporking-prong", lifespan=lifespan)

app.add_middleware(AuthMiddleware)
app.add_middleware(LoggingMiddleware)
# Last-added = outermost, so this handles preflight before auth/logging see
# the request. The frontend dev server's port varies (vite picks the next
# free one), so match any localhost port rather than hardcoding it.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(assignments_router)
app.include_router(submissions_router)
app.include_router(submission_router)
app.include_router(comments_router)
app.include_router(comment_router)
app.include_router(grading_router)


@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict:
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}
