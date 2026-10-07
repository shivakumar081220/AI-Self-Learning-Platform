from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models
from .database import Base, SessionLocal, engine
from .seed_topics import seed_topics
from .routers import assessment, diagnostic, learning, learning_path, learners


@asynccontextmanager
async def lifespan(_: FastAPI):
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(learners.router)
app.include_router(diagnostic.router)
app.include_router(learning_path.router)
app.include_router(learning.router)
app.include_router(assessment.router)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "adaptive-learning-api"}
