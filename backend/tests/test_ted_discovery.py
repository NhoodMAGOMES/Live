from datetime import date

from app.connectors.ted import TEDConnector
from app.services.normalization import normalize_ted_record


def test_ted_query_targets_active_french_notices_and_live_terms() -> None:
    connector = TEDConnector()
    query = connector._query(
        {"buyer_country": "FRA", "analysis_date": "2026-09-17", "days_back": 14},
        ["programmation culturelle", "événementiel"],
    )

    assert "buyer-country=FRA" in query
    assert "publication-date>=20260904" in query
    assert 'FT~"programmation culturelle"' in query
    assert "FT~événementiel" in query
    assert query.endswith("SORT BY publication-date DESC")
    assert connector._date_from({"analysis_date": "2026-09-17", "days_back": 14}) == date(2026, 9, 4)


def test_ted_notice_is_normalized_in_french_with_document_links() -> None:
    normalized = normalize_ted_record(
        {
            "publication-number": "642395-2026",
            "publication-date": "2026-09-17+02:00",
            "notice-title": {
                "eng": "France - Cultural services - English title",
                "fra": "France - Services culturels - Programmation artistique",
            },
            "buyer-name": {"fra": ["MAIRIE DES LILAS"]},
            "classification-cpv": ["79953000", "79952100", "79953000"],
            "contract-nature": ["services"],
            "place-of-performance": ["FR106", "FRA"],
            "deadline-receipt-tender-date-lot": ["2026-10-15T12:00:00+02:00"],
            "links": {
                "html": {"FRA": "https://ted.europa.eu/fr/notice/-/detail/642395-2026"},
                "pdf": {"FRA": "https://ted.europa.eu/fr/notice/642395-2026/pdf"},
                "xml": {"MUL": "https://ted.europa.eu/en/notice/642395-2026/xml"},
            },
        }
    )

    assert normalized["source"] == "TED"
    assert normalized["source_reference"] == "642395-2026"
    assert normalized["title"].endswith("Programmation artistique")
    assert normalized["buyer"] == "MAIRIE DES LILAS"
    assert normalized["cpv"] == ["79953000", "79952100"]
    assert normalized["source_url"].endswith("/detail/642395-2026")
    assert normalized["deadline"].isoformat() == "2026-10-15T12:00:00+02:00"
    assert normalized["normalized_payload"]["document_links"]["pdf"].endswith("642395-2026/pdf")


def test_ted_long_buyer_is_bounded_but_preserved_in_raw_payload() -> None:
    long_buyer = " / ".join(f"Acheteur public numéro {index}" for index in range(50))
    normalized = normalize_ted_record(
        {
            "publication-number": "1-2026",
            "notice-title": {"fra": "Programmation culturelle"},
            "buyer-name": {"fra": [long_buyer]},
        }
    )

    assert len(normalized["buyer"]) == 512
    assert normalized["buyer"].endswith("...")
    assert normalized["normalized_payload"]["ted"]["buyer-name"]["fra"][0] == long_buyer
