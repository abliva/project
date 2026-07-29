# -*- coding: utf-8 -*-
"""
数据模型包初始化
"""

from .database import db, DataSource, CrawlRecord, Statistics

__all__ = ['db', 'DataSource', 'CrawlRecord', 'Statistics']
