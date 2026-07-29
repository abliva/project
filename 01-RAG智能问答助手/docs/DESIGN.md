# RAG 智能问答助手 - 设计文档

## 项目简介

基于检索增强生成（RAG）的垂直领域问答系统

## 架构概览

```
Flask API → RAG 引擎 → 向量检索 → SenseNova 生成
```

## 核心模块

- `rag_engine/retriever.py - 文档加载/切分/向量化/检索`
- `rag_engine/generator.py - SenseNova API 调用与流式输出`
- `api/routes.py - RESTful 接口与 SSE 流式响应`


## 数据流程

```
用户问题 → 向量检索 Top-K 文档片段 → 组装 Prompt → SenseNova 生成 → SSE 流式返回
```

## 项目亮点

- 自实现 1536 维字符级哈希向量，零成本离线可用
- chunk_size=500 / overlap=50 平衡上下文与召回率
- 余弦相似度 + 阈值过滤，避免无关内容污染回答

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
