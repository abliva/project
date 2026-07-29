"""
AI智能助手配置文件
包含LLM API配置、工具配置、安全策略配置等
"""

import os
from typing import Dict, List, Any
from dataclasses import dataclass, field


@dataclass
class LLMConfig:
    """大语言模型API配置 - SenseNova（商汤大模型）"""
    # API密钥 - SenseNova（商汤），从环境变量读取，默认使用预置密钥
    api_key: str = field(default_factory=lambda: os.getenv("SENSENOVA_API_KEY", "sk-aYstKmpELhDTGdz7rHkBUYeXBIH8TjCa"))
    # API基础URL（OpenAI兼容接口）
    base_url: str = field(default_factory=lambda: os.getenv("SENSENOVA_BASE_URL", "https://token.sensenova.cn/v1"))
    # 模型名称（SenseNova 6.7 Flash-Lite：轻量多模态模型）
    model_name: str = "sensenova-6.7-flash-lite"
    # 最大token数
    max_tokens: int = 4096
    # 温度参数（0-1，越高越随机）
    temperature: float = 0.7
    # 超时时间（秒）
    timeout: int = 60


@dataclass
class ToolConfig:
    """工具配置"""
    # 天气API配置
    weather_api_key: str = field(default_factory=lambda: os.getenv("WEATHER_API_KEY", ""))
    weather_api_url: str = "https://api.weather.com/v1"

    # 搜索API配置
    search_api_key: str = field(default_factory=lambda: os.getenv("SEARCH_API_KEY", ""))
    search_api_url: str = "https://api.search.com/v1"

    # 启用的工具列表
    enabled_tools: List[str] = field(default_factory=lambda: [
        "info_query",      # 信息查询工具
        "text_generator",  # 文案生成工具
        "data_analyzer",   # 数据分析工具
        "scheduler"        # 日程管理工具
    ])

    # 工具调用最大重试次数
    max_retries: int = 3

    # 工具执行超时时间（秒）
    tool_timeout: int = 60


@dataclass
class ChatConfig:
    """对话管理配置"""
    # 最大历史消息数
    max_history_messages: int = 20
    # 上下文窗口大小（token数）
    context_window_size: int = 8192
    # 是否启用会话摘要
    enable_summary: bool = True
    # 摘要触发阈值（当历史超过此值时触发摘要）
    summary_threshold: int = 10
    # 系统提示词文件路径
    system_prompt_file: str = "templates/prompt_templates.txt"


@dataclass
class SafetyConfig:
    """安全策略配置"""
    # 是否启用敏感词过滤
    enable_content_filter: bool = True
    # 敏感词列表文件路径
    sensitive_words_file: str = ""

    # 自定义敏感词列表
    custom_sensitive_words: List[str] = field(default_factory=lambda: [
        "暴力", "恐怖主义", "非法活动", "黑客攻击", "破解密码",
        "制造武器", "毒品", "赌博", "诈骗", "色情"
    ])

    # 输出内容规范
    output_rules: List[str] = field(default_factory=lambda: [
        "不得生成违法内容",
        "不得泄露个人隐私信息",
        "不得生成歧视性言论",
        "必须标注AI生成内容的局限性"
    ])

    # 最大输出长度限制
    max_output_length: int = 5000


@dataclass
class SchedulerConfig:
    """任务调度器配置"""
    # 是否启用定时任务
    enable_scheduler: bool = True
    # 默认时区
    timezone: str = "Asia/Shanghai"
    # 任务存储路径
    task_storage_path: str = "data/tasks.json"


# 全局配置实例
llm_config = LLMConfig()
tool_config = ToolConfig()
chat_config = ChatConfig()
safety_config = SafetyConfig()
scheduler_config = SchedulerConfig()


def load_config_from_env():
    """
    从环境变量加载配置
    支持通过环境变量覆盖默认配置
    """
    global llm_config, tool_config, chat_config, safety_config

    # LLM配置
    if os.getenv("LLM_MODEL_NAME"):
        llm_config.model_name = os.getenv("LLM_MODEL_NAME")
    if os.getenv("LLM_MAX_TOKENS"):
        llm_config.max_tokens = int(os.getenv("LLM_MAX_TOKENS"))
    if os.getenv("LLM_TEMPERATURE"):
        llm_config.temperature = float(os.getenv("LLM_TEMPERATURE"))

    # 安全配置
    if os.getenv("ENABLE_CONTENT_FILTER"):
        safety_config.enable_content_filter = os.getenv("ENABLE_CONTENT_FILTER").lower() == "true"

    print(f"✓ 配置加载完成 | 模型: {llm_config.model_name} | 安全过滤: {'开启' if safety_config.enable_content_filter else '关闭'}")


def get_all_configs() -> Dict[str, Any]:
    """
    获取所有配置信息的字典形式
    用于调试和展示
    """
    return {
        "llm": {
            "model_name": llm_config.model_name,
            "max_tokens": llm_config.max_tokens,
            "temperature": llm_config.temperature,
            "base_url": llm_config.base_url[:50] + "..." if len(llm_config.base_url) > 50 else llm_config.base_url
        },
        "tools": {
            "enabled_tools": tool_config.enabled_tools,
            "max_retries": tool_config.max_retries
        },
        "chat": {
            "max_history_messages": chat_config.max_history_messages,
            "context_window_size": chat_config.context_window_size,
            "enable_summary": chat_config.enable_summary
        },
        "safety": {
            "enable_content_filter": safety_config.enable_content_filter,
            "custom_sensitive_words_count": len(safety_config.custom_sensitive_words)
        }
    }


if __name__ == "__main__":
    # 测试配置加载
    load_config_from_env()
    import json
    print("\n当前配置信息:")
    print(json.dumps(get_all_configs(), indent=2, ensure_ascii=False))
