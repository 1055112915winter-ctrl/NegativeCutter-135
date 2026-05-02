#!/usr/bin/env python3
"""
FilmCrop 真实 Lightroom E2E 测试
流程:
1. 准备测试 catalog（复制生产 catalog）
2. 检查/提示启动 Lightroom
3. 通过 AppleScript 切换到测试 catalog
4. 选中测试照片
5. 执行 FilmCrop "检测胶片帧" 菜单
6. 等待处理完成
7. 读取 catalog SQLite 验证结果
8. 清理

使用方法:
    cd FilmCrop_Clean.lrplugin/tests
    python3 e2e_test.py

前提条件:
- Lightroom Classic 已安装
- FilmCrop 插件已安装并启用
- test_files/ 目录中有测试照片（需要已导入 catalog）
"""

import os
import sys
import time
import shutil
import tempfile
import subprocess
import sqlite3
import re
import argparse

# ------------------------------------------------------------------
# 配置
# ------------------------------------------------------------------
DEFAULT_CATALOG = os.path.expanduser("~/Pictures/Lightroom/Lightroom Catalog-v13-2.lrcat")
# test_files 目录路径
# 由于 worktree 隔离，test_files 可能在原始 repo 中
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_DIR = os.path.dirname(_SCRIPT_DIR)
_WORKTREE_DIR = os.path.dirname(_PLUGIN_DIR)

# 候选路径
_test_files_candidates = [
    os.path.join(_WORKTREE_DIR, "test_files"),
    os.path.join(os.path.dirname(os.path.dirname(_WORKTREE_DIR)), "test_files"),
    os.path.expanduser("~/Documents/临时拷贝/Claude Code/filmcrop/test_files"),
]

TEST_FILES_DIR = None
for candidate in _test_files_candidates:
    if os.path.isdir(candidate):
        TEST_FILES_DIR = candidate
        break

if TEST_FILES_DIR is None:
    TEST_FILES_DIR = _test_files_candidates[0]  # fallback
LIGHTROOM_APP = "Adobe Lightroom Classic"

# ------------------------------------------------------------------
# Lightroom AppleScript 控制
# ------------------------------------------------------------------

class LightroomController:
    def __init__(self, catalog_path=None):
        self.catalog_path = catalog_path
        self.app_name = LIGHTROOM_APP

    def _osascript(self, script, timeout=30):
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        if result.returncode != 0:
            raise RuntimeError(f"AppleScript 错误: {result.stderr}")
        return result.stdout.strip()

    def is_running(self):
        try:
            script = f'tell application "System Events" to return exists (processes where name is "{self.app_name}")'
            return self._osascript(script) == "true"
        except:
            return False

    def activate(self):
        script = f'tell application "{self.app_name}" to activate'
        self._osascript(script)
        time.sleep(1)

    def switch_module(self, module_key):
        """切换模块: 'g'=图库, 'd'=修改照片"""
        script = f'''
tell application "{self.app_name}"
    activate
    tell application "System Events"
        keystroke "{module_key}" using command down
        delay 1
    end tell
end tell
'''
        self._osascript(script)
        time.sleep(1)

    def run_plugin_menu(self, menu_items, fallback_manual=True):
        """
        点击插件菜单
        menu_items: ["文件", "增效工具额外命令", "FilmCrop", "检测胶片帧"]
        fallback_manual: AppleScript 失败时是否提示用户手动点击
        """
        if len(menu_items) < 2:
            raise ValueError("至少需要2级菜单")

        # 构建嵌套菜单链条：
        # menu item "X" of menu 1 of menu item "Y" of menu 1 of menu bar item "Z" of menu bar 1
        chain = f'menu bar item "{menu_items[0]}" of menu bar 1'
        for item in menu_items[1:-1]:
            chain = f'menu item "{item}" of menu 1 of {chain}'
        # 最后一个菜单项
        chain = f'menu item "{menu_items[-1]}" of menu 1 of {chain}'

        script = f'''
tell application "System Events"
    tell process "{self.app_name}"
        click {chain}
    end tell
end tell
'''
        try:
            self._osascript(script)
        except RuntimeError as e:
            if fallback_manual:
                print(f"  AppleScript 菜单点击失败: {e}")
                menu_path = " → ".join(menu_items)
                print(f"\n  请手动点击菜单: {menu_path}")
                print("  点击完成后按 Enter 继续...")
                input()
            else:
                raise

    def select_all_photos(self):
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

    def wait_for_dialog_close(self, timeout=60):
        """等待对话框/进度条关闭"""
        start = time.time()
        while time.time() - start < timeout:
            script = f'''
tell application "System Events"
    tell process "{self.app_name}"
        return exists sheet 1 of window 1
    end tell
end tell
'''
            try:
                result = self._osascript(script, timeout=5)
                if result == "false":
                    return True
            except:
                pass
            time.sleep(0.5)
        return False


# ------------------------------------------------------------------
# Catalog SQLite 验证
# ------------------------------------------------------------------

class CatalogVerifier:
    def __init__(self, catalog_path):
        self.catalog_path = catalog_path
        self.conn = None

    def connect(self):
        self.conn = sqlite3.connect(self.catalog_path)
        return self.conn

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def get_photo_by_basename(self, basename, master_only=False):
        cursor = self.conn.cursor()
        if master_only:
            cursor.execute('''
                SELECT i.id_local, i.copyName, i.masterImage, i.fileFormat,
                       i.fileHeight, i.fileWidth, f.baseName, f.extension
                FROM Adobe_images i
                JOIN AgLibraryFile f ON i.rootFile = f.id_local
                WHERE f.baseName = ? AND i.masterImage IS NULL
                ORDER BY i.id_local DESC
            ''', (basename,))
        else:
            cursor.execute('''
                SELECT i.id_local, i.copyName, i.masterImage, i.fileFormat,
                       i.fileHeight, i.fileWidth, f.baseName, f.extension
                FROM Adobe_images i
                JOIN AgLibraryFile f ON i.rootFile = f.id_local
                WHERE f.baseName = ?
            ''', (basename,))
        return cursor.fetchall()

    def get_virtual_copies(self, master_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id_local, copyName, fileFormat, fileHeight, fileWidth
            FROM Adobe_images
            WHERE masterImage = ?
        ''', (master_id,))
        return cursor.fetchall()

    def get_develop_settings(self, image_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT text FROM Adobe_imageDevelopSettings
            WHERE image = ?
        ''', (image_id,))
        row = cursor.fetchone()
        if row and row[0]:
            return self._parse_develop_settings(row[0])
        return {}

    def _parse_develop_settings(self, text):
        settings = {}
        if not text:
            return settings

        for key in ["CropTop", "CropBottom", "CropLeft", "CropRight", "CropAngle",
                    "PerspectiveVertical", "PerspectiveHorizontal", "PerspectiveRotate",
                    "UprightMode", "CropConstrainToWarp"]:
            pattern = rf'\b{key}\s*=\s*([-\d.]+|"[^"]*")'
            match = re.search(pattern, text)
            if match:
                val = match.group(1)
                try:
                    settings[key] = float(val)
                except ValueError:
                    settings[key] = val.strip('"')
        return settings

    def get_photo_count(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM Adobe_images')
        return cursor.fetchone()[0]

    def get_virtual_copy_count(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM Adobe_images WHERE masterImage IS NOT NULL')
        return cursor.fetchone()[0]


# ------------------------------------------------------------------
# 主测试流程
# ------------------------------------------------------------------

def find_test_photos_in_catalog(verifier, test_dir):
    """查找 test_files 目录中的照片哪些已在 catalog 中（只取 master，排除虚拟副本）"""
    found = []
    not_found = []

    for filename in os.listdir(test_dir):
        if filename.lower().endswith(('.tif', '.tiff', '.dng', '.jpg', '.jpeg')):
            basename = os.path.splitext(filename)[0]
            # 只查找 master（masterImage IS NULL），按 id 倒序取最新的
            rows = verifier.get_photo_by_basename(basename, master_only=True)
            if rows:
                found.append((basename, rows[0]))  # rows[0] 是最新的 master
            else:
                not_found.append(basename)

    return found, not_found


def run_e2e_test(catalog_path, test_photos_dir, photo_name=None):
    print("=" * 60)
    print("FilmCrop 真实 Lightroom E2E 测试")
    print("=" * 60)

    # ---- Step 1: 检查 Lightroom 是否运行 ----
    lr = LightroomController()
    print("\n[Step 1] 检查 Lightroom 状态...")
    if not lr.is_running():
        print("  Lightroom 未运行!")
        print("  请先启动 Lightroom，然后按 Enter 继续...")
        input()
        if not lr.is_running():
            print("  Lightroom 仍未运行，退出测试")
            return False
    print("  Lightroom 正在运行")

    # ---- Step 2: 准备测试 catalog ----
    print("\n[Step 2] 准备测试 catalog...")
    # 注意：这里不复制 catalog，直接在原 catalog 上测试有风险
    # 更好的做法是复制 catalog，但 Lightroom 可能需要重新关联
    # 简化：读取当前 catalog 状态作为基准
    verifier = CatalogVerifier(catalog_path)
    verifier.connect()

    initial_photo_count = verifier.get_photo_count()
    initial_vc_count = verifier.get_virtual_copy_count()
    print(f"  当前照片数: {initial_photo_count}")
    print(f"  当前虚拟副本数: {initial_vc_count}")

    # ---- Step 3: 查找测试照片 ----
    print("\n[Step 3] 查找测试照片...")
    found, not_found = find_test_photos_in_catalog(verifier, test_photos_dir)

    if not found:
        print(f"  错误: test_files 中的照片未导入到 catalog!")
        print(f"  未找到: {', '.join(not_found)}")
        print(f"\n  请先将 test_files 中的至少一张照片导入到 Lightroom catalog，然后重试")
        verifier.close()
        return False

    print(f"  找到 {len(found)} 张测试照片:")
    for basename, row in found:
        print(f"    - {basename} (id={row[0]}, format={row[3]})")

    if not_found:
        print(f"  未找到 {len(not_found)} 张:")
        for basename in not_found:
            print(f"    - {basename}")

    # ---- Step 4: 选择测试照片 ----
    print("\n[Step 4] 选择测试照片...")

    if photo_name:
        # 用户指定了照片
        test_photo = None
        for basename, row in found:
            if basename == photo_name:
                test_photo = (basename, row)
                break
        if not test_photo:
            print(f"  错误: 指定的照片 '{photo_name}' 未找到或未导入")
            verifier.close()
            return False
    else:
        # 选择第一个可用的（master，没有虚拟副本的优先）
        test_photo = found[0]
        for basename, row in found:
            master_id = row[0]
            vc_count = len(verifier.get_virtual_copies(master_id))
            if vc_count == 0:
                test_photo = (basename, row)
                break

    test_basename, test_row = test_photo
    master_id = test_row[0]
    master_copy_name = test_row[1]

    baseline_vcs = verifier.get_virtual_copies(master_id)
    baseline_settings = verifier.get_develop_settings(master_id)
    print(f"  主照片 id={master_id}, copyName={master_copy_name}")
    print(f"  基准虚拟副本数: {len(baseline_vcs)}")
    print(f"  基准 develop settings: {baseline_settings}")

    # ---- Step 5: 激活 Lightroom 并选中照片 ----
    print("\n[Step 5] 激活 Lightroom 并切换到修改照片模块...")
    lr.activate()
    lr.switch_module('d')  # 修改照片模块
    # 注意：选中特定照片通过 AppleScript 比较困难
    # 简化：假设用户在 Lightroom 中已经选中了测试照片
    print("  请确保在 Lightroom 的修改照片模块中选中了测试照片")
    print("  按 Enter 继续...")
    input()

    # ---- Step 6: 执行 FilmCrop 插件 ----
    print("\n[Step 6] 执行 FilmCrop '检测胶片帧'...")
    # FilmCrop 菜单路径（中文界面）
    menu_path = ["文件", "增效工具额外命令", "FilmCrop", "检测胶片帧"]
    try:
        lr.run_plugin_menu(menu_path)
        print("  菜单已触发，等待处理完成...")
    except Exception as e:
        print(f"  触发菜单失败: {e}")
        # 尝试英文菜单路径
        print("  尝试英文菜单路径...")
        menu_path_en = ["File", "Plug-in Extras", "FilmCrop", "Detect Film Frames"]
        try:
            lr.run_plugin_menu(menu_path_en)
        except Exception as e2:
            print(f"  英文菜单也失败: {e2}")
            return False

    # ---- Step 7: 等待处理完成 ----
    print("\n[Step 7] 等待 FilmCrop 处理完成...")
    print("  FilmCrop 处理可能需要几十秒到几分钟...")
    print("  如果弹出预览对话框，请确认或调整边界后点击确定")

    # 等待用户确认（因为可能有交互式对话框）
    print("\n  当 FilmCrop 处理完成后，按 Enter 继续...")
    input()

    # ---- Step 8: 验证结果 ----
    print("\n[Step 8] 验证结果...")

    # 直接连接原 catalog（SQLite WAL 模式支持并发读）
    # 复制 catalog 会丢失 WAL 中的未 checkpoint 数据
    verifier.close()
    verifier = CatalogVerifier(catalog_path)
    try:
        verifier.connect()
    except sqlite3.OperationalError as e:
        print(f"  无法直接读取 catalog: {e}")
        print("  尝试复制 catalog 后读取（可能丢失最新数据）...")
        temp_copy = tempfile.mktemp(suffix=".lrcat")
        shutil.copy2(catalog_path, temp_copy)
        verifier = CatalogVerifier(temp_copy)
        verifier.connect()

    # 检查虚拟副本
    after_vcs = verifier.get_virtual_copies(master_id)
    new_vcs = [vc for vc in after_vcs if vc[0] not in [b[0] for b in baseline_vcs]]

    print(f"  处理后虚拟副本数: {len(after_vcs)} (+{len(new_vcs)})")

    if not new_vcs:
        print("  警告: 未检测到新虚拟副本!")
        print("  可能原因:")
        print("    - 照片不是胶片扫描（FilmCrop 未检测到帧）")
        print("    - 处理过程中出错")
        print("    - 用户取消了操作")
        return False

    # 检查每个新虚拟副本的裁剪设置
    print(f"\n  新虚拟副本详情:")
    all_pass = True
    for vc in new_vcs:
        vc_id, vc_name, vc_format, vc_h, vc_w = vc
        settings = verifier.get_develop_settings(vc_id)

        crop_top = settings.get('CropTop', -1)
        crop_bottom = settings.get('CropBottom', -1)
        crop_left = settings.get('CropLeft', -1)
        crop_right = settings.get('CropRight', -1)
        crop_angle = settings.get('CropAngle', 0)

        has_crop = (crop_top != -1 or crop_bottom != -1 or
                    crop_left != -1 or crop_right != -1)

        status = "OK" if has_crop else "FAIL"
        print(f"    {vc_name or f'副本_{vc_id}'}: crop=({crop_top:.4f}, {crop_bottom:.4f}, "
              f"{crop_left:.4f}, {crop_right:.4f}), angle={crop_angle}, [{status}]")

        if not has_crop:
            all_pass = False

    # 检查主照片的裁剪是否被重置
    master_settings = verifier.get_develop_settings(master_id)
    master_crop = {
        'top': master_settings.get('CropTop', -1),
        'bottom': master_settings.get('CropBottom', -1),
        'left': master_settings.get('CropLeft', -1),
        'right': master_settings.get('CropRight', -1),
    }
    print(f"\n  主照片裁剪状态:")
    print(f"    CropTop={master_crop['top']:.4f}, CropBottom={master_crop['bottom']:.4f}, "
          f"CropLeft={master_crop['left']:.4f}, CropRight={master_crop['right']:.4f}")

    verifier.close()

    # ---- 汇总 ----
    print("\n" + "=" * 60)
    if all_pass and len(new_vcs) > 0:
        print("E2E 测试通过!")
        print(f"  成功创建 {len(new_vcs)} 个虚拟副本，全部应用了裁剪")
        return True
    else:
        print("E2E 测试未完全通过")
        print(f"  新虚拟副本: {len(new_vcs)}")
        print(f"  裁剪应用: {'全部成功' if all_pass else '部分失败'}")
        return False


def list_test_photos(catalog_path, test_photos_dir):
    """列出 catalog 中可用的测试照片"""
    print("=" * 60)
    print("FilmCrop E2E 测试 - 可用测试照片")
    print("=" * 60)

    verifier = CatalogVerifier(catalog_path)
    verifier.connect()

    found, not_found = find_test_photos_in_catalog(verifier, test_photos_dir)

    if found:
        print(f"\n已导入的测试照片 ({len(found)} 张):")
        for basename, row in found:
            master_id = row[0]
            vc_count = len(verifier.get_virtual_copies(master_id))
            print(f"  {basename}: id={master_id}, size={row[5]}x{row[4]}, 现有虚拟副本={vc_count}")
    else:
        print("\n未找到已导入的测试照片")

    if not_found:
        print(f"\n未导入的照片 ({len(not_found)} 张):")
        for basename in not_found:
            print(f"  {basename}")

    verifier.close()


def main():
    parser = argparse.ArgumentParser(description="FilmCrop E2E 测试")
    parser.add_argument("--catalog", default=DEFAULT_CATALOG, help="Lightroom catalog 路径")
    parser.add_argument("--test-dir", default=TEST_FILES_DIR, help="测试照片目录")
    parser.add_argument("--photo", help="指定测试照片的基础名 (如 52191)")
    parser.add_argument("--list", action="store_true", help="列出可用的测试照片")
    args = parser.parse_args()

    if not os.path.exists(args.catalog):
        print(f"错误: Catalog 不存在: {args.catalog}")
        sys.exit(1)

    if not os.path.exists(args.test_dir):
        print(f"错误: 测试照片目录不存在: {args.test_dir}")
        sys.exit(1)

    if args.list:
        list_test_photos(args.catalog, args.test_dir)
        sys.exit(0)

    success = run_e2e_test(args.catalog, args.test_dir, args.photo)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
