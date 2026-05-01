#!/usr/bin/env python3
"""列出 Lightroom 增效工具额外信息子菜单下的所有菜单项"""
import subprocess

script = '''
tell application "Adobe Lightroom Classic"
    activate
end tell

delay 1

tell application "System Events"
    tell process "Adobe Lightroom Classic"
        -- 尝试获取增效工具额外信息下的菜单项
        try
            set pluginMenuItems to name of every menu item of menu 1 of menu item "增效工具额外信息" of menu 1 of menu bar item "文件" of menu bar 1
            return "增效工具额外信息: " & (pluginMenuItems as string)
        on error errMsg
            return "增效工具额外信息 failed: " & errMsg
        end try
    end tell
end tell
'''

result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
print(f"returncode: {result.returncode}")
print(f"stdout: {result.stdout}")
print(f"stderr: {result.stderr}")
