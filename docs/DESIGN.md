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

- While every size is a plain Python `int` between 1 and 2^30, `fitness` and `add_rect` call the C++ `Core`, which keeps the free rectangles in a vector of 64-bit integer structs (the "int path").
- On the first size that is a Python `float`, a `numpy.float64` or a `numpy.int64`, the core converts its free list once and continues on the "mixed path" described below. This is not a fallback: the work stays in C++.
- On the first input neither path accepts (`Decimal`, `bool`, any other numpy type, NaN, infinity, zero, negative, above 2^30, wrong type) the C++ code raises an internal `Deopt`. The wrapper copies the current free-rectangle list into the original's `_max_rects` attribute and carries on with the original Python code for the rest of that object's life. Results and error messages therefore come from the original implementation.
- The 2^30 bound keeps every sum and product (`MaxRectsBaf` multiplies two sizes) well inside `int64`.
- `bool` is excluded on purpose: the original would return coordinates of type `bool` for such input, and the tests compare value types as well as values.
- Code that peeks at `_max_rects` still works: it is built on demand from the C++ state until the object falls back.
- Pickling and `copy.deepcopy` work: the state is serialised as plain Python, and the restored object continues on the original code path (correct, not accelerated).

## The mixed path: floats and numpy scalars

Added in 0.2.0. The algorithm is one C++ template, instantiated for 64-bit integers (the int path) and for a small `Num` struct (the mixed path), so both paths run the same code.

**Values.** A `Num` holds a `double`. Python floats and `numpy.float64` are doubles already, and Python evaluates `+`, `-` and `*` on them with single IEEE 754 operations, so doing the same operations in the same order in C++ gives the same bits. Integers are held in the double too. That is exact because every integer that can occur is below 2^53: sizes are capped at 2^30, and for `MaxRectsBaf`, which multiplies two sizes, at 2^26 on this path. Comparing an int with a float then also matches Python, which compares them exactly.

**Types.** The original's results are whatever Python arithmetic produces: `int + numpy.float64` is a `numpy.float64`, `int - int` is an `int`, and `min(a, b)` is whichever argument won. For gdsfactory's input (int rectangles in a `numpy.float64` bin) the free rectangles end up with `int` positions and a mix of `int` and `numpy.float64` sizes. To reproduce that, each `Num` carries a two-bit tag: bit 0 means floating point, bit 1 means numpy scalar. The type of a sum, difference or product is the bitwise OR of the operands' tags, which matches Python and numpy for these four types. `std::min` and `std::max` return their first argument on a tie, as Python's `min` and `max` do, so the tag of a fitness value is right too. The tests compare the type of every number, not just its value.

**Compiler settings.** The build passes `-ffp-contract=off` (GCC, Clang) so that `w*h - cw*ch` is not fused into a multiply-add, which rounds once instead of twice and would change the last bit. Clang does that by default on Apple silicon. On a compiler that evaluates `double` expressions with extra precision (`FLT_EVAL_METHOD != 0`, in practice 32-bit x86 without SSE2) the mixed path is compiled out and those inputs fall back.

**numpy is not a dependency.** The extension never imports it. It looks up `numpy.float64` and `numpy.int64` in `sys.modules` the first time it is handed an object whose type name starts with `numpy.`.

**Not supported, so still falling back:** `numpy.int32` and the other numpy integer widths (their overflow and promotion rules differ between numpy 1 and 2), `numpy.float32`, `Decimal`, `Fraction`, `bool`.

## What "identical" means here

The port reproduces these details of the original exactly:

1. **Candidate order.** The original picks the minimum with Python's `min`, which keeps the *first* minimal candidate. It scans free rectangles in list order, normal orientation first, then rotated. The C++ does the same, with a strict `<`.
2. **`MaxRectsBl` tie-break.** The docstring promises "smallest x"; the code compares only `y + height`. The port follows the code.
3. **Free-list order.** After a split, new pieces are inserted where the split rectangle was, in the order left, right, top, bottom. Order matters because of point 1, so the tests compare the whole list after every step.
4. **Duplicate removal by value.** The original puts "contained" rectangles in a set and removes anything equal to one of them, so two identical free rectangles would both disappear. The port does the same. In more than 97,000 calls on benchmark workloads and a small-size fuzz, I never saw two identical free rectangles at once, so this may be unreachable; it is reproduced anyway.
5. **Which rectangle of a pair is marked.** For a pair where the earlier rectangle contains the later one, the original marks the later one and does not test the other direction. With integers that detail cannot matter. With floats, two rectangles of different widths would each contain the other if `x + width` rounded to the same number, so the port follows the same rule. In 14,000 fuzzed float packings, including ones built to provoke that rounding, it never happened.
6. **Result types** on the mixed path, as described above.

## The one algorithmic change, and why it is safe

The original compares every pair of free rectangles after every placement, which is about 90% of its run time. The port, and the pure-Python variant in `bench/cheap_wins.py`, compare only pairs that involve a newly created rectangle.

That is valid because the list left by the previous duplicate-removal step contains no rectangle that contains another (every contained rectangle was removed). A split only adds new rectangles, so any containing pair must involve one. The tests compare against the original's all-pairs result at every step.

## How correctness is checked

| Check | What it catches |
|---|---|
| Step-by-step parity against the original | Any difference in fitness, placement or free-list order |
| Edge cases | Differences in handling of `Decimal`, NaN, infinity, bools, zero/negative sizes, huge ints, unsupported numpy types, errors |
| Mixed-type parity (`tests/test_mixed_types.py`) | Any difference in value or type for int, float, `numpy.float64` and `numpy.int64` sizes in any mix; also checks these stay in C++ |
| Property-based tests (Hypothesis) | Inputs nobody thought of |
| All 200 packer configurations | Differences through the bin heuristics, modes and sort orders |
| `tools/mutation_check.py` | Tests that cannot fail: it breaks the C++ in eleven ways and expects failures |
| AddressSanitizer + UBSan (CI, Linux) | Memory errors and undefined behaviour in the C++ |
| Benchmark digests | Every benchmark run hashes the full output of every variant |

## Known gaps

- The bin-selection loops (`PackerBBF` and others) are still Python, so jobs spread over many bins gain only about 5x. Moving them into C++ is the most valuable next step.
- numpy integer types other than `numpy.int64`, `numpy.float32`, `Decimal` and `Fraction` sizes fall back to the original code.
- On the mixed path `MaxRectsBaf` accepts sizes up to 2^26 (about 67 million); larger ones fall back.
- Skyline and Guillotine algorithms are unchanged original code.
