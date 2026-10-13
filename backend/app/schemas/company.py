from typing import List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CompanyUpdate(BaseModel):
    name: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        if not s:
            return None
        if len(s) > 120:
            raise ValueError("Company name cannot exceed 120 characters.")
        return s


class LocationCreate(BaseModel):
    name: str
    city: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Location name cannot be empty.")
        if len(s) > 80:
            raise ValueError("Location name cannot exceed 80 characters.")
        return s

    @field_validator("city")
    @classmethod
    def validate_city(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("City cannot be empty.")
        if len(s) > 80:
            raise ValueError("City cannot exceed 80 characters.")
        return s


class LocationUpdate(BaseModel):
    name: Optional[str] = None
    city: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            raise ValueError("Location name cannot be empty.")
        s = v.strip()
        if not s:
            raise ValueError("Location name cannot be empty.")
        if len(s) > 80:
            raise ValueError("Location name cannot exceed 80 characters.")
        return s

    @field_validator("city")
    @classmethod
    def validate_city(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            raise ValueError("City cannot be empty.")
        s = v.strip()
        if not s:
            raise ValueError("City cannot be empty.")
        if len(s) > 80:
            raise ValueError("City cannot exceed 80 characters.")
        return s


class LocationResponse(BaseModel):
    id: uuid.UUID
    name: str
    city: str
    position: int
    evaluation_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class CompanyResponse(BaseModel):
    id: uuid.UUID
    name: Optional[str] = None
    locations: List[LocationResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class EvaluationLocationResponse(BaseModel):
    id: uuid.UUID
    name: str
    city: str

    model_config = ConfigDict(from_attributes=True)
