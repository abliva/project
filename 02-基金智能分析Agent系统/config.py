# -*- coding: utf-8 -*-
"""
基金智能分析决策 Agent 系统 - 配置文件
包含基金代码配置、AkShare参数、LLM配置等
"""

import os
from typing import Dict, List

# ==================== 基金代码配置 ====================
# 示例基金代码列表（可根据需要修改）
SAMPLE_FUND_CODES: List[str] = [
    "110011",  # 易方达中小盘混合
    "000001",  # 华夏成长混合
    "161725",  # 招商中证白酒指数
    "005827",  # 易方达蓝筹精选混合
    "000961",  # 天弘沪深300ETF联接
]

# ==================== AkShare 配置 ====================
AKSHARE_CONFIG: Dict = {
    # 数据获取相关配置
    "retry_times": 3,                    # 数据获取重试次数
    "retry_delay": 2,                    # 重试间隔（秒）
    "timeout": 30,                       # 请求超时时间（秒）
    
    # 历史净值数据配置
    "nav_history_days": 180,             # 获取历史净值天数（约6个月）
    "nav_start_date": "20250101",        # 净值数据起始日期
    
    # 持仓数据配置
    "holding_report_period": "20241231", # 季度报告期（YYYYMMDD格式）
}

# ==================== LLM/SenseNova 配置（商汤大模型） ====================
LLM_CONFIG: Dict = {
    # SenseNova API配置（OpenAI兼容接口）
    "api_key": os.getenv("SENSENOVA_API_KEY", "sk-aYstKmpELhDTGdz7rHkBUYeXBIH8TjCa"),
    "base_url": "https://token.sensenova.cn/v1",
    "model": "sensenova-6.7-flash-lite",  # 轻量多模态模型，每5小时1500次
    "timeout": 60,
    "temperature": 0.3,
}

# ==================== 情感分析配置 ====================
SENTIMENT_CONFIG: Dict = {
    # 情感分析关键词权重配置
    "positive_keywords": {               # 利好关键词及权重
        "上涨": 2.0,
        "增长": 1.8,
        "利好": 2.5,
        "突破": 2.0,
        "创新高": 2.5,
        "强势": 1.5,
        "反弹": 1.3,
        "回升": 1.5,
        "看好": 2.0,
        "推荐": 1.8,
        "买入": 2.0,
        "增持": 1.8,
        "超预期": 2.2,
        "盈利": 1.6,
        "收益": 1.4,
        "牛市": 2.0,
        "资金流入": 1.8,
        "放量上涨": 2.3,
        "主力资金": 1.5,
        "业绩优良": 2.0,
    },
    "negative_keywords": {               # 利空关键词及权重
        "下跌": -2.0,
        "下降": -1.8,
        "利空": -2.5,
        "暴跌": -2.5,
        "创新低": -2.5,
        "弱势": -1.5,
        "回调": -1.3,
        "回落": -1.5,
        "看空": -2.0,
        "卖出": -2.0,
        "减持": -1.8,
        "低于预期": -2.2,
        "亏损": -1.6,
        "熊市": -2.0,
        "资金流出": -1.8,
        "缩量下跌": -2.3,
        "风险": -1.5,
        "预警": -1.8,
        "崩盘": -2.5,
        "恐慌": -2.0,
    },
    
    # 情感阈值配置
    "strong_positive_threshold": 3.0,     # 强烈利好阈值
    "positive_threshold": 1.0,            # 利好阈值
    "neutral_range": (-1.0, 1.0),         # 中性区间
    "negative_threshold": -1.0,           # 利空阈值
    "strong_negative_threshold": -3.0,    # 强烈利空阈值
}

# ==================== 决策引擎配置 ====================
DECISION_CONFIG: Dict = {
    # 多因子权重配置
    "factor_weights": {
        "technical": 0.35,                # 技术面因子权重（基于净值走势）
        "sentiment": 0.35,                # 舆情面因子权重（新闻情感）
        "fundamental": 0.20,              # 基本面因子权重（持仓、规模等）
        "market": 0.10,                   # 市场环境因子权重
    },
    
    # 决策信号阈值
    "buy_threshold": 65,                  # 买入建议得分阈值（百分制）
    "hold_threshold": 45,                 # 持有建议得分阈值
    "sell_threshold": 30,                 # 卖出建议得分阈值
    
    # 风险控制参数
    "max_position_ratio": 0.30,           # 单只基金最大建议仓位比例
    "min_confidence": 0.6,                # 最小置信度要求
    "volatility_penalty": 0.15,           # 波动率惩罚系数
}

# ==================== 系统配置 ====================
SYSTEM_CONFIG: Dict = {
    # 日志配置
    "log_level": "INFO",                  # 日志级别：DEBUG/INFO/WARNING/ERROR
    "log_file": "logs/fund_agent.log",    # 日志文件路径
    "log_max_size": 10 * 1024 * 1024,     # 单个日志文件最大大小（10MB）
    "log_backup_count": 5,                # 保留日志文件数量
    
    # 输出配置
    "output_dir": "output",               # 报告输出目录
    "report_format": "markdown",          # 报告格式：markdown/json/html
    
    # 新闻抓取配置
    "news_fetch_count": 20,               # 每次获取新闻条数
    "news_time_range_days": 7,            # 新闻时间范围（天）
    
    # 缓存配置
    "cache_enabled": True,                # 是否启用缓存
    "cache_expire_hours": 24,             # 缓存过期时间（小时）
}

# ==================== 文心一言提示词配置 ====================
PROMPTS_CONFIG: List[Dict] = [
    {
        "id": 1,
        "name": "金融数据分析仪表盘",
        "prompt": "创建一个现代化的金融数据分析仪表盘界面，包含多个实时更新的K线图、技术指标图表、资金流向图、持仓分布饼图。使用深色主题，蓝绿色调为主，数据以动态卡片形式展示，支持交互式筛选和时间范围选择。整体风格专业、简洁、科技感强。",
        "style": "专业金融科技风"
    },
    {
        "id": 2,
        "name": "基金K线走势图",
        "prompt": "绘制一只基金的K线走势图，包含开盘价、收盘价、最高价、最低价的蜡烛图，叠加均线系统（MA5、MA10、MA20、MA60），成交量柱状图在下方，MACD指标在最下方。使用渐变色填充，关键点位标注买入卖出信号，整体配色采用专业的金融图表配色方案。",
        "style": "专业技术分析风"
    },
    {
        "id": 3,
        "name": "AI投资顾问界面",
        "prompt": "设计一个AI智能投资顾问的对话界面，左侧显示用户资产概览卡片（总资产、收益率、风险等级），中间是对话区域显示AI分析建议，右侧是推荐基金列表和风险评估仪表盘。界面友好现代，使用圆角卡片设计，配合微交互动画效果。",
        "style": "智能助手交互风"
    },
    {
        "id": 4,
        "name": "股票市场情绪热力图",
        "prompt": "生成一个股票市场情绪热力图，横轴为不同行业板块（新能源、半导体、医药、消费、金融等），纵轴为时间维度，颜色深浅表示情绪强度（红色代表乐观、绿色代表悲观），每个格子内显示具体数值和趋势箭头。整体视觉效果清晰直观，适合快速把握市场情绪变化。",
        "style": "数据可视化风"
    },
    {
        "id": 5,
        "name": "智能投研报告模板",
        "prompt": "设计一份专业的智能投研报告模板，包含：封面（标题、日期、分析师信息）、执行摘要、市场概况、基金表现分析（收益率曲线、风险指标）、持仓结构分析（行业分布、重仓股）、舆情分析（新闻摘要、情感倾向）、投资建议与风险提示。排版精美，图文并茂，适合打印或PDF输出。",
        "style": "专业报告文档风"
    },
]

# ==================== 路径配置 ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, SYSTEM_CONFIG["output_dir"])
LOG_DIR = os.path.join(BASE_DIR, "logs")

# 确保必要目录存在
for dir_path in [DATA_DIR, OUTPUT_DIR, LOG_DIR]:
    os.makedirs(dir_path, exist_ok=True)
