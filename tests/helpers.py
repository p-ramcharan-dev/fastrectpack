"""Shared helpers: run the same operations through the original rectpack and fastrectpack and capture everything."""

import rectpack

ALGOS = ("MaxRectsBl", "MaxRectsBssf", "MaxRectsBaf", "MaxRectsBlsf")


def snap(value):
    """Snapshot of a result that records the exact type of every number as well as its value.

    repr alone is not enough: under numpy 1.x, repr(numpy.float64(1.5)) is '1.5', the same as a plain float.
    """
    if isinstance(value, (list, tuple)):
        return type(value).__name__ + "(" + ", ".join(snap(v) for v in value) + ")"
    return f"{type(value).__module__}.{type(value).__qualname__}:{value!r}"


def run_algo(mod, name, width, height, rot, ops):
    """Drive one packing algorithm object directly. Records, after every step, the fitness, the placement
    and the complete free-rectangle list (order matters for tie-breaking), or the exception raised."""
    try:
        algo = getattr(mod, name)(width, height, rot=rot)
    except Exception as e:  # noqa: BLE001
        return [("init-error", type(e).__name__, str(e))], None
    steps = []
    for w, h, rid in ops:
        step = []
        for call in (lambda: algo.fitness(w, h), lambda: algo.add_rect(w, h, rid)):
            try:
                r = call()
                if hasattr(r, "x"):
                    r = (r.x, r.y, r.width, r.height, r.rid)
                step.append(snap(r))
            except Exception as e:  # noqa: BLE001
                step.append(("error", type(e).__name__, str(e)))
        step.append(snap([(m.x, m.y, m.width, m.height) for m in algo._max_rects]))
        steps.append(tuple(step))
    return steps, (snap(algo.rect_list()), snap(algo.used_area()), len(algo))


def run_packer(mod, rects, bins, **kwargs):
    """Build, fill and pack a packer; return everything observable.

    Offline packers: add rectangles and bins, then pack(). Online packers have no pack(): bins must exist
    first and every add_rect() places immediately, so its return value is recorded too.
    """
    try:
        packer = mod.newPacker(**kwargs)
        returned = []
        if kwargs.get("mode", rectpack.PackingMode.Offline) == rectpack.PackingMode.Online:
            for w, h, count in bins:
                packer.add_bin(w, h, count)
            for w, h, rid in rects:
                r = packer.add_rect(w, h, rid)
                if hasattr(r, "x"):
                    r = (r.x, r.y, r.width, r.height, r.rid)
                returned.append(snap(r))
        else:
            for w, h, rid in rects:
                packer.add_rect(w, h, rid)
            for w, h, count in bins:
                packer.add_bin(w, h, count)
            packer.pack()
        return (snap(packer.rect_list()), snap(packer.bin_list()), len(packer),
                [snap(b.rect_list()) for b in packer], returned)
    except Exception as e:  # noqa: BLE001
        return ("error", type(e).__name__, str(e))


def random_ops(rng, n, max_dim):
    return [(rng.randint(1, max_dim), rng.randint(1, max_dim), i) for i in range(n)]


def all_packer_configs():
    """Every combination newPacker accepts that involves a MaxRects algorithm."""
    configs = []
    for algo in ALGOS:
        for rot in (True, False):
            for bin_algo in (rectpack.PackingBin.BNF, rectpack.PackingBin.BFF, rectpack.PackingBin.BBF):
                for sort in ("SORT_AREA", "SORT_NONE", "SORT_PERI", "SORT_SSIDE", "SORT_LSIDE", "SORT_DIFF", "SORT_RATIO"):
                    configs.append((algo, rot, bin_algo, sort, rectpack.PackingMode.Offline))
            for bin_algo in (rectpack.PackingBin.BNF, rectpack.PackingBin.BFF, rectpack.PackingBin.BBF):
                configs.append((algo, rot, bin_algo, "SORT_NONE", rectpack.PackingMode.Online))
            configs.append((algo, rot, rectpack.PackingBin.Global, "SORT_NONE", rectpack.PackingMode.Offline))
    return configs


def packer_kwargs(mod, cfg):
    algo, rot, bin_algo, sort, mode = cfg
    return dict(mode=mode, bin_algo=bin_algo, pack_algo=getattr(mod, algo), sort_algo=getattr(mod, sort), rotation=rot)


def sample_configs(rng, k):
    cfgs = all_packer_configs()
    return rng.sample(cfgs, min(k, len(cfgs)))
