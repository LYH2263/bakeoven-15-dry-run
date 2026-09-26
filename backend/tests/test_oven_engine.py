from app.services.oven_engine import (
    Interval,
    Occupancy,
    RecipeDurations,
    build_occupancies,
    find_conflicts,
    next_free_window,
)


def test_zero_minute_phase_does_not_occupy():
    # 发酵 0 分钟的产品只占烘烤段，零宽区间不应制造假重叠。
    recipe = RecipeDurations(0, 30)
    occs = build_occupancies(1, 9, 600, recipe)
    assert [(o.phase, o.interval) for o in occs] == [("bake", Interval(600, 630))]
    existing = [Occupancy(1, Interval(580, 615), "bake", 1)]
    assert find_conflicts(existing, occs)
    # 仅首尾相接（半开）不算重叠。
    assert find_conflicts([Occupancy(1, Interval(570, 600), "bake", 1)], occs) == []



def test_half_open_no_touch_conflict():
    a = Occupancy(1, Interval(0, 30), "bake", 1)
    b = Occupancy(1, Interval(30, 60), "bake", 2)
    assert find_conflicts([a], [b]) == []


def test_overlap_detected():
    recipe = RecipeDurations(20, 30)
    cand = build_occupancies(1, 9, 10, recipe)
    existing = [Occupancy(1, Interval(25, 40), "bake", 1)]
    assert find_conflicts(existing, cand)


def test_next_free_window_after_busy():
    existing = [
        Occupancy(1, Interval(0, 40), "ferment", 1),
        Occupancy(1, Interval(40, 70), "bake", 1),
    ]
    w = next_free_window(existing, 1, duration=30, search_from=0)
    assert w == Interval(70, 100)


def test_next_free_in_gap():
    existing = [
        Occupancy(1, Interval(0, 20), "bake", 1),
        Occupancy(1, Interval(80, 100), "bake", 2),
    ]
    w = next_free_window(existing, 1, duration=30, search_from=0)
    assert w == Interval(20, 50)
