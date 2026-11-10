"""Deterministic workload generators. Every workload is a pure function of (kind, n, seed)."""
import random

# Each workload returns (rects, bins): rects = [(w, h, rid), ...], bins = [(w, h, count), ...]

CUTTING_SIZES = [  # typical sheet-goods part sizes (mm); heavy duplication on purpose
    (300, 200), (450, 300), (600, 400), (800, 250), (250, 250), (120, 80), (500, 500),
    (700, 350), (900, 150), (350, 350), (150, 150), (1000, 200), (220, 440), (180, 90),
    (640, 320), (400, 400), (75, 75), (60, 240), (960, 480), (280, 560),
]
SPRITE_SIZES = [16, 24, 32, 48, 64, 96, 128, 192, 256]


def make(kind, n, seed=1):
    rng = random.Random(f"{kind}/{n}/{seed}")
    if kind == "random":
        rects = [(rng.randint(10, 100), rng.randint(10, 100), i) for i in range(n)]
        bins = [(1000, 1000, 400)]
    elif kind == "cutting":
        rects = [(*rng.choice(CUTTING_SIZES), i) for i in range(n)]
        bins = [(2440, 1220, 400)]
    elif kind == "sprites":
        rects = [(rng.choice(SPRITE_SIZES), rng.choice(SPRITE_SIZES), i) for i in range(n)]
        bins = [(2048, 2048, 400)]
    elif kind == "skewed":  # a few big pieces plus many small ones
        rects = []
        for i in range(n):
            if rng.random() < 0.05:
                rects.append((rng.randint(200, 600), rng.randint(200, 600), i))
            else:
                rects.append((rng.randint(5, 60), rng.randint(5, 60), i))
        bins = [(1500, 1500, 400)]
    else:
        raise ValueError(kind)
    return rects, bins


KINDS = ("random", "cutting", "sprites", "skewed")
