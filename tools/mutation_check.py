"""Mutation check: break the C++ on purpose and confirm the test-suite notices. Restores the file afterwards.

Usage (from the project root, with CMAKE_GENERATOR set for the platform):  python tools/mutation_check.py
"""
import os
import re
import subprocess
import sys

SRC = "src/fastrectpack/_native.cpp"
PY = sys.executable
original = open(SRC, encoding="utf-8").read()

MUTATIONS = [
    ("tie-break picks LAST minimal candidate (<= instead of <)", lambda s: s.replace("key < best_key", "key <= best_key")),
    ("MaxRectsBl rotated key uses height instead of width", lambda s: s.replace("m.y + w : rect_fitness(m, h, w)", "m.y + h : rect_fitness(m, h, w)")),
    ("skip 'contained by another' direction in duplicate removal", lambda s: s.replace(
        "                } else if (contains(next[b], next[a])) {\n                    flagged.push_back(next[a]);\n                }\n", "                }\n")),
    ("touching rectangles counted as intersecting", lambda s: s.replace("m.y >= r.top() || m.top() <= r.y", "m.y > r.top() || m.top() <= r.y")),
    ("Baf fitness ignores the placed rectangle's area", lambda s: s.replace("m.w * m.h - cw * ch", "m.w * m.h")),
    ("split pieces emitted in a different order (top before right)", lambda s: re.sub(
        r"(            if \(r\.right\(\) < m\.right\(\)\) \{\n.*\n.*\n            \}\n)(            if \(r\.top\(\) < m\.top\(\)\) \{\n.*\n.*\n            \}\n)",
        r"\2\1", s)),
    # mixed path (floats and numpy scalars)
    ("mixed path: result type of + - * is the narrower type instead of the wider one", lambda s: s.replace("a.tag | b.tag", "a.tag & b.tag")),
    ("mixed path: Blsf returns the second of two equal leftovers (wrong type on a tie)", lambda s: s.replace(
        "std::max(m.w - cw, m.h - ch)", "std::max(m.h - ch, m.w - cw)")),
    ("mixed path: Baf accepts sizes whose products are not exact in a double", lambda s: s.replace(
        "kMixedBafLimit = i64(1) << 26", "kMixedBafLimit = i64(1) << 30")),
    ("mixed path: zero, negative and NaN sizes are accepted", lambda s: s.replace("a.n.v > 0.0 && ", "")),
    ("mixed path: numpy.float64 results come back as plain floats", lambda s: s.replace(
        'PyObject_CallFunction(reinterpret_cast<PyObject*>(g_np_float64), "d", n.v)', "PyFloat_FromDouble(n.v)")),
]

env = dict(os.environ)
results = []
try:
    for label, mutate in MUTATIONS:
        mutated = mutate(original)
        if mutated == original:
            results.append((label, "MUTATION DID NOT APPLY"))
            continue
        open(SRC, "w", encoding="utf-8", newline="\n").write(mutated)
        b = subprocess.run([PY, "-m", "pip", "install", ".", "-q", "--no-deps"], env=env, capture_output=True, text=True)
        if b.returncode != 0:
            results.append((label, "BUILD FAILED: " + b.stderr[-200:]))
            continue
        t = subprocess.run([PY, "-m", "pytest", "tests", "-q", "-x", "-p", "no:cacheprovider"], env=env, capture_output=True, text=True)
        last = [ln for ln in t.stdout.strip().splitlines() if ln.strip()][-1]
        results.append((label, ("CAUGHT" if t.returncode != 0 else "*** SURVIVED ***") + " | " + last))
        print(results[-1], flush=True)
finally:
    open(SRC, "w", encoding="utf-8", newline="\n").write(original)
    subprocess.run([PY, "-m", "pip", "install", ".", "-q", "--no-deps"], env=env, capture_output=True, text=True)

print("\nSUMMARY")
for label, r in results:
    print(f"  {r.split(' |')[0]:18s} {label}")
