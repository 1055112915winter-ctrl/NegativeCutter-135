#!/usr/bin/env python3
"""测试通过 AppleScript 点击 FilmCrop 嵌套菜单"""
import subprocess

script = '''
tell application "Adobe Lightroom Classic"
    activate
end tell

delay 1

tell application "System Events"
    tell process "Adobe Lightroom Classic"
        -- 尝试列出增效工具额外信息下的菜单项
        try
            set pluginMenuItems to name of every menu item of menu 1 of menu item "增效工具额外信息" of menu 1 of menu bar item "文件" of menu bar 1
            return "Found plugin menu items: " & (pluginMenuItems as string)
        on error errMsg
            return "Failed to list: " & errMsg
        end try
    end tell
end tell
'''

result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
print(f"returncode: {result.returncode}")
print(f"stdout: {result.stdout}")
print(f"stderr: {result.stderr}")
