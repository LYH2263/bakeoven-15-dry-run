from app.services.oven_engine import (
    Interval,
    Occupancy,
    RecipeDurations,
    build_occupancies,
    find_conflicts,
    next_free_window,
)


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


def test_empty_interval_never_conflicts():
    empty = Occupancy(1, Interval(600, 600), "ferment", 2)
    bake = Occupancy(1, Interval(580, 615), "bake", 1)
    assert find_conflicts([bake], [empty]) == []
    assert find_conflicts([empty], [bake]) == []


def test_zero_ferment_recipe_only_bake_conflicts():
    # 发酵 0 分钟的配方：空发酵段不算重叠，只有烘烤段与 BO-0900 烘烤重叠
    recipe = RecipeDurations(0, 30)
    cand = build_occupancies(1, 9, 600, recipe)
    existing = [Occupancy(1, Interval(580, 615), "bake", 1)]
    hits = find_conflicts(existing, cand)
    assert len(hits) == 1
    ex, c = hits[0]
    assert ex.phase == "bake" and c.phase == "bake"
