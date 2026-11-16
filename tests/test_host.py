import threading
import unittest
from unittest.mock import Mock
from actions import SafetyGate, ControlStopped
from host import VisualHost
from screens import DisplayTopology, Monitor, Rect


class TestHostSecurity(unittest.TestCase):
    def setUp(self):
        host = VisualHost.__new__(VisualHost)  # no Tk root or Windows API required
        host.gate = SafetyGate()
        host.busy = threading.Lock()
        host.events = Mock()
        host.displays = Mock()
        host.displays.topology.return_value = DisplayTopology([Monitor('one', Rect(-100,20,1200,900),True)])
        host.windows = Mock()
        host.desktop = Mock()
        self.host = host

    def test_status_and_displays_work_while_paused(self):
        self.assertFalse(self.host.perform('status', {})['enabled'])
        self.assertEqual(self.host.perform('displays', {})['virtual']['left'], -100)

    def test_window_listing_and_focus_require_resume(self):
        with self.assertRaises(ControlStopped):
            self.host.perform('windows', {})
        with self.assertRaises(ControlStopped):
            self.host.perform('focus_window', {'hwnd': 123})
        self.host.windows.assert_not_called()
        self.host.gate.resume()
        self.host.windows.list_windows.return_value = [{'hwnd': 123}]
        self.assertEqual(self.host.perform('windows', {})['windows'], [{'hwnd': 123}])
        self.host.windows.activate.return_value = 'Focused'
        self.assertEqual(self.host.perform('focus_window', {'hwnd': 123})['message'], 'Focused')

    def test_screenshot_paused_then_allowed(self):
        with self.assertRaises(ControlStopped):
            self.host.perform('screenshot', {})
        self.host.gate.resume()
        self.host.desktop.screenshot_png.return_value = b'PNG'
        result = self.host.perform('screenshot', {'monitor_id': 'one', 'max_width': 900})
        self.assertEqual(result['image'], 'UE5H')
        self.host.desktop.screenshot_png.assert_called_once_with(900, 'one')
