#!/usr/bin/env bash
set -euo pipefail
# Download and program the latest official skeleton BIT for amaneq-v4.
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec bash "$script_dir/firmware-latest-amaneq-common.sh" amaneq-v4 skeleton bit "$@"
