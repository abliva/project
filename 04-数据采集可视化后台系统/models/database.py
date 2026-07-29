# -*- coding: utf-8 -*-
"""
数据库模型与连接管理模块
包含：数据库连接池配置、SQLAlchemy模型定义
数据表：采集源（datasource）、采集记录（crawlrecord）、统计数据（statistics）
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Text, DateTime, Date, Float, Boolean, JSON, Index, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base

# 创建SQLAlchemy实例（延迟初始化，在app.py中绑定Flask应用）
db = SQLAlchemy()


class DataSource(db.Model):
    """
    采集源表 - 存储所有数据源的配置信息
    支持多种类型的数据源：网页API、数据库、文件等
    """
    __tablename__ = 'datasource'
    
    # 主键ID
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    
    # 基础信息
    name = Column(String(100), nullable=False, unique=True, comment='数据源名称')
    source_type = Column(String(50), nullable=False, comment='数据源类型：web_api/database/file/other')
    url = Column(Text, comment='数据源URL或连接地址')
    description = Column(Text, comment='数据源描述说明')
    
    # 配置信息（JSON格式存储灵活配置）
    config = Column(JSON, comment='数据源配置参数（JSON格式）：请求头、认证信息、字段映射等')
    
    # 采集规则
    crawl_rule = Column(JSON, comment='爬取规则：CSS选择器、XPath、API参数等')
    data_mapping = Column(JSON, comment='字段映射关系：源字段 -> 目标字段')
    
    # 状态管理
    is_active = Column(Boolean, default=True, comment='是否启用')
    priority = Column(Integer, default=0, comment='优先级（数字越大优先级越高）')
    
    # 统计信息
    total_crawls = Column(Integer, default=0, comment='总采集次数')
    last_crawl_time = Column(DateTime, comment='最后采集时间')
    last_crawl_status = Column(String(20), comment='最后采集状态：success/failed/pending')
    error_message = Column(Text, comment='错误信息')
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    
    def __repr__(self):
        return f'<DataSource {self.name}>'
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'name': self.name,
            'source_type': self.source_type,
            'url': self.url,
            'description': self.description,
            'config': self.config,
            'crawl_rule': self.crawl_rule,
            'data_mapping': self.data_mapping,
            'is_active': self.is_active,
            'priority': self.priority,
            'total_crawls': self.total_crawls,
            'last_crawl_time': self.last_crawl_time.isoformat() if self.last_crawl_time else None,
            'last_crawl_status': self.last_crawl_status,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class CrawlRecord(db.Model):
    """
    采集记录表 - 记录每次数据采集的详细信息
    用于追踪采集历史、排查问题、统计分析
    """
    __tablename__ = 'crawlrecord'
    
    # 主键ID
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    
    # 关联数据源
    datasource_id = Column(Integer, db.ForeignKey('datasource.id'), nullable=False, comment='关联的数据源ID')
    datasource_name = Column(String(100), comment='数据源名称（冗余存储，方便查询）')
    
    # 采集任务信息
    task_id = Column(String(100), comment='任务ID（关联定时任务）')
    task_name = Column(String(100), comment='任务名称')
    
    # 采集结果统计
    status = Column(String(20), nullable=False, default='pending', comment='任务状态：running/success/failed/cancelled')
    total_count = Column(Integer, default=0, comment='采集到的总数据条数')
    success_count = Column(Integer, default=0, comment='成功处理的数据条数')
    failed_count = Column(Integer, default=0, comment='失败的数据条数')
    duplicate_count = Column(Integer, default=0, comment='重复数据条数')
    
    # 数据详情（JSON格式存储实际采集的数据）
    raw_data = Column(JSON, comment='原始采集数据（JSON数组）')
    processed_data = Column(JSON, comment='清洗后的数据（JSON数组）')
    
    # 执行信息
    start_time = Column(DateTime, comment='开始时间')
    end_time = Column(DateTime, comment='结束时间')
    duration = Column(Float, comment='执行耗时（秒）')
    
    # 错误信息
    error_code = Column(String(20), comment='错误代码')
    error_message = Column(Text, comment='错误详细描述')
    error_traceback = Column(Text, comment='异常堆栈信息')
    
    # 其他信息
    remark = Column(Text, comment='备注信息')
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    
    # 索引优化查询性能
    __table_args__ = (
        Index('idx_crawlrecord_datasource', 'datasource_id'),  # 按数据源查询索引
        Index('idx_crawlrecord_status', 'status'),  # 按状态查询索引
        Index('idx_crawlrecord_created', 'created_at'),  # 按时间排序索引
        Index('idx_crawlrecord_task', 'task_id'),  # 按任务ID查询索引
    )
    
    def __repr__(self):
        return f'<CrawlRecord {self.id} - {self.status}>'
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'datasource_id': self.datasource_id,
            'datasource_name': self.datasource_name,
            'task_id': self.task_id,
            'task_name': self.task_name,
            'status': self.status,
            'total_count': self.total_count,
            'success_count': self.success_count,
            'failed_count': self.failed_count,
            'duplicate_count': self.duplicate_count,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration': self.duration,
            'error_code': self.error_code,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Statistics(db.Model):
    """
    统计数据表 - 存储聚合后的统计数据
    用于前端ECharts图表展示，避免实时计算的性能开销
    支持按时间维度（小时/天/周/月）的聚合统计
    """
    __tablename__ = 'statistics'
    
    # 主键ID
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    
    # 统计维度
    stat_type = Column(String(50), nullable=False, comment='统计类型：crawl_count/data_volume/success_rate/error_distribution')
    stat_dimension = Column(String(50), nullable=False, comment='统计维度：hourly/daily/weekly/monthly/datasource/category')
    
    # 时间维度
    stat_date = Column(Date, nullable=False, comment='统计日期')
    stat_hour = Column(Integer, comment='统计小时（仅hourly维度使用）')
    
    # 关联信息
    datasource_id = Column(Integer, db.ForeignKey('datasource.id'), comment='数据源ID（可选，为空表示全局统计）')
    category = Column(String(100), comment='分类标签（可选）')
    
    # 统计指标值（使用JSON支持多指标）
    metrics = Column(JSON, nullable=False, comment='统计指标（JSON格式）：{"count": 100, "success_rate": 95.5, ...}')
    
    # 额外信息
    extra_data = Column(JSON, comment='额外数据或明细')
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    
    # 联合唯一约束，防止重复统计
    __table_args__ = (
        UniqueConstraint('stat_type', 'stat_dimension', 'stat_date', 'stat_hour', 'datasource_id', 
                         name='uq_statistics_unique'),
        Index('idx_statistics_type_dim', 'stat_type', 'stat_dimension'),  # 按类型和维度查询
        Index('idx_statistics_date', 'stat_date'),  # 按日期范围查询
        Index('idx_statistics_datasource', 'datasource_id'),  # 按数据源查询
    )
    
    def __repr__(self):
        return f'<Statistics {self.stat_type}-{self.stat_dimension}>'
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'stat_type': self.stat_type,
            'stat_dimension': self.stat_dimension,
            'stat_date': self.stat_date.isoformat() if self.stat_date else None,
            'stat_hour': self.stat_hour,
            'datasource_id': self.datasource_id,
            'category': self.category,
            'metrics': self.metrics,
            'extra_data': self.extra_data,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


def init_db(app):
    """
    初始化数据库
    在Flask应用上下文中调用，创建所有数据表
    
    参数:
        app: Flask应用实例
    """
    with app.app_context():
        # 创建所有定义的表
        db.create_all()
        print("✅ 数据库初始化完成，所有数据表已创建")


def get_session():
    """
    获取数据库会话
    返回当前的SQLAlchemy session
    
    返回:
        Session: 数据库会话对象
    """
    return db.session
