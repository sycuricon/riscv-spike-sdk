#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
# Initialize only the dependencies needed for KVM. No floating --remote update.
exec python3 scripts/kvm.py prepare
