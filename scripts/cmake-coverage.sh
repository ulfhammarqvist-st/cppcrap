#!/usr/bin/env bash
# Build a CMake project with clang source-based coverage, run its tests, and report CRAP.
#
#   scripts/cmake-coverage.sh <source-dir> [build-dir] [-- extra cmake args]
#   SKIP_BUILD=1 scripts/cmake-coverage.sh ...   reuse an existing instrumented build
set -euo pipefail

source_dir="$(cd "${1:?usage: cmake-coverage.sh <source-dir> [build-dir]}" && pwd)"
build_dir="${2:-$source_dir/build-coverage}"
shift $(( $# > 1 ? 2 : 1 ))
[ "${1:-}" = "--" ] && shift

instrument="-fprofile-instr-generate -fcoverage-mapping"

if [ "${SKIP_BUILD:-0}" != "1" ]; then
    cmake -S "$source_dir" -B "$build_dir" -G Ninja \
        -DCMAKE_BUILD_TYPE=Debug \
        -DCMAKE_C_FLAGS="$instrument" \
        -DCMAKE_CXX_FLAGS="$instrument" \
        -DCMAKE_OBJC_FLAGS="$instrument" \
        -DCMAKE_OBJCXX_FLAGS="$instrument" \
        -DCMAKE_EXE_LINKER_FLAGS="-fprofile-instr-generate" \
        -DCMAKE_SHARED_LINKER_FLAGS="-fprofile-instr-generate" \
        "$@"
    cmake --build "$build_dir"
fi

# Pass the flags globally rather than through a project's own coverage option: a project that adds
# --coverage after add_subdirectory() leaves those targets linking instrumented libraries without
# the runtime. One profile per process also lets the suite run in parallel; shared .gcda files race.
rm -rf "$build_dir/prof" && mkdir -p "$build_dir/prof"
LLVM_PROFILE_FILE="$build_dir/prof/%p.profraw" ctest --test-dir "$build_dir" -LE benchmark -j"$(sysctl -n hw.ncpu 2>/dev/null || nproc)"

profiles=("$build_dir"/prof/*.profraw)
[ -e "${profiles[0]}" ] || { echo "no profiles written -- did the tests run?" >&2; exit 2; }
xcrun llvm-profdata merge -sparse "${profiles[@]}" -o "$build_dir/all.profdata"

binaries=()
while IFS= read -r binary; do binaries+=("$binary"); done < <(
    ctest --test-dir "$build_dir" -N --show-only=json-v1 2>/dev/null |
        python3 -c 'import json,sys; print("\n".join(sorted({t["command"][0] for t in json.load(sys.stdin)["tests"] if t.get("command")})))'
)
[ "${#binaries[@]}" -gt 0 ] || { echo "no test binaries found" >&2; exit 2; }

objects=()
for binary in "${binaries[@]:1}"; do objects+=(-object "$binary"); done
xcrun llvm-cov export "${binaries[0]}" "${objects[@]}" \
    -instr-profile="$build_dir/all.profdata" -format=lcov > "$build_dir/coverage.info"

echo "coverage written to $build_dir/coverage.info"
