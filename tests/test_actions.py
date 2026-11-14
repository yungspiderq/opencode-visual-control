import unittest
from actions import SafetyGate, DesktopActions, ControlStopped


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
    def hotkey(self, *keys, **kwargs): self.log.append(('hotkey',keys))
    def write(self, char): self.log.append(('write',char))
    def scroll(self, clicks): self.log.append(('scroll',clicks))


class TestDesktopActions(unittest.TestCase):
    def setUp(self):
        self.gate = SafetyGate()
        self.gui = FakeGui()
        self.actions = DesktopActions(self.gui, self.gate)

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
        self.assertFalse(self.gui.log)

    def test_hotkey_and_scroll_validation(self):
        self.gate.resume()
        self.actions.hotkey(['ctrl','s'])
        with self.assertRaises(ValueError):
            self.actions.scroll(99)
        self.assertIn(('hotkey', ('ctrl','s')), self.gui.log)

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
