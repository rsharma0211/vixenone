from enum import Enum
from typing import Optional
import uuid
from pydantic import BaseModel, ConfigDict, field_validator


class UserRole(str, Enum):
    FACILITIES_MANAGER = "facilities_manager"
    PROCUREMENT = "procurement"
    APPROVER = "approver"


class UserProfileResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    role: UserRole

    model_config = ConfigDict(from_attributes=True)


class UserProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    role: Optional[UserRole] = None

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            stripped = v.strip()
            if not stripped:
                raise ValueError("Display name cannot be empty or whitespace")
            return stripped
        return v
