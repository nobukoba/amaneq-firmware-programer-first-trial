#!/usr/bin/env bash
set -euo pipefail
if (( $# < 3 )); then
  printf 'ERROR: Target, firmware family, and format are required.\n' >&2
  exit 2
fi
target=$1
family=$2
format=$3
shift 3
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
python_bin=${AMANEQ_PYTHON:-python3}
if ! command -v "$python_bin" >/dev/null 2>&1; then
  printf 'ERROR: Python 3.10+ not found. Set AMANEQ_PYTHON to its executable path.\n' >&2
  exit 1
fi
exec "$python_bin" "$script_dir/amaneq-firmware-programer.py" program "$@" --latest --firmware "$family" --target "$target" --format "$format" --yes
