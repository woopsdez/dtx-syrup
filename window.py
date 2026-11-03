"""画面を「アプリの窓」で開く。Edge / Chrome / Brave の --app（アドレスバーもタブも無い 1 枚の窓）。

どれも無ければ既定のブラウザで普通に開く。黒いコンソールを出さずに使うため（pythonw / exe から呼ぶ）。
"""
from __future__ import annotations

import os
import subprocess
import webbrowser
from pathlib import Path

_NAMES = ('msedge.exe', 'chrome.exe', 'brave.exe')
_FALLBACK = [
    r'%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe',
    r'%ProgramFiles%\Microsoft\Edge\Application\msedge.exe',
    r'%ProgramFiles%\Google\Chrome\Application\chrome.exe',
    r'%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe',
    r'%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe',
    r'%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe',
]


def _app_paths() -> list[str]:
    try:
        import winreg
    except ImportError:
        return []
    found = []
    for name in _NAMES:
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(hive, rf'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{name}') as k:
                    found.append(winreg.QueryValue(k, None))
            except OSError:
                continue
    return found


def find_browser() -> str | None:
    for p in _app_paths() + [os.path.expandvars(x) for x in _FALLBACK]:
        p = (p or '').strip('"')
        if p and Path(p).exists():
            return p
    return None


def open_app(url: str) -> bool:
    exe = find_browser()
    if exe:
        try:
            subprocess.Popen([exe, f'--app={url}', '--window-size=1320,880'],
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            return True
        except OSError:
            pass
    return webbrowser.open(url)
