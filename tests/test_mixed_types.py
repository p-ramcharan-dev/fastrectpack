"""Sizes that are not plain ints: Python floats, numpy.float64 and numpy.int64, in any mix.

These run in C++ since 0.2.0. Every result must have the same value AND the same type as the original gives,
so the snapshots in helpers.snap record types.
"""
import copy
import math
import pickle
import random

import pytest
import rectpack
from helpers import ALGOS, all_packer_configs, packer_kwargs, run_algo, run_packer, snap
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import fastrectpack
from fastrectpack import _native

np = pytest.importorskip("numpy")

pytestmark = pytest.mark.skipif(not _native.MIXED_PATH, reason="this build has no native float path")

KINDS = {"int": int, "float": float, "np.float64": np.float64, "np.int64": np.int64}
POOLS = [
    ("int",), ("float",), ("np.float64",), ("np.int64",), ("int", "np.float64"), ("int", "float"),
    ("float", "np.float64"), ("np.int64", "np.float64"), ("int", "np.int64"), ("int", "float", "np.float64", "np.int64"),
]


def value(rng, kind, style, hi):
    """One size of the given type. `style` picks how awkward the float values are."""
    if kind in ("int", "np.int64"):
        return KINDS[kind](rng.randint(1, max(1, int(hi))))
    if style == 0:
        v = rng.uniform(0.5, hi)                          # arbitrary floats
    elif style == 1:
        v = rng.randint(1, max(1, int(hi * 10))) / 10     # tenths: not exact in binary
    elif style == 2:
        v = rng.randint(1, max(1, int(hi * 4))) / 4       # quarters: exact, so many exact ties
    else:
        v = float(rng.randint(1, max(1, int(hi))))        # whole-number floats
    return KINDS[kind](v)


def random_case(rng):
    style = rng.randrange(4)
    scale = rng.choice([8, 40, 300, 5000])
    pool, bin_pool = rng.choice(POOLS), rng.choice(POOLS)
    width, height = value(rng, rng.choice(bin_pool), style, scale), value(rng, rng.choice(bin_pool), style, scale)
    max_dim = scale / rng.choice([1.5, 4, 12])  # 1.5: some pieces are bigger than the bin
    if rng.random() < 0.3:  # few distinct sizes -> identical free rectangles and exact fits
        sizes = [(value(rng, rng.choice(pool), style, max_dim), value(rng, rng.choice(pool), style, max_dim)) for _ in range(3)]
        ops = [(*rng.choice(sizes), i) for i in range(rng.randint(0, 60))]
    else:
        ops = [(value(rng, rng.choice(pool), style, max_dim), value(rng, rng.choice(pool), style, max_dim), i)
               for i in range(rng.randint(0, 60))]
    return width, height, ops


def free_list(algo):
    return snap([(m.x, m.y, m.width, m.height) for m in algo._max_rects])


@pytest.mark.parametrize("name", ALGOS)
@pytest.mark.parametrize("rot", [True, False])
@pytest.mark.parametrize("seed", range(60))
def test_mixed_types_step_by_step(name, rot, seed):
    rng = random.Random(f"mixed/{name}/{rot}/{seed}")
    width, height, ops = random_case(rng)
    assert run_algo(fastrectpack, name, width, height, rot, ops) == run_algo(rectpack, name, width, height, rot, ops)


@pytest.mark.parametrize("name", ALGOS)
@pytest.mark.parametrize("kind", list(KINDS))
def test_each_type_stays_on_the_native_path(name, kind):
    """Guards against these tests silently comparing the fallback with the original."""
    make = KINDS[kind]
    a = getattr(fastrectpack, name)(make(100), make(80))
    assert a._native is not None and a._native.mode == ("int" if kind == "int" else "mixed")
    for i in range(20):
        a.fitness(make(3 + i % 5), make(4))
        a.add_rect(make(3 + i % 5), make(4), i)
    assert a._native is not None
    assert len(a) == 20


def test_int_run_moves_to_the_mixed_path_without_falling_back():
    a, o = fastrectpack.MaxRectsBssf(100, 100), rectpack.MaxRectsBssf(100, 100)
    for alg in (a, o):
        alg.add_rect(10, 10, 0)
    assert a._native.mode == "int"
    for w, h in [(7.5, 3.25), (np.float64(4.5), 6), (np.int64(5), 5), (9, 9)]:
        ra, ro = a.add_rect(w, h, "r"), o.add_rect(w, h, "r")
        assert snap((ra.x, ra.y, ra.width, ra.height)) == snap((ro.x, ro.y, ro.width, ro.height))
    assert a._native is not None and a._native.mode == "mixed"
    assert free_list(a) == free_list(o)


def gdsfactory_style(mod, n, seed):
    """The way gdsfactory.pack calls rectpack: int rectangle sizes, a numpy.float64 bin, MaxRectsBlsf."""
    rng = random.Random(seed)
    rects = [(rng.randint(10, 200), rng.randint(10, 200), i) for i in range(n)]
    total_area = sum(w * h for w, h, _ in rects)
    aspect = np.asarray((1.0, 1.0)) / np.linalg.norm((1.0, 1.0))
    box = np.asarray(aspect * np.sqrt(total_area), dtype=np.float64)
    box = np.clip(box, None, (np.inf, np.inf))
    results = []
    while True:
        packer = mod.newPacker(mode=mod.PackingMode.Offline, pack_algo=mod.MaxRectsBlsf, sort_algo=mod.SORT_AREA,
                               bin_algo=mod.PackingBin.BBF, rotation=False)
        for w, h, rid in rects:
            packer.add_rect(width=w, height=h, rid=rid)
        packer.add_bin(width=box[0], height=box[1])
        packer.pack()
        results.append(snap(packer.rect_list()))
        box *= 1.1
        if len(packer.rect_list()) == len(rects):
            return results, packer


@pytest.mark.parametrize("seed", range(5))
def test_gdsfactory_style_packing_matches_and_is_native(seed):
    fast, packer = gdsfactory_style(fastrectpack, 120, seed)
    orig, _ = gdsfactory_style(rectpack, 120, seed)
    assert fast == orig
    assert len(fast) > 1  # the first box is too small, so the retry loop is exercised too
    assert packer[0]._native is not None and packer[0]._native.mode == "mixed"


def test_every_packer_configuration_matches_with_mixed_types():
    rng = random.Random(21)
    for cfg in all_packer_configs():
        pool = rng.choice(POOLS)
        style = rng.randrange(4)
        rects = [(value(rng, rng.choice(pool), style, 40), value(rng, rng.choice(pool), style, 40), i)
                 for i in range(rng.randint(1, 50))]
        bins = [(value(rng, rng.choice(pool), style, 120) + 30, value(rng, rng.choice(pool), style, 120) + 30, rng.randint(1, 5))
                for _ in range(rng.randint(1, 3))]
        a = run_packer(fastrectpack, rects, bins, **packer_kwargs(fastrectpack, cfg))
        b = run_packer(rectpack, rects, bins, **packer_kwargs(rectpack, cfg))
        assert a == b, cfg
        assert a[0] != "error", (cfg, a)


@pytest.mark.parametrize("name", ALGOS)
@pytest.mark.parametrize("label,w,h", [
    ("np nan", np.float64("nan"), np.float64(4)), ("np inf", np.float64("inf"), np.float64(3)),
    ("np zero", np.float64(0), np.float64(5)), ("np negative", np.float64(-2.5), np.float64(5)),
    ("negative zero", -0.0, 5.0), ("np.float32", np.float32(2.5), np.float32(3.5)),
    ("np.int32", np.int32(4), np.int32(6)), ("np.bool_", np.bool_(True), np.bool_(True)),
    ("np int zero", np.int64(0), np.int64(3)), ("np int negative", np.int64(-4), np.int64(3)),
    ("np int huge", np.int64(2**40), np.int64(3)), ("float huge", 1e300, 2.0), ("np.float16", np.float16(1.5), np.float16(2)),
])
def test_unsupported_numpy_and_float_values_fall_back_identically(name, label, w, h):
    for bin_w, bin_h in [(100, 100), (100.5, np.float64(80))]:
        ops = [(10, 10.5, 0), (w, h, 1), (7, np.float64(7.25), 2), (3, 15, 3)]
        assert run_algo(fastrectpack, name, bin_w, bin_h, True, ops) == run_algo(rectpack, name, bin_w, bin_h, True, ops)
        ops = [(w, h, 0), (10, 10, 1)]
        assert run_algo(fastrectpack, name, bin_w, bin_h, True, ops) == run_algo(rectpack, name, bin_w, bin_h, True, ops)
    # ... and as a bin size
    ops = [(10, 10.5, 0), (3, 4, 1)]
    assert run_algo(fastrectpack, name, w, h, True, ops) == run_algo(rectpack, name, w, h, True, ops)


@pytest.mark.parametrize("name", ALGOS)
def test_size_limits_of_the_mixed_path(name):
    """Sizes around 2^26 (the Baf limit on the mixed path) and 2^30 (the limit everywhere)."""
    for big in (2**26, 2**26 + 1, 2**30, 2**30 + 1):
        for bin_size in (big, float(big), np.float64(big) + 0.5):
            ops = [(big // 3, 1000.5, 0), (big // 3 + 1, np.float64(12345.25), 1), (7, 7, 2), (float(big), 1.0, 3)]
            for rot in (True, False):
                assert run_algo(fastrectpack, name, bin_size, bin_size, rot, ops) == run_algo(rectpack, name, bin_size, bin_size, rot, ops)
    a = getattr(fastrectpack, name)(2.0**27, 2.0**27)
    assert (a._native is None) == (name == "MaxRectsBaf")  # Baf multiplies two sizes, so its limit is lower


@pytest.mark.parametrize("name", ALGOS)
def test_tiny_and_awkward_floats(name):
    tiny = math.ulp(1.0)
    ops = [(0.1, 0.2, 0), (0.1 + 0.2, 0.3, 1), (1e-9, 1e-9, 2), (1 / 3, 2 / 3, 3), (1 + tiny, 1 - tiny / 2, 4),
           (5e-324, 5e-324, 5), (0.7, 0.1, 6), (0.30000000000000004, 0.1, 7)] * 3
    for size in (1.0, 0.9999999999999999, np.float64(1.1), 3):
        for rot in (True, False):
            assert run_algo(fastrectpack, name, size, size, rot, ops) == run_algo(rectpack, name, size, size, rot, ops)


def test_deepcopy_and_pickle_on_the_mixed_path():
    rng = random.Random(8)
    kinds = list(KINDS)
    ops = [(value(rng, rng.choice(kinds), 1, 30), value(rng, rng.choice(kinds), 1, 30), i) for i in range(60)]
    a, o = fastrectpack.MaxRectsBlsf(np.float64(200.5), 180), rectpack.MaxRectsBlsf(np.float64(200.5), 180)
    for w, h, rid in ops[:30]:
        a.add_rect(w, h, rid)
        o.add_rect(w, h, rid)
    for clone in (copy.deepcopy(a), pickle.loads(pickle.dumps(a))):
        o2 = copy.deepcopy(o)
        for w, h, rid in ops[30:]:
            clone.add_rect(w, h, rid)
            o2.add_rect(w, h, rid)
        assert snap(clone.rect_list()) == snap(o2.rect_list())
        assert free_list(clone) == free_list(o2)
    assert a._native is not None and a._native.mode == "mixed"


number = st.one_of(
    st.integers(1, 60),
    st.floats(0.25, 60, allow_nan=False, allow_infinity=False),
    st.integers(1, 240).map(lambda n: n / 4),
    st.floats(0.25, 60, allow_nan=False).map(np.float64),
    st.integers(1, 60).map(np.int64),
)


@settings(max_examples=400, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(name=st.sampled_from(ALGOS), rot=st.booleans(), width=number, height=number,
       ops=st.lists(st.tuples(number, number), max_size=40))
def test_property_mixed_types_match(name, rot, width, height, ops):
    ops = [(w, h, i) for i, (w, h) in enumerate(ops)]
    assert run_algo(fastrectpack, name, width, height, rot, ops) == run_algo(rectpack, name, width, height, rot, ops)
