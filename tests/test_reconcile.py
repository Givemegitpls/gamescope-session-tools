#!/usr/bin/env python3
"""Unit tests for the device reconciliation in gamescope-input-daemon.

Run with:

    /usr/bin/python3 tests/test_reconcile.py

Nothing here touches a real input device: the scanner and the device opener
are replaced by fakes, and ``/dev/null`` stands in for a device node so that
``_is_alive`` (which compares ``st_rdev``/``st_ino``) can be exercised for
real.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib.util
import os
import sys
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

DAEMON_PATH = Path(__file__).resolve().parent.parent / "src" / "gamescope-input-daemon"


def _load_daemon() -> object:
    loader = SourceFileLoader("gamescope_input_daemon", str(DAEMON_PATH))
    spec = importlib.util.spec_from_loader("gamescope_input_daemon", loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["gamescope_input_daemon"] = module
    loader.exec_module(module)
    return module


class FakeDevice:
    """Stands in for evdev.InputDevice."""

    def __init__(self, path: str, fd: int, name: str, phys: str) -> None:
        self.path = path
        self.fd = fd
        self.name = name
        self.phys = phys
        self.closed = False
        self.grabbed = False

    async def async_read_loop(self):
        """Never yields: stands in for a live, silent device."""
        await asyncio.Event().wait()
        return
        yield  # pragma: no cover — makes this an async generator

    def grab(self) -> None:
        self.grabbed = True

    def ungrab(self) -> None:
        self.grabbed = False

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            os.close(self.fd)
        except OSError:
            pass


class ReconcileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = _load_daemon()
        self.opened: list[FakeDevice] = []
        self.readable: list[object] = []
        self._real_readable = self.mod._readable_input_devices
        self._real_open = self.mod._open_device
        self.mod._readable_input_devices = lambda: list(self.readable)
        self.mod._open_device = self._open_device
        self.daemon = self.mod.InputDaemon(
            Path("/tmp/test-gamescope-input-daemon.sock")
        )

    def tearDown(self) -> None:
        self.mod._readable_input_devices = self._real_readable
        self.mod._open_device = self._real_open

    def _open_device(self, path: str) -> FakeDevice:
        info = path
        device = FakeDevice(
            path=path,
            fd=os.open("/dev/null", os.O_RDONLY | os.O_NONBLOCK),
            name="fake",
            phys="fake",
        )
        device.info_hint = info  # type: ignore[attr-defined]
        self.opened.append(device)
        return device

    def _info(self, path: str, name: str = "Test Device", phys: str = "test/input0"):
        return self.mod._DeviceInfo(path=path, name=name, phys=phys, uniq="uniq-1")

    def test_opens_once_and_ignores_duplicates(self) -> None:
        async def scenario() -> None:
            self.readable = [self._info("/dev/null")]
            await self.daemon._reconcile_devices()
            self.assertEqual(len(self.daemon._devices), 1)
            await self.daemon._reconcile_devices()
            self.assertEqual(len(self.daemon._devices), 1, "must not open twice")
            self.assertEqual(len(self.opened), 1)
            await self._shutdown()

        asyncio.run(scenario())

    def test_drops_device_whose_node_disappeared(self) -> None:
        gone = Path("/tmp/gst-test-gone-node")
        gone.write_text("not a device")

        async def scenario() -> None:
            self.readable = [self._info(str(gone))]
            await self.daemon._reconcile_devices()
            self.assertEqual(len(self.daemon._devices), 1)

            # Suspend/unplug: the node disappears.
            node = self.daemon._devices[0]
            gone.unlink()
            self.readable = []
            await self.daemon._reconcile_devices()
            self.assertEqual(len(self.daemon._devices), 0)
            task = node.task
            if task is not None:
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            self.assertTrue(self.opened[0].closed)
            await self._shutdown()

        asyncio.run(scenario())

    def test_reopens_device_that_returns_under_another_path(self) -> None:
        gone = Path("/tmp/gst-test-returns-node")
        gone.write_text("not a device")

        async def scenario() -> None:
            same_device = self._info(str(gone))
            self.readable = [same_device]
            await self.daemon._reconcile_devices()
            first = self.daemon._devices[0].device

            gone.unlink()
            self.readable = []  # the node is no longer listed either
            await self.daemon._reconcile_devices()
            self.assertEqual(len(self.daemon._devices), 0)

            # Back again, but now as /dev/input/eventN -> /dev/null, with the
            # same identity, which is what a resume looks like.
            self.readable = [self._info("/dev/null")]
            await self.daemon._reconcile_devices()
            self.assertEqual(
                len(self.daemon._devices), 1, "returning device not reopened"
            )
            self.assertIsNot(self.daemon._devices[0].device, first)
            await self._shutdown()

        asyncio.run(scenario())

    async def _shutdown(self) -> None:
        self.daemon._shutdown_flag = True
        await self.daemon._cleanup()


if __name__ == "__main__":
    _ = unittest.main(verbosity=2)
