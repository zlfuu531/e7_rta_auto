"""Read-only PC diagnostics; --resize explicitly adjusts the game window."""
import argparse
import json
import os
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
OUT = ROOT / 'diagnostics'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resize', action='store_true')
    parser.add_argument('--model', action='store_true')
    parser.add_argument('--test-navigation', action='store_true',
                        help='Open the mock-battle tab, then restore ranked lobby; no matchmaking')
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    report = {}
    try:
        from config_loader import cfg
        cfg.load('第七史诗')
        cfg.input_method = 'pc'
        from battle_ai import executor as ex
        from battle_ai.windows import window_class
        h = ex._find_main_hwnd(cfg.window_title)
        if not h:
            raise RuntimeError('请先启动电脑版第七史诗')
        report['window'] = {'hwnd': h, 'class': window_class(h)}
        report['before'] = ex.client_physical_size(h)
        if args.resize:
            ok, message, code = ex.resize_to_profile(h)
            report['resize'] = {'ok': ok, 'message': message, 'error': code}
            if not ok:
                raise RuntimeError(message)
        ex.focus_game_window()
        report['surface'] = ex._content_metrics(h)
        report['size'] = ex.client_physical_size(h)
        from battle_ai.perception import capture
        from PIL import Image
        frame = capture()
        Image.fromarray(frame).save(OUT / 'pc_capture.png')
        report['capture_shape'] = list(frame.shape)
        report['capture_mean'] = float(frame.mean())
        from battle_ai import lobby
        if args.test_navigation and not lobby.is_in_lobby(frame):
            ex.click_at(1740, 160, delay=3.0)
            frame = capture()
        report['lobby_recognized'] = bool(lobby.is_in_lobby(frame))
        report['lobby_ncc'] = lobby._btn_ncc(frame, lobby._lobby_tmpl)
        report['mapped_points'] = [ex._screen_coordinates(x, y) for x, y in
                                   [(0, 0), (960, 540), (1919, 1079)]]
        if args.test_navigation:
            if window_class(h) != 'GLFW30' or not report['lobby_recognized']:
                raise RuntimeError('点击验证仅支持已识别的电脑版RTA大厅')
            import time
            import numpy as np
            try:
                ex.click_at(1740, 300, delay=1.5)
                mock_frame = capture()
                Image.fromarray(mock_frame).save(OUT / 'navigation_mock.png')
                difference = float(np.abs(mock_frame.astype(float) - frame).mean())
                report['navigation_difference'] = difference
                if difference < 5:
                    raise RuntimeError('点击后画面未变化，输入可能被游戏阻止')
            finally:
                # The client may ignore input briefly while the room list loads.
                for _ in range(3):
                    ex.click_at(1740, 160, delay=2.0)
                    if lobby.is_in_lobby(capture()):
                        break
            restored = capture()
            Image.fromarray(restored).save(OUT / 'navigation_restored.png')
            report['navigation_restored_lobby'] = bool(lobby.is_in_lobby(restored))
            if not report['navigation_restored_lobby']:
                raise RuntimeError('验证后尚未识别到排名战大厅')
        if args.model:
            from transformer_inference import DraftRecommender
            model = DraftRecommender(str(ROOT/'draft_transformer.pth'),
                                     str(ROOT/'hero_list_146.json'))
            recs = model.recommend([], [], [], top_k=3)
            report['model'] = {'device': str(model.device), 'recommendations': recs}
        report['ok'] = True
    except Exception:
        report['ok'] = False
        report['error'] = traceback.format_exc()
    (OUT / 'pc_check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                                 default=str), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
