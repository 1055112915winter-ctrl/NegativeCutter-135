#!/usr/bin/env python3
"""完整测试：确保 LR 状态正确后尝试 Help 搜索触发"""
import subprocess
import time

script = '''
tell application "Adobe Lightroom Classic"
    activate
end tell

delay 2

tell application "System Events"
    tell process "Adobe Lightroom Classic"
        -- 切换到 Library 模块
        keystroke "g" using command down
        delay 1

        -- 选择所有照片
        keystroke "a" using command down
        delay 0.5

        -- 切换到 Develop 模块
        keystroke "d" using command down
        delay 1

        -- 打开 Help 搜索
        keystroke "/" using {command down, shift down}
        delay 1

        -- 输入菜单名称
        keystroke "检测胶片帧"
        delay 1

        -- 按回车执行
        key code 36
    end tell
end tell
'''

print("1. 切换到 Library")
print("2. 选择所有照片")
print("3. 切换到 Develop")
print("4. Help 搜索 -> 检测胶片帧")
result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
print(f"returncode: {result.returncode}")
print(f"stdout: {result.stdout}")
print(f"stderr: {result.stderr}")
print("\n等待 30 秒让 FilmCrop 处理...")
