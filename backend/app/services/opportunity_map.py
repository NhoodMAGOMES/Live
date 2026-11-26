from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from app.models import Opportunity


FRANCE_BOUNDS = {
    "min_lon": -5.2,
    "max_lon": 9.8,
    "min_lat": 41.0,
    "max_lat": 51.5,
}

DEPARTMENT_ANCHORS: dict[str, tuple[str, float, float]] = {
    "01": ("Ain", 46.10, 5.35),
    "02": ("Aisne", 49.55, 3.55),
    "03": ("Allier", 46.35, 3.15),
    "04": ("Alpes-de-Haute-Provence", 44.10, 6.25),
    "05": ("Hautes-Alpes", 44.65, 6.35),
    "06": ("Alpes-Maritimes", 43.90, 7.20),
    "07": ("Ardèche", 44.75, 4.40),
    "08": ("Ardennes", 49.65, 4.65),
    "09": ("Ariège", 42.95, 1.50),
    "10": ("Aube", 48.30, 4.15),
    "11": ("Aude", 43.10, 2.40),
    "12": ("Aveyron", 44.30, 2.70),
    "13": ("Bouches-du-Rhône", 43.45, 5.10),
    "14": ("Calvados", 49.10, -0.35),
    "15": ("Cantal", 45.05, 2.70),
    "16": ("Charente", 45.75, 0.20),
    "17": ("Charente-Maritime", 45.75, -0.75),
    "18": ("Cher", 47.05, 2.40),
    "19": ("Corrèze", 45.35, 1.90),
    "2A": ("Corse-du-Sud", 41.90, 8.95),
    "2B": ("Haute-Corse", 42.45, 9.20),
    "21": ("Côte-d'Or", 47.45, 4.75),
    "22": ("Côtes-d'Armor", 48.45, -2.75),
    "23": ("Creuse", 46.05, 2.00),
    "24": ("Dordogne", 45.15, 0.75),
    "25": ("Doubs", 47.15, 6.25),
    "26": ("Drôme", 44.70, 5.20),
    "27": ("Eure", 49.05, 1.05),
    "28": ("Eure-et-Loir", 48.45, 1.35),
    "29": ("Finistère", 48.25, -4.05),
    "30": ("Gard", 43.95, 4.25),
    "31": ("Haute-Garonne", 43.35, 1.20),
    "32": ("Gers", 43.70, 0.45),
    "33": ("Gironde", 44.80, -0.60),
    "34": ("Hérault", 43.55, 3.35),
    "35": ("Ille-et-Vilaine", 48.15, -1.65),
    "36": ("Indre", 46.80, 1.60),
    "37": ("Indre-et-Loire", 47.30, 0.70),
    "38": ("Isère", 45.25, 5.55),
    "39": ("Jura", 46.75, 5.75),
    "40": ("Landes", 43.95, -0.75),
    "41": ("Loir-et-Cher", 47.65, 1.45),
    "42": ("Loire", 45.75, 4.15),
    "43": ("Haute-Loire", 45.10, 3.80),
    "44": ("Loire-Atlantique", 47.35, -1.65),
    "45": ("Loiret", 47.90, 2.30),
    "46": ("Lot", 44.60, 1.60),
    "47": ("Lot-et-Garonne", 44.35, 0.45),
    "48": ("Lozère", 44.55, 3.50),
    "49": ("Maine-et-Loire", 47.35, -0.55),
    "50": ("Manche", 49.05, -1.35),
    "51": ("Marne", 49.00, 4.25),
    "52": ("Haute-Marne", 48.10, 5.25),
    "53": ("Mayenne", 48.15, -0.65),
    "54": ("Meurthe-et-Moselle", 48.75, 6.25),
    "55": ("Meuse", 49.05, 5.40),
    "56": ("Morbihan", 47.85, -2.85),
    "57": ("Moselle", 49.05, 6.65),
    "58": ("Nièvre", 47.10, 3.50),
    "59": ("Nord", 50.45, 3.05),
    "60": ("Oise", 49.40, 2.40),
    "61": ("Orne", 48.65, 0.05),
    "62": ("Pas-de-Calais", 50.45, 2.25),
    "63": ("Puy-de-Dôme", 45.75, 3.10),
    "64": ("Pyrénées-Atlantiques", 43.25, -0.75),
    "65": ("Hautes-Pyrénées", 43.05, 0.10),
    "66": ("Pyrénées-Orientales", 42.60, 2.55),
    "67": ("Bas-Rhin", 48.65, 7.55),
    "68": ("Haut-Rhin", 47.90, 7.25),
    "69": ("Rhône", 45.85, 4.65),
    "70": ("Haute-Saône", 47.65, 6.10),
    "71": ("Saône-et-Loire", 46.65, 4.55),
    "72": ("Sarthe", 48.00, 0.20),
    "73": ("Savoie", 45.50, 6.45),
    "74": ("Haute-Savoie", 46.05, 6.45),
    "75": ("Paris", 48.86, 2.35),
    "76": ("Seine-Maritime", 49.65, 1.05),
    "77": ("Seine-et-Marne", 48.60, 2.95),
    "78": ("Yvelines", 48.80, 1.85),
    "79": ("Deux-Sèvres", 46.55, -0.25),
    "80": ("Somme", 49.95, 2.30),
    "81": ("Tarn", 43.80, 2.15),
    "82": ("Tarn-et-Garonne", 44.05, 1.25),
    "83": ("Var", 43.45, 6.25),
    "84": ("Vaucluse", 44.05, 5.15),
    "85": ("Vendée", 46.70, -1.30),
    "86": ("Vienne", 46.55, 0.45),
    "87": ("Haute-Vienne", 45.85, 1.25),
    "88": ("Vosges", 48.15, 6.50),
    "89": ("Yonne", 47.80, 3.55),
    "90": ("Territoire de Belfort", 47.65, 6.90),
    "91": ("Essonne", 48.50, 2.25),
    "92": ("Hauts-de-Seine", 48.85, 2.20),
    "93": ("Seine-Saint-Denis", 48.90, 2.45),
    "94": ("Val-de-Marne", 48.78, 2.45),
    "95": ("Val-d'Oise", 49.05, 2.15),
}

OVERSEAS_ANCHORS: dict[str, str] = {
    "971": "Guadeloupe",
    "972": "Martinique",
    "973": "Guyane",
    "974": "La Réunion",
    "976": "Mayotte",
    "978": "Collectivité d'outre-mer",
}

LOCATION_ALIASES = {
    "paris": "75",
    "bordeaux": "33",
    "landes": "40",
    "biarritz": "64",
    "nord": "59",
    "marseille": "13",
    "cannes": "06",
    "nice": "06",
    "lyon": "69",
    "lille": "59",
    "nantes": "44",
    "toulouse": "31",
    "strasbourg": "67",
    "rennes": "35",
    "grenoble": "38",
    "montpellier": "34",
}

DEPARTMENT_PATTERN = re.compile(r"(?<!\d)(2A|2B|97[1-8]|0?[1-9]|[1-8]\d|9[0-5])(?!\d)", re.IGNORECASE)


def _normalize_department_code(value: str) -> str | None:
    code = value.upper()
    if code in {"2A", "2B"}:
        return code
    if code.isdigit():
        if len(code) == 1:
            return f"0{code}"
        return code
    return None


def department_codes_from_location(location: str | None) -> list[str]:
    if not location:
        return []
    codes: list[str] = []
    seen: set[str] = set()
    for match in DEPARTMENT_PATTERN.findall(location):
        code = _normalize_department_code(match)
        if code and code not in seen:
            codes.append(code)
            seen.add(code)
    lower = location.lower()
    for alias, code in LOCATION_ALIASES.items():
        if alias in lower and code not in seen:
            codes.append(code)
            seen.add(code)
    return codes


def _project(latitude: float, longitude: float) -> tuple[float, float]:
    x = ((longitude - FRANCE_BOUNDS["min_lon"]) / (FRANCE_BOUNDS["max_lon"] - FRANCE_BOUNDS["min_lon"])) * 100
    y = ((FRANCE_BOUNDS["max_lat"] - latitude) / (FRANCE_BOUNDS["max_lat"] - FRANCE_BOUNDS["min_lat"])) * 100
    return round(max(0, min(100, x)), 2), round(max(0, min(100, y)), 2)


def _opportunity_payload(opportunity: Opportunity) -> dict[str, Any]:
    return {
        "id": opportunity.id,
        "title": opportunity.title,
        "buyer": opportunity.buyer,
        "status": opportunity.status.value if hasattr(opportunity.status, "value") else str(opportunity.status),
        "global_score": opportunity.global_score,
        "deadline": opportunity.deadline,
    }


def _deadline_bucket(deadline: datetime | None) -> str:
    if deadline is None:
        return "missing"
    deadline_value = deadline if deadline.tzinfo else deadline.replace(tzinfo=timezone.utc)
    days = (deadline_value.date() - datetime.now(timezone.utc).date()).days
    if days < 0:
        return "overdue"
    if days <= 7:
        return "soon"
    return "future"


def _search_text(code: str | None, name: str, items: list[Opportunity]) -> str:
    parts: list[str] = [code or "", name]
    for item in items:
        parts.extend([item.title or "", item.buyer or "", item.location or "", item.source_reference or ""])
    return " ".join(part for part in parts if part).lower()


def _sort_key(opportunity: Opportunity) -> tuple[float, float]:
    created_at = opportunity.created_at.timestamp() if opportunity.created_at else 0
    return opportunity.global_score or 0, created_at


def build_map_points(opportunities: list[Opportunity]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Opportunity]] = defaultdict(list)
    unresolved: list[Opportunity] = []
    for opportunity in opportunities:
        codes = department_codes_from_location(opportunity.location)
        if not codes:
            unresolved.append(opportunity)
            continue
        for code in codes:
            grouped[code].append(opportunity)

    points: list[dict[str, Any]] = []
    for code, items in grouped.items():
        anchor = DEPARTMENT_ANCHORS.get(code)
        overseas_name = OVERSEAS_ANCHORS.get(code)
        statuses = Counter(item.status.value if hasattr(item.status, "value") else str(item.status) for item in items)
        deadline_counts = Counter(_deadline_bucket(item.deadline) for item in items)
        sorted_items = sorted(items, key=_sort_key, reverse=True)
        if anchor:
            name, latitude, longitude = anchor
            x, y = _project(latitude, longitude)
            is_overseas = False
        else:
            name = overseas_name or f"Code {code}"
            latitude = None
            longitude = None
            x = None
            y = None
            is_overseas = True
        points.append(
            {
                "key": code,
                "department_code": code,
                "department_name": name,
                "label": f"{code} - {name}",
                "latitude": latitude,
                "longitude": longitude,
                "x": x,
                "y": y,
                "is_overseas": is_overseas,
                "count": len(items),
                "highest_score": max((item.global_score or 0) for item in items),
                "status_counts": dict(statuses),
                "deadline_counts": dict(deadline_counts),
                "search_text": _search_text(code, name, items),
                "opportunities": [_opportunity_payload(item) for item in sorted_items[:6]],
            }
        )

    if unresolved:
        sorted_unresolved = sorted(unresolved, key=_sort_key, reverse=True)
        unresolved_deadline_counts = Counter(_deadline_bucket(item.deadline) for item in unresolved)
        points.append(
            {
                "key": "unresolved",
                "department_code": None,
                "department_name": "Localisation non cartographiée",
                "label": "Non cartographié",
                "latitude": None,
                "longitude": None,
                "x": None,
                "y": None,
                "is_overseas": False,
                "count": len(unresolved),
                "highest_score": max((item.global_score or 0) for item in unresolved),
                "status_counts": dict(Counter(item.status.value if hasattr(item.status, "value") else str(item.status) for item in unresolved)),
                "deadline_counts": dict(unresolved_deadline_counts),
                "search_text": _search_text(None, "Localisation non cartographiée", unresolved),
                "opportunities": [_opportunity_payload(item) for item in sorted_unresolved[:6]],
            }
        )

    return sorted(points, key=lambda point: (point["is_overseas"], point["x"] is None, -point["count"], point["label"]))
