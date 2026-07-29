# 无人机火情智能监测预警系统

基于 YOLOv8 的火情自动监测系统，支持图片/视频/摄像头多源输入，4维度误检过滤，集成告警存储与报告导出。

## 解决什么问题

传统人工巡检效率低、覆盖范围小、实时性差。本系统通过计算机视觉自动识别火焰，可 7×24 小时监控，替代人工巡检。

## 技术栈

- **目标检测**：YOLOv8（Ultralytics）
- **图像处理**：OpenCV
- **GUI**：Tkinter
- **数据库**：SQLite
- **告警导出**：HTML 报告

## 核心模块

```
main.py              # 主程序入口
config.py            # 配置（检测阈值、告警参数）
models/detector.py   # YOLOv8 检测器
processors/image_processor.py  # 图像预处理、4维度误检过滤
storage/db_manager.py  # SQLite 告警存储
ui/monitor_gui.py    # Tkinter 监控界面
```

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 下载 YOLOv8 权重（yolov8n.pt）
# 放到项目根目录

# 3. 运行
python main.py
```

## 4维度误检过滤机制

1. **颜色过滤**：HSV 颜色空间提取火焰候选区域
2. **纹理过滤**：火焰纹理特征判断
3. **动态过滤**：帧间差异检测动态区域
4. **植被过滤**：排除绿色植被干扰

## 支持的输入方式

- 图片检测：单张图片识别
- 视频检测：视频文件逐帧识别
- 摄像头检测：实时摄像头流识别

## 告警输出

- 实时弹窗告警
- SQLite 告警记录存储
- HTML 报告导出（含告警截图、时间、置信度）
