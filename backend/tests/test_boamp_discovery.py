from datetime import datetime, timezone

from app.connectors.boamp import BOAMPConnector
from app.services.normalization import normalize_boamp_record
from app.services.scoring import KeywordConfig, score_opportunity


def test_boamp_where_clauses_expand_live_query_families_and_departments() -> None:
    connector = BOAMPConnector()

    clauses = connector._where_clauses(
        {
            "keywords": ["programmation événementielle"],
            "analysis_date": "2026-06-25",
            "days_back": 7,
            "departments": ["22"],
            "use_live_query_expansion": True,
        }
    )
    serialized = "\n".join(clause or "" for clause in clauses)

    assert len(clauses) > 3
    assert 'search("AMO")' in serialized
    assert 'search("prestation intellectuelle")' in serialized
    assert 'search("programmation événementielle")' in serialized
    assert 'search("équipement culturel")' in serialized
    assert 'search("valorisation patrimoniale")' in serialized
    assert "code_departement_prestation in" in serialized
    assert "code_departement in" in serialized
    assert "dateparution >= date'2026-06-19'" in serialized
    assert "dateparution <= date'2026-06-25'" in serialized


def test_boamp_cultural_facility_notice_scores_as_live_watch_or_better() -> None:
    record = {
        "idweb": "26-52747",
        "url_avis": "https://www.boamp.fr/pages/avis/?q=idweb:26-52747",
        "objet": (
            "transformation et la valorisation de cet édifice afin de créer un équipement culturel "
            "ouvert au public, intégrant des espaces d’exposition, de médiation, d’accueil et de "
            "programmation culturelle."
        ),
        "nomacheteur": "Commune de Pléneuf-Val-André",
        "famille_libelle": "Marchés européens",
        "procedure_libelle": "Procédure Restreinte",
        "nature_libelle": "Avis de marché",
        "descripteur_libelle": ["Etude"],
        "type_marche": ["SERVICES"],
        "type_marche_facette": ["Services"],
        "code_departement": ["22", "29", "35", "56"],
        "dateparution": "2026-05-31",
    }
    normalized = normalize_boamp_record(record)
    keywords = [
        KeywordConfig(id=1, category="EVENEMENTIEL ET PROGRAMMATION", term="programmation culturelle", weight=5),
        KeywordConfig(id=2, category="EVENEMENTIEL ET PROGRAMMATION", term="équipement culturel", weight=5),
        KeywordConfig(id=3, category="EVENEMENTIEL ET PROGRAMMATION", term="médiation", weight=4),
        KeywordConfig(id=4, category="ETUDE ET CONSEIL", term="valorisation de lieu", weight=3),
    ]

    result = score_opportunity(normalized, keywords, now=datetime(2026, 6, 1, tzinfo=timezone.utc))

    assert normalized["document_context"]
    assert "Etude" in normalized["document_context"]
    assert normalized["location"] == "22, 29, 35, 56"
    assert result.global_score >= 45
    assert result.decision in {"WATCH", "GO_HUMAN_REVIEW", "GO"}
    assert "équipement culturel" in result.breakdown["live_core_hits"]
