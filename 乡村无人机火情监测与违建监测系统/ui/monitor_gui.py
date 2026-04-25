import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont
import cv2
import numpy as np
import threading
import os
from datetime import datetime
from typing import Optional
import config
from models.detector import DualDetectionEngine
from processors.image_processor import ImageProcessor, VideoProcessor, draw_detections
from storage.db_manager import AlertManager, DatabaseManager


class ModuleCard(tk.Frame):

    def __init__(self, parent, title: str, icon: str, color: str,
                 value_text: str = "0", detail_text: str = "",
                 on_click=None, **kw):
        super().__init__(parent, **kw)
        self.on_click = on_click
        self.title = title
        self.icon = icon
        self.color = color
        self.selected = False
        self.configure(bg="#1e293b", cursor="hand2")
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self._build_ui(title, icon, color, value_text, detail_text)

    def _build_ui(self, title, icon, color, value_text, detail_text):
        self.inner = tk.Frame(self, bg="#0f172a")
        self.inner.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.header_frame = tk.Frame(self.inner, bg="#0f172a")
        self.header_frame.pack(fill=tk.X, padx=10, pady=(8, 2))
        self.icon_label = tk.Label(
            self.header_frame, text=icon,
            font=("Segoe UI Emoji", 14), bg="#0f172a", fg=color
        )
        self.icon_label.pack(side=tk.LEFT)
        self.title_label = tk.Label(
            self.header_frame, text=title,
            font=("Microsoft YaHei UI", 11, "bold"), bg="#0f172a", fg="#e2e8f0"
        )
        self.title_label.pack(side=tk.LEFT, padx=(6, 0))
        self.value_label = tk.Label(
            self.inner, text=value_text,
            font=("Microsoft YaHei UI", 24, "bold"),
            bg="#0f172a", fg="#ffffff"
        )
        self.value_label.pack(anchor=tk.W, padx=10)
        self.detail_label = tk.Label(
            self.inner, text=detail_text,
            font=("Microsoft YaHei UI", 9),
            bg="#0f172a", fg="#94a3b8"
        )
        self.detail_label.pack(anchor=tk.W, padx=10, pady=(0, 8))

    def update_value(self, value_text: str, detail_text: str = ""):
        self.value_label.config(text=value_text)
        if detail_text:
            self.detail_label.config(text=detail_text)

    def set_selected(self, selected: bool):
        self.selected = selected
        if selected:
            self.configure(bg=self.color)
        else:
            self.configure(bg="#1e293b")

    def _on_enter(self, e):
        if not self.selected:
            self.configure(bg="#334155")

    def _on_leave(self, e):
        if not self.selected:
            self.configure(bg="#1e293b")

    def _on_click(self, e):
        if self.on_click:
            self.on_click(self)


class DetailPanel(ttk.Frame):

    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self.configure(style="Detail.TFrame")
        self._build()

    def _build(self):
        self.title_bar = tk.Frame(self, bg="#1e40af")
        self.title_bar.pack(fill=tk.X)
        self.detail_title = tk.Label(
            self.title_bar, text="详细信息",
            font=("Microsoft YaHei UI", 11, "bold"),
            bg="#1e40af", fg="white"
        )
        self.detail_title.pack(side=tk.LEFT, padx=10, pady=5)
        self.close_btn = tk.Label(
            self.title_bar, text=" ✕ ",
            font=("Microsoft YaHei UI", 12, "bold"),
            bg="#1e40af", fg="white", cursor="hand2"
        )
        self.close_btn.pack(side=tk.RIGHT, padx=5, pady=5)
        self.content = tk.Text(
            self, font=("Microsoft YaHei UI", 10),
            bg="#0f172a", fg="#e2e8f0",
            relief=tk.FLAT, padx=10, pady=10,
            wrap=tk.WORD, state=tk.DISABLED,
            height=20
        )
        self.content.pack(fill=tk.BOTH, expand=True)

    def show_content(self, title: str, content: str, on_close=None):
        self.detail_title.config(text=title)
        self.content.config(state=tk.NORMAL)
        self.content.delete(1.0, tk.END)
        self.content.insert(1.0, content)
        self.content.config(state=tk.DISABLED)
        if on_close:
            self.close_btn.unbind("<Button-1>")
            self.close_btn.bind("<Button-1>", lambda e: on_close())


class DroneMonitorGUI:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("乡村无人机自动巡检系统 - 智能监测平台")
        self.root.geometry("1450x920")
        self.root.configure(bg="#0f172a")
        self.engine = DualDetectionEngine()
        self.img_processor = ImageProcessor(self.engine)
        self.video_processor = VideoProcessor(self.engine)
        self.alert_manager = AlertManager(DatabaseManager())
        self.alert_manager.register_callback(self._on_new_alert)
        self._running = False
        self._video_thread: Optional[threading.Thread] = None
        self._camera_thread: Optional[threading.Thread] = None
        self._current_mode = "idle"
        self.current_image_tk: Optional[ImageTk.PhotoImage] = None
        self.alert_log_data = []
        self.module_cards = {}
        self.current_module = None
        self._setup_ui()
        self._update_stats()

    def _setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        self._build_header()
        self._build_main_area()
        self._build_control_panel()
        self._build_status_bar()

    def _build_header(self):
        header = tk.Frame(self.root, bg="#1e293b", height=65)
        header.pack(fill=tk.X, padx=0, pady=0)
        header.pack_propagate(False)
        left_group = tk.Frame(header, bg="#1e293b")
        left_group.pack(side=tk.LEFT, padx=20, pady=8)
        title_label = tk.Label(
            left_group, text="🚁 乡村无人机自动巡检系统",
            font=("Microsoft YaHei UI", 18, "bold"),
            fg="#38bdf8", bg="#1e293b"
        )
        title_label.pack(anchor=tk.W)
        subtitle = tk.Label(
            left_group, text="违建与火情智能监测平台  |  YOLOv8 + PyTorch 深度学习引擎",
            font=("Microsoft YaHei UI", 9), fg="#94a3b8", bg="#1e293b"
        )
        subtitle.pack(anchor=tk.W)
        status_indicator = tk.Label(
            header, text="● 系统就绪",
            font=("Microsoft YaHei UI", 11, "bold"),
            fg="#22c55e", bg="#1e293b"
        )
        status_indicator.pack(side=tk.RIGHT, padx=25, pady=18)
        self.status_indicator = status_indicator

    def _build_main_area(self):
        main_frame = tk.Frame(self.root, bg="#0f172a")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        left_panel = tk.Frame(main_frame, bg="#1e293b", relief=tk.RIDGE, bd=2)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        video_title = tk.Label(
            left_panel, text="📹 实时监控画面",
            font=("Microsoft YaHei UI", 12, "bold"), fg="#38bdf8", bg="#1e293b"
        )
        video_title.pack(anchor=tk.W, padx=10, pady=(6, 3))
        self.video_label = tk.Label(left_panel, bg="#020617",
                                    text="⏳  等待输入源...\n\n点击下方按钮开始检测\n支持图片 / 视频 / 摄像头",
                                    font=("Microsoft YaHei UI", 13), fg="#64748b", justify=tk.CENTER)
        self.video_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        right_container = tk.Frame(main_frame, bg="#0f172a", width=400)
        right_container.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        right_container.pack_propagate(False)
        self._build_module_grid(right_container)
        sep = tk.Frame(right_container, bg="#334155", height=1)
        sep.pack(fill=tk.X, padx=8, pady=8)
        self._build_log_section(right_container)

    def _build_module_grid(self, parent):
        grid_frame = tk.Frame(parent, bg="#0f172a")
        grid_frame.pack(fill=tk.X, padx=5, pady=(5, 0))
        grid_title = tk.Label(
            grid_frame, text="📊 监测模块",
            font=("Microsoft YaHei UI", 11, "bold"), fg="#38bdf8", bg="#0f172a"
        )
        grid_title.pack(anchor=tk.W, padx=5, pady=(0, 6))
        cards_frame = tk.Frame(grid_frame, bg="#0f172a")
        cards_frame.pack(fill=tk.X)
        modules = [
            ("fire", "🔥 火情监测", "#ef4444", "0", "实时火焰/烟雾检测"),
            ("smoke", "💨 烟雾监测", "#9ca3af", "0", "烟雾浓度异常识别"),
            ("build", "🏗️ 违建监测", "#f59e0b", "0", "违规建筑智能识别"),
            ("total", "📈 巡检总览", "#3b82f6", "0", "综合统计与报告"),
        ]
        for key, title, color, val, detail in modules:
            card = ModuleCard(
                cards_frame, title=title, icon=title.split()[0],
                color=color, value_text=val, detail_text=detail,
                on_click=lambda c, k=key: self._on_module_click(k, c),
                width=24, height=75
            )
            card.pack(fill=tk.X, pady=3)
            self.module_cards[key] = card

    def _build_log_section(self, parent):
        log_frame = tk.Frame(parent, bg="#0f172a")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        log_title = tk.Label(
            log_frame, text="🔔 预警日志（最近30条）",
            font=("Microsoft YaHei UI", 11, "bold"), fg="#38bdf8", bg="#0f172a"
        )
        log_title.pack(anchor=tk.W, padx=5, pady=(4, 4))
        log_container = tk.Frame(log_frame, bg="#0f172a")
        log_container.pack(fill=tk.BOTH, expand=True)
        scrollbar = tk.Scrollbar(log_container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.alert_listbox = tk.Listbox(
            log_container, yscrollcommand=scrollbar.set,
            font=("Microsoft YaHei UI", 9), bg="#0f172a", fg="#e2e8f0",
            selectbackground="#3b82f6", selectforeground="white",
            height=12, relief=tk.FLAT, bd=0
        )
        self.alert_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.alert_listbox.yview)

    def _build_control_panel(self):
        control_frame = tk.Frame(self.root, bg="#1e293b", height=80)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        control_frame.pack_propagate(False)
        btn_left = tk.Frame(control_frame, bg="#1e293b")
        btn_left.pack(side=tk.LEFT, padx=15, pady=12)
        buttons = [
            ("🖼️ 打开图片", self._open_image, "#3b82f6"),
            ("🎬 打开视频", self._open_video, "#8b5cf6"),
            ("📷 启动摄像头", self._toggle_camera, "#10b981"),
        ]
        for text, cmd, color in buttons:
            btn = tk.Button(btn_left, text=text, command=cmd,
                            font=("Microsoft YaHei UI", 10, "bold"),
                            bg=color, fg="white", activebackground=color,
                            width=14, height=2, cursor="hand2",
                            relief=tk.FLAT, bd=0)
            btn.pack(side=tk.LEFT, padx=4)
            if text == "🖼️ 打开图片":
                self.btn_open_img = btn
            elif text == "🎬 打开视频":
                self.btn_open_video = btn
            elif text == "📷 启动摄像头":
                self.btn_camera = btn
        btn_right = tk.Frame(control_frame, bg="#1e293b")
        btn_right.pack(side=tk.RIGHT, padx=15, pady=12)
        self.btn_stop = tk.Button(
            btn_right, text="⏹ 停止检测", command=self._stop_detection,
            font=("Microsoft YaHei UI", 10, "bold"), bg="#ef4444", fg="white",
            activebackground="#dc2626", width=13, height=2, cursor="hand2",
            relief=tk.FLAT, bd=0, state=tk.DISABLED
        )
        self.btn_stop.pack(side=tk.LEFT, padx=4)
        self.btn_report = tk.Button(
            btn_right, text="📋 导出报告", command=self._export_report,
            font=("Microsoft YaHei UI", 10, "bold"), bg="#f59e0b", fg="white",
            activebackground="#d97706", width=13, height=2, cursor="hand2",
            relief=tk.FLAT, bd=0
        )
        self.btn_report.pack(side=tk.LEFT, padx=4)

    def _build_status_bar(self):
        status_bar = tk.Frame(self.root, bg="#020617", height=30)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_var = tk.StringVar(value="✅ 系统就绪  |  等待操作...")
        status_label = tk.Label(
            status_bar, textvariable=self.status_var,
            font=("Microsoft YaHei UI", 9), fg="#94a3b8", bg="#020617", anchor=tk.W
        )
        status_label.pack(side=tk.LEFT, padx=12, pady=5)
        time_label = tk.Label(
            status_bar, text="", font=("Microsoft YaHei UI", 9),
            fg="#64748b", bg="#020617", anchor=tk.E
        )
        time_label.pack(side=tk.RIGHT, padx=12, pady=5)
        self._update_clock(time_label)

    def _update_clock(self, label):
        label.config(text=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.root.after(1000, lambda: self._update_clock(label))

    def _on_module_click(self, module_key: str, card: ModuleCard):
        for k, c in self.module_cards.items():
            c.set_selected(k == module_key)
        self.current_module = module_key
        self._show_module_detail(module_key)

    def _show_module_detail(self, key: str):
        summary = self.alert_manager.get_alert_summary()
        db_full = summary.get("db_full", {})
        if key == "fire":
            fire_count = summary.get("fire_count", 0)
            recent_fire = [a for a in self.alert_manager.get_recent_alerts(30) if "fire" in a.get("type", "")]
            content = f"═══ 🔥 火情监测详情 ═══\n\n"
            content += f"▸ 本轮检测火情警报数：{fire_count}\n"
            content += f"▸ 数据库累计火情警报：{db_full.get('fire_total', 0)}\n"
            content += f"▸ 高严重度警报：{db_full.get('high_severity_count', 0)}\n\n"
            content += f"─── 最近火情记录 ───\n"
            if recent_fire:
                for i, a in enumerate(recent_fire[:10], 1):
                    content += f"\n{i}. [{a['timestamp']}] {a.get('label','')}\n   置信度: {a.get('confidence',0):.1%} | 严重度: {a.get('severity','')}"
            else:
                content += "\n  暂无火情警报记录"
            messagebox.showinfo("🔥 火情监测详情", content)
        elif key == "smoke":
            smoke_count = summary.get("smoke_count", 0)
            recent_smoke = [a for a in self.alert_manager.get_recent_alerts(30) if a.get("type") == "smoke"]
            content = f"═══ 💨 烟雾监测详情 ═══\n\n"
            content += f"▸ 本轮检测烟雾警报数：{smoke_count}\n"
            content += f"▸ 数据库累计烟雾警报：{db_full.get('smoke_total', 0)}\n\n"
            content += f"─── 最近烟雾记录 ───\n"
            if recent_smoke:
                for i, a in enumerate(recent_smoke[:10], 1):
                    content += f"\n{i}. [{a['timestamp']}] {a.get('label','')}\n   置信度: {a.get('confidence',0):.1%} | 严重度: {a.get('severity','')}"
            else:
                content += "\n  暂无烟雾警报记录"
            messagebox.showinfo("💨 烟雾监测详情", content)
        elif key == "build":
            build_count = summary.get("illegal_build_count", 0)
            recent_build = [a for a in self.alert_manager.get_recent_alerts(30) if "build" in a.get("type", "")]
            content = f"═══ 🏗️ 违建监测详情 ═══\n\n"
            content += f"▸ 本轮检测违建警报数：{build_count}\n"
            content += f"▸ 数据库累计违建警报：{db_full.get('build_total', 0)}\n\n"
            content += f"─── 最近违建记录 ───\n"
            if recent_build:
                for i, a in enumerate(recent_build[:10], 1):
                    content += f"\n{i}. [{a['timestamp']}] {a.get('label','')}\n   目标: {a.get('class_name','')} | 置信度: {a.get('confidence',0):.1%}"
            else:
                content += "\n  暂无违建警报记录"
            messagebox.showinfo("🏗️ 违建监测详情", content)
        elif key == "total":
            total_inspections = db_full.get("total_inspections", 0)
            total_alerts = db_full.get("total_alerts", 0)
            first_time = db_full.get("first_inspection_time", "N/A")
            last_time = db_full.get("last_inspection_time", "N/A")
            content = f"═══ 📈 巡检总览 ═══\n\n"
            content += f"▸ 总巡检次数：{total_inspections}\n"
            content += f"▸ 累计警报总数：{total_alerts}\n"
            content += f"▸ 火情警报：{db_full.get('fire_total', 0)}\n"
            content += f"▸ 烟雾警报：{db_full.get('smoke_total', 0)}\n"
            content += f"▸ 违建警报：{db_full.get('build_total', 0)}\n"
            content += f"▸ 高危警报：{db_full.get('high_severity_count', 0)}\n\n"
            content += f"▸ 首次巡检时间：{first_time}\n"
            content += f"▸ 最近巡检时间：{last_time}\n\n"
            content += f"─── 引擎信息 ───\n"
            content += f"  检测引擎: YOLOv8 + PyTorch\n"
            content += f"  图像分辨率: {config.DISPLAY_WIDTH}x{config.DISPLAY_HEIGHT}\n"
            content += f"  置信度阈值: {config.CONFIDENCE_THRESHOLD}"
            messagebox.showinfo("📈 巡检总览", content)

    def _update_display(self, frame_np: np.ndarray):
        try:
            if len(frame_np.shape) == 3:
                rgb = cv2.cvtColor(frame_np, cv2.COLOR_BGR2RGB)
            else:
                rgb = cv2.cvtColor(frame_np, cv2.COLOR_GRAY2RGB)
            image = Image.fromarray(rgb)
            display_w = self.video_label.winfo_width() or 900
            display_h = self.video_label.winfo_height() or 550
            image.thumbnail((display_w - 10, display_h - 10), Image.Resampling.LANCZOS)
            self.current_image_tk = ImageTk.PhotoImage(image)
            self.video_label.config(image=self.current_image_tk, text="")
        except Exception as e:
            print(f"[显示错误] {e}")

    def _on_new_alert(self, alerts):
        self.root.after(0, lambda: self._process_gui_alerts(alerts))

    def _process_gui_alerts(self, alerts):
        for alert in alerts:
            ts = alert.get("timestamp", "")[-8:]
            label = alert.get("label", "")
            conf = alert.get("confidence", 0)
            severity = alert.get("severity", "medium")
            type_map = {"high": "【高危】", "medium": "【中等】", "low": "【低危】"}
            prefix = type_map.get(severity, "")
            entry = f"{prefix}[{ts}] {label} ({conf:.1%})"
            self.alert_listbox.insert(0, entry)
            color_map = {"high": "#ef4444", "medium": "#f59e0b", "low": "#22c55e"}
            self.alert_listbox.itemconfig(0, {'fg': color_map.get(severity, "#ffffff")})
        total = self.alert_listbox.size()
        if total > 50:
            self.alert_listbox.delete(50, tk.END)
        self._update_stats()
        if any(a.get("severity") == "high" for a in alerts):
            self._flash_warning()

    def _flash_warning(self):
        original_bg = self.root.cget("bg")
        colors = ["#450a0a", original_bg, "#450a0a", original_bg]
        delays = [200, 200, 200]

        def flash_step(step=0):
            if step < len(colors):
                self.root.configure(bg=colors[step])
                self.root.after(delays[step], lambda: flash_step(step + 1))
            else:
                self.root.configure(bg=original_bg)
        flash_step()

    def _update_stats(self):
        summary = self.alert_manager.get_alert_summary()
        fire_cnt = summary.get("fire_count", 0)
        smoke_cnt = summary.get("smoke_count", 0)
        build_cnt = summary.get("illegal_build_count", 0)
        db_full = summary.get("db_full", {})
        total_insp = db_full.get("total_inspections", 0)
        total_alerts = fire_cnt + smoke_cnt + build_cnt
        self.module_cards["fire"].update_value(str(fire_cnt), f"本轮检测到 {fire_cnt} 条火情警报")
        self.module_cards["smoke"].update_value(str(smoke_cnt), f"本轮检测到 {smoke_cnt} 条烟雾警报")
        self.module_cards["build"].update_value(str(build_cnt), f"本轮检测到 {build_cnt} 条违建警报")
        self.module_cards["total"].update_value(str(total_insp), f"累计 {total_alerts} 条警报")

    def _set_status(self, msg: str, is_alert: bool = False):
        self.status_var.set(msg)
        if is_alert:
            self.status_indicator.config(text="● 警报中!", fg="#ef4444")
        else:
            self.status_indicator.config(text="● 运行中", fg="#22c55e")

    def _open_image(self):
        path = filedialog.askopenfilename(
            title="选择巡检图像",
            filetypes=[
                ("图像文件", "*.jpg *.jpeg *.png *.bmp *.tiff *.webp"),
                ("所有文件", "*.*")
            ]
        )
        if not path:
            return
        self._set_status(f"正在分析图像: {os.path.basename(path)}...")
        self.root.update()
        try:
            vis_frame, result = self.img_processor.process_image(path)
            self._update_display(vis_frame)
            self.alert_manager.process_detection_result(result, vis_frame, source_type="image", source_path=path)
            fire_n = len(result.get("fires", []))
            smoke_n = len(result.get("smokes", []))
            build_n = len(result.get("illegal_builds", []))
            status_msg = f"分析完成 | 🔥火情:{fire_n} 💨烟雾:{smoke_n} 🏗违建:{build_n}"
            if result.get("has_alert"):
                self._set_status(status_msg, is_alert=True)
            else:
                self._set_status(status_msg)
        except Exception as e:
            messagebox.showerror("错误", f"图像处理失败:\n{str(e)}")
            self._set_status("图像处理失败")

    def _open_video(self):
        path = filedialog.askopenfilename(
            title="选择视频文件",
            filetypes=[
                ("视频文件", "*.mp4 *.avi *.mov *.mkv *.flv *.wmv *.ts *.m2ts *.webm *.3gp *.m4v"),
                ("所有文件", "*.*")
            ]
        )
        if not path:
            return
        self._stop_detection()
        self._current_mode = "video"
        self._running = True
        self.btn_stop.config(state=tk.NORMAL)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_name = os.path.splitext(os.path.basename(path))[0]
        safe_name = "".join(c for c in safe_name if c.isalnum() or c in "_- ")
        output_path = os.path.join(config.OUTPUT_DIR, f"detect_{safe_name}_{ts}.mp4")

        def run_video():
            self._set_status(f"正在分析视频: {os.path.basename(path)}...")
            try:
                results = self.video_processor.process_video_file(
                    path, output_path=output_path,
                    callback=lambda f, r: self._video_callback(f, r),
                    show_display=False
                )
                self.root.after(0, lambda: self._on_video_done(results, output_path))
            except Exception as e:
                err_msg = str(e)
                self.root.after(0, lambda: messagebox.showerror("错误", f"视频处理失败:\n{err_msg}"))
                self.root.after(0, lambda: self._on_detection_stopped())

        self._video_thread = threading.Thread(target=run_video, daemon=True)
        self._video_thread.start()

    def _video_callback(self, frame, result):
        try:
            self.alert_manager.process_detection_result(result, frame, source_type="video")
            self.root.after(0, lambda: self._update_display(frame))
        except Exception:
            pass

    def _on_video_done(self, results, output_path):
        total = len(results)
        alert_count = sum(1 for r in results if r.get("has_alert"))
        messagebox.showinfo("视频分析完成",
                             f"✅ 分析完成！\n\n"
                             f"总帧数: {total}\n"
                             f"异常帧数: {alert_count}\n\n"
                             f"结果已保存至:\n{output_path}")
        self._on_detection_stopped()

    def _toggle_camera(self):
        if self._current_mode == "camera":
            self._stop_detection()
            return
        self._stop_detection()
        self._current_mode = "camera"
        self._running = True
        self.btn_camera.config(text="⏹ 关闭摄像头", bg="#ef4444")
        self.btn_stop.config(state=tk.NORMAL)

        def run_camera():
            self._set_status("摄像头实时检测中... 按 '停止' 结束")
            try:
                for frame, result in self.video_processor.process_camera(
                    callback=lambda f, r: self._camera_callback(f, r),
                    show_display=False
                ):
                    if not self._running:
                        break
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("错误", f"摄像头错误:\n{str(e)}"))
            finally:
                self.root.after(0, lambda: self._on_detection_stopped())

        self._camera_thread = threading.Thread(target=run_camera, daemon=True)
        self._camera_thread.start()

    def _camera_callback(self, frame, result):
        try:
            self.alert_manager.process_detection_result(result, frame, source_type="camera")
            self.root.after(0, lambda: self._update_display(frame))
        except Exception:
            pass

    def _stop_detection(self):
        self._running = False
        self.video_processor.stop()
        self._current_mode = "idle"
        self.btn_stop.config(state=tk.DISABLED)
        self.btn_camera.config(text="📷 启动摄像头", bg="#10b981")
        self.status_indicator.config(text="● 系统就绪", fg="#22c55e")
        self._set_status("已停止检测")

    def _on_detection_stopped(self):
        self._running = False
        self._current_mode = "idle"
        self.btn_stop.config(state=tk.DISABLED)
        self.btn_camera.config(text="📷 启动摄像头", bg="#10b981")
        self.status_indicator.config(text="● 系统就绪", fg="#22c55e")
        self._set_status("检测已停止")

    def _export_report(self):
        try:
            report_path = self.alert_manager.generate_report_html()
            messagebox.showinfo("报告导出成功", f"HTML可视化报告已生成！\n\n保存路径:\n{report_path}")
            os.startfile(report_path)
        except Exception as e:
            messagebox.showerror("错误", f"导出失败:\n{str(e)}")

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _on_close(self):
        self._running = False
        self.video_processor.stop()
        self.root.quit()
        self.root.destroy()


def launch_gui():
    app = DroneMonitorGUI()
    app.run()


if __name__ == "__main__":
    launch_gui()
