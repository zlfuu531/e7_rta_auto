from battle_ai.windows import (user32 as _u32, RECT as _RECT, POINT as _POINT,
    find_window as _find_main_hwnd, content_metrics as _content_metrics,
    client_physical_size, physical_pixels, focus_window, profile_to_screen,
    resize_to_profile as _resize_physical)
import pyautogui
import time
import ctypes
import ctypes.wintypes as wt


_DEFAULT_TITLE = '第七史诗'
WINDOW_TITLE   = _DEFAULT_TITLE


def _get_cfg_exec() -> dict:
    try:
        from config_loader import cfg
        if cfg.is_loaded():
            return cfg.section('executor')
    except ImportError:
        pass
    return {}


def get_window_title() -> str:
    try:
        from config_loader import cfg
        if cfg.is_loaded():
            return cfg.window_title
    except ImportError:
        pass
    return _DEFAULT_TITLE


def _get_skill_pos() -> dict:
    return {k: tuple(v) for k, v in _get_cfg_exec()['skill_pos'].items()}

def _get_burn_pos() -> tuple:
    return tuple(_get_cfg_exec()['burn_pos'])

def _get_enemy_pos() -> list:
    return [tuple(p) for p in _get_cfg_exec()['enemy_pos']]


_win_offset = None
_dpi_scale = 1.0
_stop_event = None


def set_stop_event(event):
    global _stop_event
    _stop_event = event


def _check_input_stop():
    if _stop_event is not None:
        if _u32.GetAsyncKeyState(0x77) & 0x8000:  # F8
            _stop_event.set()
        if _stop_event.is_set():
            raise RuntimeError('自动操作已停止')


def _get_expected_resolution() -> tuple:
    try:
        from config_loader import cfg
        if cfg.is_loaded():
            r = cfg._profile.get('resolution', [1920, 1080])
            return (int(r[0]), int(r[1]))
    except Exception:
        pass
    return (1920, 1080)


def resize_to_profile(hwnd, target_w=None, target_h=None):
    if target_w is None or target_h is None:
        target_w, target_h = _get_expected_resolution()
    return _resize_physical(hwnd, target_w, target_h)


def _is_adb() -> bool:
    try:
        from config_loader import cfg
        return cfg.is_loaded() and cfg.input_method == 'adb'
    except ImportError:
        return False


# ── ADB 支持 ──────────────────────────────────────────────────
import os as _os
import subprocess as _subprocess

_NO_WINDOW = _subprocess.CREATE_NO_WINDOW

_adb_device: str = ''

def _get_adb_exe() -> str:
    import sys
    proj = getattr(sys, '_MEIPASS', _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    return _os.path.join(proj, 'platform-tools', 'adb.exe')

def set_device(address: str):
    global _adb_device
    _adb_device = address.strip()

def get_device() -> str:
    return _adb_device

def _adb(*args) -> '_subprocess.CompletedProcess':
    adb_exe = _get_adb_exe()
    cmd = [adb_exe]
    if _adb_device:
        cmd += ['-s', _adb_device]
    cmd += [str(a) for a in args]
    return _subprocess.run(cmd, capture_output=True, creationflags=_NO_WINDOW)

def adb_connect() -> bool:
    if not _adb_device:
        return False
    r = _adb('connect', _adb_device)
    ok = b'connected' in r.stdout.lower() or b'already' in r.stdout.lower()
    print(f"[ADB] connect {_adb_device} → {'OK' if ok else 'FAIL'}  {r.stdout.decode(errors='ignore').strip()}")
    return ok


def focus_game_window():
    if _is_adb():
        adb_connect()
        return
    global _win_offset, _dpi_scale, WINDOW_TITLE
    WINDOW_TITLE = get_window_title()
    hwnd = _find_main_hwnd(WINDOW_TITLE)
    if not hwnd:
        raise RuntimeError(f"找不到游戏窗口: {WINDOW_TITLE}")
    focus_window(hwnd)
    ox, oy, cw, ch = _content_metrics(hwnd)
    ew, eh = _get_expected_resolution()
    _win_offset = (ox, oy)
    _dpi_scale = cw / ew
    print(f'[focus] physical origin={_win_offset}, surface={cw}x{ch}, profile={ew}x{eh}')
    return _win_offset


def _screen_coordinates(x, y):
    _check_input_stop()
    hwnd = _find_main_hwnd(get_window_title())
    if not hwnd or _u32.GetForegroundWindow() != hwnd:
        raise RuntimeError('游戏失去焦点，已停止点击；请回到游戏后重新开始')
    return profile_to_screen(hwnd, x, y, _get_expected_resolution())


def _send_input_click(sx: int, sy: int):
    """用 SendInput 归一化绝对坐标点击，DPI 无关。"""
    physical_pixels()
    vw = _u32.GetSystemMetrics(78)   # SM_CXVIRTUALSCREEN
    vh = _u32.GetSystemMetrics(79)   # SM_CYVIRTUALSCREEN
    vl = _u32.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN（多显示器左偏移）
    vt = _u32.GetSystemMetrics(77)   # SM_YVIRTUALSCREEN（多显示器上偏移）
    nx = int((sx - vl) * 65535 / max(1, vw - 1))
    ny = int((sy - vt) * 65535 / max(1, vh - 1))

    MOVE  = 0x0001; DOWN = 0x0002; UP = 0x0004
    ABS   = 0x8000; VDESK = 0x4000
    flags_move = MOVE | ABS | VDESK
    flags_dn   = DOWN | ABS | VDESK
    flags_up   = UP   | ABS | VDESK

    class _MI(ctypes.Structure):
        _fields_ = [('dx',ctypes.c_long),('dy',ctypes.c_long),
                    ('mouseData',ctypes.c_ulong),('dwFlags',ctypes.c_ulong),
                    ('time',ctypes.c_ulong),('dwExtraInfo',ctypes.c_void_p)]
    class _IN(ctypes.Structure):
        _fields_ = [('type',ctypes.c_ulong),('mi',_MI)]

    arr = (_IN * 3)(
        _IN(0, _MI(nx, ny, 0, flags_move, 0, None)),
        _IN(0, _MI(nx, ny, 0, flags_dn,   0, None)),
        _IN(0, _MI(nx, ny, 0, flags_up,   0, None)),
    )
    _u32.SendInput.argtypes = [wt.UINT, ctypes.POINTER(_IN), ctypes.c_int]
    _u32.SendInput.restype = wt.UINT
    if _u32.SendInput(1, ctypes.byref(arr[0]), ctypes.sizeof(_IN)) != 1:
        raise RuntimeError('鼠标输入失败；游戏以管理员运行时请使用管理员启动器')
    time.sleep(0.02)
    if _u32.SendInput(1, ctypes.byref(arr[1]), ctypes.sizeof(_IN)) != 1:
        raise RuntimeError('鼠标按下失败，请检查脚本与游戏的权限')
    time.sleep(0.06)
    if _u32.SendInput(1, ctypes.byref(arr[2]), ctypes.sizeof(_IN)) != 1:
        raise RuntimeError('鼠标释放失败')


def _click(x, y, delay=0.4):
    _check_input_stop()
    if _is_adb():
        _adb('shell', 'input', 'tap', int(x), int(y))
        time.sleep(delay)
        return
    if _win_offset is None:
        raise RuntimeError("请先调用 focus_game_window()")
    _send_input_click(*_screen_coordinates(x, y))
    time.sleep(delay)


def click_skill(skill: str):
    pos = _get_skill_pos()
    assert skill in pos, f"未知技能: {skill}"
    _click(*pos[skill])


def click_target(idx: int):
    from battle_ai.perception import get_dynamic_click_pos
    pos = get_dynamic_click_pos(idx)
    if pos is None:
        enemy_pos = _get_enemy_pos()
        pos = enemy_pos[idx] if 0 <= idx < len(enemy_pos) else None
    if pos:
        _click(*pos)


def click_burn():
    _click(*_get_burn_pos())


def do_action(skill: str, target_idx: int, burn: bool = False):
    """单体技能：(可选)烧魂 → 单击技能按钮激活瞄准 → 单击目标"""
    if burn:
        click_burn()
    click_skill(skill)
    time.sleep(0.2)
    click_target(target_idx)


def do_aoe(skill: str, burn: bool = False):
    """群体技能：(可选)烧魂 → 快速双击技能按钮"""
    if burn:
        click_burn()
    pos = _get_skill_pos()
    x, y = pos[skill]
    if _is_adb():
        cmd = f'input tap {int(x)} {int(y)}; sleep 0.08; input tap {int(x)} {int(y)}'
        if _adb_device:
            _subprocess.run([_get_adb_exe(), '-s', _adb_device, 'shell', cmd],
                            capture_output=True, creationflags=_NO_WINDOW)
        else:
            _subprocess.run([_get_adb_exe(), 'shell', cmd],
                            capture_output=True, creationflags=_NO_WINDOW)
        time.sleep(0.4)
        return
    if _win_offset is None:
        raise RuntimeError("请先调用 focus_game_window()")
    sx, sy = _screen_coordinates(x, y)
    _send_input_click(sx, sy)
    time.sleep(0.05)
    _send_input_click(sx, sy)
    time.sleep(0.4)


def click_at(x: int, y: int, delay: float = 0.4):
    """点击窗口内任意坐标（客户区相对坐标）"""
    _click(x, y, delay)


def type_text(text: str):
    _check_input_stop()
    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.1)
    pyautogui.typewrite(text, interval=0.05)


def type_text_chinese(text: str):
    _check_input_stop()
    if _is_adb():
        try:
            from config_loader import cfg
            if cfg.is_loaded() and getattr(cfg, 'use_adbkeyboard', False):
                _adb('shell', 'am', 'broadcast', '-a', 'ADB_INPUT_TEXT', '--es', 'msg', text)
                time.sleep(0.2)
                return
        except Exception:
            pass
        _adb('shell', 'input', 'text', text)
        time.sleep(0.2)
        return
    _set_clipboard(text)
    time.sleep(0.1)
    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.05)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.2)


def _set_clipboard(text: str):
    import ctypes as c
    k = c.windll.kernel32
    u = c.windll.user32
    k.GlobalAlloc.restype   = c.c_void_p
    k.GlobalAlloc.argtypes  = [c.c_uint, c.c_size_t]
    k.GlobalLock.restype    = c.c_void_p
    k.GlobalLock.argtypes   = [c.c_void_p]
    k.GlobalUnlock.argtypes = [c.c_void_p]
    u.SetClipboardData.restype  = c.c_void_p
    u.SetClipboardData.argtypes = [c.c_uint, c.c_void_p]

    _clipboard_lock = __import__('threading').Lock()
    with _clipboard_lock:
        buf = (text + '\0').encode('utf-16-le')
        h = k.GlobalAlloc(0x0002, len(buf))
        if not h:
            raise RuntimeError('GlobalAlloc 失败')
        p = k.GlobalLock(h)
        if not p:
            raise RuntimeError('GlobalLock 失败')
        c.memmove(p, buf, len(buf))
        k.GlobalUnlock(h)
        for _ in range(20):
            if u.OpenClipboard(0):
                break
            time.sleep(0.05)
        else:
            raise RuntimeError('OpenClipboard 失败')
        u.EmptyClipboard()
        if not u.SetClipboardData(13, h):
            u.CloseClipboard()
            raise RuntimeError('SetClipboardData 失败')
        u.CloseClipboard()
