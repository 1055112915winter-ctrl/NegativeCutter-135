#!/usr/bin/env python3
"""测试通过 Help 搜索触发 Lightroom 菜单"""
import subprocess
import time

script = '''
tell application "Adobe Lightroom Classic"
    activate
end tell

delay 0.5

tell application "System Events"
    tell process "Adobe Lightroom Classic"
        -- 打开 Help 搜索 (Cmd+Shift+/)
        keystroke "/" using {command down, shift down}
        delay 0.8

        -- 输入菜单名称
        keystroke "检测胶片帧"
        delay 0.8

        -- 按回车执行
        key code 36
    end tell
end tell
'''

print("尝试通过 Help 搜索触发 '检测胶片帧'...")
result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
print(f"returncode: {result.returncode}")
print(f"stdout: {result.stdout}")
print(f"stderr: {result.stderr}")
