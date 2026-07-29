# -*- coding: utf-8 -*-
"""
定时任务包初始化
"""

try:
    from .scheduler import TaskScheduler
    SCHEDULER_AVAILABLE = True
except ImportError as e:
    TaskScheduler = None
    SCHEDULER_AVAILABLE = False
    print(f"[警告] 定时任务模块加载失败: {e}")

__all__ = ['TaskScheduler']
