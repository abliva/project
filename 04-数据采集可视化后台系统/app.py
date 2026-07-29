# -*- coding: utf-8 -*-
"""
通用数据采集与可视化后台系统 - Flask主应用入口
功能：
1. 初始化Flask应用及所有扩展组件
2. 注册API路由蓝图
3. 配置数据库连接与初始化
4. 启动定时任务调度器
5. 提供静态文件服务（前端页面）
6. 全局错误处理与日志配置

启动方式:
    开发环境: python app.py
    生产环境: gunicorn -w 4 -b 0.0.0.0:5000 app:app

访问地址: http://localhost:5000/
         API文档: http://localhost:5000/api/v1/health
         前端页面: http://localhost:5000/static/index.html
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

from flask import Flask, jsonify, send_from_directory, render_template_string
from flask_cors import CORS

# 导入项目模块
from config import config_map, DevelopmentConfig
from models.database import db, init_db
from api.routes import create_api_blueprint
from tasks.scheduler import TaskScheduler
from services.cache import init_cache


def create_app(config_name='development'):
    """
    应用工厂函数 - 创建并配置Flask应用实例
    
    使用工厂模式的好处：
    - 方便测试时创建多个应用实例
    - 灵活切换不同环境配置（开发/生产/测试）
    - 避免循环导入问题
    
    参数:
        config_name: 环境名称，可选值：development/production/testing
        
    返回:
        Flask: 配置完成的Flask应用实例
    """
    
    # ==================== 1. 创建Flask应用实例 ====================
    app = Flask(__name__)
    
    # 加载对应环境的配置
    config_class = config_map.get(config_name, DevelopmentConfig)
    app.config.from_object(config_class)
    
    print(f"\n{'='*60}")
    try:
        print(f"🚀 正在启动数据采集与可视化后台系统...")
    except UnicodeEncodeError:
        print("[INFO] 正在启动数据采集与可视化后台系统...")
    print(f"   环境: {config_name}")
    print(f"   调试模式: {app.config.get('DEBUG', False)}")
    print(f"{'='*60}\n")
    
    # ==================== 2. 配置日志系统 ====================
    setup_logging(app)
    
    logger = logging.getLogger(__name__)
    logger.info(f"✅ 日志系统初始化完成 | 级别: {app.config.get('LOG_LEVEL', 'INFO')}")
    
    # ==================== 3. 启用CORS跨域支持 ====================
    CORS(app, resources={
        r"/api/*": {
            "origins": "*",  # 允许所有来源（生产环境应限制具体域名）
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })
    logger.info("✅ CORS跨域支持已启用")
    
    # ==================== 4. 初始化数据库 ====================
    db.init_app(app)
    
    with app.app_context():
        try:
            # 自动创建所有数据表（如果不存在）
            db.create_all()
            logger.info("✅ 数据库连接成功，表结构已检查/创建")
            
            # 测试数据库连接
            from sqlalchemy import text
            db.session.execute(text('SELECT 1'))
            db.session.commit()
            logger.info("✅ 数据库连接测试通过")
            
        except Exception as e:
            logger.error(f"❌ 数据库初始化失败: {str(e)}")
            try:
                print(f"\n⚠️ 数据库连接失败！请确保MySQL服务已启动且配置正确。")
                print(f"   错误详情: {str(e)}\n")
            except UnicodeEncodeError:
                print(f"\n[WARNING] 数据库连接失败！请确保MySQL服务已启动且配置正确。")
                print(f"   错误详情: {str(e)}\n")
            # 不退出程序，让用户可以在API中看到错误信息
    
    # ==================== 5. 注册API路由蓝图 ====================
    api_bp = create_api_blueprint()
    app.register_blueprint(api_bp)
    logger.info("✅ API路由已注册 | 前缀: /api/v1")
    
    # ==================== 6. 初始化LRU缓存 ====================
    init_cache(app.config if hasattr(app.config, 'CACHE_MAX_SIZE') else None)
    logger.info("✅ LRU缓存系统已初始化")
    
    # ==================== 7. 初始化定时任务调度器 ====================
    try:
        scheduler = TaskScheduler(app)
        
        # 注册示例定时任务（可根据实际需求修改或删除）
        register_scheduled_tasks(scheduler)
        
        # 启动调度器
        scheduler.start()
        logger.info("✅ 定时任务调度器已启动")
        
        # 将调度器实例存入app上下文，方便其他地方使用
        app.extensions['scheduler'] = scheduler
    except Exception as e:
        logger.warning(f"⚠️ 定时任务调度器初始化失败: {str(e)}")
        print(f"[警告] 定时任务功能不可用: {e}")
        app.extensions['scheduler'] = None
    
    # ==================== 8. 注册路由和错误处理 ====================
    register_routes(app)
    register_error_handlers(app)
    
    # ==================== 9. 应用启动钩子 ====================
    @app.before_request
    def before_request():
        """每个请求前的处理（可用于请求日志、认证等）"""
        pass
    
    @app.after_request
    def after_request(response):
        """每个请求后的处理（可添加响应头等）"""
        response.headers['X-Request-Time'] = datetime.now().isoformat()
        return response
    
    logger.info("=" * 50)
    logger.info("🎉 Flask应用初始化完成！")
    logger.info("=" * 50)
    
    return app


def setup_logging(app):
    """
    配置日志系统
    
    参数:
        app: Flask应用实例
    """
    # 确保日志目录存在
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # 获取日志级别
    log_level = getattr(logging, app.config.get('LOG_LEVEL', 'INFO').upper(), logging.INFO)
    
    # 配置根日志记录器
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            # 控制台输出（带颜色）
            logging.StreamHandler(sys.stdout),
            # 文件输出（自动轮转，最大10MB，保留5个备份）
            RotatingFileHandler(
                filename=os.path.join(log_dir, 'app.log'),
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
        ]
    )


def register_scheduled_tasks(scheduler):
    """
    注册定时任务到调度器
    
    参数:
        scheduler: TaskScheduler实例
    """
    from tasks.scheduler import sample_crawl_job, sample_cleanup_job, sample_stats_job
    
    # 任务1：每天凌晨2点执行全量数据采集
    scheduler.add_job(
        func=sample_crawl_job,
        job_id='daily_full_crawl',
        trigger='cron',
        hour=2,
        minute=0,
        second=0
    )
    
    # 任务2：每6小时执行增量采集
    scheduler.add_job(
        func=sample_crawl_job,
        job_id='incremental_crawl',
        trigger='cron',
        hour='*/6',
        minute=0,
        second=0
    )
    
    # 任务3：每小时清理过期缓存
    scheduler.add_job(
        func=sample_cleanup_job,
        job_id='hourly_cache_cleanup',
        trigger='interval',
        hours=1
    )
    
    # 任务4：每天凌晨3点30分统计前一天的数据
    scheduler.add_job(
        func=sample_stats_job,
        job_id='daily_statistics_aggregation',
        trigger='cron',
        hour=3,
        minute=30,
        second=0
    )


def register_routes(app):
    """
    注册额外的路由（非API路由）
    
    参数:
        app: Flask应用实例
    """
    
    @app.route('/')
    def index():
        """
        首页路由 - 重定向到前端页面
        访问 http://localhost:5000/ 会自动打开可视化界面
        """
        return send_from_directory('static', 'index.html')
    
    @app.route('/static/<path:filename>')
    def serve_static(filename):
        """
        静态文件服务路由
        
        参数:
            filename: 文件名或路径
            
        返回:
            Response: 静态文件内容
        """
        return send_from_directory('static', filename)
    
    @app.route('/api')
    def api_info():
        """
        API信息接口 - 返回可用端点列表和使用说明
        """
        info = {
            'service': '数据采集与可视化后台系统',
            'version': '1.0.0',
            'endpoints': {
                '健康检查': '/api/v1/health',
                '数据源管理': {
                    '列表': 'GET /api/v1/datasources',
                    '详情': 'GET /api/v1/datasources/{id}',
                    '创建': 'POST /api/v1/datasources',
                    '更新': 'PUT /api/v1/datasources/{id}',
                    '删除': 'DELETE /api/v1/datasource/{id}'
                },
                '采集记录': {
                    '列表': 'GET /api/v1/crawlrecords',
                    '导出CSV': 'GET /api/v1/crawlrecords/export'
                },
                '统计数据': {
                    '概览': 'GET /api/v1/statistics/overview',
                    '趋势': 'GET /api/v1/statistics/trend',
                    '按数据源': 'GET /api/v1/statistics/by-datasource'
                },
                '缓存管理': {
                    '统计': 'GET /api/v1/cache/stats',
                    '清空': 'POST /api/v1/cache/clear'
                },
                '手动触发': 'POST /api/v1/crawl/trigger'
            },
            'frontend': 'http://localhost:5000/static/index.html',
            'documentation': '详见README.md'
        }
        return jsonify(info)


def register_error_handlers(app):
    """
    注册全局错误处理器
    
    参数:
        app: Flask应用实例
    """
    
    @app.errorhandler(400)
    def bad_request(error):
        """400 Bad Request"""
        return jsonify({
            'success': False,
            'code': 400,
            'message': '请求参数有误',
            'error': str(error.description) if hasattr(error, 'description') else str(error),
            'timestamp': datetime.now().isoformat()
        }), 400
    
    @app.errorhandler(404)
    def not_found(error):
        """404 Not Found"""
        return jsonify({
            'success': False,
            'code': 404,
            'message': '请求的资源不存在',
            'error': str(error.description) if hasattr(error, 'description') else str(error),
            'timestamp': datetime.now().isoformat()
        }), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        """405 Method Not Allowed"""
        return jsonify({
            'success': False,
            'code': 405,
            'message': '请求方法不允许',
            'error': str(error.description) if hasattr(error, 'description') else str(error),
            'timestamp': datetime.now().isoformat()
        }), 405
    
    @app.errorhandler(500)
    def internal_error(error):
        """500 Internal Server Error"""
        return jsonify({
            'success': False,
            'code': 500,
            'message': '服务器内部错误',
            'error': '服务器遇到了意外情况，请稍后重试' if not app.debug else str(error),
            'timestamp': datetime.now().isoformat()
        }), 500


# ==================== 应用入口 ====================

if __name__ == '__main__':
    """
    程序主入口
    直接运行此文件会启动开发服务器
    """
    
    # 从环境变量读取配置，默认使用开发环境
    env = os.environ.get('FLASK_ENV', 'development')
    
    # 创建Flask应用
    app = create_app(config_name=env)
    
    # 启动开发服务器
    # host='0.0.0.0' 表示监听所有网络接口（允许局域网访问）
    # port=5000 指定端口
    # debug=False 关闭调试模式（避免Windows下自动重启问题）
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False
    )
