# -*- coding: utf-8 -*-
import datetime
import time
import subprocess

target_time = datetime.datetime(2026, 7, 14, 15, 50, 0)
print("Target time set to:", target_time)

while True:
    now = datetime.datetime.now()
    remaining = (target_time - now).total_seconds()
    if remaining <= 0:
        # 時間到了，發送通知 (採用微軟原生 Explorer 的 AppID，100% 能進入 Windows 通知欄)
        powershell_code = '''
        $appId = 'Microsoft.Windows.Explorer'
        $title = "風紀委員長 Hina 的會議提醒"
        $message = "蕭憶謙！15:50 的線上會議要開始了，快進會議室，別遲到了！"

        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] > $null
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $toastTextElements = $template.GetElementsByTagName("text")
        $toastTextElements.Item(0).AppendChild($template.CreateTextNode($title)) > $null
        $toastTextElements.Item(1).AppendChild($template.CreateTextNode($message)) > $null
        $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
        '''
        subprocess.run(["powershell", "-Command", powershell_code], capture_output=True)
        print("Toast sent successfully at 15:50.")
        break
    
    # 每 10 秒檢查一次，避免佔用 CPU
    time.sleep(10)
