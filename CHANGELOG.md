# Changelog

All notable changes to this project are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.3.0] - 2026-11-10

### Added
- `fastrectpack.install()`: makes `rectpack` itself hand out the accelerated classes, so a library that uses rectpack internally gets faster without being edited. `uninstall()` reverses it and `is_installed()` reports the state. `rectpack.newPacker`, the four `rectpack.MaxRects*` names (also in `rectpack.maxrects`) and the default algorithm of every packer class are covered.
- Prebuilt wheels for Python 3.14 and 3.15, Linux ARM64, Alpine Linux (musl, x86_64 and ARM64) and Intel Macs. 49 wheels in total, up from 15. Previously these all had to compile the C++ at install time.
- `tests/test_install.py`, including all 200 packer configurations run through the patched `rectpack` and a fresh-interpreter test. The suite has 1,045 tests.

### Changed
- Wheel tests now install numpy where a prebuilt numpy wheel exists, so the numpy tests run inside the wheels instead of being skipped.

## [0.2.0] - 2026-11-10

### Added
- Sizes given as Python `float`, `numpy.float64` or `numpy.int64`, in any mix with plain `int`, now run in C++. Results have the same values and the same types as `rectpack` returns. This covers the way gdsfactory and phidl call rectpack (integer rectangle sizes in a `numpy.float64` bin), which 0.1.0 handed to the original Python code. Measured speedups are in `BENCHMARKS.md`.
- An object that starts with `int` sizes and later receives a float or numpy size stays in C++ instead of falling back.
- `tests/test_mixed_types.py`: step-by-step parity for every mix of the four types, all 200 packer configurations with mixed types, a gdsfactory-style test, size limits, and a Hypothesis property test. All test snapshots now record the type of every number. The suite has 1,038 tests.
- `bench/run_mixed.py`, a benchmark for float and numpy input.
- Five more mutations in `tools/mutation_check.py` for the new path. All eleven are caught.

### Fixed
- The "known issue" recorded after 0.1.0, that the fallback to the original code ran about 2x slower than plain `rectpack`, was a measurement artifact and not a defect. The fallback makes 0.007% more Python function calls than `rectpack` and takes the same time when the two are timed in alternation. The two original figures were taken one after the other on a laptop whose speed for identical work changes by 2x to 4x between minutes. Evidence: `research/fallback_slowdown.py` and `results/fallback_slowdown.txt`.
- `tools/mutation_check.py`: the "split pieces in a different order" mutation no longer applied to the source and was reported as not applied. It applies again and is caught.

### Changed
- Wheels no longer include `_native.cpp`. The C++ source stays in the source distribution.
- The build passes `-ffp-contract=off` (GCC, Clang) and `/fp:precise` (MSVC), which the float path needs to match Python bit for bit.
- On the float path, `MaxRectsBaf` accepts sizes up to 2^26; larger sizes fall back to the original code. Other algorithms accept up to 2^30, as before.

### Still falling back to the original code
- `Decimal`, `Fraction`, `bool`, `numpy.float32`, numpy integer types other than `numpy.int64`, NaN, infinity, zero or negative sizes, and sizes above 2^30. Output is identical; speed is that of `rectpack`.

## [0.1.0] - 2026-11-10

First release, on PyPI: https://pypi.org/project/fastrectpack/0.1.0/

### Added
- C++17 (pybind11) implementations of `MaxRectsBl`, `MaxRectsBssf`, `MaxRectsBaf` and `MaxRectsBlsf`, exposed as subclasses of the originals. Output is identical to `rectpack` 0.2.2.
- Fast path for plain Python `int` sizes up to 2^30. Any other input (floats, `Decimal`, numpy integers, `bool`, zero or negative sizes, larger integers) hands the object over to the original Python code for the rest of its life.
- `fastrectpack.newPacker`, same signature as `rectpack.newPacker`, defaulting to the accelerated algorithm. Everything else `rectpack` exports is re-exported unchanged.
- Test suite of 474 tests: step-by-step parity, edge cases, property-based tests, all 200 packer configurations that use a MaxRects algorithm.
- Benchmarks (`bench/`), raw results (`results/`) and a chart (`docs/`).
- CI: wheels for CPython 3.9 to 3.13 on Linux x86_64, Windows x86_64 and macOS arm64; AddressSanitizer and UndefinedBehaviorSanitizer on Linux.
