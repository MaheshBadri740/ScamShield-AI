from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.database import Base, engine
from app.core.limiter import limiter
from app.routes.investigate import router as investigate_router
import app.models  # Register SQLAlchemy models with Base.metadata


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-create database tables on application startup
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="ScamShield AI API",
    description="AI-Powered Career Opportunity Fraud Detection & Student Protection Platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(investigate_router)


@app.get("/health")
@limiter.limit("60/minute")
async def health(request: Request):
    return {"status": "ok", "service": "ScamShield AI"}
