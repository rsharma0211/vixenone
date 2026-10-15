import logging
from decimal import Decimal
from typing import Dict, List, Optional
import uuid
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import GeminiClient, GeminiClientError, ParsedEvaluationDetails
from app.repositories.evaluation_repo import EvaluationRepository
from app.schemas.chat import (
    ChatAction,
    ChatChoiceOption,
    ChatCollectedDetails,
    ChatExpect,
    ChatJobInfo,
    ChatSummary,
    ChatTurnRequest,
    ChatTurnResponse,
    ChatVendorSummary,
)
from app.schemas.evaluation import EvaluationResultsResponse
from app.services.evaluation_service import EvaluationService
from app.services.job_launcher import JobLauncher

logger = logging.getLogger(__name__)

OFF_TOPIC_REPLY = (
    "I can help you set up and run an evaluation. For anything else, use the tabs or Help."
)


def format_inr(amount: Optional[float | Decimal | int]) -> str:
    """Format numeric INR amount with Indian grouping system, e.g. ₹4,72,000."""
    if amount is None:
        return "Not stated"
    val = int(round(float(amount)))
    s = str(abs(val))
    if len(s) <= 3:
        formatted = s
    else:
        last3 = s[-3:]
        rest = s[:-3]
        groups = []
        while len(rest) > 2:
            groups.append(rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.append(rest)
        groups.reverse()
        formatted = ",".join(groups) + "," + last3
    sign = "-" if val < 0 else ""
    return f"₹{sign}{formatted}"


def build_chat_summary(results: EvaluationResultsResponse) -> ChatSummary:
    """Pure function building ChatSummary from EvaluationResultsResponse."""
    vendors_summary: List[ChatVendorSummary] = []
    for v in results.vendors:
        total = v.mandatory_total
        met = v.mandatory_met
        failures = v.mandatory_failures
        to_check = max(0, total - met - failures)

        vendors_summary.append(
            ChatVendorSummary(
                name=v.name,
                total=v.display_total if v.display_total is not None else (v.score or 0),
                mandatory_met=f"{met} of {total}",
                mandatory_failures=failures,
                mandatory_to_check=to_check,
                monthly_total=format_inr(v.monthly_total_inr),
                needs_review_count=v.needs_review_count,
            )
        )

    rec = results.recommendation
    if rec and rec.state == "recommended":
        rec_vendor_name = None
        for v in results.vendors:
            if str(v.id) == str(rec.vendor_id):
                rec_vendor_name = v.name
                break
        outcome_str = f"Recommended: {rec_vendor_name or rec.vendor_id}"
        return ChatSummary(
            vendors=vendors_summary,
            outcome=outcome_str,
            recommended_vendor=rec_vendor_name,
            reasons=list(rec.reasons),
        )

    reasons = (
        list(rec.reasons)
        if rec and rec.reasons
        else ["Insufficient information to make a recommendation."]
    )
    return ChatSummary(
        vendors=vendors_summary,
        outcome="Insufficient information to recommend",
        recommended_vendor=None,
        reasons=reasons,
    )


class ChatService:
    @staticmethod
    def _get_links(eval_id: uuid.UUID) -> Dict[str, str]:
        return {
            "documents": f"/evaluations/{eval_id}/documents",
            "requirements": f"/evaluations/{eval_id}/requirements",
            "comparison": f"/evaluations/{eval_id}/comparison",
            "recommendation": f"/evaluations/{eval_id}/recommendation",
        }

    @staticmethod
    async def resolve_turn(
        session: AsyncSession,
        user_id: uuid.UUID,
        request: ChatTurnRequest,
        launcher: JobLauncher,
        gemini_client: GeminiClient,
    ) -> ChatTurnResponse:
        # Step A: No evaluation ID provided -> Step 4 (No evaluation)
        if request.evaluation_id is None:
            return await ChatService._resolve_no_evaluation(
                session=session,
                user_id=user_id,
                request=request,
                gemini_client=gemini_client,
            )

        # Step B: Evaluation ID provided -> Scoped to token user
        eval_obj = await EvaluationRepository.get_by_id(session, user_id, request.evaluation_id)
        if not eval_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Evaluation {request.evaluation_id} not found",
            )

        links = ChatService._get_links(eval_obj.id)
        latest_job = await EvaluationRepository.get_latest_job(session, user_id, eval_obj.id)

        # Step 10: Check if previous job failed
        if latest_job and latest_job.status == "failed":
            if request.action == ChatAction.TRY_AGAIN:
                if latest_job.kind == "extract_requirements":
                    job = await EvaluationService.start_extraction(
                        session=session,
                        user_id=user_id,
                        evaluation_id=eval_obj.id,
                        confirm_replace=True,
                        launcher=launcher,
                    )
                    return ChatTurnResponse(
                        reply="Restarting requirement extraction...",
                        state="extracting",
                        evaluation_id=eval_obj.id,
                        job=ChatJobInfo(id=job.id, status=job.status, step_label=job.step_label),
                        links=links,
                    )
                else:
                    job = await EvaluationService.start_analysis(
                        session=session,
                        user_id=user_id,
                        evaluation_id=eval_obj.id,
                        confirm_rerun=True,
                        launcher=launcher,
                    )
                    return ChatTurnResponse(
                        reply="Restarting analysis...",
                        state="analysing",
                        evaluation_id=eval_obj.id,
                        job=ChatJobInfo(id=job.id, status=job.status, step_label=job.step_label),
                        links=links,
                    )

            if request.message and request.message.strip():
                return ChatTurnResponse(
                    reply=OFF_TOPIC_REPLY,
                    state="failed",
                    evaluation_id=eval_obj.id,
                    expect=ChatExpect(
                        kind="choice",
                        options=[ChatChoiceOption(action="try_again", label="Try again")],
                    ),
                    links=links,
                )

            safe_error = latest_job.error_message or "An unexpected error occurred during processing."
            return ChatTurnResponse(
                reply=f"The previous job encountered an issue: {safe_error} Would you like to try again?",
                state="failed",
                evaluation_id=eval_obj.id,
                expect=ChatExpect(
                    kind="choice",
                    options=[ChatChoiceOption(action="try_again", label="Try again")],
                ),
                links=links,
            )

        # Check if an active job is running
        if latest_job and latest_job.status in ("queued", "extracting", "analysing"):
            job_info = ChatJobInfo(
                id=latest_job.id,
                status=latest_job.status,
                step_label=latest_job.step_label,
            )
            state = "extracting" if latest_job.kind == "extract_requirements" else "analysing"
            if request.message and request.message.strip():
                return ChatTurnResponse(
                    reply=OFF_TOPIC_REPLY,
                    state=state,
                    evaluation_id=eval_obj.id,
                    job=job_info,
                    links=links,
                )

            label = latest_job.step_label or latest_job.status
            noun = "Requirement extraction" if state == "extracting" else "Analysis"
            return ChatTurnResponse(
                reply=f"{noun} is in progress ({label}).",
                state=state,
                evaluation_id=eval_obj.id,
                job=job_info,
                links=links,
            )

        # Step 9: Analysed
        if eval_obj.status == "analysed":
            if request.action == ChatAction.CONFIRM_RERUN:
                try:
                    job = await EvaluationService.start_analysis(
                        session=session,
                        user_id=user_id,
                        evaluation_id=eval_obj.id,
                        confirm_rerun=True,
                        launcher=launcher,
                    )
                    return ChatTurnResponse(
                        reply="Re-running analysis...",
                        state="analysing",
                        evaluation_id=eval_obj.id,
                        job=ChatJobInfo(id=job.id, status=job.status, step_label=job.step_label),
                        links=links,
                    )
                except HTTPException as exc:
                    return ChatTurnResponse(
                        reply=f"Cannot start analysis: {exc.detail}",
                        state="analysed",
                        evaluation_id=eval_obj.id,
                        links=links,
                    )

            results_data = await EvaluationService.get_results(session, user_id, eval_obj.id)
            summary = build_chat_summary(results_data)

            if request.message and request.message.strip():
                return ChatTurnResponse(
                    reply=OFF_TOPIC_REPLY,
                    state="analysed",
                    evaluation_id=eval_obj.id,
                    summary=summary,
                    links=links,
                )

            return ChatTurnResponse(
                reply="Evaluation complete. Here is the summary of vendor results and recommendation.",
                state="analysed",
                evaluation_id=eval_obj.id,
                summary=summary,
                links=links,
            )

        # Step 9: Stale
        if eval_obj.status == "stale":
            if request.action == ChatAction.CONFIRM_RERUN or request.action == ChatAction.RUN_ANALYSIS:
                try:
                    job = await EvaluationService.start_analysis(
                        session=session,
                        user_id=user_id,
                        evaluation_id=eval_obj.id,
                        confirm_rerun=True,
                        launcher=launcher,
                    )
                    return ChatTurnResponse(
                        reply="Re-running analysis with updated requirements...",
                        state="analysing",
                        evaluation_id=eval_obj.id,
                        job=ChatJobInfo(id=job.id, status=job.status, step_label=job.step_label),
                        links=links,
                    )
                except HTTPException as exc:
                    return ChatTurnResponse(
                        reply=f"Cannot re-run analysis: {exc.detail}",
                        state="stale",
                        evaluation_id=eval_obj.id,
                        links=links,
                    )

            results_data = await EvaluationService.get_results(session, user_id, eval_obj.id)
            summary = build_chat_summary(results_data)

            if request.message and request.message.strip():
                return ChatTurnResponse(
                    reply=OFF_TOPIC_REPLY,
                    state="stale",
                    evaluation_id=eval_obj.id,
                    summary=summary,
                    expect=ChatExpect(
                        kind="choice",
                        options=[ChatChoiceOption(action="confirm_rerun", label="Re-run analysis")],
                    ),
                    links=links,
                )

            return ChatTurnResponse(
                reply="Requirements were updated after analysis, so results are out of date. Would you like to re-run analysis?",
                state="stale",
                evaluation_id=eval_obj.id,
                summary=summary,
                expect=ChatExpect(
                    kind="choice",
                    options=[ChatChoiceOption(action="confirm_rerun", label="Re-run analysis")],
                ),
                links=links,
            )

        # Step 7 & 8: Requirements ready for review & Run analysis
        if eval_obj.status == "requirements_review":
            reqs = eval_obj.requirements or []
            total_reqs = len(reqs)
            mandatory_reqs = sum(1 for r in reqs if r.mandatory)

            review_options = [
                ChatChoiceOption(
                    action="review_first",
                    label="Review requirements first",
                    link=links["requirements"],
                ),
                ChatChoiceOption(
                    action="run_analysis",
                    label="Run analysis now",
                ),
            ]

            if request.action == ChatAction.RUN_ANALYSIS:
                try:
                    job = await EvaluationService.start_analysis(
                        session=session,
                        user_id=user_id,
                        evaluation_id=eval_obj.id,
                        confirm_rerun=False,
                        launcher=launcher,
                    )
                    return ChatTurnResponse(
                        reply="Analysis started. Evaluating vendor proposals against requirements...",
                        state="analysing",
                        evaluation_id=eval_obj.id,
                        job=ChatJobInfo(id=job.id, status=job.status, step_label=job.step_label),
                        links=links,
                    )
                except HTTPException as exc:
                    return ChatTurnResponse(
                        reply=f"Cannot start analysis: {exc.detail}",
                        state="requirements_review",
                        evaluation_id=eval_obj.id,
                        expect=ChatExpect(kind="choice", options=review_options),
                        links=links,
                    )

            if request.action == ChatAction.REVIEW_FIRST:
                return ChatTurnResponse(
                    reply="You can review and edit requirements on the Requirements tab. When you are ready, choose 'Run analysis now' below.",
                    state="requirements_review",
                    evaluation_id=eval_obj.id,
                    expect=ChatExpect(
                        kind="choice",
                        options=[ChatChoiceOption(action="run_analysis", label="Run analysis now")],
                    ),
                    links=links,
                )

            if request.message and request.message.strip():
                return ChatTurnResponse(
                    reply=OFF_TOPIC_REPLY,
                    state="requirements_review",
                    evaluation_id=eval_obj.id,
                    expect=ChatExpect(kind="choice", options=review_options),
                    links=links,
                )

            return ChatTurnResponse(
                reply=f"Extracted {total_reqs} requirements ({mandatory_reqs} mandatory). You can review the requirements or run analysis now.",
                state="requirements_review",
                evaluation_id=eval_obj.id,
                expect=ChatExpect(kind="choice", options=review_options),
                links=links,
            )

        # Step 5 & 6: Evaluation in draft (check documents and start extraction)
        docs = eval_obj.documents or []
        vendors = sorted(eval_obj.vendors or [], key=lambda v: v.position)
        req_doc = next((d for d in docs if d.kind == "requirements"), None)
        proposal_vendor_ids = {
            d.vendor_id for d in docs if d.kind == "proposal" and d.vendor_id is not None
        }
        missing_proposals = [v for v in vendors if v.id not in proposal_vendor_ids]

        if req_doc is None:
            if request.message and request.message.strip():
                return ChatTurnResponse(
                    reply=OFF_TOPIC_REPLY,
                    state="upload_requirements",
                    evaluation_id=eval_obj.id,
                    expect=ChatExpect(kind="file", file_kind="requirements"),
                    links=links,
                )
            return ChatTurnResponse(
                reply="Please upload the requirements document (PDF or DOCX).",
                state="upload_requirements",
                evaluation_id=eval_obj.id,
                expect=ChatExpect(kind="file", file_kind="requirements"),
                links=links,
            )

        if missing_proposals:
            next_vendor = missing_proposals[0]
            if request.message and request.message.strip():
                return ChatTurnResponse(
                    reply=OFF_TOPIC_REPLY,
                    state="upload_proposal",
                    evaluation_id=eval_obj.id,
                    expect=ChatExpect(
                        kind="file",
                        file_kind="proposal",
                        vendor_id=next_vendor.id,
                        vendor_name=next_vendor.name,
                    ),
                    links=links,
                )
            return ChatTurnResponse(
                reply=f"Please upload the proposal document for {next_vendor.name}.",
                state="upload_proposal",
                evaluation_id=eval_obj.id,
                expect=ChatExpect(
                    kind="file",
                    file_kind="proposal",
                    vendor_id=next_vendor.id,
                    vendor_name=next_vendor.name,
                ),
                links=links,
            )

        # All documents present, never extracted
        if eval_obj.status == "draft" and len(eval_obj.requirements or []) == 0:
            try:
                job = await EvaluationService.start_extraction(
                    session=session,
                    user_id=user_id,
                    evaluation_id=eval_obj.id,
                    confirm_replace=False,
                    launcher=launcher,
                )
                return ChatTurnResponse(
                    reply="All documents uploaded. Requirement extraction has started.",
                    state="extracting",
                    evaluation_id=eval_obj.id,
                    job=ChatJobInfo(id=job.id, status=job.status, step_label=job.step_label),
                    links=links,
                )
            except HTTPException as exc:
                return ChatTurnResponse(
                    reply=f"Cannot start extraction: {exc.detail}",
                    state="draft",
                    evaluation_id=eval_obj.id,
                    links=links,
                )

        # Fallback for any unknown state
        return ChatTurnResponse(
            reply="I can help you set up and run an evaluation. For anything else, use the tabs or Help.",
            state=eval_obj.status,
            evaluation_id=eval_obj.id,
            links=links,
        )

    @staticmethod
    async def _resolve_no_evaluation(
        session: AsyncSession,
        user_id: uuid.UUID,
        request: ChatTurnRequest,
        gemini_client: GeminiClient,
    ) -> ChatTurnResponse:
        collected = request.collected or ChatCollectedDetails()

        # If no message provided, ask for initial details
        if not request.message or not request.message.strip():
            return ChatTurnResponse(
                reply="To get started, what are you evaluating? Please provide a title, category (e.g. Housekeeping, Security), and 2–3 vendor names.",
                state="collecting_details",
                expect=ChatExpect(kind="text"),
                collected=collected,
            )

        # Step 4: Free text -> Gemini details parser
        try:
            parsed: ParsedEvaluationDetails = await gemini_client.parse_evaluation_details(
                request.message.strip()
            )
        except GeminiClientError:
            return ChatTurnResponse(
                reply="I had trouble understanding that. Please provide a title, category, and 2–3 vendor names to get started.",
                state="collecting_details",
                expect=ChatExpect(kind="text"),
                collected=collected,
            )

        # Update collected fields with parsed values
        if parsed.title and parsed.title.strip():
            collected.title = parsed.title.strip()

        if parsed.category and parsed.category.strip():
            cat = parsed.category.strip()
            if 1 <= len(cat) <= 60:
                collected.category = cat

        if parsed.vendor_names:
            seen = {v.lower() for v in (collected.vendor_names or [])}
            new_vendors: List[str] = []
            for v in parsed.vendor_names:
                v_clean = v.strip()
                if v_clean and v_clean.lower() not in seen:
                    seen.add(v_clean.lower())
                    new_vendors.append(v_clean[:80])
            collected.vendor_names = (collected.vendor_names or []) + new_vendors

        # If message parsed no valid fields at all and nothing was collected previously
        has_title = bool(collected.title and collected.title.strip())
        has_category = bool(collected.category and collected.category.strip())
        vendor_names = collected.vendor_names or []
        vendor_count = len(vendor_names)

        if not has_title and not has_category and vendor_count == 0:
            return ChatTurnResponse(
                reply="I can help you set up and run an evaluation. For anything else, use the tabs or Help.",
                state="collecting_details",
                expect=ChatExpect(kind="text"),
                collected=collected,
            )

        # If more than 3 vendors -> ask to choose up to 3
        if vendor_count > 3:
            vendors_str = ", ".join(vendor_names)
            return ChatTurnResponse(
                reply=f"You provided {vendor_count} vendors ({vendors_str}). An evaluation can have at most 3 vendors. Please choose 2 or 3 vendors to compare.",
                state="collecting_details",
                expect=ChatExpect(kind="text"),
                collected=collected,
            )

        # Missing fields -> ask only for those
        missing_parts: List[str] = []
        if not has_title:
            missing_parts.append("a title")
        if not has_category:
            missing_parts.append("a category (e.g. Housekeeping, Security)")
        if vendor_count == 0:
            missing_parts.append("2–3 vendor names")
        elif vendor_count == 1:
            missing_parts.append(f"at least one more vendor name to compare with {vendor_names[0]}")

        if missing_parts:
            if len(missing_parts) == 3:
                reply = "Please provide a title, category, and 2–3 vendor names to get started."
            elif len(missing_parts) == 2:
                reply = f"Please provide {missing_parts[0]} and {missing_parts[1]}."
            else:
                reply = f"Please provide {missing_parts[0]}."

            return ChatTurnResponse(
                reply=reply,
                state="collecting_details",
                expect=ChatExpect(kind="text"),
                collected=collected,
            )

        # When complete -> create evaluation with existing create function
        assert collected.title is not None and collected.category is not None
        eval_obj = await EvaluationRepository.create(
            session=session,
            user_id=user_id,
            title=collected.title.strip(),
            category=collected.category.strip(),
            vendor_names=collected.vendor_names,
            location_id=None,
        )

        links = ChatService._get_links(eval_obj.id)
        return ChatTurnResponse(
            reply=f"Created evaluation '{eval_obj.title}'. Please upload the requirements document to begin.",
            state="upload_requirements",
            evaluation_id=eval_obj.id,
            expect=ChatExpect(kind="file", file_kind="requirements"),
            links=links,
        )
