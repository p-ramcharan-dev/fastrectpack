"""Edge cases: unusual input must behave exactly like the original (results AND errors)."""
import decimal
import math
import random

import pytest
import rectpack
from helpers import ALGOS, run_algo, run_packer, snap

import fastrectpack

D = decimal.Decimal

WEIRD_SIZES = [
    ("float", 7.5, 3.25), ("float whole", 8.0, 4.0), ("bool", True, True), ("zero", 0, 5), ("negative", -3, 4),
    ("huge int", 10**30, 5), ("decimal", D("5.5"), D("2.25")), ("nan", float("nan"), 4.0), ("inf", math.inf, 3.0),
    ("string", "5", 5), ("none", None, 5), ("tiny float", 1e-9, 1e-9),
]


@pytest.mark.parametrize("name", ALGOS)
@pytest.mark.parametrize("label,w,h", WEIRD_SIZES)
def test_weird_piece_after_int_pieces(name, label, w, h):
    """A non-int piece arrives in the middle of an int-only run: state must hand over cleanly."""
    ops = [(10, 10, 0), (20, 5, 1), (w, h, 2), (7, 7, 3), (3, 15, 4)]
    assert run_algo(fastrectpack, name, 100, 100, True, ops) == run_algo(rectpack, name, 100, 100, True, ops)


@pytest.mark.parametrize("name", ALGOS)
@pytest.mark.parametrize("label,w,h", WEIRD_SIZES)
def test_weird_piece_first(name, label, w, h):
    ops = [(w, h, 0), (10, 10, 1), (5, 5, 2)]
    assert run_algo(fastrectpack, name, 100, 100, True, ops) == run_algo(rectpack, name, 100, 100, True, ops)


@pytest.mark.parametrize("name", ALGOS)
@pytest.mark.parametrize("bw,bh", [(100.0, 100.0), (D("100"), D("100")), (0, 10), (-5, 10), (True, 50), (10**30, 10**30), (50, 100.5)])
def test_weird_bins(name, bw, bh):
    ops = [(10, 10, 0), (12.5, 3, 1), (4, 4, 2), (2, 2, 3)]
    assert run_algo(fastrectpack, name, bw, bh, True, ops) == run_algo(rectpack, name, bw, bh, True, ops)


@pytest.mark.parametrize("name", ALGOS)
def test_float_workload(name):
    rng = random.Random(11)
    ops = [(round(rng.uniform(1, 30), 2), round(rng.uniform(1, 30), 2), i) for i in range(60)]
    assert run_algo(fastrectpack, name, 120.0, 90.0, True, ops) == run_algo(rectpack, name, 120.0, 90.0, True, ops)


@pytest.mark.parametrize("name", ALGOS)
def test_decimal_workload_via_float2dec(name):
    rng = random.Random(5)
    ops = [(rectpack.float2dec(rng.uniform(1, 30), 2), rectpack.float2dec(rng.uniform(1, 30), 2), i) for i in range(40)]
    W, H = rectpack.float2dec(120, 2), rectpack.float2dec(90, 2)
    assert run_algo(fastrectpack, name, W, H, True, ops) == run_algo(rectpack, name, W, H, True, ops)


@pytest.mark.parametrize("name", ALGOS)
def test_degenerate_shapes(name):
    cases = [
        (1, 1, [(1, 1, 0), (1, 1, 1)]),                      # exactly one fits
        (10, 1, [(1, 10, 0), (10, 1, 1), (5, 1, 2)]),        # needs rotation
        (5, 5, [(5, 5, 0), (5, 5, 1)]),                      # full bin
        (5, 5, [(6, 6, 0), (1, 1, 1)]),                      # too big first
        (100, 100, [(100, 100, 0)]),                         # whole bin
        (100, 100, []),                                      # nothing to do
        (2**30, 2**30, [(2**30, 2**30, 0), (1, 1, 1)]),      # at the native range limit
        (2**30 + 1, 5, [(1, 1, 0), (3, 3, 1)]),              # just beyond it -> fallback
    ]
    for W, H, ops in cases:
        for rot in (True, False):
            assert run_algo(fastrectpack, name, W, H, rot, ops) == run_algo(rectpack, name, W, H, rot, ops)


def test_rid_types_are_preserved():
    rids = [None, 0, "a", ("t", 1), 3.5, object]
    a, o = fastrectpack.MaxRectsBssf(100, 100), rectpack.MaxRectsBssf(100, 100)
    for rid in rids:
        ra, ro = a.add_rect(10, 10, rid), o.add_rect(10, 10, rid)
        assert ra.rid is ro.rid or ra.rid == ro.rid


def test_returned_objects_are_real_rectangles():
    a = fastrectpack.MaxRectsBssf(100, 100)
    r = a.add_rect(10, 20, "id")
    assert isinstance(r, rectpack.geometry.Rectangle)
    assert r is a.rectangles[-1]
    assert isinstance(a, rectpack.MaxRectsBssf)  # isinstance checks keep working


def test_no_valid_placement_leaves_state_unchanged():
    a, o = fastrectpack.MaxRectsBssf(10, 10), rectpack.MaxRectsBssf(10, 10)
    assert a.add_rect(11, 11, 0) is None and o.add_rect(11, 11, 0) is None
    assert a.fitness(11, 11) is None and o.fitness(11, 11) is None
    assert snap(a.rect_list()) == snap(o.rect_list())


def test_mixed_algorithm_packers_with_original_classes():
    """Passing the ORIGINAL class to the fast newPacker still works (just not accelerated)."""
    rng = random.Random(2)
    rects = [(rng.randint(1, 30), rng.randint(1, 30), i) for i in range(40)]
    bins = [(100, 100, 5)]
    a = run_packer(fastrectpack, rects, bins, pack_algo=rectpack.MaxRectsBssf)
    b = run_packer(rectpack, rects, bins)
    assert a == b


def test_other_algorithms_are_reexported_unchanged():
    for name in ("SkylineBl", "GuillotineBssfSas", "PackerBBF", "SORT_AREA", "float2dec", "PackingBin", "PackingMode"):
        assert getattr(fastrectpack, name) is getattr(rectpack, name)
    rng = random.Random(9)
    rects = [(rng.randint(1, 30), rng.randint(1, 30), i) for i in range(50)]
    for algo in ("SkylineBl", "GuillotineBssfSas"):
        a = run_packer(fastrectpack, rects, [(100, 100, 5)], pack_algo=getattr(fastrectpack, algo))
        b = run_packer(rectpack, rects, [(100, 100, 5)], pack_algo=getattr(rectpack, algo))
        assert a == b
