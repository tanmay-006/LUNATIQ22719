#!/usr/bin/env bash
set -eo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONDA_SH="${HOME}/miniforge3/etc/profile.d/conda.sh"

if [[ ! -f "$CONDA_SH" ]]; then
    echo "Miniforge was not found at ${HOME}/miniforge3" >&2
    exit 1
fi

source "$CONDA_SH"
if [[ "${CONDA_DEFAULT_ENV:-}" != "isis" ]]; then
    conda activate isis
fi
exec python "$ROOT_DIR/src/lunar_isis_gui/app.py" "$@"
