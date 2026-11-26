from app.models import OpportunityStatus, User, UserRole
from app.services.audit import actor_snapshot, status_transition


def test_status_transition_exposes_business_labels() -> None:
    transition = status_transition(OpportunityStatus.NEW, OpportunityStatus.GO)

    assert transition == {
        "from_status": "nouveau",
        "from_status_label": "À analyser",
        "to_status": "go",
        "to_status_label": "En étude réponse",
    }


def test_actor_snapshot_keeps_identity_for_audit_history() -> None:
    user = User(
        id=42,
        email="manuel@example.com",
        full_name="Manuel Gomes",
        role=UserRole.ADMIN,
        hashed_password="hash",
        is_active=True,
    )

    assert actor_snapshot(user) == {
        "id": 42,
        "label": "Manuel Gomes",
        "email": "manuel@example.com",
        "role": "admin",
    }
