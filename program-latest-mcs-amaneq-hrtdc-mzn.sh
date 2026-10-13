#!/usr/bin/env bash
set -euo pipefail
# Download and program the latest official HR-TDC mezzanine MCS.
# Detect MT25QU256/N25Q128 automatically before selecting the download.
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec bash "$script_dir/firmware-latest-amaneq-common.sh" hrtdc-mezzanine hrtdc mcs "$@"
