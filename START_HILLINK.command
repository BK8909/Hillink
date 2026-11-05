#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "$0")/hillink"
exec bash tools/start_product.sh "$@"
