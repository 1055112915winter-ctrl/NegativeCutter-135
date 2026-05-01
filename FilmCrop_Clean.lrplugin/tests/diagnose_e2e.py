#!/usr/bin/env python3
"""
E2E 测试诊断脚本
检查 catalog 中测试照片的完整状态
"""

import sqlite3
import os
import sys

CATALOG = os.path.expanduser("~/Pictures/Lightroom/Lightroom Catalog-v13-2.lrcat")

def main():
    conn = sqlite3.connect(CATALOG)
    cursor = conn.cursor()

    print("=" * 60)
    print("FilmCrop E2E 诊断")
    print("=" * 60)

    # 1. 检查测试照片的 master
    print("\n[1] 测试照片 Master 状态:")
    for basename in ['52191', '52194', 'luckyc20013']:
        cursor.execute('''
            SELECT i.id_local, i.copyName, i.masterImage, i.fileFormat,
                   i.fileHeight, i.fileWidth, f.baseName
            FROM Adobe_images i
            JOIN AgLibraryFile f ON i.rootFile = f.id_local
            WHERE f.baseName = ? AND i.masterImage IS NULL
            ORDER BY i.id_local DESC
            LIMIT 1
        ''', (basename,))
        rows = cursor.fetchall()
        if rows:
            r = rows[0]
            print(f"  {basename}: master_id={r[0]}, size={r[5]}x{r[4]}")
        else:
            print(f"  {basename}: NO MASTER FOUND")

    # 2. 检查所有虚拟副本（不限于测试照片）
    print("\n[2] 最新创建的虚拟副本（最近10个）:")
    cursor.execute('''
        SELECT i.id_local, i.copyName, i.masterImage, f.baseName,
               i.fileHeight, i.fileWidth
        FROM Adobe_images i
        JOIN AgLibraryFile f ON i.rootFile = f.id_local
        WHERE i.masterImage IS NOT NULL
        ORDER BY i.id_local DESC
        LIMIT 10
    ''')
    for r in cursor.fetchall():
        print(f"  id={r[0]}, copyName={r[1]}, master={r[2]}, file={r[3]}")

    # 3. 检查测试照片的虚拟副本
    print("\n[3] 测试照片的虚拟副本:")
    for basename, master_id in [('52191', 3560771), ('52194', 3560772), ('luckyc20013', 3560773)]:
        cursor.execute('''
            SELECT i.id_local, i.copyName, i.fileHeight, i.fileWidth
            FROM Adobe_images i
            JOIN AgLibraryFile f ON i.rootFile = f.id_local
            WHERE i.masterImage = ?
        ''', (master_id,))
        vcs = cursor.fetchall()
        print(f"  {basename} (master={master_id}): {len(vcs)} 个虚拟副本")
        for vc in vcs:
            print(f"    id={vc[0]}, copyName={vc[1]}")

    # 4. 检查 develop settings
    print("\n[4] 测试照片的 Develop Settings:")
    for basename, master_id in [('52191', 3560771), ('52194', 3560772), ('luckyc20013', 3560773)]:
        cursor.execute('SELECT text FROM Adobe_imageDevelopSettings WHERE image = ?', (master_id,))
        row = cursor.fetchone()
        if row and row[0]:
            text = row[0]
            import re
            crops = {}
            for key in ['CropTop', 'CropBottom', 'CropLeft', 'CropRight', 'CropAngle']:
                m = re.search(rf'\b{key}\s*=\s*([-\d.]+)', text)
                if m:
                    crops[key] = float(m.group(1))
            print(f"  {basename}: {crops}")
        else:
            print(f"  {basename}: 无 develop settings")

    # 5. 检查虚拟副本的 develop settings
    print("\n[5] 测试照片虚拟副本的 Develop Settings:")
    for basename, master_id in [('52191', 3560771), ('52194', 3560772), ('luckyc20013', 3560773)]:
        cursor.execute('''
            SELECT i.id_local, i.copyName
            FROM Adobe_images i
            WHERE i.masterImage = ?
        ''', (master_id,))
        vcs = cursor.fetchall()
        if not vcs:
            print(f"  {basename}: 无虚拟副本")
            continue
        for vc in vcs:
            vc_id = vc[0]
            cursor.execute('SELECT text FROM Adobe_imageDevelopSettings WHERE image = ?', (vc_id,))
            row = cursor.fetchone()
            if row and row[0]:
                text = row[0]
                import re
                crops = {}
                for key in ['CropTop', 'CropBottom', 'CropLeft', 'CropRight', 'CropAngle']:
                    m = re.search(rf'\b{key}\s*=\s*([-\d.]+)', text)
                    if m:
                        crops[key] = float(m.group(1))
                print(f"  {basename} vc(id={vc_id}): {crops}")
            else:
                print(f"  {basename} vc(id={vc_id}): 无 develop settings")

    conn.close()
    print("\n诊断完成")

if __name__ == "__main__":
    main()
