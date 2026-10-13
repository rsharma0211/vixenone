from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.company import router as company_router
from app.api.criteria import router as criteria_router
from app.api.evaluations import router as evaluations_router
from app.api.users import router as users_router
import logging
from app.core.auth import init_firebase
from app.core.config import settings
from app.core.database import async_session, check_db_health
from app.services.worker import recover_interrupted_jobs

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Firebase Admin on startup (fails fast if production + emulator)
    init_firebase(settings)
    try:
        await recover_interrupted_jobs(async_session)
    except Exception as exc:
        logger.warning("Startup job recovery skipped: error_type=%s", type(exc).__name__)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    lifespan=lifespan,
)

# CORS configuration allowing web origin only
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users_router)
app.include_router(company_router)
app.include_router(criteria_router)
app.include_router(evaluations_router)


@app.get("/health")
async def health_check():
    db_healthy = await check_db_health()
    return {
        "status": "ok",
        "db": "ok" if db_healthy else "error",
    }


@app.get("/api/health")
async def api_health_check():
    return await health_check()
