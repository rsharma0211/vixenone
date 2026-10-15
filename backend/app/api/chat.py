from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.database import get_db
from app.llm.client import GeminiClient, create_gemini_client
from app.schemas.chat import ChatTurnRequest, ChatTurnResponse
from app.services.chat_service import ChatService
from app.services.job_launcher import JobLauncher, get_job_launcher
from app.services.user_service import UserService

router = APIRouter(prefix="/api/chat", tags=["chat"])


def get_gemini_client() -> GeminiClient:
    return create_gemini_client()


@router.post("/turn", response_model=ChatTurnResponse, status_code=status.HTTP_200_OK)
async def chat_turn(
    payload: ChatTurnRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    launcher: JobLauncher = Depends(get_job_launcher),
    gemini_client: GeminiClient = Depends(get_gemini_client),
) -> ChatTurnResponse:
    user = await UserService.get_or_create_profile(db, current_user)
    return await ChatService.resolve_turn(
        session=db,
        user_id=user.id,
        request=payload,
        launcher=launcher,
        gemini_client=gemini_client,
    )
