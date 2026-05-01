#!/usr/bin/env python3
"""
生成带帧边界标记的预览图
"""
import sys
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps


def generate_preview(thumb_path: str, frames_json: str, output_path: str):
    """生成带有帧边界标记的预览图"""

    # 解析帧数据
    frames = json.loads(frames_json)

    # 打开缩略图（禁用 EXIF 旋转，确保与 detect_thumb.py 和 Lightroom 坐标系一致）
    img = Image.open(thumb_path)
    # img = ImageOps.exif_transpose(img)
    if img.mode != 'RGB':
        img = img.convert('RGB')

    img_width, img_height = img.size

    # 创建可绘制对象
    draw = ImageDraw.Draw(img)

    # 颜色定义
    colors = [
        (255, 0, 0),    # 红
        (0, 255, 0),    # 绿
        (0, 0, 255),    # 蓝
        (255, 255, 0),  # 黄
        (255, 0, 255),  # 紫
        (0, 255, 255),  # 青
    ]

    # 为每个帧绘制边界
    for i, frame in enumerate(frames):
        color = colors[i % len(colors)]

        # 使用实际检测到的边界（不再硬编码 3:2）
        source_width = frame.get('sourceWidth', img_width)
        source_height = frame.get('sourceHeight', img_height)
        scale_x = img_width / source_width if source_width > 0 else 1.0
        scale_y = img_height / source_height if source_height > 0 else 1.0

        left = max(0, int(frame.get('left', 0) * scale_x))
        right = min(img_width, int(frame.get('right', img_width) * scale_x))
        top = max(0, int(frame.get('top', 0) * scale_y))
        bottom = min(img_height, int(frame.get('bottom', img_height) * scale_y))

        # 绘制边界框
        line_width = 3
        draw.line([(left, top), (left, bottom)], fill=color, width=line_width)
        draw.line([(right, top), (right, bottom)], fill=color, width=line_width)
        draw.line([(left, top), (right, top)], fill=color, width=line_width)
        draw.line([(left, bottom), (right, bottom)], fill=color, width=line_width)

        # 绘制标签背景
        label = f" 帧{i+1} "
        try:
            font_paths = [
                "/System/Library/Fonts/Helvetica.ttc",
                "/System/Library/Fonts/Helvetica.ttf",
                "/Library/Fonts/Helvetica.ttf",
                "/System/Library/Fonts/PingFang.ttc",
                "/System/Library/Fonts/STHeiti Light.ttc",
            ]
            font = None
            for fp in font_paths:
                try:
                    if Path(fp).exists():
                        font = ImageFont.truetype(fp, 20)
                        break
                except:
                    continue
            if font is None:
                font = ImageFont.load_default()
        except:
            font = ImageFont.load_default()

        # 获取文本尺寸（兼容旧版 Pillow）
        try:
            bbox = draw.textbbox((0, 0), label, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        except AttributeError:
            text_width, text_height = draw.textsize(label, font=font)

        label_y = top + 5
        draw.rectangle(
            [(left + 5, label_y), (left + 5 + text_width + 10, label_y + text_height + 6)],
            fill=color
        )
        draw.text((left + 10, label_y), label, fill=(255, 255, 255), font=font)

    # 添加图例
    legend_y = img_height - 30
    legend_x = 10
    for i, frame in enumerate(frames):
        if i >= 6:
            break
        color = colors[i % len(colors)]
        draw.rectangle(
            [(legend_x, legend_y), (legend_x + 15, legend_y + 15)],
            fill=color
        )
        draw.text((legend_x + 20, legend_y), f"帧{i+1}", fill=(255, 255, 255))
        legend_x += 60

    # 保存预览图
    img.save(output_path, quality=90)
    print(f"预览图已保存: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("用法: python3 generate_preview.py <thumb_path> <frames_json_path> <output_path>")
        sys.exit(1)

    thumb_path = sys.argv[1]
    frames_json_path = sys.argv[2]
    output_path = sys.argv[3]

    if not Path(thumb_path).exists():
        print(f"错误: 缩略图不存在: {thumb_path}")
        sys.exit(1)

    if not Path(frames_json_path).exists():
        print(f"错误: JSON文件不存在: {frames_json_path}")
        sys.exit(1)

    try:
        with open(frames_json_path, 'r') as f:
            frames_json = f.read()
        generate_preview(thumb_path, frames_json, output_path)
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
