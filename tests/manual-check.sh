#!/usr/bin/env bash
# Verify that gamescope-input-daemon discovers input devices read-only.
#
#   tests/manual-check.sh
#
# Run this as root (or in a shell that has read access to /dev/input/event*,
# e.g. after `newgrp input`). It prints the device count the daemon's scanner
# returns, then opens the Power Button and volume keys and prints them.
#
# Non-root users without the `input` group see "0" — that is expected and does
# NOT indicate a bug: the scanner requires only read access, and this script
# checks exactly what the service account can reach.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DAEMON="$HERE/../src/gamescope-input-daemon"
PYTHON="${PYTHON:-/usr/bin/python3}"

echo "user:       $(id -un)"
echo "input group: $(id -nG | tr ' ' '\n' | grep -cx input || true)"
echo

"$PYTHON" - "$DAEMON" <<'PY'
import importlib.util
import sys
from importlib.machinery import SourceFileLoader

path = sys.argv[1]
loader = SourceFileLoader("gamescope_input_daemon", path)
spec = importlib.util.spec_from_loader("gamescope_input_daemon", loader)
assert spec is not None
mod = importlib.util.module_from_spec(spec)
sys.modules["gamescope_input_daemon"] = mod
loader.exec_module(mod)

infos = mod._readable_input_devices()
print(f"readable input devices: {len(infos)}")
for info in infos:
    print(f"  {info.path}  {info.name!r}  {info.phys!r}")

if not infos:
    print("No readable device: run as root or with the input group.", file=sys.stderr)
    sys.exit(1)

interesting = {
    "KEY_VOLUMEUP": 115,
    "KEY_VOLUMEDOWN": 114,
    "KEY_MUTE": 113,
    "KEY_POWER": 116,
}
for info in infos:
    device = mod._open_device(info.path)
    try:
        caps = set(device.capabilities(absinfo=False).get(1, []))
        hits = sorted(name for name, code in interesting.items() if code in caps)
        if hits:
            print(f"{info.path} ({info.name}): {hits}")
    finally:
        device.close()
PY
