"""Windows の通知（トースト）を出す。標準ライブラリ + Windows PowerShell 5.1 の WinRT だけで動く。

譜面ができたときなど、ブラウザを開いていなくても気づけるように使う。通知には Windows の既定の音が付く。
失敗しても例外は出さない（通知は付録）。
"""
from __future__ import annotations

import os
import subprocess
import sys

# PowerShell 自身の AppUserModelID。これで送ると「Windows PowerShell」名義の通知になる
_APP_ID = r'{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
_SCRIPT = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
$t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$n = $t.GetElementsByTagName('text')
$n.Item(0).AppendChild($t.CreateTextNode($env:DTXS_TITLE)) | Out-Null
$n.Item(1).AppendChild($t.CreateTextNode($env:DTXS_BODY)) | Out-Null
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:DTXS_APP).Show([Windows.UI.Notifications.ToastNotification]::new($t))
"""
ENABLED = os.environ.get('DTX_SYRUP_NOTIFY', '1') != '0'   # テストや CI では 0 にする


def toast(title: str, body: str) -> bool:
    if not ENABLED or sys.platform != 'win32':
        return False
    env = dict(os.environ, DTXS_TITLE=title[:120], DTXS_BODY=body[:240], DTXS_APP=_APP_ID)
    try:
        subprocess.Popen(['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command', _SCRIPT],
                         env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return True
    except OSError:
        return False
