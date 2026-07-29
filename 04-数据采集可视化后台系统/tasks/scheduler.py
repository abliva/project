# -*- coding: utf-8 -*-
"""
定时任务调度模块 - 基于APScheduler实现
功能：
1. 支持cron表达式配置定时任务
2. 任务的动态添加/删除/暂停/恢复
3. 任务执行日志记录
4. 支持多种触发器（interval/date/cron）
5. 任务状态监控与错误处理
6. 与Flask应用集成，支持上下文管理

使用示例：
>>> scheduler = TaskScheduler(app)
>>> scheduler.add_job(func=crawl_job, trigger='cron', hour='*/6', id='hourly_crawl')
>>> scheduler.start()
"""

import logging
from datetime import datetime
from typing import Callable, Dict, Any, Optional, List
from functools import wraps

# 可选导入APScheduler，提供降级方案
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.triggers.date import DateTrigger
    from apscheduler.jobstores.memory import MemoryJobStore
    from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
    from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    BackgroundScheduler = None
    CronTrigger = None
    IntervalTrigger = None
    DateTrigger = None
    MemoryJobStore = None
    ThreadPoolExecutor = None
    ProcessPoolExecutor = None
    EVENT_JOB_EXECUTED = None
    EVENT_JOB_ERROR = None
    print("[警告] APScheduler未安装，定时任务功能不可用。请执行: pip install apscheduler")

# 配置日志
logger = logging.getLogger(__name__)


class TaskScheduler:
    """
    定时任务调度器
    
    封装APScheduler，提供更友好的任务管理接口：
    - 添加定时任务（支持cron/interval/date三种模式）
    - 管理任务生命周期（暂停/恢复/删除）
    - 监控任务执行情况
    - 错误处理与重试机制
    
    集成到Flask应用中，自动处理数据库会话等上下文问题
    """
    
    def __init__(self, app=None):
        """
        初始化任务调度器

        参数:
            app: Flask应用实例（可选，稍后可通过init_app()传入）
        """
        if not APSCHEDULER_AVAILABLE:
            print("[警告] APScheduler未安装，TaskScheduler功能不可用")
            return

        self.app = app
        self.scheduler = None
        self.jobs_info = {}  # 存储任务的额外信息

        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """
        初始化调度器并绑定到Flask应用

        参数:
            app: Flask应用实例
        """
        if not APSCHEDULER_AVAILABLE:
            print("[警告] APScheduler未安装，无法初始化调度器")
            return

        self.app = app
        
        # 配置APScheduler
        jobstores = {
            'default': MemoryJobStore()  # 使用内存存储（生产环境可改用SQLAlchemyJobStore持久化）
        }
        
        executors = {
            'default': ThreadPoolExecutor(10),  # 线程池执行器（用于IO密集型任务）
            'processpool': ProcessPoolExecutor(3)  # 进程池执行器（用于CPU密集型任务）
        }
        
        job_defaults = {
            'coalesce': False,  # 不合并错过的任务
            'max_instances': 1,  # 同一任务最大并发实例数
            'misfire_grace_time': 300  # 错过执行的宽限时间（秒）
        }
        
        # 创建后台调度器实例
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='Asia/Shanghai'  # 设置时区为东八区
        )
        
        # 注册事件监听器
        self.scheduler.add_listener(self._job_executed_listener, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._job_error_listener, EVENT_JOB_ERROR)
        
        logger.info("✅ 定时任务调度器初始化完成")
    
    def _job_executed_listener(self, event):
        """任务成功执行事件监听器"""
        job_id = event.job_id
        logger.info(f"✅ 定时任务执行成功 | Job ID: {job_id}")
        
        # 更新任务信息
        if job_id in self.jobs_info:
            self.jobs_info[job_id]['last_run'] = datetime.now().isoformat()
            self.jobs_info[job_id]['last_status'] = 'success'
            self.jobs_info[job_id]['run_count'] = self.jobs_info[job_id].get('run_count', 0) + 1
    
    def _job_error_listener(self, event):
        """任务执行失败事件监听器"""
        job_id = event.job_id
        exception = event.exception
        traceback = getattr(event, 'traceback', '')
        
        logger.error(f"❌ 定时任务执行失败 | Job ID: {job_id} | 错误: {str(exception)}")
        if traceback:
            logger.debug(f"堆栈信息:\n{traceback}")
        
        # 更新任务信息
        if job_id in self.jobs_info:
            self.jobs_info[job_id]['last_run'] = datetime.now().isoformat()
            self.jobs_info[job_id]['last_status'] = 'failed'
            self.jobs_info[job_id]['last_error'] = str(exception)
    
    def add_job(self, func: Callable, job_id: str, 
                trigger: str = 'interval',
                **trigger_args) -> bool:
        """
        添加定时任务
        
        参数:
            func: 要执行的函数（任务函数）
            job_id: 任务唯一标识符（用于后续管理）
            trigger: 触发器类型：
                    - 'interval': 固定间隔执行
                    - 'cron': cron表达式（推荐）
                    - 'date': 指定时间执行一次
            **trigger_args: 触发器参数：
                interval模式: seconds, minutes, hours
                cron模式: year, month, day, week, day_of_week, hour, minute, second
                date模式: run_date (datetime对象或ISO格式字符串)
                
        返回:
            bool: 是否添加成功
            
        示例:
            >>> # 每6小时执行一次
            >>> scheduler.add_job(crawl_func, 'crawl_task', trigger='cron', hour='*/6')
            >>> 
            >>> # 每30分钟执行一次
            >>> scheduler.add_job(check_func, 'check_task', trigger='interval', minutes=30)
            >>> 
            >>> # 在指定时间执行一次
            >>> scheduler.add_job(once_func, 'once_task', trigger='date', run_date='2024-01-01 00:00:00')
        """
        try:
            if not APSCHEDULER_AVAILABLE or not self.scheduler:
                logger.error("❌ APScheduler不可用或调度器未初始化")
                return False

            # 根据触发器类型创建对应的Trigger对象
            if trigger == 'interval':
                trigger_obj = IntervalTrigger(**trigger_args)
                trigger_desc = f"间隔{trigger_args}"
            
            elif trigger == 'cron':
                trigger_obj = CronTrigger(**trigger_args)
                # 格式化cron表达式描述
                desc_parts = []
                for key in ['second', 'minute', 'hour', 'day', 'month', 'day_of_week']:
                    if key in trigger_args:
                        desc_parts.append(f"{key}={trigger_args[key]}")
                trigger_desc = f"Cron({', '.join(desc_parts)})"
            
            elif trigger == 'date':
                trigger_obj = DateTrigger(**trigger_args)
                run_date = trigger_args.get('run_date', '未指定')
                trigger_desc = f"一次性任务@{run_date}"
            
            else:
                raise ValueError(f"不支持的触发器类型: {trigger}")
            
            # 包装任务函数，确保在Flask应用上下文中执行
            @wraps(func)
            def job_wrapper(*args, **kwargs):
                with self.app.app_context():
                    return func(*args, **kwargs)
            
            # 添加任务到调度器
            job = self.scheduler.add_job(
                job_wrapper,
                trigger=trigger_obj,
                id=job_id,
                name=f'Task-{job_id}',
                replace_existing=True  # 如果ID已存在则替换
            )
            
            # 记录任务额外信息
            self.jobs_info[job_id] = {
                'func_name': func.__name__,
                'trigger_type': trigger,
                'trigger_desc': trigger_desc,
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                'added_at': datetime.now().isoformat(),
                'last_run': None,
                'last_status': 'pending',
                'run_count': 0,
                **trigger_args
            }
            
            logger.info(f"➕ 添加定时任务 | ID: {job_id} | 函数: {func.__name__} | 触发器: {trigger_desc}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 添加定时任务失败 | ID: {job_id} | 错误: {str(e)}")
            return False
    
    def remove_job(self, job_id: str) -> bool:
        """
        移除指定任务
        
        参数:
            job_id: 任务ID
            
        返回:
            bool: 是否移除成功
        """
        try:
            if not APSCHEDULER_AVAILABLE or not self.scheduler:
                logger.error("❌ APScheduler不可用或调度器未初始化")
                return False
            self.scheduler.remove_job(job_id)
            
            # 清理任务信息
            if job_id in self.jobs_info:
                del self.jobs_info[job_id]
            
            logger.info(f"🗑️ 移除定时任务 | ID: {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 移除任务失败 | ID: {job_id} | 错误: {str(e)}")
            return False
    
    def pause_job(self, job_id: str) -> bool:
        """
        暂停指定任务
        
        参数:
            job_id: 任务ID
            
        返回:
            bool: 是否暂停成功
        """
        try:
            if not APSCHEDULER_AVAILABLE or not self.scheduler:
                logger.error("❌ APScheduler不可用或调度器未初始化")
                return False
            self.scheduler.pause_job(job_id)
            
            if job_id in self.jobs_info:
                self.jobs_info[job_id]['status'] = 'paused'
            
            logger.info(f"⏸️ 暂停定时任务 | ID: {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 暂停任务失败 | ID: {job_id} | 错误: {str(e)}")
            return False
    
    def resume_job(self, job_id: str) -> bool:
        """
        恢复已暂停的任务
        
        参数:
            job_id: 任务ID
            
        返回:
            bool: 是否恢复成功
        """
        try:
            if not APSCHEDULER_AVAILABLE or not self.scheduler:
                logger.error("❌ APScheduler不可用或调度器未初始化")
                return False
            self.scheduler.resume_job(job_id)
            
            if job_id in self.jobs_info:
                self.jobs_info[job_id]['status'] = 'active'
            
            logger.info(f"▶️ 恢复定时任务 | ID: {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 恢复任务失败 | ID: {job_id} | 错误: {str(e)}")
            return False
    
    def modify_job(self, job_id: str, **changes) -> bool:
        """
        修改任务参数（如触发器参数等）
        
        参数:
            job_id: 任务ID
            **changes: 要修改的参数，例如：trigger='cron', hour='*/3'
            
        返回:
            bool: 是否修改成功
        """
        try:
            self.scheduler.modify_job(job_id, **changes)
            logger.info(f"🔧 修改定时任务 | ID: {job_id} | 变更: {changes}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 修改任务失败 | ID: {job_id} | 错误: {str(e)}")
            return False
    
    def get_job(self, job_id: str) -> Optional[Dict]:
        """
        获取指定任务的详细信息
        
        参数:
            job_id: 任务ID
            
        返回:
            dict: 任务详细信息字典，如果不存在则返回None
        """
        job = self.scheduler.get_job(job_id)
        
        if not job:
            return None
        
        # 合并基础信息和扩展信息
        info = self.jobs_info.get(job_id, {})
        
        return {
            'id': job.id,
            'name': job.name,
            'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
            'trigger': str(job.trigger),
            **info
        }
    
    def get_all_jobs(self) -> List[Dict]:
        """
        获取所有注册的任务列表
        
        返回:
            list: 所有任务的详细信息列表
        """
        jobs = self.scheduler.get_jobs()
        
        result = []
        for job in jobs:
            info = self.jobs_info.get(job.id, {})
            result.append({
                'id': job.id,
                'name': job.name,
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger),
                **info
            })
        
        return result
    
    def run_job_now(self, job_id: str) -> bool:
        """
        立即执行指定任务（不等待下次计划时间）
        
        参数:
            job_id: 任务ID
            
        返回:
            bool: 是否触发成功
        """
        try:
            job = self.scheduler.get_job(job_id)
            if not job:
                logger.warning(f"⚠️ 任务不存在，无法立即执行 | ID: {job_id}")
                return False
            
            # 手动触发任务执行
            job.modify(next_run_time=datetime.now())
            
            logger.info(f"⚡ 立即执行定时任务 | ID: {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 立即执行任务失败 | ID: {job_id} | 错误: {str(e)}")
            return False
    
    def start(self):
        """
        启动调度器（开始运行所有任务）
        应在应用启动后调用
        """
        # 安全检查：确保APScheduler可用且调度器已初始化
        if not APSCHEDULER_AVAILABLE:
            logger.warning("⚠️ APScheduler未安装，无法启动调度器")
            print("[警告] APScheduler未安装，定时任务功能不可用。请执行: pip install apscheduler")
            return
        
        if not self.scheduler:
            logger.warning("⚠️ 调度器未初始化，无法启动")
            return
        
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("🚀 定时任务调度器已启动")
    
    def shutdown(self, wait: bool = True):
        """
        关闭调度器（停止所有任务）
        应在应用关闭前调用

        参数:
            wait: 是否等待正在执行的任务完成
        """
        if not APSCHEDULER_AVAILABLE or not self.scheduler:
            logger.warning("⚠️ APScheduler不可用或调度器未初始化，无需关闭")
            return

        if self.scheduler.running:
            self.scheduler.shutdown(wait=wait)
            logger.info("🛑 定时任务调度器已关闭")
    
    def print_jobs(self):
        """
        打印当前所有任务的信息（调试用）
        """
        if not APSCHEDULER_AVAILABLE or not self.scheduler:
            print("\n⚠️ APScheduler不可用或调度器未初始化，无法打印任务列表")
            return

        jobs = self.get_all_jobs()
        
        print("\n" + "=" * 70)
        print("📋 当前定时任务列表:")
        print("=" * 70)
        
        if not jobs:
            print("  （暂无注册的任务）")
        else:
            for idx, job in enumerate(jobs, 1):
                status = job.get('status', 'active')
                status_icon = '✅' if status == 'active' else '⏸️'
                
                print(f"\n[{idx}] {status_icon} {job['id']}")
                print(f"    名称: {job['name']}")
                print(f"    触发器: {job.get('trigger_desc', job['trigger'])}")
                print(f"    下次执行: {job['next_run_time'] or '未安排'}")
                print(f"    执行次数: {job.get('run_count', 0)}次")
                print(f"    最后状态: {job.get('last_status', '从未执行')}")
        
        print("\n" + "=" * 70)


# ==================== 示例任务函数 ====================

def sample_crawl_job():
    """
    示例：数据采集任务
    实际项目中应该替换为真实的业务逻辑
    """
    from services.crawler import DataCrawler
    from config import CrawlerConfig
    from models.database import db, DataSource, CrawlRecord
    from services.data_processor import DataProcessor
    from datetime import datetime
    
    logger.info("🔄 开始执行定时采集任务...")
    
    try:
        # 获取所有启用的数据源
        datasources = DataSource.query.filter_by(is_active=True).all()
        
        for ds in datasources:
            if not ds.url:
                continue
            
            logger.info(f"📡 正在采集: {ds.name} ({ds.url})")
            
            # 创建爬虫实例
            crawler = DataCrawler(config=CrawlerConfig.__dict__)
            
            # 执行采集
            result = crawler.crawl_single(ds.url)
            
            # 创建采集记录
            record = CrawlRecord(
                datasource_id=ds.id,
                datasource_name=ds.name,
                task_id='scheduled_crawl',
                task_name='定时采集任务',
                start_time=datetime.now(),
                created_at=datetime.now()
            )
            
            if result.success:
                # 数据清洗
                processor = DataProcessor(result.data if isinstance(result.data, list) else [result.data])
                cleaned_data = processor.process()
                
                record.status = 'success'
                record.total_count = len(cleaned_data) if cleaned_data else 1
                record.success_count = record.total_count
                record.processed_data = cleaned_data
                
                logger.info(f"✅ 采集成功 | 数据源: {ds.name} | 条数: {record.total_count}")
            else:
                record.status = 'failed'
                record.error_message = result.error_message
                logger.error(f"❌ 采集失败 | 数据源: {ds.name} | 原因: {result.error_message}")
            
            record.end_time = datetime.now()
            record.duration = (record.end_time - record.start_time).total_seconds()
            
            # 更新数据源统计
            ds.total_crawls += 1
            ds.last_crawl_time = datetime.now()
            ds.last_crawl_status = record.status
            
            db.session.add(record)
            crawler.close()
        
        db.session.commit()
        logger.info("✅ 定时采集任务全部完成")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ 定时采集任务异常: {str(e)}", exc_info=True)


def sample_cleanup_job():
    """
    示例：缓存清理任务
    定期清理LRU缓存中的过期项
    """
    from services.cache import get_cache
    
    logger.info("🧹 开始执行缓存清理任务...")
    
    cache = get_cache()
    cleaned_count = cache.cleanup()
    
    stats = cache.get_stats()
    
    logger.info(f"✅ 缓存清理完成 | 清理过期项: {cleaned_count} | 当前容量: {stats['current_size']}/{stats['maxsize']}")


def sample_stats_job():
    """
    示例：统计聚合任务
    将原始采集记录聚合成统计数据（按天/周/月）
    用于前端图表展示，避免实时计算的性能开销
    """
    from models.database import db, CrawlRecord, Statistics
    from datetime import date, timedelta
    from sqlalchemy import func
    
    logger.info("📊 开始执行统计聚合任务...")
    
    try:
        today = date.today()
        yesterday = today - timedelta(days=1)
        
        # 统计昨天的采集数据
        records = db.session.query(CrawlRecord).filter(
            func.date(CrawlRecord.created_at) == yesterday
        ).all()
        
        total_count = len(records)
        success_count = sum(1 for r in records if r.status == 'success')
        failed_count = sum(1 for r in records if r.status == 'failed')
        
        success_rate = (success_count / total_count * 100) if total_count > 0 else 0
        
        # 创建或更新统计记录
        stats_record = Statistics.query.filter_by(
            stat_type='crawl_summary',
            stat_dimension='daily',
            stat_date=yesterday
        ).first()
        
        metrics = {
            'total_count': total_count,
            'success_count': success_count,
            'failed_count': failed_count,
            'success_rate': round(success_rate, 2),
            'avg_duration': sum(r.duration for r in records if r.duration) / total_count if total_count > 0 else 0
        }
        
        if stats_record:
            stats_record.metrics = metrics
            stats_record.updated_at = datetime.now()
        else:
            stats_record = Statistics(
                stat_type='crawl_summary',
                stat_dimension='daily',
                stat_date=yesterday,
                metrics=metrics
            )
            db.session.add(stats_record)
        
        db.session.commit()
        
        logger.info(f"✅ 统计聚合完成 | 日期: {yesterday} | 总计: {total_count}条 | 成功率: {success_rate}%")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ 统计聚合任务异常: {str(e)}", exc_info=True)


# ==================== 使用示例 ====================
if __name__ == '__main__':
    from flask import Flask
    
    # 创建测试用的Flask应用
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-key'
    
    # 初始化调度器
    scheduler = TaskScheduler(app)
    
    # 添加示例任务
    scheduler.add_job(
        func=sample_crawl_job,
        job_id='daily_crawl',
        trigger='cron',
        hour=2,  # 每天凌晨2点执行
        minute=0
    )
    
    scheduler.add_job(
        func=sample_cleanup_job,
        job_id='cache_cleanup',
        trigger='interval',
        hours=1  # 每小时清理一次缓存
    )
    
    scheduler.add_job(
        func=sample_stats_job,
        job_id='daily_stats',
        trigger='cron',
        hour=3,  # 每天凌晨3点统计前一天数据
        minute=30
    )
    
    # 启动调度器
    scheduler.start()
    
    # 打印任务列表
    scheduler.print_jobs()
    
    print("\n✅ 调度器演示完成！在实际应用中，这些任务会在后台持续运行。")
    print("   按 Ctrl+C 可停止调度器。")
    
    # 保持程序运行（实际应用中不需要这行）
    try:
        import time
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        scheduler.shutdown()
        print("\n👋 调度器已停止")
