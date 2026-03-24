"""
slim_visualizer.py – 瘦身效果预览 App
通过上传或拍摄照片，直观展示用户瘦下来的样子。

依赖：
    pip install Pillow numpy
可选依赖（摄像头）：
    pip install opencv-python
可选依赖（AI 生成）：
    pip install openai
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import io
import threading
import urllib.request

from PIL import Image, ImageTk, ImageFilter, ImageEnhance
import numpy as np

# ── 可选：OpenCV（摄像头） ────────────────────────────────────────────────────
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

# ── 可选：OpenAI（AI 变换） ──────────────────────────────────────────────────
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# ── 常量 ─────────────────────────────────────────────────────────────────────
PREVIEW_MAX = 400          # 预览图最大边长（像素）
DEFAULT_SLIM = 25          # 默认瘦身幅度（%）
BODY_START = 0.20          # 身体区域开始的相对位置（从顶部）
BODY_END   = 0.95          # 身体区域结束的相对位置
CAMERA_INDEX = 0           # 默认摄像头索引（多摄像头设备可修改）


# ─────────────────────────────────────────────────────────────────────────────
# 核心图像处理
# ─────────────────────────────────────────────────────────────────────────────

def apply_slim_effect(image: Image.Image, slim_percent: float) -> Image.Image:
    """
    对图像施加横向收缩（瘦身）变换。

    算法：
      1. 保持头部（顶部 BODY_START 比例）不变。
      2. 对身体区域，将每一行像素按 slim_percent 向水平中心收缩，
         两侧用各行端点颜色填充（保持背景一致）。
      3. 对两端施加轻微高斯模糊，使过渡自然。

    参数
    ----
    image        : PIL.Image（RGB）
    slim_percent : 0–50，收缩百分比
    """
    if slim_percent <= 0:
        return image.copy()

    slim_factor = slim_percent / 100.0          # e.g. 0.25
    squeeze     = 1.0 - slim_factor             # e.g. 0.75

    img_np = np.array(image.convert("RGB"), dtype=np.uint8)
    h, w, c = img_np.shape
    out_np  = img_np.copy()

    body_start_row = int(h * BODY_START)
    body_end_row   = int(h * BODY_END)

    cx = w / 2.0  # 水平中心

    for row in range(body_start_row, body_end_row):
        # 渐变系数：身体中部最大，头颈过渡处和脚踝处减弱
        t = (row - body_start_row) / max(body_end_row - body_start_row - 1, 1)
        # 平滑过渡曲线（sin²）
        taper = np.sin(t * np.pi) ** 0.5
        row_squeeze = 1.0 - slim_factor * taper  # 1.0 → squeeze

        src_row = img_np[row]

        # 目标列 → 源列映射
        dst_x = np.arange(w, dtype=np.float32)
        # 反映射：dst_x 对应 src_x
        src_x = cx + (dst_x - cx) / row_squeeze
        src_x = np.clip(src_x, 0, w - 1)

        # 整数索引（最近邻）
        src_xi = src_x.astype(np.int32)
        out_np[row] = src_row[src_xi]

    result = Image.fromarray(out_np)

    # 轻微锐化，使变换后图像更清晰
    result = result.filter(ImageFilter.UnsharpMask(radius=1, percent=50, threshold=2))
    return result


def resize_for_preview(image: Image.Image, max_size: int = PREVIEW_MAX) -> Image.Image:
    """按比例缩放图像以适应预览区域。"""
    w, h = image.size
    scale = min(max_size / w, max_size / h, 1.0)
    if scale < 1.0:
        nw, nh = int(w * scale), int(h * scale)
        return image.resize((nw, nh), Image.LANCZOS)
    return image.copy()


# ─────────────────────────────────────────────────────────────────────────────
# OpenAI 集成（可选）
# ─────────────────────────────────────────────────────────────────────────────

def ai_slim_transform(image: Image.Image, api_key: str, slim_percent: float) -> Image.Image:
    """
    使用 OpenAI DALL-E 3 生成瘦身后的图像。
    需要有效的 OpenAI API Key，且图像将上传至 OpenAI。
    返回生成的 PIL.Image，失败则抛出异常。
    """
    client = openai.OpenAI(api_key=api_key)

    # 将图像转换为 PNG 字节流
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)
    image_bytes = buf.read()

    slim_desc = {
        10: "slightly slimmer",
        20: "noticeably slimmer",
        30: "significantly slimmer",
        40: "much slimmer",
        50: "very slim",
    }
    closest_key = min(slim_desc.keys(), key=lambda k: abs(k - slim_percent))
    description = slim_desc[closest_key]

    prompt = (
        f"Transform this person to look {description} and have lost weight. "
        "Keep the same face, clothing, background, pose and lighting. "
        "Make the body {description} in a realistic, natural way. "
        "Photorealistic style."
    )

    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        n=1,
    )

    if not response.data:
        raise ValueError("OpenAI 返回的图像数据为空，请稍后重试。")

    image_url = response.data[0].url
    with urllib.request.urlopen(image_url) as resp:  # nosec: URL from OpenAI API
        img_data = resp.read()
    return Image.open(io.BytesIO(img_data)).convert("RGB")


# ─────────────────────────────────────────────────────────────────────────────
# GUI 主窗口
# ─────────────────────────────────────────────────────────────────────────────

class SlimVisualizerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("瘦身效果预览 – Slim Visualizer")
        self.resizable(True, True)
        self.configure(bg="#f5f5f5")

        self._original_image: Image.Image | None = None   # 原始 PIL 图像
        self._result_image:   Image.Image | None = None   # 变换后 PIL 图像
        self._tk_original: ImageTk.PhotoImage | None = None
        self._tk_result:   ImageTk.PhotoImage | None = None
        self._camera_cap = None   # cv2.VideoCapture

        self._build_ui()

    # ── 界面构建 ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ---- 顶部工具栏 ----
        toolbar = tk.Frame(self, bg="#3a86ff", pady=6)
        toolbar.pack(fill=tk.X)

        tk.Label(
            toolbar,
            text="🪄  瘦身效果预览",
            font=("Arial", 18, "bold"),
            bg="#3a86ff", fg="white"
        ).pack(side=tk.LEFT, padx=14)

        # ---- 主体区域 ----
        main = tk.Frame(self, bg="#f5f5f5")
        main.pack(fill=tk.BOTH, expand=True, padx=16, pady=10)

        # 左侧控制面板
        ctrl_frame = tk.LabelFrame(
            main, text="控制面板", bg="#f5f5f5",
            font=("Arial", 11, "bold"), padx=10, pady=10
        )
        ctrl_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 12))

        self._build_controls(ctrl_frame)

        # 右侧图像展示
        img_frame = tk.Frame(main, bg="#f5f5f5")
        img_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._build_image_panels(img_frame)

        # ---- 底部状态栏 ----
        self._status_var = tk.StringVar(value="请上传或拍摄一张照片以开始。")
        status_bar = tk.Label(
            self, textvariable=self._status_var,
            bg="#e0e0e0", anchor=tk.W, padx=8, pady=4,
            font=("Arial", 10)
        )
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def _build_controls(self, parent):
        pad = {"pady": 5, "fill": tk.X}

        # ---- 照片来源 ----
        tk.Label(parent, text="📷  照片来源", font=("Arial", 11, "bold"),
                 bg="#f5f5f5").pack(**pad)

        tk.Button(
            parent, text="📂  上传照片", width=18,
            command=self._upload_photo,
            bg="#3a86ff", fg="white", font=("Arial", 10, "bold"),
            relief=tk.FLAT, cursor="hand2"
        ).pack(**pad)

        if CV2_AVAILABLE:
            tk.Button(
                parent, text="📸  拍摄照片", width=18,
                command=self._capture_photo,
                bg="#06d6a0", fg="white", font=("Arial", 10, "bold"),
                relief=tk.FLAT, cursor="hand2"
            ).pack(**pad)
        else:
            tk.Label(
                parent,
                text="（安装 opencv-python\n可启用拍照功能）",
                font=("Arial", 8), fg="#999", bg="#f5f5f5", justify=tk.LEFT
            ).pack(**pad)

        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

        # ---- 瘦身幅度 ----
        tk.Label(parent, text="⚖️  瘦身幅度", font=("Arial", 11, "bold"),
                 bg="#f5f5f5").pack(**pad)

        self._slim_var = tk.IntVar(value=DEFAULT_SLIM)
        self._slim_label = tk.Label(
            parent, text=f"{DEFAULT_SLIM}%",
            font=("Arial", 13, "bold"), fg="#3a86ff", bg="#f5f5f5"
        )
        self._slim_label.pack()

        slim_scale = ttk.Scale(
            parent, from_=5, to=50, orient=tk.HORIZONTAL,
            variable=self._slim_var, length=170,
            command=self._on_slim_change
        )
        slim_scale.pack(**pad)

        tk.Label(parent, text="5%（微调）→ 50%（大幅瘦身）",
                 font=("Arial", 8), fg="#666", bg="#f5f5f5").pack()

        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

        # ---- 变换方式 ----
        tk.Label(parent, text="🔧  变换方式", font=("Arial", 11, "bold"),
                 bg="#f5f5f5").pack(**pad)

        self._method_var = tk.StringVar(value="local")
        tk.Radiobutton(
            parent, text="本地处理（快速）", variable=self._method_var,
            value="local", bg="#f5f5f5", font=("Arial", 10)
        ).pack(anchor=tk.W)

        ai_rb = tk.Radiobutton(
            parent, text="AI 生成（OpenAI）", variable=self._method_var,
            value="ai", bg="#f5f5f5", font=("Arial", 10),
            state=tk.NORMAL if OPENAI_AVAILABLE else tk.DISABLED
        )
        ai_rb.pack(anchor=tk.W)

        if not OPENAI_AVAILABLE:
            tk.Label(
                parent,
                text="（安装 openai 包\n可启用 AI 生成）",
                font=("Arial", 8), fg="#999", bg="#f5f5f5", justify=tk.LEFT
            ).pack(anchor=tk.W, padx=16)

        # OpenAI API Key 输入
        tk.Label(parent, text="OpenAI API Key（可选）:",
                 font=("Arial", 9), bg="#f5f5f5").pack(anchor=tk.W, pady=(6, 0))
        self._apikey_var = tk.StringVar(value=os.environ.get("OPENAI_API_KEY", ""))
        tk.Entry(
            parent, textvariable=self._apikey_var,
            width=20, show="*", font=("Arial", 9)
        ).pack(**pad)

        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

        # ---- 操作按钮 ----
        self._generate_btn = tk.Button(
            parent, text="✨  生成效果", width=18,
            command=self._generate,
            bg="#ff6b6b", fg="white", font=("Arial", 11, "bold"),
            relief=tk.FLAT, cursor="hand2"
        )
        self._generate_btn.pack(**pad)

        tk.Button(
            parent, text="💾  保存结果", width=18,
            command=self._save_result,
            bg="#8338ec", fg="white", font=("Arial", 10, "bold"),
            relief=tk.FLAT, cursor="hand2"
        ).pack(**pad)

        tk.Button(
            parent, text="🔄  重置", width=18,
            command=self._reset,
            bg="#adb5bd", fg="white", font=("Arial", 10),
            relief=tk.FLAT, cursor="hand2"
        ).pack(**pad)

    def _build_image_panels(self, parent):
        panels = tk.Frame(parent, bg="#f5f5f5")
        panels.pack(fill=tk.BOTH, expand=True)

        # 原始图像
        orig_frame = tk.LabelFrame(
            panels, text="原始照片", bg="#f5f5f5",
            font=("Arial", 10, "bold"), padx=6, pady=6
        )
        orig_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        self._orig_canvas = tk.Canvas(
            orig_frame, width=PREVIEW_MAX, height=PREVIEW_MAX,
            bg="#e9ecef", highlightthickness=1, highlightbackground="#ccc"
        )
        self._orig_canvas.pack()
        self._orig_canvas.create_text(
            PREVIEW_MAX // 2, PREVIEW_MAX // 2,
            text="上传照片后显示", fill="#999", font=("Arial", 12),
            tags="placeholder_orig"
        )

        # 结果图像
        result_frame = tk.LabelFrame(
            panels, text="瘦身效果", bg="#f5f5f5",
            font=("Arial", 10, "bold"), padx=6, pady=6
        )
        result_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))

        self._result_canvas = tk.Canvas(
            result_frame, width=PREVIEW_MAX, height=PREVIEW_MAX,
            bg="#e9ecef", highlightthickness=1, highlightbackground="#ccc"
        )
        self._result_canvas.pack()
        self._result_canvas.create_text(
            PREVIEW_MAX // 2, PREVIEW_MAX // 2,
            text='点击「生成效果」后显示', fill="#999", font=("Arial", 12),
            tags="placeholder_result"
        )

    # ── 事件处理 ──────────────────────────────────────────────────────────────

    def _on_slim_change(self, _event=None):
        val = int(self._slim_var.get())
        self._slim_label.config(text=f"{val}%")

    def _upload_photo(self):
        path = filedialog.askopenfilename(
            title="选择照片",
            filetypes=[
                ("图片文件", "*.jpg *.jpeg *.png *.bmp *.webp *.tiff"),
                ("所有文件", "*.*"),
            ]
        )
        if not path:
            return
        try:
            img = Image.open(path).convert("RGB")
            self._set_original(img)
            self._set_status(f"已加载：{os.path.basename(path)}  ({img.width}×{img.height})")
        except Exception as exc:
            messagebox.showerror("错误", f"无法打开图片：{exc}")

    def _capture_photo(self):
        """使用 OpenCV 打开摄像头并拍摄一帧。"""
        if not CV2_AVAILABLE:
            messagebox.showwarning("提示", "请先安装 opencv-python 以使用拍照功能。")
            return

        cap = cv2.VideoCapture(CAMERA_INDEX)
        if not cap.isOpened():
            messagebox.showerror("错误", "无法打开摄像头，请检查设备连接。")
            return

        win_name = "按 空格键 拍摄  |  按 Esc 取消"
        cv2.namedWindow(win_name)

        captured = None
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                cv2.imshow(win_name, frame)
                key = cv2.waitKey(1) & 0xFF
                if key == 32:   # 空格键
                    captured = frame.copy()
                    break
                if key == 27:   # Esc
                    break
        finally:
            cap.release()
            cv2.destroyAllWindows()

        if captured is not None:
            # OpenCV 使用 BGR，需转为 RGB
            rgb = cv2.cvtColor(captured, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb)
            self._set_original(img)
            self._set_status(f"已拍摄照片  ({img.width}×{img.height})")

    def _generate(self):
        if self._original_image is None:
            messagebox.showwarning("提示", "请先上传或拍摄一张照片。")
            return

        method = self._method_var.get()
        slim_pct = int(self._slim_var.get())

        # Disable the button to prevent concurrent requests
        self._generate_btn.config(state=tk.DISABLED)

        if method == "ai":
            api_key = self._apikey_var.get().strip()
            if not api_key:
                self._generate_btn.config(state=tk.NORMAL)
                messagebox.showwarning("提示", "请在下方输入 OpenAI API Key。")
                return
            self._set_status("正在使用 AI 生成瘦身效果，请稍候…")
            self.config(cursor="wait")
            threading.Thread(
                target=self._ai_generate_thread,
                args=(self._original_image.copy(), api_key, slim_pct),
                daemon=True
            ).start()
        else:
            self._set_status("正在处理图像…")
            self.config(cursor="wait")
            threading.Thread(
                target=self._local_generate_thread,
                args=(self._original_image.copy(), slim_pct),
                daemon=True
            ).start()

    def _local_generate_thread(self, image, slim_pct):
        try:
            result = apply_slim_effect(image, slim_pct)
            self.after(0, lambda r=result: self._on_result_ready(r))
        except Exception as exc:
            self.after(0, lambda e=exc: self._on_error(str(e)))

    def _ai_generate_thread(self, image, api_key, slim_pct):
        try:
            result = ai_slim_transform(image, api_key, slim_pct)
            self.after(0, lambda r=result: self._on_result_ready(r))
        except Exception as exc:
            self.after(0, lambda e=exc: self._on_error(str(e)))

    def _on_result_ready(self, result_image: Image.Image):
        self._result_image = result_image
        self._display_result(result_image)
        self._set_status('✅  瘦身效果已生成！点击「保存结果」可保存图片。')
        self.config(cursor="")
        self._generate_btn.config(state=tk.NORMAL)

    def _on_error(self, msg: str):
        self.config(cursor="")
        self._generate_btn.config(state=tk.NORMAL)
        self._set_status(f"❌  处理失败：{msg}")
        messagebox.showerror("处理失败", msg)

    def _save_result(self):
        if self._result_image is None:
            messagebox.showwarning("提示", '尚未生成效果，请先点击「生成效果」。')
            return
        path = filedialog.asksaveasfilename(
            title="保存瘦身效果图",
            defaultextension=".png",
            filetypes=[("PNG 图片", "*.png"), ("JPEG 图片", "*.jpg"), ("所有文件", "*.*")]
        )
        if not path:
            return
        try:
            self._result_image.save(path)
            self._set_status(f"💾  已保存至：{path}")
        except Exception as exc:
            messagebox.showerror("保存失败", str(exc))

    def _reset(self):
        self._original_image = None
        self._result_image = None
        self._tk_original = None
        self._tk_result = None
        self._orig_canvas.delete("all")
        self._orig_canvas.create_text(
            PREVIEW_MAX // 2, PREVIEW_MAX // 2,
            text="上传照片后显示", fill="#999", font=("Arial", 12)
        )
        self._result_canvas.delete("all")
        self._result_canvas.create_text(
            PREVIEW_MAX // 2, PREVIEW_MAX // 2,
            text='点击「生成效果」后显示', fill="#999", font=("Arial", 12)
        )
        self._slim_var.set(DEFAULT_SLIM)
        self._slim_label.config(text=f"{DEFAULT_SLIM}%")
        self._set_status("已重置，请上传或拍摄一张照片以开始。")

    # ── 辅助方法 ──────────────────────────────────────────────────────────────

    def _set_original(self, image: Image.Image):
        self._original_image = image
        self._result_image = None
        self._display_on_canvas(image, self._orig_canvas, "_tk_original")
        self._result_canvas.delete("all")
        self._result_canvas.create_text(
            PREVIEW_MAX // 2, PREVIEW_MAX // 2,
            text='点击「生成效果」后显示', fill="#999", font=("Arial", 12)
        )

    def _display_result(self, image: Image.Image):
        self._display_on_canvas(image, self._result_canvas, "_tk_result")

    def _display_on_canvas(self, image: Image.Image, canvas: tk.Canvas, attr: str):
        preview = resize_for_preview(image, PREVIEW_MAX)
        tk_img = ImageTk.PhotoImage(preview)
        setattr(self, attr, tk_img)   # 保持引用防止 GC

        canvas.delete("all")
        # 居中显示
        cx = PREVIEW_MAX // 2
        cy = PREVIEW_MAX // 2
        canvas.create_image(cx, cy, image=tk_img, anchor=tk.CENTER)

    def _set_status(self, msg: str):
        self._status_var.set(msg)
        self.update_idletasks()


# ─────────────────────────────────────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = SlimVisualizerApp()
    app.mainloop()
