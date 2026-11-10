# Contributing

Thanks for looking. This project has one rule that matters more than the others: **fastrectpack must give exactly the same answers as the original `rectpack`.** Speed is the point, but only if the output is identical.

## Set up

You need Python 3.9+, CMake 3.15+ and a C++17 compiler (MSVC 2019+, GCC 9+ or Clang 10+).

```
python -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install ".[test]" numpy
pytest -q
```

Re-run `pip install .` after changing `src/fastrectpack/_native.cpp`; the extension is rebuilt on install.

On Windows from Git Bash, set `CMAKE_GENERATOR="Visual Studio 17 2022"` first. A "Developer PowerShell for VS" prompt should not need it, but that has not been tested.

## Before you open a pull request

1. **Parity first.** The tests compare every placement and the full free-rectangle list against the original, step by step. If you change behaviour on purpose, say why in the PR; if a change alters output, the tests are meant to fail.
2. **Add a test** for what you changed. For anything touching the C++, extend `tests/test_parity.py` or `tests/test_edge_cases.py`.
3. **Claiming a speedup?** Include numbers from `python bench/run_bench.py`, with the hardware, and say how many runs they came from. Please quote the best-of ratio and show the spread. See `BENCHMARKS.md` for why.
4. **Style.** `ruff check .` for Python and `clang-format -i src/fastrectpack/_native.cpp` for C++. CI checks both.
5. **Changelog.** Add a line to `CHANGELOG.md`.

If a substantial part of a change was written with an AI assistant, please say so in the PR description.

## Things worth knowing

- Quirks inherited from rectpack are **reproduced on purpose** so that output matches (see "Behaviour inherited from rectpack" in the README). Please do not fix them here; they belong upstream.
- The fast path handles Python `int`, Python `float`, `numpy.float64` and `numpy.int64` sizes up to 2^30. Anything else falls back to the original code. Results must keep the original's value types (`0` versus `0.0` versus `numpy.float64(0.0)`); the tests compare types as well as values. See `docs/DESIGN.md`.
- Moving the bin-selection loop (`PackerBBF` and friends) into C++ is the most valuable open improvement. It would lift workloads that spread rectangles over many bins above the current ~5x.

## Checks you can run

| What | Command |
|---|---|
| Tests | `pytest -q` |
| Quick benchmark (about a minute) | `python bench/run_bench.py --quick` |
| Float and numpy benchmark | `python bench/run_mixed.py --quick` |
| Mutation check (breaks the C++ on purpose, expects the tests to notice) | `python tools/mutation_check.py` |
| AddressSanitizer + UBSan (Linux) | `bash tools/sanitize_linux.sh` |

## Reporting problems

Use the issue templates. For a performance report, include the workload shape (rectangle count and size range, bin size and count) and the packer settings. For anything that looks like a memory-safety problem, see [SECURITY.md](SECURITY.md) instead of opening a public issue.
