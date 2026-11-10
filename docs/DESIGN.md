# Design

How fastrectpack is put together, and why. For measurements see [BENCHMARKS.md](../BENCHMARKS.md).

## Goal and constraint

Make rectpack's MaxRects packing fast **without changing a single answer**. Everything below follows from that constraint: the original library is the specification, so the port copies its behaviour, including its quirks, instead of fixing them.

## Layout

| Path | What it is |
|---|---|
| `src/fastrectpack/_native.cpp` | The C++17 core (`Core`), exposed with pybind11 |
| `src/fastrectpack/_maxrects.py` | Python classes that subclass rectpack's `MaxRects*` and delegate to the core |
| `src/fastrectpack/__init__.py` | Re-exports the whole rectpack API, replaces the four MaxRects classes and `newPacker` |
| `tests/` | Parity, edge-case, property-based and metadata tests |
| `bench/`, `results/`, `docs/` | Benchmark harness, raw numbers, chart |
| `tools/` | Mutation check, sanitizer script, result summariser |

## Subclass, delegate, fall back

Each accelerated class (`MaxRectsBssf` and friends) subclasses the original, so `isinstance` checks, `rect_list()`, `validate_packing()` and everything else keep working. Only `fitness`, `add_rect` and `reset` are overridden.

- While every size is a plain Python `int` between 1 and 2^30, `fitness` and `add_rect` call the C++ `Core`, which keeps the free rectangles in a vector of 64-bit structs.
- On the first input outside that range (float, `Decimal`, numpy integer, `bool`, zero, negative, huge int, wrong type) the C++ code raises an internal `Deopt`. The wrapper copies the current free-rectangle list into the original's `_max_rects` attribute and carries on with the original Python code for the rest of that object's life. Results and error messages therefore come from the original implementation.
- The 2^30 bound keeps every sum and product (`MaxRectsBaf` multiplies two sizes) well inside `int64`.
- `bool` is excluded on purpose: the original would return coordinates of type `bool` for such input, and the tests compare value types as well as values.
- Code that peeks at `_max_rects` still works: it is built on demand from the C++ state until the object falls back.
- Pickling and `copy.deepcopy` work: the state is serialised as plain Python, and the restored object continues on the original code path (correct, not accelerated).

## What "identical" means here

The port reproduces these details of the original exactly:

1. **Candidate order.** The original picks the minimum with Python's `min`, which keeps the *first* minimal candidate. It scans free rectangles in list order, normal orientation first, then rotated. The C++ does the same, with a strict `<`.
2. **`MaxRectsBl` tie-break.** The docstring promises "smallest x"; the code compares only `y + height`. The port follows the code.
3. **Free-list order.** After a split, new pieces are inserted where the split rectangle was, in the order left, right, top, bottom. Order matters because of point 1, so the tests compare the whole list after every step.
4. **Duplicate removal by value.** The original puts "contained" rectangles in a set and removes anything equal to one of them, so two identical free rectangles would both disappear. The port does the same. In more than 97,000 calls on benchmark workloads and a small-size fuzz, I never saw two identical free rectangles at once, so this may be unreachable; it is reproduced anyway.

## The one algorithmic change, and why it is safe

The original compares every pair of free rectangles after every placement, which is about 90% of its run time. The port, and the pure-Python variant in `bench/cheap_wins.py`, compare only pairs that involve a newly created rectangle.

That is valid because the list left by the previous duplicate-removal step contains no rectangle that contains another (every contained rectangle was removed). A split only adds new rectangles, so any containing pair must involve one. The tests compare against the original's all-pairs result at every step.

## How correctness is checked

| Check | What it catches |
|---|---|
| Step-by-step parity against the original | Any difference in fitness, placement or free-list order |
| Edge cases | Differences in handling of floats, `Decimal`, NaN, bools, zero/negative sizes, huge ints, errors |
| Property-based tests (Hypothesis) | Inputs nobody thought of |
| All 200 packer configurations | Differences through the bin heuristics, modes and sort orders |
| `tools/mutation_check.py` | Tests that cannot fail: it breaks the C++ in six ways and expects failures |
| AddressSanitizer + UBSan (CI, Linux) | Memory errors and undefined behaviour in the C++ |
| Benchmark digests | Every benchmark run hashes the full output of every variant |

## Known gaps

- The bin-selection loops (`PackerBBF` and others) are still Python, so jobs spread over many bins gain only about 5x. Moving them into C++ is the most valuable next step.
- No fast path for float sizes. Matching the original also means matching the *types* of results (`0` versus `0.0`), which needs care.
- Skyline and Guillotine algorithms are unchanged original code.
