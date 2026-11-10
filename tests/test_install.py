"""fastrectpack.install(): rectpack itself hands out the accelerated classes, for code that cannot be edited."""
import random
import subprocess
import sys
import textwrap

import pytest
import rectpack
from helpers import ALGOS, all_packer_configs, packer_kwargs, random_ops, run_packer, snap
from rectpack import newPacker as early_newPacker  # a by-name import made before install(), as a library would

import fastrectpack

ORIGINAL = {name: getattr(rectpack, name) for name in ALGOS}
ORIGINAL_DEFAULTS = rectpack.newPacker.__defaults__


@pytest.fixture
def installed():
    fastrectpack.install()
    try:
        yield
    finally:
        fastrectpack.uninstall()


def third_party_pack(rects, bin_size):
    """Stands in for a library that only knows about rectpack (this is how gdsfactory calls it)."""
    import rectpack as rp
    packer = rp.newPacker(mode=rp.PackingMode.Offline, pack_algo=rp.MaxRectsBlsf, sort_algo=rp.SORT_AREA,
                          bin_algo=rp.PackingBin.BBF, rotation=False)
    for w, h, rid in rects:
        packer.add_rect(width=w, height=h, rid=rid)
    packer.add_bin(width=bin_size, height=bin_size)
    packer.pack()
    return packer


def uses_native(packer):
    return getattr(packer[0], "_native", None) is not None


def test_nothing_is_patched_until_install_is_called():
    assert not fastrectpack.is_installed()
    for name in ALGOS:
        assert getattr(rectpack, name) is ORIGINAL[name]
    assert rectpack.newPacker.__defaults__ == ORIGINAL_DEFAULTS
    assert not uses_native(third_party_pack(random_ops(random.Random(0), 20, 30), 200))


def test_install_speeds_up_code_that_only_knows_rectpack(installed):
    rects = random_ops(random.Random(1), 80, 40)
    fastrectpack.uninstall()
    before = third_party_pack(rects, 400.5)
    fastrectpack.install()
    after = third_party_pack(rects, 400.5)
    assert not uses_native(before) and uses_native(after)
    assert snap(after.rect_list()) == snap(before.rect_list())


def test_install_replaces_the_names_and_the_defaults(installed):
    assert fastrectpack.is_installed()
    for name in ALGOS:
        fast = getattr(fastrectpack, name)
        assert getattr(rectpack, name) is fast
        assert getattr(rectpack.maxrects, name) is fast
        assert issubclass(fast, ORIGINAL[name])  # isinstance checks against the original keep working
    assert rectpack.packer.MaxRectsBssf is fastrectpack.MaxRectsBssf
    for make in (rectpack.newPacker, early_newPacker, rectpack.PackerBBF, rectpack.PackerOnlineBNF, rectpack.PackerGlobal):
        packer = make()
        packer.add_bin(100, 100)
        packer.add_rect(10, 10)
        if hasattr(packer, "pack"):
            packer.pack()
        assert uses_native(packer), make


def test_everything_else_in_rectpack_is_untouched(installed):
    for name in ("SkylineBl", "GuillotineBssfSas", "PackerBBF", "SORT_AREA", "float2dec", "PackingBin", "PackingMode"):
        assert getattr(rectpack, name) is getattr(fastrectpack, name)
    packer = rectpack.newPacker(pack_algo=rectpack.SkylineBl)
    packer.add_rect(10, 10)
    packer.add_bin(50, 50)
    packer.pack()
    assert type(packer[0]) is rectpack.SkylineBl


def test_uninstall_restores_everything():
    fastrectpack.install()
    fastrectpack.install()  # twice is harmless
    fastrectpack.uninstall()
    fastrectpack.uninstall()
    assert not fastrectpack.is_installed()
    for name in ALGOS:
        assert getattr(rectpack, name) is ORIGINAL[name]
        assert getattr(rectpack.maxrects, name) is ORIGINAL[name]
    assert rectpack.packer.MaxRectsBssf is ORIGINAL["MaxRectsBssf"]
    assert rectpack.newPacker.__defaults__ == ORIGINAL_DEFAULTS
    for make in (rectpack.newPacker, rectpack.PackerBBF, rectpack.PackerOnlineBNF, rectpack.PackerGlobal):
        packer = make()
        packer.add_bin(100, 100)
        packer.add_rect(10, 10)
        if hasattr(packer, "pack"):
            packer.pack()
        assert not uses_native(packer), make


def test_every_packer_configuration_matches_through_patched_rectpack():
    """With install() active, rectpack's own entry points must still give the original's answers."""
    rng = random.Random(33)
    cases = []
    for cfg in all_packer_configs():
        rects = random_ops(rng, rng.randint(1, 40), 40)
        bins = [(rng.randint(30, 120), rng.randint(30, 120), rng.randint(1, 4))]
        cases.append((cfg, rects, bins, run_packer(rectpack, rects, bins, **packer_kwargs(rectpack, cfg))))
    fastrectpack.install()
    try:
        for cfg, rects, bins, expected in cases:
            assert run_packer(rectpack, rects, bins, **packer_kwargs(rectpack, cfg)) == expected, cfg
    finally:
        fastrectpack.uninstall()


def test_install_in_a_fresh_interpreter():
    """The documented usage, end to end, in a process where nothing else has touched rectpack."""
    code = textwrap.dedent("""
        import fastrectpack
        fastrectpack.install()
        import rectpack
        p = rectpack.newPacker()
        for i in range(30):
            p.add_rect(10 + i, 5 + i)
        p.add_bin(500, 500)
        p.pack()
        assert type(p[0]).__module__ == "fastrectpack._maxrects", type(p[0])
        assert p[0]._native is not None and len(p.rect_list()) == 30
        print("ok")
    """)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.returncode == 0 and out.stdout.strip() == "ok", out.stderr
