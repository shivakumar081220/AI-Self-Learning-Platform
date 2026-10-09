from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import models
from .database import Base, SessionLocal, ensure_legacy_columns, engine
from .seed_topics import seed_topics
from .routers import assessment, auth, curriculum, diagnostic, learning, learning_path, learners


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_legacy_columns()
    Base.metadata.create_all(bind=engine)
    database = SessionLocal()
    try:
        seed_topics(database)
    finally:
        database.close()
    yield


app = FastAPI(
    title="AI Self-Learning Platform API",
    version="0.1.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def tutor_image_request_limit(request: Request, call_next):
    if request.method != "POST" or not request.url.path.endswith("/images"):
        return await call_next(request)
    content_length = request.headers.get("content-length")
    if content_length is None:
        return JSONResponse(
            status_code=411,
            content={"detail": "Image uploads require a bounded Content-Length request."},
        )
    try:
        exceeds_limit = int(content_length) > 11 * 1024 * 1024
    except ValueError:
        exceeds_limit = True
    if exceeds_limit:
        return JSONResponse(status_code=413, content={"detail": "Image upload request is too large."})
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_origin_regex=r"https?://(127\.0\.0\.1|localhost):517[0-9]$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(learners.router)
app.include_router(auth.router)
app.include_router(curriculum.router)
app.include_router(diagnostic.router)
app.include_router(learning_path.router)
app.include_router(learning.router)
app.include_router(assessment.router)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "adaptive-learning-api"}
