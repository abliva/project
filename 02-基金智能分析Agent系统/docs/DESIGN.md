# 基金智能分析 Agent 系统 - 设计文档

## 项目简介

多因子决策引擎驱动的基金分析智能体

## 架构概览

```
Agent Core → 工具调用 → 多因子评分 → 投资建议生成
```

## 核心模块

- `agent/core.py - Agent 主控与任务规划`
- `agent/decision.py - 多因子决策引擎（技术35%+舆情35%+基本面20%+市场10%）`
- `agent/tools/data_fetcher.py - AkShare 基金数据抓取`
- `agent/tools/news_crawler.py - 新闻爬虫`
- `agent/tools/sentiment.py - LLM 情感分析`


## 数据流程

```
基金代码 → 数据抓取 → 技术面/舆情/基本面评分 → 加权汇总 → 结构化投资建议
```

## 项目亮点

- ReAct 模式驱动多工具串联，支持动态工具注册
- 多因子权重可配置，覆盖量化+情绪+基本面三维度
- 输出结构化投资建议报告，可解释性强

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
