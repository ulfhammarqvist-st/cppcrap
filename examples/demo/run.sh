#!/usr/bin/env bash
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/../.." && pwd)"
build="$here/build"
rm -rf "$build" && mkdir -p "$build"

clang++ -std=c++17 -g -O0 -fprofile-instr-generate -fcoverage-mapping \
    -I "$here/src" -o "$build/pricing_test" "$here/src/pricing.cpp" "$here/tests/pricing_test.cpp"

LLVM_PROFILE_FILE="$build/pricing.profraw" "$build/pricing_test"
xcrun llvm-profdata merge -sparse "$build/pricing.profraw" -o "$build/pricing.profdata"
xcrun llvm-cov export "$build/pricing_test" -instr-profile="$build/pricing.profdata" \
    -format=lcov > "$build/coverage.info"

cd "$root"
python3 -m cppcrap "$here/src" --coverage "$build/coverage.info" --all "$@"
