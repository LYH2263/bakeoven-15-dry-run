"""API tests for the trial (dry-run) endpoint and create side effects.

Runs against an in-memory SQLite DB via dependency override; the app's own
engine is never touched (lifespan does not run under a bare TestClient).
"""

import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SEED_ON_EMPTY"] = "false"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.services.seed import seed_if_empty


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSession()
    try:
        seed_if_empty(db)
    finally:
        db.close()

    def override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def _ids(client):
    products = {p["name"]: p["id"] for p in client.get("/api/products").json()}
    ovens = {o["label"]: o["id"] for o in client.get("/api/ovens").json()}
    return products, ovens


def _trial(client, product_id, oven_id, start_min):
    return client.post(
        "/api/batches/trial",
        json={"product_id": product_id, "oven_id": oven_id, "start_min": start_min},
    )


def test_seed_has_three_batches_and_one_conflict_log(client):
    assert len(client.get("/api/batches").json()) == 3
    assert len(client.get("/api/conflicts").json()) == 1


def test_trial_overlapping_bo0900_bake_keeps_state(client):
    """用与 BO-0900 烘烤段重叠的开工试算一层 1 号炉：报重叠，但不落库。"""
    products, ovens = _ids(client)
    # BO-0900 烘烤段为 [580, 615)；布朗尼发酵 0 分钟，600 开工的烘烤段 [600, 630) 与之重叠
    res = _trial(client, products["布朗尼"], ovens["一层 1 号炉"], 600)
    assert res.status_code == 200
    body = res.json()
    assert body["would_overlap"] is True
    assert body["phases"] == ["bake"]
    assert body["opponents"] == ["BO-0900"]
    assert body["ferment_end"] == 600
    assert body["bake_end"] == 630
    assert len(body["conflicts"]) == 1
    hit = body["conflicts"][0]
    assert hit["code"] == "BO-0900"
    assert hit["phase"] == "bake"
    assert hit["candidate_phase"] == "bake"
    assert (hit["existing_start"], hit["existing_end"]) == (580, 615)
    assert (hit["candidate_start"], hit["candidate_end"]) == (600, 630)
    # 试算无副作用：批次表条数不变，冲突日志不新增
    assert len(client.get("/api/batches").json()) == 3
    assert len(client.get("/api/conflicts").json()) == 1


def test_trial_free_slot_reports_no_overlap_and_keeps_state(client):
    products, ovens = _ids(client)
    res = _trial(client, products["乡村欧包"], ovens["一层 1 号炉"], 720)
    assert res.status_code == 200
    body = res.json()
    assert body["would_overlap"] is False
    assert body["phases"] == []
    assert body["opponents"] == []
    assert body["conflicts"] == []
    assert body["ferment_end"] == 760
    assert body["bake_end"] == 795
    assert len(client.get("/api/batches").json()) == 3
    assert len(client.get("/api/conflicts").json()) == 1


def test_trial_unknown_product_or_oven_404(client):
    _, ovens = _ids(client)
    assert _trial(client, 999, ovens["一层 1 号炉"], 600).status_code == 404
    assert _trial(client, 1, 999, 600).status_code == 404


def test_create_conflict_still_rejects_and_logs(client):
    """真正创建失败：仍 409 拒绝排入，并写入一条拒绝记录。"""
    products, ovens = _ids(client)
    res = client.post(
        "/api/batches",
        json={"product_id": products["布朗尼"], "oven_id": ovens["一层 1 号炉"], "start_min": 600},
    )
    assert res.status_code == 409
    assert len(client.get("/api/batches").json()) == 3
    logs = client.get("/api/conflicts").json()
    assert len(logs) == 2
    assert logs[0]["batch_code"] == "BO-600"  # 按 id 倒序，最新一条在前
    assert logs[0]["oven_id"] == ovens["一层 1 号炉"]


def test_create_success_adds_two_gantt_segments_without_rejection(client):
    """真正创建成功：甘特出现发酵+烘烤两段，且不新增拒绝记录。"""
    products, ovens = _ids(client)
    res = client.post(
        "/api/batches",
        json={"product_id": products["乡村欧包"], "oven_id": ovens["一层 1 号炉"], "start_min": 720},
    )
    assert res.status_code == 200
    code = res.json()["code"]
    assert len(client.get("/api/batches").json()) == 4
    blocks = [b for b in client.get("/api/gantt").json() if b["code"] == code]
    assert len(blocks) == 2
    assert {b["phase"] for b in blocks} == {"ferment", "bake"}
    assert len(client.get("/api/conflicts").json()) == 1
