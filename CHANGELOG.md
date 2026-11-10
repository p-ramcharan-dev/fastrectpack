# Changelog

All notable changes to this project are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [0.1.0] - not yet released

First version.

### Added
- C++17 (pybind11) implementations of `MaxRectsBl`, `MaxRectsBssf`, `MaxRectsBaf` and `MaxRectsBlsf`, exposed as subclasses of the originals. Output is identical to `rectpack` 0.2.2.
- Fast path for plain Python `int` sizes up to 2^30. Any other input (floats, `Decimal`, numpy integers, `bool`, zero or negative sizes, larger integers) hands the object over to the original Python code for the rest of its life.
- `fastrectpack.newPacker`, same signature as `rectpack.newPacker`, defaulting to the accelerated algorithm. Everything else `rectpack` exports is re-exported unchanged.
- Test suite of 474 tests: step-by-step parity, edge cases, property-based tests, all 200 packer configurations that use a MaxRects algorithm.
- Benchmarks (`bench/`), raw results (`results/`) and a chart (`docs/`).
- CI: wheels for CPython 3.9 to 3.13 on Linux x86_64, Windows x86_64 and macOS arm64; AddressSanitizer and UndefinedBehaviorSanitizer on Linux.
