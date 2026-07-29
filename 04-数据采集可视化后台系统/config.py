# -*- coding: utf-8 -*-
"""
通用数据采集与可视化后台系统 - 配置文件
包含：MySQL连接配置、缓存配置、爬虫配置、应用基础配置
"""

import os

# ==================== 应用基础配置 ====================
class BaseConfig:
    """应用基础配置"""
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY', 'data-collector-secret-key-2024')
    DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'
    
    # JSON配置
    JSON_AS_ASCII = False  # 支持中文JSON输出
    
    # 日志配置
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_FILE = 'logs/app.log'

# ==================== MySQL数据库配置 ====================
class MySQLConfig:
    """MySQL数据库连接配置"""
    # 数据库连接参数
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '123456')
    MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE', 'data_collector')
    MYSQL_CHARSET = os.environ.get('MYSQL_CHARSET', 'utf8mb4')
    
    # SQLAlchemy连接URI
    SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}?charset={MYSQL_CHARSET}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = DEBUG if 'DEBUG' in dir() else False
    
    # 连接池配置
    SQLALCHEMY_POOL_SIZE = int(os.environ.get('SQLALCHEMY_POOL_SIZE', 10))  # 连接池大小
    SQLALCHEMY_MAX_OVERFLOW = int(os.environ.get('SQLALCHEMY_MAX_OVERFLOW', 5))  # 超出连接池大小后最多可创建的连接数
    SQLALCHEMY_POOL_TIMEOUT = int(os.environ.get('SQLALCHEMY_POOL_TIMEOUT', 30))  # 连接池获取连接超时时间（秒）
    SQLALCHEMY_POOL_RECYCLE = int(os.environ.get('SQLALCHEMY_POOL_RECYCLE', 3600))  # 连接回收时间（秒）

# ==================== LRU缓存配置 ====================
class CacheConfig:
    """LRU缓存配置"""
    CACHE_ENABLED = True  # 是否启用缓存
    CACHE_MAX_SIZE = int(os.environ.get('CACHE_MAX_SIZE', 1000))  # 缓存最大容量（条目数）
    CACHE_DEFAULT_TTL = int(os.environ.get('CACHE_DEFAULT_TTL', 300))  # 默认TTL过期时间（秒）
    CACHE_CLEANUP_INTERVAL = int(os.environ.get('CACHE_CLEANUP_INTERVAL', 60))  # 缓存清理间隔（秒）
    
    # 命中率统计配置
    CACHE_STATS_ENABLED = True  # 是否启用命中率统计

# ==================== 爬虫配置 ====================
class CrawlerConfig:
    """爬虫模块配置"""
    # 请求配置
    CRAWLER_REQUEST_TIMEOUT = int(os.environ.get('CRAWLER_REQUEST_TIMEOUT', 30))  # 请求超时时间（秒）
    CRAWLER_MAX_RETRIES = int(os.environ.get('CRAWLER_MAX_RETRIES', 3))  # 最大重试次数
    CRAWLER_RETRY_DELAY = float(os.environ.get('CRAWLER_RETRY_DELAY', 1.0))  # 重试延迟（秒）
    
    # 并发配置
    CRAWLER_THREAD_POOL_SIZE = int(os.environ.get('CRAWLER_THREAD_POOL_SIZE', 5))  # 线程池大小
    CRAWLER_CONCURRENT_REQUESTS = int(os.environ.get('CRAWLER_CONCURRENT_REQUESTS', 10))  # 并发请求数
    
    # 反爬策略配置
    CRAWLER_USER_AGENTS = [  # 随机User-Agent列表
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15; rv:121.0) Gecko/20100101 Firefox/121.0',
    ]
    
    # 请求间隔（秒），避免被封禁
    CRAWLER_REQUEST_DELAY_MIN = float(os.environ.get('CRAWLER_REQUEST_DELAY_MIN', 0.5))
    CRAWLER_REQUEST_DELAY_MAX = float(os.environ.get('CRAWLER_REQUEST_DELAY_MAX', 2.0))
    
    # 代理配置（可选）
    CRAWLER_PROXY_ENABLED = os.environ.get('CRAWLER_PROXY_ENABLED', 'False').lower() == 'true'
    CRAWLER_PROXY_LIST = []  # 代理列表，格式：['http://ip:port', ...]
    
    # Cookie管理
    CRAWLER_COOKIE_ENABLED = True
    CRAWLER_COOKIE_FILE = 'cookies.json'  # Cookie存储文件

# ==================== 定时任务配置 ====================
class SchedulerConfig:
    """APScheduler定时任务配置"""
    SCHEDULER_API_ENABLED = True  # 启用Scheduler API
    SCHEDULER_TIMEZONE = 'Asia/Shanghai'  # 时区设置
    JOBS_DEFAULT = {
        'coalesce': False,  # 合并错过的任务
        'max_instances': 1,  # 同一任务最大实例数
        'misfire_grace_time': 300  # 错过执行时间的宽限时间（秒）
    }

# ==================== API配置 ====================
class APIConfig:
    """API接口配置"""
    API_PREFIX = '/api/v1'  # API前缀
    API_VERSION = '1.0.0'  # API版本号
    
    # 分页配置
    DEFAULT_PAGE_SIZE = 20  # 默认每页条数
    MAX_PAGE_SIZE = 100  # 最大每页条数
    
    # 导出配置
    EXPORT_BATCH_SIZE = 1000  # 导出批次大小
    SUPPORTED_EXPORT_FORMATS = ['csv']  # 支持的导出格式

# ==================== 综合配置类 ====================
class DevelopmentConfig(BaseConfig, MySQLConfig, CacheConfig, CrawlerConfig, SchedulerConfig, APIConfig):
    """开发环境配置"""
    DEBUG = True

class ProductionConfig(BaseConfig, MySQLConfig, CacheConfig, CrawlerConfig, SchedulerConfig, APIConfig):
    """生产环境配置"""
    DEBUG = False
    LOG_LEVEL = 'WARNING'

class TestingConfig(BaseConfig, MySQLConfig, CacheConfig, CrawlerConfig, SchedulerConfig, APIConfig):
    """测试环境配置"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///test.db'

# 配置映射字典
config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
