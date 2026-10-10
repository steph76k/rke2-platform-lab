#!/usr/bin/env bash
set -euo pipefail
build_dir=$(mktemp -d)
trap 'rm -rf "$build_dir"' EXIT
recipe_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
image_tag=${1:-harbor-ha.berger.ph/platform-builds/minio:lab-20261010-security1}
git clone --quiet --depth 1 --branch RELEASE.2025-10-15T17-29-55Z https://github.com/minio/minio.git "$build_dir/source"
test "$(git -C "$build_dir/source" rev-parse HEAD)" = 9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a
git -C "$build_dir/source" apply "$recipe_dir/dependencies.patch"
docker build -f "$recipe_dir/Dockerfile" -t "$image_tag" "$build_dir/source"
