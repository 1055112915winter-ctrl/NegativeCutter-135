#!/usr/bin/env python3
"""
真实 Lightroom 自动化控制模块
通过 AppleScript 控制 Lightroom Classic 执行插件菜单
"""

import subprocess
import time
import os
import shutil
import tempfile


class LightroomController:
    """通过 AppleScript 控制 Lightroom Classic"""

    def __init__(self, catalog_path=None):
        self.catalog_path = catalog_path
        self.app_name = "Adobe Lightroom Classic"

    def _osascript(self, script):
        """执行 AppleScript，返回输出"""
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            raise RuntimeError(f"AppleScript 失败: {result.stderr}")
        return result.stdout.strip()

    def is_running(self):
        """检查 Lightroom 是否在运行"""
        try:
            script = f'tell application "System Events" to return exists (processes where name is "{self.app_name}")'
            result = self._osascript(script)
            return result == "true"
        except:
            return False

    def activate(self):
        """激活 Lightroom 窗口"""
        script = f'tell application "{self.app_name}" to activate'
        self._osascript(script)
        time.sleep(1)

    def open_catalog(self, catalog_path):
        """打开指定 catalog"""
        # Lightroom 只能同时打开一个 catalog，需要先关闭当前的
        script = f'''
tell application "{self.app_name}"
    activate
    -- 尝试打开 catalog（如果已经打开同一个则跳过）
    try
        open POSIX file "{catalog_path}"
        delay 3
    end try
end tell
'''
        self._osascript(script)
        # 等待 catalog 加载
        time.sleep(5)

    def select_folder_by_path(self, folder_path):
        """在图库模块中选择指定文件夹（通过路径）"""
        # 这个比较复杂，需要通过 Lightroom 的菜单系统
        # 简化方案：使用快捷键切换到图库模块，然后选择所有照片
        script = f'''
tell application "{self.app_name}"
    activate
    -- 切换到图库模块（快捷键 G）
    tell application "System Events"
        keystroke "g" using command down
        delay 1
    end tell
end tell
'''
        self._osascript(script)
        time.sleep(1)

    def select_all_photos(self):
        """选择所有照片"""
        script = f'''
tell application "{self.app_name}"
    activate
    tell application "System Events"
        keystroke "a" using command down
        delay 0.5
    end tell
end tell
'''
        self._osascript(script)
        time.sleep(0.5)

    def run_plugin_menu(self, menu_path):
        """
        执行插件菜单命令
        menu_path: 菜单路径列表，如 ["文件", "增效工具额外命令", "FilmCrop", "检测胶片帧"]
        """
        if len(menu_path) < 2:
            raise ValueError("menu_path 至少需要两级菜单")

        # 构建 AppleScript 菜单点击
        menu_items = ", ".join([f'"{item}"' for item in menu_path])
        script = f'''
tell application "System Events"
    tell process "{self.app_name}"
        click menu item {menu_items} of menu 1 of menu bar item "{menu_path[0]}" of menu bar 1
    end tell
end tell
'''
        self._osascript(script)

    def switch_to_develop_module(self):
        """切换到修改照片模块"""
        script = f'''
tell application "{self.app_name}"
    activate
    tell application "System Events"
        keystroke "d" using command down
        delay 1
    end tell
end tell
'''
        self._osascript(script)
        time.sleep(1)

    def wait_for_idle(self, timeout_seconds=60):
        """等待 Lightroom 空闲（没有进度条/对话框）"""
        start = time.time()
        while time.time() - start < timeout_seconds:
            # 检查是否有对话框或进度条
            script = f'''
tell application "System Events"
    tell process "{self.app_name}"
        return exists sheet 1 of window 1
    end tell
end tell
'''
            try:
                result = self._osascript(script)
                if result == "false":
                    return True
            except:
                pass
            time.sleep(1)
        raise TimeoutError(f"等待 Lightroom 空闲超时 ({timeout_seconds}s)")

    def get_selected_photo_count(self):
        """获取当前选中的照片数量"""
        # 这个需要通过 Lightroom SDK 或读取 catalog
        # 简化：返回 1（假设已选中）
        return 1


class CatalogVerifier:
    """通过 SQLite 读取 catalog 验证插件执行结果"""

    def __init__(self, catalog_path):
        self.catalog_path = catalog_path
        self._conn = None

    def _connect(self):
        import sqlite3
        if self._conn is None:
            self._conn = sqlite3.connect(self.catalog_path)
        return self._conn

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def get_photo_by_basename(self, basename):
        """通过文件名基础名查找照片"""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT i.id_local, i.copyName, i.masterImage, i.fileFormat,
                   i.fileHeight, i.fileWidth, f.baseName, f.extension
            FROM Adobe_images i
            JOIN AgLibraryFile f ON i.rootFile = f.id_local
            WHERE f.baseName = ?
        ''', (basename,))
        return cursor.fetchall()

    def get_virtual_copies(self, master_id):
        """获取指定主照片的虚拟副本"""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id_local, copyName, fileFormat, fileHeight, fileWidth
            FROM Adobe_images
            WHERE masterImage = ?
        ''', (master_id,))
        return cursor.fetchall()

    def get_develop_settings(self, image_id):
        """获取照片的开发设置"""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT text FROM Adobe_imageDevelopSettings
            WHERE image = ?
        ''', (image_id,))
        row = cursor.fetchone()
        if row and row[0]:
            return self._parse_develop_settings(row[0])
        return {}

    def _parse_develop_settings(self, text):
        """解析 Lua 格式的开发设置字符串"""
        settings = {}
        if not text:
            return settings

        # 简单解析：提取 key = value 对
        # 格式: s = { key = value, key2 = "string", ... }
        # 移除前缀 "s = {"
        content = text
        if content.startswith("s = {"):
            content = content[5:]
        if content.rstrip().endswith("}"):
            content = content.rstrip()[:-1]

        # 提取 Crop 相关设置
        for key in ["CropTop", "CropBottom", "CropLeft", "CropRight", "CropAngle",
                    "PerspectiveVertical", "PerspectiveHorizontal", "PerspectiveRotate",
                    "UprightMode"]:
            pattern = rf'\b{key}\s*=\s*([-\d.]+|"[^"]*")'
            import re
            match = re.search(pattern, text)
            if match:
                val = match.group(1)
                try:
                    settings[key] = float(val)
                except ValueError:
                    settings[key] = val.strip('"')

        return settings

    def get_photo_count(self):
        """获取 catalog 中的照片总数"""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM Adobe_images')
        return cursor.fetchone()[0]

    def get_virtual_copy_count(self):
        """获取虚拟副本数量"""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM Adobe_images WHERE masterImage IS NOT NULL')
        return cursor.fetchone()[0]


def prepare_test_catalog(source_catalog, test_photos_dir):
    """
    准备测试 catalog
    复制生产 catalog，确保 test_photos 中的照片已导入
    """
    # 创建临时目录
    test_dir = tempfile.mkdtemp(prefix="filmcrop_e2e_")
    test_catalog = os.path.join(test_dir, "TestCatalog.lrcat")

    # 复制 catalog
    shutil.copy2(source_catalog, test_catalog)

    # 复制辅助文件（previews 等，可选）
    source_preview = source_catalog + "-previews.lrdata"
    if os.path.exists(source_preview):
        test_preview = test_catalog + "-previews.lrdata"
        shutil.copytree(source_preview, test_preview, ignore_dangling_symlinks=True)

    return test_catalog, test_dir


def cleanup_test_catalog(test_catalog, test_dir):
    """清理测试 catalog"""
    if os.path.exists(test_catalog):
        os.remove(test_catalog)
    # 清理 preview 目录
    preview_dir = test_catalog + "-previews.lrdata"
    if os.path.exists(preview_dir):
        shutil.rmtree(preview_dir)
    # 清理临时目录
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)


if __name__ == "__main__":
    # 简单测试
    print("Lightroom 控制器测试")

    lr = LightroomController()
    print(f"Lightroom 运行中: {lr.is_running()}")

    if lr.is_running():
        print("激活 Lightroom...")
        lr.activate()
        print("切换到修改照片模块...")
        lr.switch_to_develop_module()
        print("测试完成")
    else:
        print("Lightroom 未运行，请先启动")
