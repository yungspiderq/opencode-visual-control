import unittest
from unittest.mock import patch
from PIL import Image
from screens import DisplayTopology, Monitor, Rect, VirtualDesktopCapture, set_dpi_awareness


def sample_topology():
    return DisplayTopology([
        Monitor('\\\\.\\DISPLAY1', Rect(0, 0, 1920, 1080), True),
        Monitor('\\\\.\\DISPLAY2', Rect(-1280, 100, 1280, 1024), False),
        Monitor('\\\\.\\DISPLAY3', Rect(1920, -150, 1000, 800), False),
    ])


class TestDisplayTopology(unittest.TestCase):
    def test_negative_coordinates_and_virtual_bounds(self):
        t = sample_topology()
        self.assertEqual(t.virtual, Rect(-1280, -150, 4200, 1274))
        self.assertTrue(t.contains(-1200, 500))
        self.assertTrue(t.contains(2600, -80))
        self.assertTrue(t.contains(0, 0))
        self.assertFalse(t.contains(-2, 0))  # gap above the left-hand monitor
        self.assertFalse(t.contains(2920, 0))  # outside right edge

    def test_monitor_resolution_and_unknown(self):
        t = sample_topology()
        self.assertEqual(t.monitor('\\\\.\\DISPLAY2').rect.left, -1280)
        self.assertIsNone(t.monitor('all'))
        with self.assertRaises(ValueError):
            t.monitor('not-a-monitor')
        self.assertEqual(t.as_dict()['coordinate_system'], 'absolute_virtual_desktop_physical_pixels')

    def test_duplicate_ids_and_empty(self):
        with self.assertRaises(RuntimeError):
            DisplayTopology([])
        with self.assertRaises(RuntimeError):
            DisplayTopology([Monitor('1', Rect(0,0,3,3),True), Monitor('1', Rect(3,0,3,3),False)])

    def test_capture_crops_using_virtual_offsets(self):
        t = sample_topology()
        image = Image.new('RGB', (4200, 1274), 'black')
        cap = VirtualDesktopCapture(lambda: t)
        with patch('PIL.ImageGrab.grab', return_value=image) as grab:
            selected = cap.capture('\\\\.\\DISPLAY2')
            self.assertEqual(selected.size, (1280, 1024))
            self.assertEqual(cap.capture('all').size, (4200, 1274))
            grab.assert_called_with(all_screens=True)

    def test_display_change_during_capture_fails(self):
        cap = VirtualDesktopCapture(sample_topology)
        with patch('PIL.ImageGrab.grab', return_value=Image.new('RGB', (100,100))):
            with self.assertRaisesRegex(RuntimeError, 'topology changed'):
                cap.capture('all')

    def test_dpi_aware_fallback_non_windows(self):
        with patch('screens.sys.platform', 'linux'):
            self.assertEqual(set_dpi_awareness(), 'not-windows')
