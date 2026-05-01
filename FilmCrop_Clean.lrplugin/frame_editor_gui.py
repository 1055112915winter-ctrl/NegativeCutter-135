#!/usr/bin/env python3
"""
FilmCrop 帧边界图形编辑器 v2
与 Lightroom 深度集成：接收检测帧 → 用户编辑 → 自动保存 → Lightroom 读取并创建虚拟副本
"""

import sys
import json
import argparse
from pathlib import Path

try:
    from PIL import Image, ImageOps, ImageTk, ImageDraw
except ImportError:
    print("错误: 需要安装 Pillow: pip install Pillow")
    sys.exit(1)

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except ImportError:
    print("错误: 无法导入 tkinter")
    sys.exit(1)


class FrameEditor(tk.Tk):
    def __init__(self, image_path, frames_data, output_path, is_horizontal=True):
        super().__init__()

        self.title("FilmCrop - 帧边界编辑器")
        self.geometry("1400x900")
        self.output_path = output_path
        self.is_horizontal = is_horizontal

        # 加载图片（禁用 EXIF 旋转，确保与 Lightroom 坐标系一致）
        self.original_image = Image.open(image_path)
        # self.original_image = ImageOps.exif_transpose(self.original_image)
        if self.original_image.mode != 'RGB':
            self.original_image = self.original_image.convert('RGB')
        self.img_width, self.img_height = self.original_image.size

        # 初始化帧数据
        self.frames = frames_data if frames_data else self._create_default_frames(6)
        self._normalize_frames()

        # 当前选中的帧和拖拽模式
        self.selected_frame_idx = 0
        self.drag_mode = None   # 'top', 'bottom', 'left', 'right'
        self.drag_start = 0

        # 缩放与显示
        self.scale = 1.0
        self.canvas_width = 1000
        self.canvas_height = 750
        self.offset_x = 0
        self.offset_y = 0

        self._create_ui()
        self._calculate_scale()
        self._update_display()

    def _create_default_frames(self, count):
        """默认均匀分割"""
        frames = []
        if self.is_horizontal:
            fh = self.img_width // count
            for i in range(count):
                frames.append({
                    'index': i + 1,
                    'top': 0,
                    'bottom': self.img_height,
                    'left': i * fh,
                    'right': (i + 1) * fh
                })
        else:
            fh = self.img_height // count
            for i in range(count):
                frames.append({
                    'index': i + 1,
                    'top': i * fh,
                    'bottom': (i + 1) * fh,
                    'left': 0,
                    'right': self.img_width
                })
        return frames

    def _normalize_frames(self):
        """确保每帧都有完整的四边坐标"""
        for f in self.frames:
            f.setdefault('top', 0)
            f.setdefault('bottom', self.img_height)
            f.setdefault('left', 0)
            f.setdefault('right', self.img_width)

    def _create_ui(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)

        # 左侧面板 - 画布
        left_frame = ttk.LabelFrame(main_frame, text="预览 (拖拽边界线调整)", padding="5")
        left_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        left_frame.columnconfigure(0, weight=1)
        left_frame.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(left_frame, width=self.canvas_width, height=self.canvas_height,
                                bg='#1a1a1a', highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.canvas.bind("<Button-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)

        # 右侧面板
        right_frame = ttk.Frame(main_frame, padding="10")
        right_frame.grid(row=0, column=1, sticky=(tk.N, tk.S), padx=(10, 0))

        # 帧列表
        ttk.Label(right_frame, text="帧列表:").grid(row=0, column=0, sticky=tk.W)
        self.frame_listbox = tk.Listbox(right_frame, height=10, width=24)
        self.frame_listbox.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        self.frame_listbox.bind("<<ListboxSelect>>", self._on_frame_select)
        self._update_frame_list()

        # 四边控制
        control_frame = ttk.LabelFrame(right_frame, text="当前帧边界 (像素)", padding="10")
        control_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=10)

        self.spin_vars = {}
        for idx, (label, key, max_val) in enumerate([
            ("Top:", 'top', self.img_height),
            ("Bottom:", 'bottom', self.img_height),
            ("Left:", 'left', self.img_width),
            ("Right:", 'right', self.img_width)
        ]):
            ttk.Label(control_frame, text=label).grid(row=idx, column=0, sticky=tk.W)
            var = tk.IntVar()
            self.spin_vars[key] = var
            sb = ttk.Spinbox(control_frame, from_=0, to=max_val, textvariable=var,
                             width=10, command=self._on_spinbox_change)
            sb.grid(row=idx, column=1, sticky=(tk.W, tk.E), padx=5, pady=2)

        # 操作按钮
        btn_frame = ttk.Frame(control_frame)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="添加帧", command=self._add_frame).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="删除帧", command=self._delete_frame).pack(side=tk.LEFT, padx=2)

        # 底部操作
        action_frame = ttk.Frame(right_frame)
        action_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=10)
        ttk.Button(action_frame, text="导出预览图", command=self._export_preview).pack(fill=tk.X, pady=2)
        ttk.Button(action_frame, text="重置为默认", command=self._reset).pack(fill=tk.X, pady=2)

        # 确认按钮（醒目）
        confirm_btn = ttk.Button(right_frame, text="确认并应用到 Lightroom",
                                 command=self._confirm_and_exit)
        confirm_btn.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(20, 5))
        ttk.Label(right_frame, text="点击后将保存帧边界并返回 Lightroom 创建虚拟副本",
                  wraplength=220, justify=tk.LEFT, foreground="gray").grid(
                      row=5, column=0, sticky=(tk.W, tk.E))

        help_text = """
操作说明:
• 点击帧列表切换当前帧
• 拖拽红色线(上/左)调整起始边界
• 拖拽绿色线(下/右)调整结束边界
• 滚轮缩放图片
• 数值框可精确调整像素位置
        """
        ttk.Label(right_frame, text=help_text, wraplength=220, justify=tk.LEFT).grid(
            row=6, column=0, sticky=(tk.W, tk.E), pady=10)

    def _calculate_scale(self):
        scale_x = self.canvas_width / self.img_width
        scale_y = self.canvas_height / self.img_height
        self.scale = min(scale_x, scale_y, 1.0)
        self.scaled_width = int(self.img_width * self.scale)
        self.scaled_height = int(self.img_height * self.scale)
        self.offset_x = (self.canvas_width - self.scaled_width) // 2
        self.offset_y = (self.canvas_height - self.scaled_height) // 2

    def _to_screen(self, x, y):
        return self.offset_x + int(x * self.scale), self.offset_y + int(y * self.scale)

    def _to_image(self, sx, sy):
        return (sx - self.offset_x) / self.scale, (sy - self.offset_y) / self.scale

    def _update_display(self):
        scaled = self.original_image.resize((self.scaled_width, self.scaled_height),
                                            Image.Resampling.LANCZOS)
        draw = ImageDraw.Draw(scaled)
        colors = ['#ff4444', '#44ff44', '#4444ff', '#ffff44', '#ff44ff', '#44ffff']

        for i, frame in enumerate(self.frames):
            color = colors[i % len(colors)]
            x1, y1 = self._to_screen(frame['left'], frame['top'])
            x2, y2 = self._to_screen(frame['right'], frame['bottom'])
            lw = 4 if i == self.selected_frame_idx else 2

            # 绘制边界框
            draw.rectangle([(x1, y1), (x2, y2)], outline=color, width=lw)

            # 拖拽手柄（在边界中点）
            if i == self.selected_frame_idx:
                for hx, hy in [(x1, (y1+y2)//2), (x2, (y1+y2)//2), ((x1+x2)//2, y1), ((x1+x2)//2, y2)]:
                    draw.ellipse([(hx-4, hy-4), (hx+4, hy+4)], fill='#ffffff')

            # 编号
            draw.text((x1 + 4, y1 + 4), f"帧{i+1}", fill=color)

        self.tk_image = ImageTk.PhotoImage(scaled)
        self.canvas.delete("all")
        self.canvas.create_image(self.canvas_width // 2, self.canvas_height // 2, image=self.tk_image)

    def _update_frame_list(self):
        self.frame_listbox.delete(0, tk.END)
        for i, f in enumerate(self.frames):
            label = f"帧{i+1}: T={f['top']} B={f['bottom']} L={f['left']} R={f['right']}"
            self.frame_listbox.insert(tk.END, label)
        if self.frames:
            self.frame_listbox.select_set(self.selected_frame_idx)
            self._load_frame_data()

    def _load_frame_data(self):
        if not self.frames:
            return
        f = self.frames[self.selected_frame_idx]
        for key in ['top', 'bottom', 'left', 'right']:
            self.spin_vars[key].set(int(f.get(key, 0)))

    def _on_frame_select(self, event):
        sel = self.frame_listbox.curselection()
        if sel:
            self.selected_frame_idx = sel[0]
            self._load_frame_data()
            self._update_display()

    def _on_spinbox_change(self):
        if not self.frames:
            return
        f = self.frames[self.selected_frame_idx]
        try:
            for key in ['top', 'bottom', 'left', 'right']:
                val = int(self.spin_vars[key].get())
                if key in ('top', 'left'):
                    f[key] = max(0, min(val, f.get({'top':'bottom','left':'right'}[key], val+1)-1))
                else:
                    f[key] = max(f.get({'bottom':'top','right':'left'}[key], 0)+1, min(val, {'bottom':self.img_height,'right':self.img_width}[key]))
            self._update_display()
            self._update_frame_list()
        except ValueError:
            pass

    def _on_mouse_down(self, event):
        if not self.frames:
            return
        ix, iy = self._to_image(event.x, event.y)
        f = self.frames[self.selected_frame_idx]
        tol = 10 / self.scale

        # 检查是否接近某条边界
        edges = [
            (abs(iy - f['top']), 'top'),
            (abs(iy - f['bottom']), 'bottom'),
            (abs(ix - f['left']), 'left'),
            (abs(ix - f['right']), 'right'),
        ]
        edges.sort(key=lambda x: x[0])
        if edges[0][0] < tol:
            self.drag_mode = edges[0][1]

    def _on_mouse_drag(self, event):
        if not self.drag_mode or not self.frames:
            return
        ix, iy = self._to_image(event.x, event.y)
        ix = max(0, min(self.img_width, int(ix)))
        iy = max(0, min(self.img_height, int(iy)))
        f = self.frames[self.selected_frame_idx]

        if self.drag_mode == 'top':
            f['top'] = min(iy, f['bottom'] - 20)
        elif self.drag_mode == 'bottom':
            f['bottom'] = max(iy, f['top'] + 20)
        elif self.drag_mode == 'left':
            f['left'] = min(ix, f['right'] - 20)
        elif self.drag_mode == 'right':
            f['right'] = max(ix, f['left'] + 20)

        self._load_frame_data()
        self._update_display()

    def _on_mouse_up(self, event):
        if self.drag_mode:
            self.drag_mode = None
            self._update_frame_list()

    def _on_mouse_wheel(self, event):
        delta = getattr(event, 'delta', 0)
        if delta > 0:
            self.scale = min(self.scale * 1.1, 3.0)
        else:
            self.scale = max(self.scale / 1.1, 0.2)
        self._update_display()

    def _add_frame(self):
        if not self.frames:
            return
        cur = self.frames[self.selected_frame_idx]
        if self.is_horizontal:
            mid = (cur['left'] + cur['right']) // 2
            new_frame = {'index': 0, 'top': cur['top'], 'bottom': cur['bottom'],
                         'left': mid, 'right': cur['right']}
            cur['right'] = mid
        else:
            mid = (cur['top'] + cur['bottom']) // 2
            new_frame = {'index': 0, 'top': mid, 'bottom': cur['bottom'],
                         'left': cur['left'], 'right': cur['right']}
            cur['bottom'] = mid

        self.frames.insert(self.selected_frame_idx + 1, new_frame)
        for i, fr in enumerate(self.frames):
            fr['index'] = i + 1
        self.selected_frame_idx += 1
        self._update_frame_list()
        self._update_display()

    def _delete_frame(self):
        if len(self.frames) <= 1:
            messagebox.showwarning("警告", "至少需要保留一帧")
            return
        if messagebox.askyesno("确认", f"确定要删除帧{self.selected_frame_idx + 1}吗？"):
            del self.frames[self.selected_frame_idx]
            for i, fr in enumerate(self.frames):
                fr['index'] = i + 1
            self.selected_frame_idx = max(0, self.selected_frame_idx - 1)
            self._update_frame_list()
            self._update_display()

    def _export_preview(self):
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(defaultextension=".jpg",
                                            filetypes=[("JPEG", "*.jpg")])
        if path:
            preview = self.original_image.copy()
            draw = ImageDraw.Draw(preview)
            colors = [(255,0,0),(0,255,0),(0,0,255),(255,255,0),(255,0,255),(0,255,255)]
            for i, f in enumerate(self.frames):
                c = colors[i % len(colors)]
                draw.rectangle([(f['left'], f['top']), (f['right'], f['bottom'])],
                               outline=c, width=3)
                draw.text((f['left']+5, f['top']+5), f"帧{i+1}", fill=c)
            preview.save(path, quality=95)
            messagebox.showinfo("成功", f"已导出到: {path}")

    def _reset(self):
        if messagebox.askyesno("确认", "重置为6帧默认分割吗？"):
            self.frames = self._create_default_frames(6)
            self.selected_frame_idx = 0
            self._update_frame_list()
            self._update_display()

    def _build_export_data(self):
        """生成与 detect_thumb.py 输出兼容的 JSON 结构"""
        export_data = {
            'frameCount': len(self.frames),
            'sourceWidth': self.img_width,
            'sourceHeight': self.img_height,
            'cropAngle': 0.0,
            'frames': []
        }
        for frame in self.frames:
            top = max(0, frame.get('top', 0))
            bottom = max(top + 1, min(self.img_height, frame.get('bottom', self.img_height)))
            left = max(0, frame.get('left', 0))
            right = max(left + 1, min(self.img_width, frame.get('right', self.img_width)))
            export_data['frames'].append({
                'index': frame.get('index', 0),
                'top': top,
                'bottom': bottom,
                'left': left,
                'right': right,
                'relativeTop': round(top / self.img_height, 6),
                'relativeBottom': round(bottom / self.img_height, 6),
                'relativeLeft': round(left / self.img_width, 6),
                'relativeRight': round(right / self.img_width, 6),
            })
        return export_data

    def _confirm_and_exit(self):
        """保存并退出，让 Lightroom 读取输出文件"""
        data = self._build_export_data()
        try:
            with open(self.output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"[FilmCropEditor] 已保存到: {self.output_path}")
            self.destroy()
        except Exception as e:
            messagebox.showerror("保存失败", str(e))


def main():
    parser = argparse.ArgumentParser(description="FilmCrop 帧边界编辑器")
    parser.add_argument("image_path", help="扫描图像路径")
    parser.add_argument("--frames-json", help="初始帧数据 JSON 路径")
    parser.add_argument("--output", required=True, help="编辑后保存的 JSON 路径")
    parser.add_argument("--horizontal", action="store_true",
                        help="指定为横向排列（影响默认分割方向）")
    args = parser.parse_args()

    image_path = args.image_path
    output_path = args.output
    is_horizontal = args.horizontal

    frames_data = None
    if args.frames_json and Path(args.frames_json).exists():
        with open(args.frames_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
            frames_data = data.get('frames', [])
            # 从已有数据推断方向
            if frames_data and not is_horizontal:
                first = frames_data[0]
                fw = first.get('right', 1) - first.get('left', 0)
                fh = first.get('bottom', 1) - first.get('top', 0)
                is_horizontal = fw > fh

    app = FrameEditor(image_path, frames_data, output_path, is_horizontal)
    app.mainloop()


if __name__ == "__main__":
    main()
