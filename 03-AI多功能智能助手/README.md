# 多功能AI智能助手（Agent架构）

基于 ReAct 模式的智能助手，支持复合任务自动拆解与多步执行，集成天气查询、文案生成、数据计算等多个工具。

## 解决什么问题

单一功能 AI 工具无法满足用户复合需求（如"查天气然后写文案"）。本项目通过 Agent 架构，自动识别意图、拆解任务、调度工具，完成多步骤复合任务。

## 技术栈

- **大模型**：SenseNova（商汤）sensenova-6.7-flash-lite
- **架构模式**：ReAct（Reasoning + Acting）
- **工具系统**：BaseTool 抽象基类 + 动态注册
- **安全过滤**：关键词匹配 + 风险等级判定

## 核心模块

```
agent/
├── core.py           # Agent 核心，ReAct 循环
├── task_planner.py   # 任务规划器（意图识别、任务拆解）
├── tool_executor.py  # 工具执行器（参数校验、失败重试）
├── chat_manager.py   # 对话管理器（历史记忆、自动摘要）
└── safety_filter.py  # 安全过滤器

tools/
├── info_query.py     # 信息查询工具（天气、时间）
├── text_generator.py # 文案生成工具
├── data_analyzer.py  # 数据分析工具（计算）
└── scheduler.py      # 任务调度工具
```

## 快速开始

```bash
pip install -r requirements.txt
python main.py
```

## 已集成的工具

| 工具 | 功能 |
|------|------|
| WeatherTool | 天气查询 |
| CalculatorTool | 数学计算 |
| TimeTool | 时间查询 |
| TextGeneratorTool | 文案生成 |

## 扩展新工具

```python
from tools.base import BaseTool

class MyTool(BaseTool):
    name = "my_tool"
    description = "我的工具"
    parameters = {"param": "参数说明"}

    def execute(self, **kwargs) -> str:
        # 实现逻辑
        return "结果"

# 注册工具
registry.register(MyTool())
```

## 关键设计

1. **BaseTool 抽象基类**：统一工具接口（name、description、execute），开闭原则
2. **动态工具注册**：运行时注册，新增工具无需修改主逻辑
3. **任务规划器**：关键词匹配识别意图，复合任务按"然后/接着"拆解
4. **失败重试**：max_retries=3，工具调用失败自动重试
5. **自动摘要**：对话历史超过 20 条时，自动用 LLM 总结历史
