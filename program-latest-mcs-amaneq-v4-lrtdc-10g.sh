#!/usr/bin/env bash
set -euo pipefail
# Download and program the latest official lrtdc-10g MCS for AMANEQ v4.
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec bash "$script_dir/firmware-latest-amaneq-common.sh" amaneq-v4 lrtdc-10g mcs "$@"
