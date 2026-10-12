import logging
from typing import Optional
import firebase_admin
from firebase_admin import auth
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.core.config import Settings, settings

logger = logging.getLogger("uvicorn.error")


def init_firebase(app_settings: Optional[Settings] = None) -> firebase_admin.App:
    """Initialize Firebase Admin SDK based on environment configuration.

    - Emulator mode: if FIREBASE_AUTH_EMULATOR_HOST is configured.
    - ADC mode: if absent, uses Application Default Credentials (no credentials argument).
    - Fails fast if environment is production and emulator host is set.
    """
    cfg = app_settings or settings
    if cfg.is_production and cfg.FIREBASE_AUTH_EMULATOR_HOST:
        raise ValueError("Firebase Auth emulator cannot be used in production environment")

    mode = "emulator" if cfg.FIREBASE_AUTH_EMULATOR_HOST else "ADC"
    logger.info("Firebase Admin initialized in %s mode (project: %s)", mode, cfg.FIREBASE_PROJECT_ID)

    try:
        return firebase_admin.get_app()
    except ValueError:
        return firebase_admin.initialize_app(
            options={"projectId": cfg.FIREBASE_PROJECT_ID}
        )


class AuthenticatedUser(BaseModel):
    uid: str
    email: Optional[str] = None
    display_name: Optional[str] = None


security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> AuthenticatedUser:
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        firebase_admin.get_app()
    except ValueError:
        init_firebase()

    token = credentials.credentials
    try:
        decoded = auth.verify_id_token(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    uid = decoded.get("uid") or decoded.get("user_id")
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token does not contain a valid user ID",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = decoded.get("email")
    display_name = decoded.get("name") or decoded.get("displayName")

    return AuthenticatedUser(uid=uid, email=email, display_name=display_name)
