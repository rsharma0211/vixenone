from typing import List, cast
import uuid
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.models.criteria import EvaluationCriterion
from app.schemas.criteria import (
    BUILTIN_CRITERIA_DEFAULTS,
    CriterionKind,
    EvaluationCriterionUpdateItem,
)


class CriteriaRepository:
    @staticmethod
    async def get_or_create_builtins(
        session: AsyncSession, user_id: uuid.UUID
    ) -> List[EvaluationCriterion]:
        """Fetch all criteria for user; if user has no built-ins, create all 5 concurrency-safely."""
        stmt = (
            select(EvaluationCriterion)
            .where(EvaluationCriterion.user_id == user_id)
            .order_by(EvaluationCriterion.position, EvaluationCriterion.created_at)
        )
        result = await session.execute(stmt)
        criteria = list(result.scalars().all())

        builtin_keys_present = {c.builtin_key for c in criteria if c.kind == CriterionKind.BUILTIN.value}
        all_builtin_keys = set(BUILTIN_CRITERIA_DEFAULTS.keys())

        missing_builtins = all_builtin_keys - builtin_keys_present
        if missing_builtins:
            for b_key in sorted(missing_builtins, key=lambda k: cast(int, BUILTIN_CRITERIA_DEFAULTS[k]["position"])):
                default_data = BUILTIN_CRITERIA_DEFAULTS[b_key]
                insert_stmt = (
                    insert(EvaluationCriterion)
                    .values(
                        id=uuid.uuid4(),
                        user_id=user_id,
                        kind=CriterionKind.BUILTIN.value,
                        builtin_key=b_key,
                        name=default_data["name"],
                        guidance=default_data["guidance"],
                        weight=default_data["default_weight"],
                        position=default_data["position"],
                    )
                    .on_conflict_do_nothing(
                        index_elements=["user_id", "builtin_key"],
                        index_where=EvaluationCriterion.builtin_key.is_not(None),
                    )
                )
                await session.execute(insert_stmt)

            await session.commit()

            # Re-fetch full sorted list
            refetch_stmt = (
                select(EvaluationCriterion)
                .where(EvaluationCriterion.user_id == user_id)
                .order_by(EvaluationCriterion.position, EvaluationCriterion.created_at)
            )
            res = await session.execute(refetch_stmt)
            criteria = list(res.scalars().all())

        return criteria

    @staticmethod
    async def atomic_replace(
        session: AsyncSession,
        user_id: uuid.UUID,
        items: List[EvaluationCriterionUpdateItem],
    ) -> List[EvaluationCriterion]:
        """Atomically replace criteria set with strict validation.

        Rules:
        - All 5 built-ins present.
        - Built-in name and guidance unchanged.
        - <= 10 custom criteria.
        - Total weight exactly 100.
        - Unique names (case-insensitive).
        - Guidance length 20–1000.
        - Weight 0–100.
        """
        # 1. Total weight exactly 100
        total_weight = sum(item.weight for item in items)
        if total_weight != 100:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Total weight across all criteria must equal 100 (got {total_weight})",
            )

        # 2. Check built-ins
        all_builtin_keys = set(BUILTIN_CRITERIA_DEFAULTS.keys())
        submitted_builtins = {}
        custom_items: List[EvaluationCriterionUpdateItem] = []

        for item in items:
            if item.kind == CriterionKind.BUILTIN:
                if not item.builtin_key or item.builtin_key not in all_builtin_keys:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Invalid builtin criterion key: {item.builtin_key}",
                    )
                if item.builtin_key in submitted_builtins:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Duplicate builtin criterion: {item.builtin_key}",
                    )
                submitted_builtins[item.builtin_key] = item
            else:
                custom_items.append(item)

        missing_builtins = all_builtin_keys - set(submitted_builtins.keys())
        if missing_builtins:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"All 5 built-in criteria must be present. Missing: {', '.join(sorted(missing_builtins))}",
            )

        # 3. Built-in name and guidance unchanged
        for b_key, b_item in submitted_builtins.items():
            canonical = BUILTIN_CRITERIA_DEFAULTS[b_key]
            if b_item.name != canonical["name"]:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Built-in criterion '{b_key}' name cannot be modified (expected '{canonical['name']}', got '{b_item.name}')",
                )
            if b_item.guidance != canonical["guidance"]:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Built-in criterion '{b_key}' guidance cannot be modified",
                )

        # 4. Custom criteria count <= 10
        if len(custom_items) > 10:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Maximum 10 custom criteria allowed (submitted {len(custom_items)})",
            )

        # 5. Unique names (case-insensitive)
        names_seen = set()
        for item in items:
            low_name = item.name.strip().lower()
            if low_name in names_seen:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Duplicate criterion name: '{item.name}'",
                )
            names_seen.add(low_name)

        # 6. Atomic DB update
        existing_criteria = await CriteriaRepository.get_or_create_builtins(session, user_id)
        existing_builtin_map = {
            c.builtin_key: c for c in existing_criteria if c.kind == CriterionKind.BUILTIN.value
        }
        existing_custom_map = {
            c.id: c for c in existing_criteria if c.kind == CriterionKind.CUSTOM.value
        }

        # Update built-ins
        for b_key, b_item in submitted_builtins.items():
            db_builtin = existing_builtin_map.get(b_key)
            if db_builtin:
                db_builtin.weight = b_item.weight
                db_builtin.position = b_item.position if b_item.position is not None else cast(int, BUILTIN_CRITERIA_DEFAULTS[b_key]["position"])
                db_builtin.updated_at = func.now()

        # Handle custom criteria
        submitted_custom_ids = {item.id for item in custom_items if item.id is not None}
        for existing_id, existing_custom in existing_custom_map.items():
            if existing_id not in submitted_custom_ids:
                await session.delete(existing_custom)

        for item in custom_items:
            if item.id and item.id in existing_custom_map:
                c = existing_custom_map[item.id]
                c.name = item.name
                c.guidance = item.guidance
                c.weight = item.weight
                c.position = item.position if item.position is not None else 0
                c.updated_at = func.now()
            else:
                new_c = EvaluationCriterion(
                    id=item.id or uuid.uuid4(),
                    user_id=user_id,
                    kind=CriterionKind.CUSTOM.value,
                    builtin_key=None,
                    name=item.name,
                    guidance=item.guidance,
                    weight=item.weight,
                    position=item.position if item.position is not None else 0,
                )
                session.add(new_c)

        await session.commit()

        # Return updated set
        final_stmt = (
            select(EvaluationCriterion)
            .where(EvaluationCriterion.user_id == user_id)
            .order_by(EvaluationCriterion.position, EvaluationCriterion.created_at)
        )
        final_res = await session.execute(final_stmt)
        return list(final_res.scalars().all())
