#!/usr/bin/env python3
"""列出 Lightroom 文件菜单下的所有菜单项"""
import subprocess

script = '''
tell application "Adobe Lightroom Classic"
    activate
end tell

delay 1

tell application "System Events"
    tell process "Adobe Lightroom Classic"
        set menuItems to name of every menu item of menu 1 of menu bar item "文件" of menu bar 1
        return menuItems as string
    end tell
end tell
'''

result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
print(f"returncode: {result.returncode}")
print(f"stdout: {result.stdout}")
print(f"stderr: {result.stderr}")
