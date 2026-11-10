"""Parity tests: fastrectpack must give exactly the same answers as the original rectpack."""
import copy
import random

import pytest
import rectpack
from helpers import ALGOS, all_packer_configs, packer_kwargs, random_ops, run_algo, run_packer
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import fastrectpack


def test_native_extension_is_loaded():
    """Guards against silently benchmarking / testing the Python fallback."""
    assert fastrectpack.NATIVE_AVAILABLE, "the C++ extension did not import"
    a = fastrectpack.MaxRectsBssf(100, 100)
    assert a._native is not None
    a.add_rect(10, 10, "x")
    assert a._native is not None, "int inputs must stay on the native path"


# ---------------------------------------------------------------- algorithm level, step by step
@pytest.mark.parametrize("name", ALGOS)
@pytest.mark.parametrize("rot", [True, False])
@pytest.mark.parametrize("seed", range(40))
def test_algorithm_step_by_step(name, rot, seed):
    rng = random.Random(f"{name}/{rot}/{seed}")
    width, height = rng.randint(1, 300), rng.randint(1, 300)
    max_dim = rng.choice([5, 20, 80, 320])  # includes pieces bigger than the bin
    ops = random_ops(rng, rng.randint(0, 120), max_dim)
    assert run_algo(fastrectpack, name, width, height, rot, ops) == run_algo(rectpack, name, width, height, rot, ops)


@pytest.mark.parametrize("name", ALGOS)
def test_many_duplicates_and_exact_fits(name):
    """Few distinct sizes -> lots of identical free rectangles (exercises the value-based duplicate removal)."""
    rng = random.Random(name)
    for trial in range(30):
        sizes = [(rng.randint(1, 12), rng.randint(1, 12)) for _ in range(3)]
        ops = [(*rng.choice(sizes), i) for i in range(80)]
        W, H = rng.choice([12, 24, 36, 48, 50]), rng.choice([12, 24, 36, 48, 50])
        assert run_algo(fastrectpack, name, W, H, True, ops) == run_algo(rectpack, name, W, H, True, ops)


# ---------------------------------------------------------------- packer level
def test_every_packer_configuration_matches():
    rng = random.Random(7)
    mismatches = []
    for cfg in all_packer_configs():
        placed_anything = False
        for trial in range(2):
            rects = random_ops(rng, rng.randint(1, 60), 40)
            bins = [(rng.randint(30, 120), rng.randint(30, 120), rng.randint(1, 6)) for _ in range(rng.randint(1, 3))]
            a = run_packer(fastrectpack, rects, bins, **packer_kwargs(fastrectpack, cfg))
            b = run_packer(rectpack, rects, bins, **packer_kwargs(rectpack, cfg))
            if a != b:
                mismatches.append(cfg)
            # a configuration that only ever errors would compare equal without testing anything
            assert a[0] != "error", (cfg, a)
            placed_anything = placed_anything or a[0] != "[]"
        assert placed_anything, cfg
    assert not mismatches


def test_default_newpacker_on_larger_inputs():
    for seed in range(5):
        rng = random.Random(seed)
        rects = random_ops(rng, 300, 60)
        bins = [(400, 400, 50)]
        assert run_packer(fastrectpack, rects, bins) == run_packer(rectpack, rects, bins)


# ---------------------------------------------------------------- property based
@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    name=st.sampled_from(ALGOS),
    rot=st.booleans(),
    width=st.integers(1, 120),
    height=st.integers(1, 120),
    ops=st.lists(st.tuples(st.integers(1, 130), st.integers(1, 130)), max_size=50),
)
def test_property_algorithm_matches(name, rot, width, height, ops):
    ops = [(w, h, i) for i, (w, h) in enumerate(ops)]
    assert run_algo(fastrectpack, name, width, height, rot, ops) == run_algo(rectpack, name, width, height, rot, ops)


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    cfg=st.sampled_from(all_packer_configs()),
    rects=st.lists(st.tuples(st.integers(1, 50), st.integers(1, 50)), min_size=1, max_size=40),
    bins=st.lists(st.tuples(st.integers(10, 90), st.integers(10, 90), st.integers(1, 4)), min_size=1, max_size=3),
)
def test_property_packer_matches(cfg, rects, bins):
    rects = [(w, h, i) for i, (w, h) in enumerate(rects)]
    a = run_packer(fastrectpack, rects, bins, **packer_kwargs(fastrectpack, cfg))
    b = run_packer(rectpack, rects, bins, **packer_kwargs(rectpack, cfg))
    assert a == b


# ---------------------------------------------------------------- copy / pickle
def test_deepcopy_and_pickle_continue_identically():
    import pickle
    rng = random.Random(3)
    ops = random_ops(rng, 60, 30)
    a = fastrectpack.MaxRectsBssf(200, 200)
    o = rectpack.MaxRectsBssf(200, 200)
    for w, h, rid in ops[:30]:
        a.add_rect(w, h, rid)
        o.add_rect(w, h, rid)
    for clone in (copy.deepcopy(a), pickle.loads(pickle.dumps(a))):
        c = clone
        o2 = copy.deepcopy(o)
        for w, h, rid in ops[30:]:
            ra, ro = c.add_rect(w, h, rid), o2.add_rect(w, h, rid)
            assert (ra and (ra.x, ra.y, ra.width, ra.height, ra.rid)) == (ro and (ro.x, ro.y, ro.width, ro.height, ro.rid))
        assert c.rect_list() == o2.rect_list()
    # the original object is untouched by serialising it
    assert a._native is not None
