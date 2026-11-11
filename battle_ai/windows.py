"""Win32 geometry in physical pixels, shared by capture, resize and input."""
import ctypes as c
from ctypes import wintypes as w
import time
import math

user32 = c.WinDLL('user32', use_last_error=True)


def _api(name, result, *args):
    fn = getattr(user32, name)
    fn.restype, fn.argtypes = result, list(args)
    return fn


_set_process_dpi = _api('SetProcessDpiAwarenessContext', w.BOOL, c.c_void_p)
_set_thread_dpi = _api('SetThreadDpiAwarenessContext', c.c_void_p, c.c_void_p)


def physical_pixels():
    # Also covers workers and entry points imported after another UI library.
    if not _set_thread_dpi(c.c_void_p(-4)):
        raise c.WinError(c.get_last_error())


# Must precede tkinter/pyautogui imports and creation of any application window.
_set_process_dpi(c.c_void_p(-4))
physical_pixels()

RECT, POINT = w.RECT, w.POINT
ENUMPROC = c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
_api('FindWindowW', w.HWND, w.LPCWSTR, w.LPCWSTR)
_api('GetForegroundWindow', w.HWND)
_api('GetClientRect', w.BOOL, w.HWND, c.POINTER(RECT))
_api('GetWindowRect', w.BOOL, w.HWND, c.POINTER(RECT))
_api('ClientToScreen', w.BOOL, w.HWND, c.POINTER(POINT))
_api('GetClassNameW', c.c_int, w.HWND, w.LPWSTR, c.c_int)
_api('GetWindowTextLengthW', c.c_int, w.HWND)
_api('GetWindowTextW', c.c_int, w.HWND, w.LPWSTR, c.c_int)
_api('EnumWindows', w.BOOL, ENUMPROC, w.LPARAM)
_api('EnumChildWindows', w.BOOL, w.HWND, ENUMPROC, w.LPARAM)
for _name in ('IsWindow', 'IsWindowVisible', 'IsIconic', 'IsZoomed', 'SetForegroundWindow'):
    _api(_name, w.BOOL, w.HWND)
_api('ShowWindow', w.BOOL, w.HWND, c.c_int)
_api('SetWindowPos', w.BOOL, w.HWND, w.HWND, c.c_int, c.c_int,
     c.c_int, c.c_int, w.UINT)
_api('MonitorFromWindow', w.HMONITOR, w.HWND, w.DWORD)
_api('GetDpiForWindow', w.UINT, w.HWND)
_api('GetCursorPos', w.BOOL, c.POINTER(POINT))
_api('SetCursorPos', w.BOOL, c.c_int, c.c_int)


class MONITORINFO(c.Structure):
    _fields_ = [('cbSize', w.DWORD), ('rcMonitor', RECT), ('rcWork', RECT),
                ('dwFlags', w.DWORD)]


_api('GetMonitorInfoW', w.BOOL, w.HMONITOR, c.POINTER(MONITORINFO))


def window_class(hwnd):
    buf = c.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, len(buf))
    return buf.value


def find_window(title):
    physical_pixels()
    # An explicit PC selection must never silently target an emulator/launcher.
    return user32.FindWindowW(None, title)


def content_metrics(hwnd):
    """Return the physical screen origin and dimensions of the game surface."""
    physical_pixels()
    if not user32.IsWindow(hwnd) or user32.IsIconic(hwnd):
        raise RuntimeError('游戏窗口已关闭或最小化')
    rc, pt = RECT(), POINT()
    if not user32.GetClientRect(hwnd, c.byref(rc)):
        raise c.WinError(c.get_last_error())
    target = hwnd
    width, height = rc.right, rc.bottom
    if window_class(hwnd) != 'GLFW30':
        candidates = []

        def child(ch, _):
            r = RECT()
            user32.GetClientRect(ch, c.byref(r))
            if (user32.IsWindowVisible(ch) and r.right >= 200 and r.bottom >= 200
                    and 1.6 <= r.right / r.bottom <= 1.9):
                candidates.append((r.right * r.bottom, ch, r.right, r.bottom))
            return True

        user32.EnumChildWindows(hwnd, ENUMPROC(child), 0)
        if candidates:
            _, target, width, height = max(candidates)
    if width <= 0 or height <= 0:
        raise RuntimeError('游戏客户区为空')
    user32.ClientToScreen(target, c.byref(pt))
    return pt.x, pt.y, width, height


def client_physical_size(hwnd):
    _, _, width, height = content_metrics(hwnd)
    return width, height, user32.GetDpiForWindow(hwnd) / 96


def focus_window(hwnd):
    physical_pixels()
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)
        time.sleep(0.3)
    if user32.GetForegroundWindow() != hwnd:
        user32.keybd_event(0x12, 0, 0, 0)
        user32.SetForegroundWindow(hwnd)
        user32.keybd_event(0x12, 0, 2, 0)
        time.sleep(0.25)
    if user32.GetForegroundWindow() != hwnd:
        raise RuntimeError('无法聚焦游戏；若游戏以管理员运行，请使用管理员启动器')


def fit_resolution(resolution, available):
    """Fit the canonical profile into the work area, retaining its exact ratio."""
    width, height = resolution
    available_w, available_h = available
    if min(width, height, available_w, available_h) <= 0:
        raise ValueError('屏幕可用区域或目标分辨率无效')
    divisor = math.gcd(width, height)
    unit_w, unit_h = width // divisor, height // divisor
    units = min(divisor, available_w // unit_w, available_h // unit_h)
    if units < 1:
        raise ValueError('屏幕可用区域过小')
    return units * unit_w, units * unit_h


def resize_to_profile(hwnd, target_w, target_h):
    """Resize and verify the actual surface; never report success on API return alone."""
    physical_pixels()
    if not user32.IsWindow(hwnd):
        return False, '窗口已关闭', 0
    if user32.IsIconic(hwnd) or user32.IsZoomed(hwnd):
        user32.ShowWindow(hwnd, 9)
        time.sleep(0.4)
    monitor = MONITORINFO()
    monitor.cbSize = c.sizeof(monitor)
    if not user32.GetMonitorInfoW(user32.MonitorFromWindow(hwnd, 2), c.byref(monitor)):
        return False, '无法读取游戏所在显示器', c.get_last_error()
    work = monitor.rcWork
    wr = RECT()
    user32.GetWindowRect(hwnd, c.byref(wr))
    _, _, cw, ch = content_metrics(hwnd)
    available = (work.right - work.left - (wr.right - wr.left - cw),
                 work.bottom - work.top - (wr.bottom - wr.top - ch))
    canonical = (target_w, target_h)
    try:
        target_w, target_h = fit_resolution(canonical, available)
    except ValueError as error:
        return False, str(error), 0

    def describe(width, height):
        message = f'已验证游戏画面 {width}×{height}（物理像素）'
        if (width, height) != canonical:
            message += f'；已适应屏幕，识别坐标保持 {canonical[0]}×{canonical[1]}'
        return message

    for _ in range(4):
        _, _, cw, ch = content_metrics(hwnd)
        if (cw, ch) == (target_w, target_h):
            return True, describe(cw, ch), 0
        wr = RECT()
        user32.GetWindowRect(hwnd, c.byref(wr))
        ow = wr.right - wr.left + target_w - cw
        oh = wr.bottom - wr.top + target_h - ch
        if ow > work.right - work.left or oh > work.bottom - work.top:
            return False, '目标窗口超出屏幕可用区域，请选择更小分辨率', 0
        x = max(work.left, min(wr.left, work.right - ow))
        y = max(work.top, min(wr.top, work.bottom - oh))
        c.set_last_error(0)
        if not user32.SetWindowPos(hwnd, None, x, y, ow, oh, 0x0004 | 0x0010):
            error = c.get_last_error()
            return False, f'调整窗口失败（Win32 {error}）', error
        time.sleep(0.25)
    _, _, cw, ch = content_metrics(hwnd)
    ok = (cw, ch) == (target_w, target_h)
    return ok, (describe(cw, ch) if ok else
                f'实际游戏画面 {cw}×{ch}，目标 {target_w}×{target_h}'), 0


def profile_to_screen(hwnd, x, y, resolution):
    ox, oy, width, height = content_metrics(hwnd)
    ew, eh = resolution
    if abs(width / height - ew / eh) > 0.01:
        raise RuntimeError('游戏画面比例发生变化，请停止后重新设置窗口')
    if not (0 <= x < ew and 0 <= y < eh):
        raise ValueError(f'坐标超出游戏画面: {x}, {y}')
    return round(ox + x * width / ew), round(oy + y * height / eh)
