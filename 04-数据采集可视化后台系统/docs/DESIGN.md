# 数据采集可视化后台系统 - 设计文档

## 项目简介

从数据采集到可视化展示的全链路后端系统

## 架构概览

```
Flask API → Service 层 → LRU 缓存 → MySQL → ECharts 可视化
```

## 核心模块

- `api/routes.py - RESTful 接口层`
- `services/crawler.py - 多线程爬虫`
- `services/cache.py - 自实现 LRU 缓存（双向链表+哈希表）`
- `services/data_processor.py - 数据清洗与聚合`
- `models/database.py - MySQL 连接池`
- `tasks/scheduler.py - 定时任务调度`


## 数据流程

```
定时任务 → 多线程爬虫 → 数据清洗 → MySQL 存储 → LRU 缓存查询 → ECharts 渲染
```

## 项目亮点

- 自实现 LRU 缓存，避免重复查询数据库
- MySQL 连接池管理，支持高并发
- 前后端分离架构，前端 ECharts 可视化

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
