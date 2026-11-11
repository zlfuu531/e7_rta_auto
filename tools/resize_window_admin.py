"""Elevated resize helper; use the same physical-pixel implementation as the GUI."""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from battle_ai.executor import resize_to_profile
if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(1)
    with open(sys.argv[1], encoding='utf-8') as f:
        args = json.load(f)
    ok, message, _ = resize_to_profile(args['hwnd'], args['w'], args['h'])
    print(message)
    sys.exit(0 if ok else 3)
