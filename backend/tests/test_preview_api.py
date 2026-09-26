"""试算不落库；真正创建才落批次或写拒绝记录。"""


def _count(client, path):
    return len(client.get(path).json())


def test_preview_detects_bo0900_bake_overlap_without_persistence(client):
    # 布朗尼发酵 0 / 烘烤 30；一层 1 号炉 600 开工 -> 烘烤 [600,630)
    # BO-0900 在同炉：发酵 [540,580)、烘烤 [580,615)，仅烘烤段重叠。
    r = client.post(
        "/api/batches/preview",
        json={"product_id": 3, "oven_id": 1, "start_min": 600},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["overlaps"] is True
    assert data["ferment_end"] == 600
    assert data["bake_end"] == 630
    assert len(data["conflicts"]) == 1
    hit = data["conflicts"][0]
    assert hit["opponent_code"] == "BO-0900"
    assert hit["phase"] == "bake"
    assert hit["opponent_phase"] == "bake"
    assert hit["interval"] == "[10:00,10:30)"

    # 试算结束：批次仍是种子三批，冲突日志不新增（种子里有 1 条历史记录）。
    assert _count(client, "/api/batches") == 3
    assert _count(client, "/api/conflicts") == 1


def test_preview_clean_slot_reports_no_overlap(client):
    # 二层石板炉整天空闲
    r = client.post(
        "/api/batches/preview",
        json={"product_id": 1, "oven_id": 3, "start_min": 600},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["overlaps"] is False
    assert data["conflicts"] == []
    assert data["ferment_end"] == 640
    assert data["bake_end"] == 675
    assert _count(client, "/api/batches") == 3
    assert _count(client, "/api/conflicts") == 1


def test_real_create_conflict_is_rejected_and_logged_once(client):
    r = client.post(
        "/api/batches",
        json={"product_id": 3, "oven_id": 1, "start_min": 600},
    )
    assert r.status_code == 409
    assert "BO-0900" in r.json()["detail"]

    # 拒绝排入：批次仍三批，冲突日志新增且只新增一条拒绝记录。
    assert _count(client, "/api/batches") == 3
    logs = client.get("/api/conflicts").json()
    assert len(logs) == 2
    assert logs[0]["batch_code"] == "BO-600"
    assert "BO-0900" in logs[0]["detail"]


def test_real_create_success_shows_two_gantt_blocks_and_no_rejection(client):
    conflicts_before = _count(client, "/api/conflicts")
    r = client.post(
        "/api/batches",
        json={"product_id": 1, "oven_id": 3, "start_min": 600, "code": "BO-TEST"},
    )
    assert r.status_code == 200
    new_id = r.json()["id"]

    batches = client.get("/api/batches").json()
    assert len(batches) == 4

    # 成功不记拒绝：冲突日志条数不变。
    assert _count(client, "/api/conflicts") == conflicts_before

    # 甘特出现两段：发酵 + 烘烤。
    blocks = [b for b in client.get("/api/gantt").json() if b["batch_id"] == new_id]
    assert [b["phase"] for b in blocks] == ["ferment", "bake"]
    assert [(b["start_min"], b["end_min"]) for b in blocks] == [
        (600, 640),
        (640, 675),
    ]
