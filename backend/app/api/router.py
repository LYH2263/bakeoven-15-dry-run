from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Batch, ConflictLog, Oven, Product
from app.schemas.schemas import (
    BatchCreate,
    BatchOut,
    BatchPreviewOut,
    ConflictOut,
    GanttBlock,
    OvenOut,
    PreviewConflictOut,
    ProductOut,
    WindowOut,
)
from app.services.oven_engine import (
    Occupancy,
    RecipeDurations,
    build_occupancies,
    find_conflicts,
    next_free_window,
)

api_router = APIRouter()

PHASE_LABELS = {"ferment": "发酵", "bake": "烘烤"}


def _recipe(p: Product) -> RecipeDurations:
    return RecipeDurations(p.ferment_min, p.bake_min)


def _hhmm(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def _evaluate(
    db: Session, product: Product, oven: Oven, start_min: int
) -> tuple[list[PreviewConflictOut], list[tuple[Occupancy, Occupancy]]]:
    """试算：不落库。返回（对外冲突明细, 原始命中对）。"""
    recipe = _recipe(product)
    candidates = build_occupancies(oven.id, -1, start_min, recipe)
    hits = find_conflicts(_all_occupancies(db), candidates)
    conflicts: list[PreviewConflictOut] = []
    for ex, cand in hits:
        opp = db.get(Batch, ex.batch_id)
        conflicts.append(
            PreviewConflictOut(
                opponent_batch_id=ex.batch_id,
                opponent_code=opp.code if opp else f"#{ex.batch_id}",
                phase=cand.phase,
                opponent_phase=ex.phase,
                interval=f"[{_hhmm(cand.interval.start)},{_hhmm(cand.interval.end)})",
            )
        )
    return conflicts, hits


def _all_occupancies(db: Session) -> list[Occupancy]:
    batches = db.scalars(select(Batch)).all()
    out: list[Occupancy] = []
    for b in batches:
        p = db.get(Product, b.product_id)
        if not p:
            continue
        out.extend(build_occupancies(b.oven_id, b.id, b.start_min, _recipe(p)))
    return out


def _batch_out(db: Session, b: Batch) -> BatchOut:
    p = db.get(Product, b.product_id)
    o = db.get(Oven, b.oven_id)
    ferment_end = b.start_min + (p.ferment_min if p else 0)
    bake_end = ferment_end + (p.bake_min if p else 0)
    return BatchOut(
        id=b.id,
        product_id=b.product_id,
        oven_id=b.oven_id,
        code=b.code,
        start_min=b.start_min,
        status=b.status,
        product_name=p.name if p else None,
        oven_label=o.label if o else None,
        ferment_end=ferment_end,
        bake_end=bake_end,
    )


@api_router.get("/health")
def health():
    return {"status": "ok"}


@api_router.get("/products", response_model=list[ProductOut])
def products(db: Session = Depends(get_db)):
    return db.scalars(select(Product).order_by(Product.id)).all()


@api_router.get("/ovens", response_model=list[OvenOut])
def ovens(db: Session = Depends(get_db)):
    return db.scalars(select(Oven).order_by(Oven.id)).all()


@api_router.get("/batches", response_model=list[BatchOut])
def batches(db: Session = Depends(get_db)):
    rows = db.scalars(select(Batch).order_by(Batch.start_min)).all()
    return [_batch_out(db, b) for b in rows]


@api_router.post("/batches/preview", response_model=BatchPreviewOut)
def preview_batch(body: BatchCreate, db: Session = Depends(get_db)):
    """试算：只读，不新增批次、不写冲突日志。"""
    product = db.get(Product, body.product_id)
    oven = db.get(Oven, body.oven_id)
    if not product or not oven:
        raise HTTPException(404, "产品或炉位不存在")
    recipe = _recipe(product)
    conflicts, _hits = _evaluate(db, product, oven, body.start_min)
    ferment_end = body.start_min + recipe.ferment_min
    return BatchPreviewOut(
        product_id=product.id,
        oven_id=oven.id,
        start_min=body.start_min,
        ferment_end=ferment_end,
        bake_end=ferment_end + recipe.bake_min,
        overlaps=bool(conflicts),
        conflicts=conflicts,
    )


@api_router.post("/batches", response_model=BatchOut)
def create_batch(body: BatchCreate, db: Session = Depends(get_db)):
    product = db.get(Product, body.product_id)
    oven = db.get(Oven, body.oven_id)
    if not product or not oven:
        raise HTTPException(404, "产品或炉位不存在")
    code = body.code or f"BO-{body.start_min}"
    conflicts, hits = _evaluate(db, product, oven, body.start_min)
    if hits:
        first = conflicts[0]
        detail = (
            f"与批次{first.opponent_code} 的 {PHASE_LABELS[first.opponent_phase]} 段重叠："
            f"{first.interval}"
        )
        db.add(ConflictLog(batch_code=code, oven_id=oven.id, detail=detail))
        db.commit()
        raise HTTPException(409, detail)
    batch = Batch(
        product_id=product.id,
        oven_id=oven.id,
        code=code,
        start_min=body.start_min,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return _batch_out(db, batch)


@api_router.get("/gantt", response_model=list[GanttBlock])
def gantt(db: Session = Depends(get_db)):
    blocks: list[GanttBlock] = []
    for b in db.scalars(select(Batch).order_by(Batch.start_min)).all():
        p = db.get(Product, b.product_id)
        o = db.get(Oven, b.oven_id)
        if not p or not o:
            continue
        for occ in build_occupancies(b.oven_id, b.id, b.start_min, _recipe(p)):
            blocks.append(
                GanttBlock(
                    batch_id=b.id,
                    code=b.code,
                    oven_id=o.id,
                    oven_label=o.label,
                    phase=occ.phase,
                    start_min=occ.interval.start,
                    end_min=occ.interval.end,
                )
            )
    return blocks


@api_router.get("/conflicts", response_model=list[ConflictOut])
def conflicts(db: Session = Depends(get_db)):
    return db.scalars(select(ConflictLog).order_by(ConflictLog.id.desc())).all()


@api_router.get("/windows", response_model=list[WindowOut])
def windows(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "产品不存在")
    duration = product.ferment_min + product.bake_min
    existing = _all_occupancies(db)
    out: list[WindowOut] = []
    for oven in db.scalars(select(Oven).order_by(Oven.id)).all():
        w = next_free_window(existing, oven.id, duration, search_from=8 * 60, search_to=22 * 60)
        if w:
            out.append(
                WindowOut(
                    oven_id=oven.id,
                    oven_label=oven.label,
                    start_min=w.start,
                    end_min=w.end,
                    duration_min=duration,
                )
            )
    return out
