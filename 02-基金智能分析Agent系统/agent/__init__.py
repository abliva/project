# -*- coding: utf-8 -*-
"""
agent 包初始化文件
导出主要的类和函数，方便外部引用
"""

from .core import FundAnalysisAgent, AnalysisReport, TaskStatus
from .decision import DecisionEngine, DecisionResult, FactorScore
from .tools.data_fetcher import FundDataFetcher
from .tools.news_crawler import NewsCrawler, SentimentAnalyzer, NewsItem
from .tools.sentiment import LLMAnalyzer, SentimentResult

__all__ = [
    # 核心模块
    'FundAnalysisAgent',
    'AnalysisReport',
    'TaskStatus',
    # 决策引擎
    'DecisionEngine',
    'DecisionResult',
    'FactorScore',
    # 工具模块
    'FundDataFetcher',
    'NewsCrawler',
    'SentimentAnalyzer',
    'NewsItem',
    'LLMAnalyzer',
    'SentimentResult',
]

__version__ = '1.0.0'
__author__ = 'Fund AI Team'
