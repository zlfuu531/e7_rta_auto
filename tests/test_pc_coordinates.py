import threading
import unittest
from unittest.mock import patch

from battle_ai import windows, executor


class CoordinateTests(unittest.TestCase):
    def test_large_monitor_keeps_canonical_resolution(self):
        self.assertEqual(windows.fit_resolution((1920, 1080), (2538, 1470)), (1920, 1080))

    def test_1080p_monitor_leaves_space_for_taskbar_and_titlebar(self):
        self.assertEqual(windows.fit_resolution((1920, 1080), (1898, 993)), (1760, 990))

    def test_laptop_monitor_preserves_16_by_9(self):
        self.assertEqual(windows.fit_resolution((1920, 1080), (1344, 681)), (1200, 675))

    def test_fit_rejects_empty_work_area(self):
        with self.assertRaises(ValueError):
            windows.fit_resolution((1920, 1080), (0, 680))

    def test_negative_monitor_origin(self):
        with patch.object(windows, 'content_metrics', return_value=(-1931, 189, 1920, 1080)):
            self.assertEqual(windows.profile_to_screen(1, 960, 540, (1920, 1080)), (-971, 729))

    def test_profile_scaling_after_move(self):
        with patch.object(windows, 'content_metrics', side_effect=[
                (-2560, 100, 1280, 720), (50, 80, 1920, 1080)]):
            self.assertEqual(windows.profile_to_screen(1, 960, 540, (1920, 1080)), (-1920, 460))
            self.assertEqual(windows.profile_to_screen(1, 960, 540, (1920, 1080)), (1010, 620))

    def test_wrong_aspect_rejected(self):
        with patch.object(windows, 'content_metrics', return_value=(-2560, 34, 2560, 1494)):
            with self.assertRaises(RuntimeError):
                windows.profile_to_screen(1, 960, 540, (1920, 1080))

    def test_outside_profile_rejected(self):
        with patch.object(windows, 'content_metrics', return_value=(0, 0, 1920, 1080)):
            with self.assertRaises(ValueError):
                windows.profile_to_screen(1, 1920, 1080, (1920, 1080))

    def test_stop_blocks_input_before_sending(self):
        stop = threading.Event()
        stop.set()
        executor.set_stop_event(stop)
        try:
            with patch.object(executor, '_send_input_click') as send:
                with self.assertRaises(RuntimeError):
                    executor.click_at(500, 500, delay=0)
                send.assert_not_called()
        finally:
            executor.set_stop_event(None)


if __name__ == '__main__':
    unittest.main()
