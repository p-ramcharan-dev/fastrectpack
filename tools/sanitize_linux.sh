#!/usr/bin/env bash
# Build the extension with AddressSanitizer + UndefinedBehaviorSanitizer (GCC or Clang, Linux) and run the tests.
# Usage: bash tools/sanitize_linux.sh
set -euo pipefail

SRC="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${WORK:-$HOME/.cache/fastrectpack-sanitize}"
rm -rf "$WORK"
mkdir -p "$WORK"
# Work on a copy so nothing is built inside the source tree.
tar -C "$SRC" --exclude=.venv --exclude='.venv*' --exclude=.git --exclude=results --exclude=build -cf - . | tar -C "$WORK" -xf -

python3 -m venv "$WORK/venv"
. "$WORK/venv/bin/activate"
python -m pip -q install --upgrade pip
python -m pip -q install pytest hypothesis
cd "$WORK"
python -m pip -q install . -C cmake.define.FASTRECTPACK_SANITIZE=address,undefined

echo "compiler: $(g++ --version | head -1)"
echo "python:   $(python --version)"
export LD_PRELOAD="$(gcc -print-file-name=libasan.so) $(gcc -print-file-name=libubsan.so)"
# Leak checking is off: CPython itself does not free everything at exit, which drowns real reports.
export ASAN_OPTIONS=detect_leaks=0:abort_on_error=1
export UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1
python -c "import fastrectpack; assert fastrectpack.NATIVE_AVAILABLE; print('native extension loaded under sanitizers')"
nm -D "$(python -c 'import fastrectpack._native as m; print(m.__file__)')" | grep -c -E "__asan|__ubsan" | sed 's/^/sanitizer symbols referenced by the extension: /'
python -m pytest tests -q -p no:cacheprovider
