from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import DbSession, require_admin
from app.models import AuditLog, Source, SourceRun
from app.schemas import SourceCreate, SourceRead, SourceRunLaunchResponse, SourceRunRead, SourceRunTaskResponse, SourceUpdate
from app.tasks import run_source as run_source_task
from app.worker import celery_app


router = APIRouter(prefix="/sources", tags=["sources"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[SourceRead])
def list_sources(db: DbSession) -> list[Source]:
    return list(db.scalars(select(Source).order_by(Source.name)).all())


@router.post("", response_model=SourceRead)
def create_source(payload: SourceCreate, db: DbSession) -> Source:
    source = Source(**payload.model_dump())
    db.add(source)
    db.flush()
    db.add(AuditLog(entity_type="source", entity_id=str(source.id), action="create", before=None, after=payload.model_dump()))
    db.commit()
    db.refresh(source)
    return source


@router.patch("/{source_id}", response_model=SourceRead)
def update_source(source_id: int, payload: SourceUpdate, db: DbSession) -> Source:
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    before = {"name": source.name, "connector_type": source.connector_type.value, "is_active": source.is_active}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(source, field, value)
    db.add(AuditLog(entity_type="source", entity_id=str(source.id), action="update", before=before, after=payload.model_dump(exclude_unset=True)))
    db.commit()
    db.refresh(source)
    return source


@router.delete("/{source_id}")
def delete_source(source_id: int, db: DbSession) -> dict:
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    db.add(AuditLog(entity_type="source", entity_id=str(source.id), action="delete", before={"name": source.name}, after=None))
    db.delete(source)
    db.commit()
    return {"ok": True}


@router.post("/{source_id}/run", response_model=SourceRunLaunchResponse, status_code=status.HTTP_202_ACCEPTED)
def run_source(source_id: int, db: DbSession) -> dict:
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    task = run_source_task.delay(source_id)
    return {"task_id": task.id, "source_id": source_id, "status": "queued"}


@router.get("/tasks/{task_id}", response_model=SourceRunTaskResponse)
def source_run_task_status(task_id: str) -> dict:
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


@router.get("/{source_id}/runs", response_model=list[SourceRunRead])
def list_source_runs(source_id: int, db: DbSession) -> list[SourceRun]:
    return list(db.scalars(select(SourceRun).where(SourceRun.source_id == source_id).order_by(SourceRun.started_at.desc())).all())
