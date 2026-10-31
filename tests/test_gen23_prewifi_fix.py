"""Offline production-module regressions; run: python3 -m unittest discover -s tests -v."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


SOURCE = Path(__file__).resolve().parents[1] / "src/vacuula_installer/core/gen23_prewifi_fix.py"


class Signal:
    def __init__(self, *args):
        self.slots = []
        self.calls = []

    def connect(self, slot):
        self.slots.append(slot)

    def emit(self, *args):
        self.calls.append(args)
        for slot in self.slots:
            slot(*args)


class ImmediateThread:
    """Run worker callbacks deterministically, without Qt or real threads."""
    def __init__(self, target, daemon):
        self.target = target

    def start(self):
        self.target()


def load_module():
    adapters = {
        "usb": {"__path__": []},
        "usb.core": {},
        "PySide6": {"__path__": []},
        "PySide6.QtCore": {"QObject": object, "Signal": Signal},
        "vacuula_installer": {"__path__": []},
        "vacuula_installer.core": {"__path__": []},
        "vacuula_installer.constants": {"GEN3_DEFAULT_PORT": 335, "SCRIPTS_DIR": SOURCE.parents[3] / "assets/scripts"},
        "vacuula_installer.core.neato_blast": {"upload_file": Mock()},
        "vacuula_installer.core.robot_detector": {"RobotDetector": Mock()},
        "vacuula_installer.core.session": {"SessionData": object},
    }
    modules = {}
    for name, values in adapters.items():
        modules[name] = types.ModuleType(name)
        modules[name].__dict__.update(values)
    modules["usb"].core = modules["usb.core"]
    spec = importlib.util.spec_from_file_location("prewifi_under_test", SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {**modules, spec.name: module}):
        spec.loader.exec_module(module)
    return module


class UploadResultTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        # Avoid QObject initialization, but exercise the actual worker and callbacks.
        self.fixer = self.module.Gen23WiFiFixer.__new__(self.module.Gen23WiFiFixer)
        self.fixer._active = False
        for name in ("_uploadDone", "_resetDone", "fixFailed"):
            setattr(self.fixer, name, Signal())
        self.fixer._uploadDone.connect(self.fixer._on_upload_done)
        self.fixer._resetDone.connect(self.fixer._on_reset_done)
        self.fixer._generate_tarball = Mock(side_effect=self.make_tarball)
        self.module.RobotDetector._get_serial.return_value = "serial"
        self.module.RobotDetector._find_serial_port.return_value = "test-port"
        self.device = object()
        self.session = object()
        self.tarball = None

    def make_tarball(self, directory, session):
        self.assertIs(session, self.session)
        self.tarball = directory / "vacuula.tar.gz"
        self.tarball.write_bytes(b"offline fixture")
        return self.tarball

    def run_fix(self):
        with patch.object(self.module.threading, "Thread", ImmediateThread):
            self.fixer.fix_robot(self.device, "001122334455", self.session)
        self.assertFalse(self.fixer._active)
        if self.tarball is not None:
            self.assertFalse(self.tarball.parent.exists(), "temporary upload directory leaked")

    def assert_upload(self):
        self.module.upload_file.assert_called_once_with("test-port", str(self.tarball), "Tarball", noburn=True)

    def test_rejected_transfer_stops_before_reset(self):
        self.module.upload_file.return_value = False
        self.run_fix()
        self.assert_upload()
        self.module.RobotDetector.write_cmd.assert_not_called()
        self.assertEqual(self.fixer._uploadDone.calls, [(False, self.device, "001122334455")])
        self.assertEqual(self.fixer.fixFailed.calls, [("error.generic.upload",)])
        self.assertEqual(self.fixer._resetDone.calls, [])

    def test_accepted_transfer_proceeds_to_reset(self):
        self.module.upload_file.return_value = True
        self.run_fix()
        self.assert_upload()
        self.assertEqual(self.fixer._uploadDone.calls, [(True, self.device, "001122334455")])
        self.module.RobotDetector.write_cmd.assert_called_once_with(
            self.device, self.module.reset_network_cmd("001122334455")
        )
        self.assertEqual(self.fixer._resetDone.calls, [(True,)])
        self.assertEqual(self.fixer.fixFailed.calls, [])

    def test_transfer_exception_remains_upload_failure(self):
        self.module.upload_file.side_effect = RuntimeError("transfer failed")
        self.run_fix()
        self.assert_upload()
        self.assertEqual(self.fixer.fixFailed.calls, [("error.generic.upload",)])
        self.module.RobotDetector.write_cmd.assert_not_called()
        self.assertEqual(self.fixer._resetDone.calls, [])

    def test_missing_port_remains_upload_failure(self):
        self.module.RobotDetector._find_serial_port.return_value = None
        self.run_fix()
        self.module.upload_file.assert_not_called()
        self.fixer._generate_tarball.assert_not_called()
        self.module.RobotDetector.write_cmd.assert_not_called()
        self.assertEqual(self.fixer.fixFailed.calls, [("error.generic.upload",)])

    def test_tarball_exception_still_propagates(self):
        self.fixer._generate_tarball.side_effect = ValueError("archive failed")
        with self.assertRaisesRegex(ValueError, "archive failed"):
            self.fixer._upload_scripts(self.device, self.session)
        self.module.upload_file.assert_not_called()


if __name__ == "__main__":
    unittest.main()
