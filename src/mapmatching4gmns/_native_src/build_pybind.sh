#!/usr/bin/env bash
# Developer helper. Official release wheels are built by cibuildwheel.
set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/../../.." && pwd)

python -m build --wheel --outdir "$repo_root/dist" "$repo_root"
echo "built platform wheel in $repo_root/dist"
