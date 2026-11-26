import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Keyword, KeywordCategory, Source, SourceConnectorType, User, UserRole
from app.core.config import get_settings
from app.core.security import hash_password


INITIAL_KEYWORDS_PATH = Path(__file__).resolve().parents[1] / "data" / "initial_keywords.json"


def _default_weight(category_name: str, term: str) -> float:
    if category_name == "TERMES GENERIQUES MARCHES PUBLIQUES":
        return 2.0
    if "événementiel" in term.lower() or "lieu" in term.lower():
        return 5.0
    return 3.0


def seed_keywords(db: Session) -> dict[str, int]:
    data = json.loads(INITIAL_KEYWORDS_PATH.read_text(encoding="utf-8"))
    categories_created = 0
    keywords_created = 0

    for category_name, terms in data.items():
        category = db.scalar(select(KeywordCategory).where(KeywordCategory.name == category_name))
        if not category:
            category = KeywordCategory(
                name=category_name,
                threshold=8,
                strategic_tags=["Pulse LIVE", "AO", "veille"],
            )
            db.add(category)
            db.flush()
            categories_created += 1

        existing_terms = {
            row[0].casefold()
            for row in db.execute(select(Keyword.term).where(Keyword.category_id == category.id)).all()
        }
        for term in terms:
            if term.casefold() in existing_terms:
                continue
            db.add(
                Keyword(
                    category_id=category.id,
                    term=term,
                    weight=_default_weight(category_name, term),
                    is_active=True,
                    tags=["seed"],
                )
            )
            keywords_created += 1

    db.commit()
    return {"categories_created": categories_created, "keywords_created": keywords_created}


def seed_sources(db: Session) -> dict[str, int]:
    settings = get_settings()
    live_source_config = {
        "keywords": [
            "AMO",
            "assistance à maîtrise d'ouvrage",
            "prestation intellectuelle",
            "marché de prestation intellectuelle",
            "mission de conseil",
            "mission d'étude",
            "étude de faisabilité",
            "étude de potentiel",
            "audit stratégique",
            "programmation événementielle",
            "programmation culturelle",
            "exploitation événementielle",
            "lieu culturel",
            "équipement culturel",
            "espaces d'exposition",
            "médiation culturelle",
            "valorisation patrimoniale",
            "transformation d'édifice",
            "reconversion de site",
            "spectacle vivant",
            "activation de lieu",
            "commercialisation d'espaces",
            "concession culturelle",
            "DSP culturelle",
        ],
        "days_back": 14,
        "limit": 300,
        "min_live_score": 25,
        "prequalification_enabled": True,
        "use_live_query_expansion": True,
    }
    defaults = [
        Source(
            name="BOAMP",
            connector_type=SourceConnectorType.BOAMP_API,
            api_endpoint=settings.boamp_api_base_url,
            frequency_minutes=720,
            is_active=True,
            config={
                **live_source_config,
                "departments": [],
                "verify_ssl": False,
                "connection_status": "connected",
                "access_mode": "official_api",
            },
        ),
        Source(
            name="TED Europe",
            connector_type=SourceConnectorType.TED_API,
            url="https://ted.europa.eu/fr/",
            api_endpoint=settings.ted_api_base_url,
            frequency_minutes=720,
            is_active=True,
            config={
                **live_source_config,
                "limit": 50,
                "page_size": 50,
                "buyer_country": "FRA",
                "scope": "ACTIVE",
                "verify_ssl": False,
                "request_delay_seconds": 0.5,
                "rate_limit_retries": 5,
                "connection_status": "connected",
                "access_mode": "official_api",
            },
        ),
        Source(
            name="VTscan",
            connector_type=SourceConnectorType.WEB_WATCH,
            frequency_minutes=1440,
            is_active=False,
            config={"mode": "manual_or_authorized_watch", "robots_required": True},
        ),
        Source(
            name="Pitchville",
            connector_type=SourceConnectorType.WEB_WATCH,
            frequency_minutes=1440,
            is_active=False,
            config={"mode": "manual_or_authorized_watch", "robots_required": True},
        ),
    ]
    restricted_platforms = [
        ("PLACE", "https://www.marches-publics.gouv.fr/", "Accès API/flux à obtenir auprès de l'AIFE ou de l'éditeur de PLACE."),
        ("Maximilien", "https://marches.maximilien.fr/", "Accès éditeur ou flux réutilisable à contractualiser avec le GIP Maximilien."),
        ("AWS-Achat", "https://www.aws-entreprises.com/", "Accès au flux de consultations à obtenir auprès d'AWS-Achat."),
        ("Achatpublic.com", "https://www.achatpublic.com/", "Accès au flux/API à obtenir auprès d'Achatpublic.com."),
        ("Marchés-Sécurisés", "https://www.marches-securises.fr/", "Accès au flux/API à obtenir auprès de l'éditeur."),
        ("e-marchespublics.com", "https://www.e-marchespublics.com/", "Accès au flux/API à obtenir auprès de l'éditeur."),
        ("Mégalis Bretagne", "https://www.megalis.bretagne.bzh/", "Accès au profil acheteur ou flux régional à obtenir auprès de Mégalis."),
        ("Klekoon", "https://www.klekoon.com/", "Accès au flux/API à obtenir auprès de Klekoon."),
        ("Dematis", "https://www.dematis.com/", "Accès au flux/API à obtenir auprès de Dematis."),
        ("Territoires Numériques BFC", "https://www.ternum-bfc.fr/", "Accès au profil acheteur régional à contractualiser."),
        ("XMarchés", "https://www.xmarches.fr/", "Accès au flux/API à obtenir auprès de l'éditeur."),
    ]
    defaults.extend(
        Source(
            name=name,
            connector_type=SourceConnectorType.WEB_WATCH,
            url=url,
            frequency_minutes=1440,
            is_active=False,
            config={
                "connection_status": "requires_agreement",
                "access_mode": "publisher_api_or_authorized_feed",
                "blocking_reason": reason,
                "scraping_allowed": False,
                "robots_required": True,
            },
        )
        for name, url, reason in restricted_platforms
    )
    defaults.append(
        Source(
            name="DECP / data.gouv.fr",
            connector_type=SourceConnectorType.WEB_WATCH,
            url="https://www.data.gouv.fr/fr/datasets/donnees-essentielles-de-la-commande-publique-fichiers-consolides/",
            frequency_minutes=1440,
            is_active=False,
            config={
                "connection_status": "reference_only",
                "access_mode": "open_data_enrichment",
                "blocking_reason": "Les DECP décrivent principalement les marchés attribués; source réservée à l'enrichissement, pas à la détection d'AO ouverts.",
            },
        )
    )
    created = 0
    for source in defaults:
        if db.scalar(select(Source).where(Source.name == source.name)):
            continue
        db.add(source)
        created += 1
    db.commit()
    return {"sources_created": created}


def seed_admin(db: Session) -> dict[str, int]:
    password = get_settings().seed_admin_password
    if not password:
        return {"users_created": 0}
    email = "admin@live.local"
    if db.scalar(select(User).where(User.email == email)):
        return {"users_created": 0}
    db.add(
        User(
            email=email,
            full_name="Admin LIVE",
            hashed_password=hash_password(password),
            role=UserRole.ADMIN,
            is_active=True,
        )
    )
    db.commit()
    return {"users_created": 1}


def seed_all(db: Session) -> dict[str, int]:
    result: dict[str, int] = {}
    result.update(seed_admin(db))
    result.update(seed_keywords(db))
    result.update(seed_sources(db))
    return result
