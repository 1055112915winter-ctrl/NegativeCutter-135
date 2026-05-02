#!/usr/bin/env python3
"""
FilmCrop 全自动 Lightroom E2E 测试（JSON 触发模式）

用法:
    python3 e2e_auto.py --wait 120

流程（全自动，无需点击菜单）：
1. 读取 catalog 当前状态（基准）
2. 自动激活 Lightroom，切换到修改照片模块
3. 用 Python 检测脚本生成 JSON 文件到 /tmp/filmcrop_e2e.json
4. 等待 N 秒（默认 90 秒），期间 FilmCrop 自动检测模式会处理 JSON
5. 时间到后自动读取 catalog 新状态
6. 对比并报告结果

前提条件：
- Lightroom 正在运行
- 已在修改照片模块中选中了测试照片
- 已手动启动 FilmCrop「自动检测 (E2E)」模式（只需启动一次）

返回码：0=通过, 1=失败, 2=Lightroom 未运行
"""

import os
import sys
import time
import shutil
import tempfile
import sqlite3
import re
import argparse
import subprocess
import json

# ------------------------------------------------------------------
# 配置
# ------------------------------------------------------------------
DEFAULT_CATALOG = os.path.expanduser("~/Pictures/Lightroom/Lightroom Catalog-v13-2.lrcat")
LIGHTROOM_APP = "Adobe Lightroom Classic"

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_DIR = os.path.dirname(_SCRIPT_DIR)
_WORKTREE_DIR = os.path.dirname(_PLUGIN_DIR)
AUTO_JSON_PATH = os.path.join(_PLUGIN_DIR, "filmcrop_e2e.json")

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
    TEST_FILES_DIR = _test_files_candidates[0]

DETECTOR_SCRIPT = os.path.join(_PLUGIN_DIR, "detect_thumb.py")


# ------------------------------------------------------------------
# Lightroom 控制
# ------------------------------------------------------------------

class LightroomController:
    def __init__(self):
        self.app_name = LIGHTROOM_APP

    def _osascript(self, script, timeout=10):
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=timeout
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()

    def is_running(self, retries=3):
        for i in range(retries):
            ok, out, err = self._osascript(
                f'tell application "System Events" to return exists (processes where name is "{self.app_name}")'
            )
            if ok and out == "true":
                return True
            if "-600" in err or "procNotFound" in err or "应用程序没有运行" in err:
                # Lightroom 可能正在启动中，等待后重试
                if i < retries - 1:
                    time.sleep(5)
                    continue
            # 最后一次也失败
            return False
        return False

    def can_use_applescript(self):
        """检测 AppleScript/System Events 是否可用"""
        ok, _, err = self._osascript(
            'tell application "System Events" to return name of first process'
        )
        return ok

    def activate(self):
        self._osascript(f'tell application "{self.app_name}" to activate')

    def switch_to_develop(self):
        script = f'''
tell application "{self.app_name}"
    activate
    tell application "System Events"
        keystroke "d" using command down
        delay 0.5
    end tell
end tell
'''
        self._osascript(script)

    def select_all_photos(self):
        """在图库模块中选择所有照片，然后切换到 develop"""
        script = f'''
tell application "{self.app_name}"
    activate
    tell application "System Events"
        keystroke "g" using command down
        delay 0.5
        keystroke "a" using command down
        delay 0.5
        keystroke "d" using command down
        delay 0.5
    end tell
end tell
'''
        self._osascript(script)


# ------------------------------------------------------------------
# Catalog 验证
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

    def get_test_photo_masters(self):
        """返回测试照片的 master 记录（可能有多个同名）"""
        results = {}
        cursor = self.conn.cursor()
        for basename in ['52191', '52194', 'luckyc20013']:
            cursor.execute('''
                SELECT i.id_local, i.fileHeight, i.fileWidth, i.fileFormat
                FROM Adobe_images i
                JOIN AgLibraryFile f ON i.rootFile = f.id_local
                WHERE f.baseName = ? AND i.masterImage IS NULL
                ORDER BY i.id_local DESC
            ''', (basename,))
            rows = cursor.fetchall()
            results[basename] = rows  # list of (id, height, width, format)
        return results

    def get_virtual_copies(self, master_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id_local, copyName, fileFormat, fileHeight, fileWidth
            FROM Adobe_images WHERE masterImage = ?
        ''', (master_id,))
        return cursor.fetchall()

    def get_develop_settings(self, image_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT text FROM Adobe_imageDevelopSettings WHERE image = ?', (image_id,))
        row = cursor.fetchone()
        if not row or not row[0]:
            return {}
        text = row[0]
        settings = {}
        for key in ["CropTop", "CropBottom", "CropLeft", "CropRight", "CropAngle",
                    "PerspectiveVertical", "PerspectiveHorizontal", "PerspectiveRotate",
                    "UprightMode", "CropConstrainToWarp"]:
            m = re.search(rf'\b{key}\s*=\s*([-\d.]+|"[^"]*")', text)
            if m:
                try:
                    settings[key] = float(m.group(1))
                except ValueError:
                    settings[key] = m.group(1).strip('"')
        return settings

    def get_all_virtual_copies(self):
        """获取所有虚拟副本，用于 diff"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT i.id_local, i.copyName, i.masterImage, f.baseName
            FROM Adobe_images i
            JOIN AgLibraryFile f ON i.rootFile = f.id_local
            WHERE i.masterImage IS NOT NULL
        ''')
        return {row[0]: row for row in cursor.fetchall()}


def copy_catalog_for_reading(src_path):
    """复制 catalog 到临时位置（避免 WAL 锁定）"""
    tmpdir = tempfile.mkdtemp(prefix="filmcrop_e2e_")
    base = os.path.basename(src_path)
    dst = os.path.join(tmpdir, base)
    shutil.copy2(src_path, dst)
    # 也复制 WAL/shm 文件
    for ext in ['-wal', '-shm']:
        src_ext = src_path + ext
        if os.path.exists(src_ext):
            shutil.copy2(src_ext, dst + ext)
    return dst, tmpdir


def cleanup_copy(dst, tmpdir):
    if os.path.exists(dst):
        os.remove(dst)
    for ext in ['-wal', '-shm']:
        if os.path.exists(dst + ext):
            os.remove(dst + ext)
    if os.path.exists(tmpdir):
        shutil.rmtree(tmpdir)


# ------------------------------------------------------------------
# JSON 生成
# ------------------------------------------------------------------

def generate_json_for_photo(photo_path, expected_frames=6):
    """用 Python 检测脚本生成 JSON 文件"""
    if not os.path.exists(DETECTOR_SCRIPT):
        print(f"  错误: 检测脚本不存在: {DETECTOR_SCRIPT}")
        return False

    cmd = [
        "python3", DETECTOR_SCRIPT,
        photo_path,
        "--frames", str(expected_frames)
    ]
    print(f"  运行检测: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"  检测失败: {result.stderr}")
        return False

    # 解析 stdout 中的 JSON（最后一行）
    lines = result.stdout.strip().split('\n')
    json_line = None
    for line in reversed(lines):
        line = line.strip()
        if line.startswith('{') and line.endswith('}'):
            json_line = line
            break

    if not json_line:
        print("  错误: 未在输出中找到 JSON")
        return False

    try:
        data = json.loads(json_line)
    except json.JSONDecodeError as e:
        print(f"  JSON 解析失败: {e}")
        return False

    # 添加目标照片信息（用于 AutoWatch 匹配）
    basename = os.path.splitext(os.path.basename(photo_path))[0]
    data['targetBasename'] = basename

    # 写入 JSON 文件（触发 AutoWatch）
    with open(AUTO_JSON_PATH, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"  JSON 已生成: {AUTO_JSON_PATH}")
    print(f"  目标照片: {basename}")
    print(f"  检测到 {data.get('frameCount', 0)} 帧")
    return True


# ------------------------------------------------------------------
# 主流程
# ------------------------------------------------------------------

def run_auto_test(catalog_path, wait_seconds=90, photo_name=None):
    lr = LightroomController()

    # ---- 1. 检查 Lightroom 运行 ----
    print("=" * 60)
    print("FilmCrop 全自动 E2E 测试 (JSON 触发模式)")
    print("=" * 60)
    print(f"\n[1/7] 检查 Lightroom...")
    applescript_ok = lr.can_use_applescript()
    if applescript_ok:
        if not lr.is_running():
            print("  警告: Lightroom 未运行!")
            print("  请先手动启动 Lightroom，然后重新运行此脚本")
            return 2
        print("  Lightroom 正在运行")
    else:
        print("  警告: AppleScript/System Events 不可用，跳过 Lightroom 进程检测")
        print("  请确保 Lightroom 已启动并在修改照片模块中选中了测试照片")

    # ---- 2. 读取基准状态 ----
    print(f"\n[2/7] 读取 catalog 基准状态...")
    tmp_before, tmpdir_before = copy_catalog_for_reading(catalog_path)
    verifier_before = CatalogVerifier(tmp_before)
    verifier_before.connect()

    masters = verifier_before.get_test_photo_masters()
    all_vcs_before = verifier_before.get_all_virtual_copies()

    # 选择测试照片
    test_basename = None
    test_master_id = None
    test_master_row = None
    test_photo_path = None

    candidates = []
    for basename, rows in masters.items():
        for row in rows:
            master_id = row[0]
            vc_count = len(verifier_before.get_virtual_copies(master_id))
            candidates.append((basename, master_id, row, vc_count))

    if photo_name:
        for basename, master_id, row, vc_count in candidates:
            if basename == photo_name:
                test_basename, test_master_id, test_master_row = basename, master_id, row
                break
    else:
        for basename, master_id, row, vc_count in candidates:
            if vc_count == 0:
                test_basename, test_master_id, test_master_row = basename, master_id, row
                break
        if test_basename is None and candidates:
            test_basename, test_master_id, test_master_row = candidates[0][:3]

    if test_basename is None:
        print("  错误: 未找到可用的测试照片")
        cleanup_copy(tmp_before, tmpdir_before)
        return 1

    # 查找测试照片的文件路径（优先用 test_files 目录）
    test_photo_path = None
    for ext in ['.tif', '.tiff', '.dng', '.jpg', '.jpeg']:
        candidate = os.path.join(TEST_FILES_DIR, test_basename + ext)
        if os.path.exists(candidate):
            test_photo_path = candidate
            break

    print(f"  测试照片: {test_basename} (master_id={test_master_id})")
    print(f"  照片路径: {test_photo_path}")
    print(f"  基准虚拟副本数: {len(verifier_before.get_virtual_copies(test_master_id))}")
    print(f"  catalog 总虚拟副本数: {len(all_vcs_before)}")

    baseline_vcs = set(all_vcs_before.keys())
    verifier_before.close()
    cleanup_copy(tmp_before, tmpdir_before)

    # ---- 3. 激活 Lightroom ----
    print(f"\n[3/7] 激活 Lightroom 并切换到修改照片模块...")
    if applescript_ok:
        lr.activate()
        time.sleep(0.5)
        lr.switch_to_develop()
        time.sleep(0.5)
    else:
        print("  AppleScript 不可用，跳过自动激活")
        print("  请确保 Lightroom 在修改照片模块中")

    # ---- 4. 生成 JSON 文件 ----
    print(f"\n[4/7] 生成 FilmCrop JSON 文件...")
    if not test_photo_path or not os.path.exists(test_photo_path):
        print(f"  错误: 找不到测试照片文件")
        return 1

    if not generate_json_for_photo(test_photo_path):
        print("  JSON 生成失败")
        return 1

    # ---- 5. 提示用户启动自动检测（如果尚未启动）----
    print(f"\n[5/7] 检查自动检测模式...")
    print(f"  JSON 文件已写入: {AUTO_JSON_PATH}")
    print(f"  如果 FilmCrop「自动检测 (E2E)」尚未启动，请手动点击:")
    print(f"    文件 → 增效工具额外命令 → FilmCrop → 启动自动检测 (E2E)")
    print(f"  如果已启动，FilmCrop 将在几秒钟内自动处理 JSON 文件。")

    # ---- 6. 等待（非交互式）----
    print(f"\n[6/7] 等待中...", end="", flush=True)
    for i in range(wait_seconds):
        time.sleep(1)
        if (i + 1) % 10 == 0:
            print(f" {i+1}s", end="", flush=True)
    print(" 完成")

    # ---- 7. 读取新状态并验证 ----
    print(f"\n[7/7] 读取新状态并验证...")
    tmp_after, tmpdir_after = copy_catalog_for_reading(catalog_path)
    verifier_after = CatalogVerifier(tmp_after)
    verifier_after.connect()

    # 查找新出现的虚拟副本
    all_vcs_after = verifier_after.get_all_virtual_copies()
    new_vc_ids = set(all_vcs_after.keys()) - baseline_vcs
    new_vcs = [all_vcs_after[vid] for vid in new_vc_ids]

    # 过滤出属于测试照片的虚拟副本
    test_new_vcs = [vc for vc in new_vcs if vc[2] == test_master_id]

    print(f"  新虚拟副本总数: {len(new_vcs)}")
    print(f"  属于测试照片的: {len(test_new_vcs)}")

    if test_new_vcs:
        print(f"\n  测试照片新虚拟副本详情:")
        all_has_crop = True
        for vc in test_new_vcs:
            vc_id, vc_name, vc_master, vc_file = vc
            settings = verifier_after.get_develop_settings(vc_id)
            crop_keys = ['CropTop', 'CropBottom', 'CropLeft', 'CropRight']
            # 默认值不会被 LR 写入 develop 文本（CropTop=0/CropBottom=1/CropLeft=0/CropRight=1）
            # 所以"裁剪已应用"的判定是：至少一个 crop key 有非默认值
            has_crop = any(k in settings for k in crop_keys)
            crop_str = f"crop=({settings.get('CropTop',-1):.4f}, {settings.get('CropBottom',-1):.4f}, " \
                       f"{settings.get('CropLeft',-1):.4f}, {settings.get('CropRight',-1):.4f})"
            status = "OK" if has_crop else "FAIL(无裁剪)"
            print(f"    {vc_name or f'副本_{vc_id}'}: {crop_str} [{status}]")
            if not has_crop:
                all_has_crop = False

        # 主照片状态
        master_settings = verifier_after.get_develop_settings(test_master_id)
        print(f"\n  主照片裁剪状态:")
        for key in ['CropTop', 'CropBottom', 'CropLeft', 'CropRight']:
            print(f"    {key} = {master_settings.get(key, 'N/A')}")

        verifier_after.close()
        cleanup_copy(tmp_after, tmpdir_after)

        print("\n" + "=" * 60)
        if all_has_crop:
            print(f"通过! 成功创建 {len(test_new_vcs)} 个虚拟副本，全部应用了裁剪")
            return 0
        else:
            print(f"部分失败: 创建了 {len(test_new_vcs)} 个虚拟副本，但部分未应用裁剪")
            return 1
    else:
        # 检查是否其他照片有新虚拟副本
        other_new = [vc for vc in new_vcs if vc[2] != test_master_id]
        if other_new:
            print(f"\n  警告: 未在测试照片上创建虚拟副本")
            print(f"  但其他照片有新虚拟副本 ({len(other_new)} 个):")
            for vc in other_new[:5]:
                print(f"    master={vc[2]}, file={vc[3]}, name={vc[1]}")
            print(f"\n  可能原因: AutoWatch 启动时选中的不是测试照片")
        else:
            print(f"\n  未检测到新虚拟副本")
            print(f"  可能原因:")
            print(f"    - FilmCrop 自动检测模式未启动")
            print(f"    - 照片不是胶片扫描（未检测到帧）")
            print(f"    - 处理过程中出错")
            print(f"    - 等待时间不够（当前 {wait_seconds}s）")

        verifier_after.close()
        cleanup_copy(tmp_after, tmpdir_after)
        return 1


def main():
    parser = argparse.ArgumentParser(description="FilmCrop 全自动 E2E 测试")
    parser.add_argument("--catalog", default=DEFAULT_CATALOG, help="catalog 路径")
    parser.add_argument("--wait", type=int, default=90, help="等待秒数（默认90）")
    parser.add_argument("--photo", help="指定测试照片（如 52191）")
    args = parser.parse_args()

    if not os.path.exists(args.catalog):
        print(f"错误: catalog 不存在: {args.catalog}")
        sys.exit(1)

    rc = run_auto_test(args.catalog, args.wait, args.photo)
    sys.exit(rc)


if __name__ == "__main__":
    main()
