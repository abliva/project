# 无人机火情监测系统 - 设计文档

## 项目简介

基于 YOLOv8 的无人机航拍火情自动识别系统

## 架构概览

```
图像输入 → YOLOv8 检测 → OpenCV 过滤 → 报警输出
```

## 核心模块

- `main.py - 系统入口与主循环`
- `config.py - 模型路径与阈值配置`


## 数据流程

```
无人机航拍图像 → YOLOv8 火焰目标检测 → 误检过滤 → 报警坐标输出
```

## 项目亮点

- YOLOv8 目标检测，针对火焰专项微调
- OpenCV 色彩空间过滤，降低误检率
- 适用于人工巡检效率低的森林/园区场景

## 目录结构

```
project/
├── README.md          # 项目说明
├── docs/
│   └── DESIGN.md      # 本设计文档
├── config.py          # 配置文件
├── requirements.txt   # 依赖列表
└── ...                # 业务代码
```

## 运行方式

1. 安装依赖：`pip install -r requirements.txt`
2. 配置 API Key（如需）：编辑 `config.py`
3. 启动主程序：`python main.py` 或 `python app.py`

## 联系方式

- 作者：蔡俊鸿
- 邮箱：2730126314@qq.com
