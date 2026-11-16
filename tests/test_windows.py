import unittest
from windows import WindowManager


class MockUser32:
    def __init__(self, focus=True, active=123):
        self.focus = focus
        self.active = active
        self.restore_calls = []
    def IsIconic(self, hwnd): return True
    def ShowWindow(self, hwnd, cmd): self.restore_calls.append(cmd)
    def SetForegroundWindow(self, hwnd): return self.focus
    def GetForegroundWindow(self): return self.active


class TestWindowManagement(unittest.TestCase):
    def setUp(self):
        self.manager = WindowManager.__new__(WindowManager)
        self.manager.user32 = MockUser32()
        self.manager._entry = lambda hwnd: {'title': 'Notepad'}

    def test_focus_valid_window(self):
        self.assertIn('Notepad', self.manager.activate(123))
        self.assertEqual(self.manager.user32.restore_calls, [9])

    def test_rejects_invalid_handle(self):
        for value in (None, '123', -1, 0, True, 2**64):
            with self.assertRaises(ValueError):
                self.manager.activate(value)

    def test_focus_denied_by_windows(self):
        self.manager.user32 = MockUser32(focus=False)
        with self.assertRaisesRegex(RuntimeError, 'denied'):
            self.manager.activate(123)

    def test_focus_not_foreground(self):
        self.manager.user32 = MockUser32(active=999)
        with self.assertRaisesRegex(RuntimeError, 'did not become foreground'):
            self.manager.activate(123)

    def test_closed_window_not_activated(self):
        self.manager._entry = lambda hwnd: None
        with self.assertRaises(ValueError):
            self.manager.activate(123)

    def test_window_limit_validation(self):
        for limit in (0, 101, None, '50', True):
            with self.assertRaises(ValueError):
                self.manager.list_windows(limit)
