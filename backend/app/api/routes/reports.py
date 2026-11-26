from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import DbSession
from app.models import AiReport
from app.schemas import AiReportRead


router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("", response_model=list[AiReportRead])
def list_reports(db: DbSession) -> list[AiReport]:
    return list(db.scalars(select(AiReport).order_by(AiReport.created_at.desc()).limit(100)).all())


@router.get("/{report_id}", response_model=AiReportRead)
def get_report(report_id: int, db: DbSession) -> AiReport:
    report = db.get(AiReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report

