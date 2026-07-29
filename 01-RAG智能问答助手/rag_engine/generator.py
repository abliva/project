"""
SenseNova生成器模块 - RAG系统的答案生成组件
基于商汤 SenseNova API（OpenAI兼容接口）实现智能问答

API文档: https://platform.sensenova.cn/docs
Base URL: https://token.sensenova.cn/v1
可用模型: sensenova-6.7-flash-lite / deepseek-v4-flash
"""

import os
import json
import time
import logging
from typing import Generator, Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class SenseNovaGenerator:
    """
    SenseNova API 生成器 - 基于商汤大模型的RAG增强生成器

    使用方式（与官方示例一致）:
        from openai import OpenAI
        client = OpenAI(base_url="https://token.sensenova.cn/v1", api_key="sk-xxx")
        resp = client.chat.completions.create(model="deepseek-v4-flash", messages=[...])
    """

    def __init__(self, config=None):
        """
        初始化生成器，创建OpenAI兼容客户端连接SenseNova

        Args:
            config: 配置对象，如果为None则使用默认配置
        """
        if config is None:
            from config import Config
            config = Config()

        self.config = config

        # 从配置读取API参数
        self.api_key = config.SENSENOVA_API_KEY
        self.base_url = config.SENSENOVA_API_BASE
        self.model = config.SENSENOVA_MODEL
        self.timeout = config.SENSENOVA_TIMEOUT

        # 创建OpenAI兼容客户端（与用户提供的示例代码一致）
        from openai import OpenAI
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout,
        )

        logger.info(f"SenseNova生成器初始化完成 | 模型:{self.model} | 接口:{self.base_url}")

    def chat(self, message: str, history=None, use_rag=False, retriever=None,
              temperature=0.7, max_tokens=2000) -> Dict[str, Any]:
        """
        对话接口 - 发送消息并获取回答

        整合RAG检索+LLM生成的一站式方法

        Args:
            message: 用户消息
            history: 对话历史 [{"role": "user/assistant", "content": "..."}]
            use_rag: 是否启用知识库检索
            retriever: 文档检索器实例
            temperature: 生成温度 (0-1)
            max_tokens: 最大生成token数

        Returns:
            dict: {'answer': str, 'sources': list, 'tokens_used': int, ...}
        """
        start_time = time.time()

        # RAG检索：获取知识库上下文
        context = ""
        if use_rag and retriever:
            try:
                context = retriever.get_context_string(message)
                if context:
                    logger.info(f"RAG检索到上下文，长度: {len(context)}")
                else:
                    logger.info("未检索到相关知识，使用纯对话模式")
            except Exception as e:
                logger.warning(f"RAG检索异常: {e}，使用纯对话模式")

        # 构建消息列表
        messages = self._build_messages(message, context, history)

        try:
            # 调用SenseNova API（与用户提供的示例代码完全一致）
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
            )

            answer = resp.choices[0].message.content
            tokens_used = resp.usage.total_tokens if resp.usage else 0
            generation_time = round(time.time() - start_time, 2)

            logger.info(f"回答生成完成 | 耗时:{generation_time}s | tokens:{tokens_used}")

            return {
                'answer': answer,
                'sources': self._extract_sources(context),
                'tokens_used': tokens_used,
                'generation_time': generation_time,
                'model': self.model,
                'used_rag': bool(context),
                'context_length': len(context),
            }

        except Exception as e:
            logger.error(f"SenseNova API调用失败: {e}", exc_info=True)
            raise RuntimeError(f"AI回答生成失败: {str(e)}")

    def chat_stream(self, message: str, history=None, use_rag=False, retriever=None,
                     temperature=0.7, max_tokens=2000) -> Generator[str, None, None]:
        """
        流式对话 - 逐token返回生成的文本

        Yields:
            str: 生成的文本片段
        """
        context = ""
        if use_rag and retriever:
            try:
                context = retriever.get_context_string(message)
            except Exception as e:
                logger.warning(f"RAG检索异常: {e}")

        messages = self._build_messages(message, context, history)

        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )

            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"流式生成失败: {e}")
            yield f"[错误] 生成过程出错: {str(e)}"

    def _build_messages(self, question: str, context: str,
                         history: Optional[List[Dict]]) -> List[Dict]:
        """构建发送给API的消息列表"""
        messages = []

        if context:
            # RAG模式：将知识库内容注入系统提示词
            system_content = f"""你是一个专业的智能问答助手。请根据以下【知识库内容】回答用户的问题。

规则：
1. 优先基于知识库内容回答，不要编造信息
2. 如果知识库中没有相关信息，请告知用户
3. 回答简洁、准确、有条理，使用中文

【知识库内容】：
{context}"""
        else:
            system_content = "你是一个友好、专业的AI助手。请用中文回答用户的问题。"

        messages.append({"role": "system", "content": system_content})

        # 追加对话历史
        if history:
            for msg in history:
                if isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                    messages.append(msg)

        # 当前用户问题
        messages.append({"role": "user", "content": question})

        return messages

    def _extract_sources(self, context: str) -> List[Dict]:
        """从上下文中提取参考来源"""
        sources = []
        if not context:
            return sources
        for line in context.split('\n'):
            if '来源:' in line or 'source:' in line.lower():
                name = line.split(':', 1)[-1].strip()
                if name:
                    sources.append({'source': name, 'type': 'knowledge_base'})
        return sources


# 工厂函数
def create_generator(config=None) -> SenseNovaGenerator:
    """创建SenseNova生成器实例"""
    return SenseNovaGenerator(config)


# ==================== 独立测试 ====================
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s [%(levelname)s] %(message)s')

    print("=" * 50)
    print("  SenseNova 生成器测试")
    print("=" * 50)

    gen = create_generator()
    print(f"模型: {gen.model}")
    print(f"接口: {gen.base_url}\n")

    # 测试对话
    print("--- 发送测试消息 ---")
    try:
        result = gen.chat("你好，请用一句话介绍你自己")
        print(f"\n回答:\n{result['answer']}")
        print(f"\ntokens: {result['tokens_used']} | 耗时: {result['generation_time']}s")
    except Exception as e:
        print(f"测试失败: {e}")
