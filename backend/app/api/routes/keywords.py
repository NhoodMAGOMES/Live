from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, require_admin
from app.models import AuditLog, Keyword, KeywordCategory, KeywordSynonym
from app.schemas import (
    KeywordCategoryCreate,
    KeywordCategoryRead,
    KeywordCategoryUpdate,
    KeywordCreate,
    KeywordRead,
    KeywordUpdate,
)


router = APIRouter(tags=["keywords"], dependencies=[Depends(require_admin)])


def audit(db: DbSession, entity_type: str, entity_id: int, action: str, before=None, after=None) -> None:
    db.add(AuditLog(entity_type=entity_type, entity_id=str(entity_id), action=action, before=before, after=after))


@router.get("/keyword-categories", response_model=list[KeywordCategoryRead])
def list_categories(db: DbSession) -> list[KeywordCategory]:
    return list(db.scalars(select(KeywordCategory).order_by(KeywordCategory.name)).all())


@router.post("/keyword-categories", response_model=KeywordCategoryRead)
def create_category(payload: KeywordCategoryCreate, db: DbSession) -> KeywordCategory:
    category = KeywordCategory(**payload.model_dump())
    db.add(category)
    db.flush()
    audit(db, "keyword_category", category.id, "create", after=payload.model_dump())
    db.commit()
    db.refresh(category)
    return category


@router.patch("/keyword-categories/{category_id}", response_model=KeywordCategoryRead)
def update_category(category_id: int, payload: KeywordCategoryUpdate, db: DbSession) -> KeywordCategory:
    category = db.get(KeywordCategory, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    before = {"name": category.name, "threshold": category.threshold, "is_active": category.is_active}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    audit(db, "keyword_category", category.id, "update", before=before, after=payload.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(category)
    return category


@router.delete("/keyword-categories/{category_id}")
def delete_category(category_id: int, db: DbSession) -> dict:
    category = db.get(KeywordCategory, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    audit(db, "keyword_category", category.id, "delete", before={"name": category.name})
    db.delete(category)
    db.commit()
    return {"ok": True}


@router.get("/keywords", response_model=list[KeywordRead])
def list_keywords(db: DbSession, category_id: int | None = None) -> list[Keyword]:
    query = select(Keyword).options(selectinload(Keyword.synonyms)).order_by(Keyword.term)
    if category_id:
        query = query.where(Keyword.category_id == category_id)
    return list(db.scalars(query).all())


def replace_synonyms(db: DbSession, keyword: Keyword, terms: list[str]) -> None:
    keyword.synonyms.clear()
    db.flush()
    for term in terms:
        if term.strip():
            db.add(KeywordSynonym(keyword_id=keyword.id, term=term.strip()))


@router.post("/keywords", response_model=KeywordRead)
def create_keyword(payload: KeywordCreate, db: DbSession) -> Keyword:
    if not db.get(KeywordCategory, payload.category_id):
        raise HTTPException(status_code=404, detail="Category not found")
    data = payload.model_dump(exclude={"synonyms"})
    keyword = Keyword(**data)
    db.add(keyword)
    db.flush()
    replace_synonyms(db, keyword, payload.synonyms)
    audit(db, "keyword", keyword.id, "create", after=payload.model_dump())
    db.commit()
    db.refresh(keyword)
    return keyword


@router.patch("/keywords/{keyword_id}", response_model=KeywordRead)
def update_keyword(keyword_id: int, payload: KeywordUpdate, db: DbSession) -> Keyword:
    keyword = db.scalar(select(Keyword).options(selectinload(Keyword.synonyms)).where(Keyword.id == keyword_id))
    if not keyword:
        raise HTTPException(status_code=404, detail="Keyword not found")
    before = {"term": keyword.term, "weight": keyword.weight, "is_active": keyword.is_active}
    data = payload.model_dump(exclude_unset=True)
    synonyms = data.pop("synonyms", None)
    for field, value in data.items():
        setattr(keyword, field, value)
    if synonyms is not None:
        replace_synonyms(db, keyword, synonyms)
    audit(db, "keyword", keyword.id, "update", before=before, after=payload.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(keyword)
    return keyword


@router.delete("/keywords/{keyword_id}")
def delete_keyword(keyword_id: int, db: DbSession) -> dict:
    keyword = db.get(Keyword, keyword_id)
    if not keyword:
        raise HTTPException(status_code=404, detail="Keyword not found")
    audit(db, "keyword", keyword.id, "delete", before={"term": keyword.term})
    db.delete(keyword)
    db.commit()
    return {"ok": True}


@router.post("/keywords/import")
async def import_keywords(file: UploadFile, db: DbSession) -> dict:
    content = (await file.read()).decode("utf-8-sig")
    rows = csv.DictReader(io.StringIO(content))
    created = 0
    for row in rows:
        category_name = row.get("category") or row.get("famille")
        term = row.get("term") or row.get("keyword") or row.get("mot_cle")
        if not category_name or not term:
            continue
        category = db.scalar(select(KeywordCategory).where(KeywordCategory.name == category_name))
        if not category:
            category = KeywordCategory(name=category_name)
            db.add(category)
            db.flush()
        exists = db.scalar(select(Keyword).where(Keyword.category_id == category.id, Keyword.term == term))
        if exists:
            continue
        db.add(Keyword(category_id=category.id, term=term, weight=float(row.get("weight") or 3)))
        created += 1
    db.commit()
    return {"created": created}


@router.get("/keywords/export")
def export_keywords(db: DbSession) -> Response:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["category", "term", "weight", "is_active", "synonyms", "exclusions", "tags"])
    rows = db.scalars(
        select(Keyword).options(selectinload(Keyword.category), selectinload(Keyword.synonyms)).order_by(Keyword.term)
    ).all()
    for keyword in rows:
        writer.writerow(
            [
                keyword.category.name,
                keyword.term,
                keyword.weight,
                keyword.is_active,
                "|".join(s.term for s in keyword.synonyms),
                "|".join(keyword.exclusions or []),
                "|".join(keyword.tags or []),
            ]
        )
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=live-pulse-keywords.csv"},
    )
