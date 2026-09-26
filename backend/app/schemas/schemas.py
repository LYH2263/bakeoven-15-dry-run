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


class TrialCreate(BaseModel):
    product_id: int
    oven_id: int
    start_min: int = Field(ge=0, le=24 * 60 - 1)


class TrialConflictOut(BaseModel):
    batch_id: int
    code: str
    phase: str  # 已有批次被重叠的阶段: ferment | bake
    existing_start: int
    existing_end: int
    candidate_phase: str  # 试算批次造成重叠的阶段
    candidate_start: int
    candidate_end: int


class TrialOut(BaseModel):
    product_id: int
    oven_id: int
    start_min: int
    would_overlap: bool
    phases: list[str]  # 重叠的阶段（去重）
    opponents: list[str]  # 对手批次 code（去重，保持出现顺序）
    ferment_end: int  # 若排入后的发酵止
    bake_end: int  # 若排入后的烘烤止
    conflicts: list[TrialConflictOut]


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
