"""Launch the PC controller at the integrity level required by the game."""
import ctypes
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    os.chdir(ROOT)
    if not ctypes.windll.shell32.IsUserAnAdmin():
        shell = ctypes.windll.shell32.ShellExecuteW
        shell.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
                          ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_int]
        shell.restype = ctypes.c_void_p
        args = subprocess.list2cmdline([str(Path(__file__).resolve())])
        result = shell(None, 'runas', sys.executable, args, str(ROOT), 0)
        if not result or result <= 32:
            print('启动已取消：电脑版游戏需要相同的管理员权限。')
            return 1
        return 0
    # Import in this order so DPI awareness is established before tkinter.
    sys.path.insert(0, str(ROOT))
    try:
        from auto_run_gui import AutoRunApp, tk
        root = tk.Tk()
        AutoRunApp(root)
        root.mainloop()
    except Exception:
        import traceback
        details = traceback.format_exc()
        (ROOT / 'startup_error.log').write_text(details, encoding='utf-8')
        ctypes.windll.user32.MessageBoxW(None,
            '启动失败，详情见项目目录 startup_error.log。请先运行 setup.bat 安装依赖。',
            '第七史诗 RTA', 0x10)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
