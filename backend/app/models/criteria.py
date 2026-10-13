from datetime import datetime
from typing import Optional
import uuid
from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.schemas.criteria import CriterionKind


class EvaluationCriterion(Base):
    __tablename__ = "evaluation_criteria"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=CriterionKind.CUSTOM.value,
    )
    builtin_key: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )
    guidance: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    weight: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_criteria_user_lower_name", user_id, func.lower(name), unique=True),
        Index(
            "ix_criteria_user_builtin_key",
            user_id,
            builtin_key,
            unique=True,
            postgresql_where=(builtin_key.is_not(None)),
        ),
    )
