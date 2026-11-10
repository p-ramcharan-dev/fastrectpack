from importlib.metadata import version

import fastrectpack


def test_version_matches_installed_metadata():
    """`fastrectpack.__version__` is written by hand; this catches it drifting from pyproject.toml."""
    assert fastrectpack.__version__ == version("fastrectpack")


def test_public_names_are_the_original_objects_except_maxrects():
    import rectpack

    replaced = {"MaxRectsBl", "MaxRectsBssf", "MaxRectsBaf", "MaxRectsBlsf", "newPacker"}
    for name in ("SkylineBl", "GuillotineBssfSas", "PackerBBF", "SORT_AREA", "float2dec", "PackingBin", "PackingMode"):
        assert name not in replaced
        assert getattr(fastrectpack, name) is getattr(rectpack, name)
    for name in replaced:
        assert getattr(fastrectpack, name) is not getattr(rectpack, name)
