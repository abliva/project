# AI 多功能智能助手 - 设计文档

## 项目简介

支持多工具调用与任务规划的对话助手

## 架构概览

```
对话管理 → 任务规划 → 工具执行 → 结果整合
```

## 核心模块

- `agent/chat_manager.py - 多轮对话与 20 条上下文记忆`
- `agent/task_planner.py - ReAct 任务拆解`
- `agent/tool_executor.py - 工具调度与执行`
- `agent/safety_filter.py - 输入安全过滤`
- `tools/* - 4 个内置工具（数据/查询/调度/文本生成）`


## 数据流程

```
用户输入 → 安全过滤 → 任务规划 → 工具调用 → 结果整合 → 自然语言回复
```

## 项目亮点

- BaseTool 抽象基类支持工具动态注册
- ReAct 模式实现复合任务自动拆解
- 20 条对话上下文记忆，支持多轮交互

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
