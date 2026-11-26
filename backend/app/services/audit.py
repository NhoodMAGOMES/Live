from __future__ import annotations

from typing import Any

from app.models import AuditLog, OpportunityStatus, User


STATUS_LABELS = {
    OpportunityStatus.NEW.value: "À analyser",
    OpportunityStatus.ANALYZED.value: "Revue IA",
    OpportunityStatus.TO_QUALIFY.value: "À qualifier",
    OpportunityStatus.RELEVANT.value: "Pertinent",
    OpportunityStatus.NOT_RELEVANT.value: "Écarté par IA",
    OpportunityStatus.GO.value: "En étude réponse",
    OpportunityStatus.WATCH.value: "Sous surveillance",
    OpportunityStatus.NO_GO.value: "NO-GO",
    OpportunityStatus.ARCHIVED.value: "Archivé",
}

ACTION_LABELS = {
    "analysis_run": "Analyse IA",
    "status_update": "Changement de statut",
}


def status_value(status: OpportunityStatus | str | None) -> str | None:
    if status is None:
        return None
    if isinstance(status, OpportunityStatus):
        return status.value
    return str(status)


def status_label(status: OpportunityStatus | str | None) -> str | None:
    value = status_value(status)
    if value is None:
        return None
    return STATUS_LABELS.get(value, value)


def actor_snapshot(user: User) -> dict[str, Any]:
    role = user.role.value if hasattr(user.role, "value") else str(user.role)
    label = user.full_name or user.email
    return {
        "id": user.id,
        "label": label,
        "email": user.email,
        "role": role,
    }


def status_snapshot(status: OpportunityStatus | str | None) -> dict[str, str | None]:
    value = status_value(status)
    return {
        "status": value,
        "status_label": status_label(value),
    }


def status_transition(
    before_status: OpportunityStatus | str | None,
    after_status: OpportunityStatus | str | None,
) -> dict[str, str | None]:
    return {
        "from_status": status_value(before_status),
        "from_status_label": status_label(before_status),
        "to_status": status_value(after_status),
        "to_status_label": status_label(after_status),
    }


def actor_from_audit(log: AuditLog, user: User | None) -> dict[str, Any]:
    for payload in (log.after, log.before):
        actor = (payload or {}).get("actor")
        if isinstance(actor, dict) and actor.get("label"):
            return {
                "label": str(actor.get("label")),
                "email": actor.get("email"),
                "role": actor.get("role"),
            }
    if user:
        snapshot = actor_snapshot(user)
        return {
            "label": snapshot["label"],
            "email": snapshot["email"],
            "role": snapshot["role"],
        }
    return {"label": "Système", "email": None, "role": None}


def transition_from_audit(log: AuditLog) -> dict[str, str | None] | None:
    before_status = (log.before or {}).get("status")
    after_status = (log.after or {}).get("status")
    if before_status is None and after_status is None:
        return None
    return status_transition(str(before_status) if before_status else None, str(after_status) if after_status else None)


def action_label(action: str) -> str:
    return ACTION_LABELS.get(action, action)
