from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.config import settings
from app.core.database import check_db_health

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
)

# CORS configuration allowing web origin only
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.get("/me")
async def get_me(user: AuthenticatedUser = Depends(get_current_user)):
    return {
        "uid": user.uid,
        "email": user.email,
        "display_name": user.display_name,
    }


@app.get("/api/me")
async def get_api_me(user: AuthenticatedUser = Depends(get_current_user)):
    return await get_me(user)
