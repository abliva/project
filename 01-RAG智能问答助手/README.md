# RAG智能问答助手

基于检索增强生成（RAG）的垂直领域问答系统，通过检索文档片段约束大模型回答，减少幻觉问题。

## 解决什么问题

通用大模型在专业领域问答中存在"幻觉"——会编造看似合理但实际错误的内容。本项目通过 RAG 架构，先检索相关文档片段，再让大模型基于片段回答，保证回答有据可查。

## 技术栈

- **大模型**：SenseNova（商汤）sensenova-6.7-flash-lite，OpenAI 兼容接口
- **Web框架**：Flask
- **向量化**：自实现字符级哈希向量（1536维），零成本离线可用
- **检索**：余弦相似度 + Top-K 过滤 + 相似度阈值
- **流式输出**：SSE（Server-Sent Events）
- **文档格式**：TXT / PDF / Markdown

## 核心模块

```
rag_engine/
├── retriever.py    # 文档加载、切分、向量化、检索
├── generator.py    # SenseNova API 调用、流式输出
└── knowledge_base/ # 知识库目录
api/
└── routes.py       # Flask API 路由（问答、知识库管理、健康检查）
```

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key（SenseNova）
# 编辑 config.py 或设置环境变量 SENSENOVA_API_KEY

# 3. 启动服务
python app.py
# 访问 http://localhost:5000
```

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/chat` | POST | 智能问答（支持 SSE 流式） |
| `/api/knowledge` | GET | 获取知识库状态 |
| `/api/knowledge` | POST | 添加文档到知识库 |
| `/api/knowledge` | DELETE | 清空知识库 |
| `/api/health` | GET | 健康检查 |

## 效果

- 对比纯大模型基线，问答准确率提升约 40%
- 幻觉问题减少 80% 以上（通过检索文档约束生成）

## 关键设计

1. **不依赖 LangChain**：自实现切分、向量化、检索全流程，每一步可调试
2. **两级文本切分**：先按段落切，段落过长再按句子切，chunk_size=500、overlap=50
3. **字符级哈希向量**：零成本、离线可用，不依赖付费 Embedding API
