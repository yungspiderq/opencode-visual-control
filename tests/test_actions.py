import unittest
from actions import SafetyGate, DesktopActions, ControlStopped, virtual_key
from screens import DisplayTopology, Monitor, Rect
from PIL import Image
import io


class FakeGui:
    FAILSAFE = None
    PAUSE = None
    def __init__(self):
        self.x, self.y = 100, 100
        self.log = []
    def size(self): return 1920, 1080
    def position(self): return self.x, self.y
    def moveTo(self, x, y): self.x, self.y = x, y; self.log.append(('move',x,y))
    def click(self, **kwargs): self.log.append(('click',kwargs))
    def mouseDown(self, **kwargs): self.log.append(('down',kwargs))
    def mouseUp(self, **kwargs): self.log.append(('up',kwargs))
    def scroll(self, clicks): self.log.append(('scroll',clicks))


class FakeKeys:
    def __init__(self): self.log = []
    def press(self, vk): self.log.append(('press', vk))
    def combo(self, keys): self.log.append(('combo', tuple(keys)))
    def type_char(self, char, gate):
        gate.check()
        self.log.append(('char', char))


class TestDesktopActions(unittest.TestCase):
    def setUp(self):
        self.gate = SafetyGate()
        self.gui = FakeGui()
        self.keys = FakeKeys()
        self.actions = DesktopActions(self.gui, self.gate, keys=self.keys)

    def test_paused_by_default(self):
        with self.assertRaises(ControlStopped):
            self.actions.move(10, 10, 0)
        self.assertFalse(self.gui.log)

    def test_move_and_click(self):
        self.gate.resume()
        self.actions.move(200, 300, 0)
        self.actions.click(250, 350)
        self.assertEqual((self.gui.x, self.gui.y), (250, 350))
        self.assertTrue(any(x[0] == 'click' for x in self.gui.log))

    def test_out_of_bounds_rejected(self):
        self.gate.resume()
        for point in [(-1,0), (1920,0), (0,1080), (float('nan'),1)]:
            with self.assertRaises(ValueError):
                self.actions.move(*point, duration=0)

    def test_esc_cannot_be_injected(self):
        self.gate.resume()
        with self.assertRaises(ValueError):
            self.actions.hotkey(['esc'])

    def test_pause_blocks_inputs(self):
        self.gate.resume()
        self.gate.pause()
        with self.assertRaises(ControlStopped):
            self.actions.type_text('private')
        self.assertFalse(self.keys.log)

    def test_hotkey_and_scroll_validation(self):
        self.gate.resume()
        self.actions.hotkey(['ctrl','s'])
        with self.assertRaises(ValueError):
            self.actions.scroll(99)
        self.assertIn(('combo', ('ctrl','s')), self.keys.log)

    def test_typing_is_layout_independent(self):
        self.gate.resume()
        self.actions.type_text('abc XYZ 123?', interval=0)
        self.assertEqual([e[1] for e in self.keys.log if e[0] == 'char'], list('abc XYZ 123?'))

    def test_virtual_keys_bypass_layout(self):
        for name, expected in [('a', 0x41), ('Z', 0x5A), ('7', 0x37), ('ctrl', 0x11), ('f5', 0x74)]:
            self.assertEqual(virtual_key(name), expected)
        with self.assertRaises(ValueError):
            virtual_key('я')

    def test_multi_monitor_negative_coordinates_and_gap(self):
        topology = DisplayTopology([Monitor('main', Rect(0,0,1920,1080),True),
                                    Monitor('left', Rect(-1280,100,1280,1024),False)])
        self.actions.topology_provider = lambda: topology
        self.gate.resume()
        self.actions.move(-1200, 150, 0)
        self.assertEqual((self.gui.x, self.gui.y), (-1200, 150))
        with self.assertRaises(ValueError):
            self.actions.move(-1200, 0, 0)  # virtual desktop gap
        self.actions.click(-100, 400)
        self.assertTrue(any(a[0] == 'click' for a in self.gui.log))

    def test_screenshot_monitor_selection_and_pause(self):
        self.actions.capture = lambda monitor: Image.new('RGB', (800, 600))
        with self.assertRaises(ControlStopped):
            self.actions.screenshot_png(600, 'left')
        self.gate.resume()
        result = self.actions.screenshot_png(600, 'left')
        self.assertEqual(Image.open(io.BytesIO(result)).size, (600, 450))
        with self.assertRaises(ValueError):
            self.actions.screenshot_png(600, None)

    def test_drag_releases_button_on_exception(self):
        self.gate.resume()
        original_move = self.actions.move
        def interrupted(*args, **kwargs):
            if args[0] == 500:
                self.gate.pause()
                raise ControlStopped('stopped')
            return original_move(*args, **kwargs)
        self.actions.move = interrupted
        with self.assertRaises(ControlStopped):
            self.actions.drag(200,300,500,600)
        self.assertEqual(self.gui.log[-1][0], 'up')


if __name__ == '__main__':
    unittest.main()
