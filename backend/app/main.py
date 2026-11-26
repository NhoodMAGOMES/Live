from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import agents, auth, dashboard, frontoffice, keywords, notifications, opportunities, reports, sources
from app.core.config import get_settings


settings = get_settings()
app = FastAPI(title=settings.project_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(agents.router)
app.include_router(frontoffice.router)
app.include_router(dashboard.router)
app.include_router(keywords.router)
app.include_router(sources.router)
app.include_router(opportunities.router)
app.include_router(reports.router)
app.include_router(notifications.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.project_name}
