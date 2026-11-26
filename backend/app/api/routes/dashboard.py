from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas import DashboardMapPoint, DashboardResponse
from app.services.opportunities import dashboard_map_points, dashboard_stats


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
def get_dashboard(db: DbSession) -> dict:
    return dashboard_stats(db)


@router.get("/map", response_model=list[DashboardMapPoint])
def get_dashboard_map(db: DbSession) -> list[dict]:
    return dashboard_map_points(db)
