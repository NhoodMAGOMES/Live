from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.models import User
from app.schemas import FrontAnalysisLaunchResponse, FrontAnalysisRequest, FrontAnalysisTaskResponse
from app.tasks import run_frontoffice_analysis_task
from app.worker import celery_app


router = APIRouter(prefix="/frontoffice", tags=["frontoffice"])


@router.post("/analyze", response_model=FrontAnalysisLaunchResponse, status_code=status.HTTP_202_ACCEPTED)
def launch_frontoffice_analysis(
    payload: FrontAnalysisRequest,
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    task = run_frontoffice_analysis_task.delay(payload.model_dump(mode="json"))
    return {"task_id": task.id, "status": "queued"}


@router.get("/analyze/{task_id}", response_model=FrontAnalysisTaskResponse)
def frontoffice_analysis_status(
    task_id: str,
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    task = celery_app.AsyncResult(task_id)
    state = task.state.lower()
    if task.successful():
        return {"task_id": task_id, "status": "success", "result": task.result, "error": None}
    if task.failed():
        return {"task_id": task_id, "status": "failed", "result": None, "error": str(task.result)}
    if state not in {"pending", "received", "started", "retry"}:
        raise HTTPException(status_code=500, detail=f"État de tâche inconnu: {task.state}")
    next_status = "running" if state in {"received", "started", "retry"} else "queued"
    return {"task_id": task_id, "status": next_status, "result": None, "error": None}
