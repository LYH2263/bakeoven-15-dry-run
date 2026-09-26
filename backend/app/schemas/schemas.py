from datetime import datetime
from pydantic import BaseModel, Field


class ProductOut(BaseModel):
    id: int
    name: str
    ferment_min: int
    bake_min: int
    model_config = {"from_attributes": True}


class OvenOut(BaseModel):
    id: int
    label: str
    capacity_note: str
    model_config = {"from_attributes": True}


class BatchOut(BaseModel):
    id: int
    product_id: int
    oven_id: int
    code: str
    start_min: int
    status: str
    product_name: str | None = None
    oven_label: str | None = None
    ferment_end: int | None = None
    bake_end: int | None = None
    model_config = {"from_attributes": True}


class BatchCreate(BaseModel):
    product_id: int
    oven_id: int
    start_min: int = Field(ge=0, le=24 * 60 - 1)
    code: str | None = None


class PreviewConflictOut(BaseModel):
    """一次重叠命中：新批次的哪个阶段撞上对手批次的哪个阶段。"""

    opponent_batch_id: int
    opponent_code: str
    phase: str  # 新批次发生重叠的阶段：ferment | bake
    opponent_phase: str
    interval: str  # 新批次该阶段的半开区间，形如 "[09:05,09:40)"


class BatchPreviewOut(BaseModel):
    product_id: int
    oven_id: int
    start_min: int
    ferment_end: int
    bake_end: int
    overlaps: bool
    conflicts: list[PreviewConflictOut]


class GanttBlock(BaseModel):
    batch_id: int
    code: str
    oven_id: int
    oven_label: str
    phase: str
    start_min: int
    end_min: int


class ConflictOut(BaseModel):
    id: int
    batch_code: str
    oven_id: int
    detail: str
    created_at: datetime
    model_config = {"from_attributes": True}


class WindowOut(BaseModel):
    oven_id: int
    oven_label: str
    start_min: int
    end_min: int
    duration_min: int
