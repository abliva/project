"""
配置文件 - RAG智能问答助手
包含SenseNova API配置、向量数据库配置、Flask应用配置等
"""

import os
from pathlib import Path


class Config:
    """基础配置类"""

    # ==================== SenseNova API 配置（商汤大模型） ====================
    # SenseNova API密钥，从环境变量获取，默认使用预置密钥
    SENSENOVA_API_KEY = os.getenv('SENSENOVA_API_KEY', 'sk-aYstKmpELhDTGdz7rHkBUYeXBIH8TjCa')

    # SenseNova API基础URL（OpenAI兼容接口）
    SENSENOVA_API_BASE = os.getenv('SENSENOVA_API_BASE', 'https://token.sensenova.cn/v1')

    # 使用的模型名称（SenseNova 6.7 Flash-Lite：轻量多模态模型，每5小时1500次）
    SENSENOVA_MODEL = os.getenv('SENSENOVA_MODEL', 'sensenova-6.7-flash-lite')

    # API请求超时时间（秒）
    SENSENOVA_TIMEOUT = int(os.getenv('SENSENOVA_TIMEOUT', '60'))

    # ==================== 向量数据库配置 ====================
    # 向量数据库存储路径
    VECTOR_DB_PATH = Path(__file__).parent / 'rag_engine' / 'knowledge_base' / 'vector_db'

    # 向量维度（使用text-embedding模型的维度）
    VECTOR_DIMENSION = int(os.getenv('VECTOR_DIMENSION', '1536'))

    # 相似度检索时返回的最相关文档数量
    TOP_K = int(os.getenv('TOP_K', '5'))

    # 相似度阈值（低于此值的文档将被过滤）
    SIMILARITY_THRESHOLD = float(os.getenv('SIMILARITY_THRESHOLD', '0.7'))

    # ==================== 文本切分配置 ====================
    # 文档切分时的最大token数
    CHUNK_SIZE = int(os.getenv('CHUNK_SIZE', '500'))

    # 文档切分时的重叠token数（保证上下文连续性）
    CHUNK_OVERLAP = int(os.getenv('CHUNK_OVERLAP', '50'))

    # ==================== Flask 应用配置 ====================
    # Flask调试模式
    DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'

    # 服务器监听主机
    HOST = os.getenv('FLASK_HOST', '0.0.0.0')

    # 服务器监听端口
    PORT = int(os.getenv('FLASK_PORT', '5000'))

    # JSON配置，确保中文正常显示
    JSON_AS_ASCII = False

    # ==================== 知识库配置 ====================
    # 知识库文档存储路径
    KNOWLEDGE_BASE_PATH = Path(__file__).parent / 'rag_engine' / 'knowledge_base'

    # 支持的文档格式
    SUPPORTED_FORMATS = ['.txt', '.pdf', '.md']

    # ==================== RAG Prompt 配置 ====================
    # 系统提示词模板
    SYSTEM_PROMPT = """你是一个专业的智能问答助手。你的任务是根据提供的知识库内容来回答用户的问题。

请遵循以下原则：
1. 仅基于提供的【知识库内容】回答问题，不要编造信息
2. 如果知识库中没有相关信息，请明确告知用户
3. 回答要简洁、准确、有条理
4. 使用中文回答
5. 可以适当引用知识库中的原文来支持你的回答

【知识库内容】：
{context}

【用户问题】：
{question}

请根据以上信息给出专业、准确的回答："""

    # 流式响应的分块大小
    STREAM_CHUNK_SIZE = int(os.getenv('STREAM_CHUNK_SIZE', '20'))


class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    LOG_LEVEL = 'DEBUG'


class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    LOG_LEVEL = 'INFO'
    # 生产环境校验API Key（延迟校验，避免import时报错）


class TestingConfig(Config):
    """测试环境配置"""
    TESTING = True
    DEBUG = True
    # 使用测试用的向量数据库路径
    VECTOR_DB_PATH = Path(__file__).parent / 'rag_engine' / 'knowledge_base' / 'test_vector_db'


# 配置映射字典，通过环境变量选择配置
config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig
}


def get_config():
    """
    根据环境变量获取配置对象
    默认使用开发环境配置
    """
    env = os.getenv('FLASK_ENV', 'development')
    return config_map.get(env, DevelopmentConfig)()
