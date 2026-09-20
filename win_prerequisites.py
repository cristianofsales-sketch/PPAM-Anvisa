"""Stdlib-only Windows prerequisites, also used by the small installer."""
import sys

def runtime_available():
    if sys.platform != 'win32':
        return False
    import winreg
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
            try:
                with winreg.OpenKey(hive, r'SOFTWARE\Microsoft\EdgeUpdate\Clients', 0, winreg.KEY_READ | view) as clients:
                    for index in range(winreg.QueryInfoKey(clients)[0]):
                        with winreg.OpenKey(clients, winreg.EnumKey(clients, index)) as key:
                            try:
                                name = winreg.QueryValueEx(key, 'name')[0]
                                version = winreg.QueryValueEx(key, 'pv')[0]
                                if 'webview2' in name.lower() and version != '0.0.0.0':
                                    return True
                            except OSError:
                                pass
            except OSError:
                pass
    return False
