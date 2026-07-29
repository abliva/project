"""
Flask主应用入口 - RAG智能问答助手RESTful API服务
提供完整的API接口，支持流式SSE输出和知识库管理

主要功能：
1. /api/chat - 智能问答接口（支持流式和非流式）
2. /api/knowledge - 知识库管理接口
3. /api/health - 健康检查接口
"""

import os
import logging
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS

# 配置日志系统
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def create_app(config=None):
    """
    应用工厂函数 - 创建并配置Flask应用实例
    
    使用工厂模式便于测试和配置管理
    
    Args:
        config: 配置对象，如果为None则使用默认配置
        
    Returns:
        Flask: 配置好的Flask应用实例
    """
    # 创建Flask应用实例
    app = Flask(__name__)

    # 加载配置
    if config is None:
        from config import get_config
        config = get_config()

    app.config.from_object(config)

    # 启用CORS跨域支持（前后端分离时必需）
    CORS(app)

    # ==================== 初始化RAG组件 ====================
    
    # 初始化文档检索器（延迟初始化，避免启动时加载）
    retriever_instance = None
    generator_instance = None


    def get_retriever():
        """获取或创建检索器实例（懒加载）"""
        nonlocal retriever_instance
        if retriever_instance is None:
            from rag_engine.retriever import DocumentRetriever
            retriever_instance = DocumentRetriever(config)
            # 如果知识库已存在则自动加载
            if retriever_instance._is_initialized:
                logger.info("知识库已自动加载")
        return retriever_instance


    def get_generator():
        """获取或创建生成器实例（懒加载）"""
        nonlocal generator_instance
        if generator_instance is None:
            from rag_engine.generator import SenseNovaGenerator
            generator_instance = SenseNovaGenerator(config)
        return generator_instance

    # ==================== 注册路由 ====================
    
    from api.routes import create_api_blueprint
    api_bp = create_api_blueprint(get_retriever, get_generator)
    app.register_blueprint(api_bp, url_prefix='/api')

    # ==================== 根路径 - 返回前端页面 ====================

    @app.route('/')
    def index():
        """根路径 - 返回RAG智能问答前端界面"""
        return app.send_static_file('index.html')

    # 静态文件路由（避免404）
    @app.errorhandler(404)
    def not_found(error):
        """处理404错误 - 对于非API请求返回前端页面（SPA fallback）"""
        if request.path.startswith('/api/'):
            return jsonify({
                'error': 'Not Found',
                'message': '请求的资源不存在',
                'code': 404
            }), 404
        return app.send_static_file('index.html')


    @app.errorhandler(500)
    def internal_error(error):
        """处理500错误 - 服务器内部错误"""
        logger.error(f"服务器内部错误: {error}")
        return jsonify({
            'error': 'Internal Server Error',
            'message': '服务器内部错误，请稍后重试',
            'code': 500
        }), 500


    @app.errorhandler(400)
    def bad_request(error):
        """处理400错误 - 请求参数错误"""
        return jsonify({
            'error': 'Bad Request',
            'message': '请求参数有误，请检查输入',
            'code': 400
        }), 400

    logger.info(f"Flask应用创建完成 - 调试模式:{config.DEBUG}")
    
    return app


# ==================== 应用入口点 ====================

if __name__ == '__main__':
    """
    应用启动入口
    
    直接运行此文件将启动开发服务器
    生产环境建议使用gunicorn或uwsgi
    """
    print("=" * 60)
    print("  RAG智能问答助手 - 启动中...")
    print("=" * 60)

    # 创建应用实例
    app = create_app()

    # 从配置获取运行参数
    host = app.config.get('HOST', '0.0.0.0')
    port = app.config.get('PORT', 5000)
    debug = app.config.get('DEBUG', True)

    print(f"\n✓ 服务地址: http://{host}:{port}")
    print(f"✓ API文档: http://{host}:{port}/")
    print(f"✓ 健康检查: http://{host}:{port}/api/health")
    print(f"\n按 Ctrl+C 停止服务\n")

    # 启动Flask开发服务器
    app.run(
        host=host,
        port=port,
        debug=debug,
        threaded=True  # 支持多线程处理并发请求
    )
