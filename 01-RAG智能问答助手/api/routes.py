"""
API路由模块 - 定义所有RESTful API接口
包含完整的请求验证、错误处理和响应格式化

提供的API端点：
1. POST /api/chat - 智能问答（支持流式SSE）
2. GET /api/knowledge - 获取知识库状态
3. POST /api/knowledge - 添加文档到知识库
4. DELETE /api/knowledge - 清空知识库
5. GET /api/health - 健康检查
"""

import json
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, Response, stream_with_context

# 配置日志
logger = logging.getLogger(__name__)


def create_api_blueprint(get_retriever_fn, get_generator_fn):
    """
    创建API蓝图工厂函数
    
    Args:
        get_retriever_fn: 获取检索器实例的函数
        get_generator_fn: 获取生成器实例的函数
        
    Returns:
        Blueprint: Flask蓝图对象，包含所有API路由
    """

    # 创建API蓝图
    api_bp = Blueprint('api', __name__)

    # ==================== 辅助函数 ====================

    def validate_json_request(required_fields=None):
        """
        验证JSON请求体
        
        Args:
            required_fields (list): 必需的字段列表
            
        Returns:
            tuple: (data_dict, error_response) 成功时error_response为None
        """
        # 检查Content-Type
        if not request.is_json:
            return None, jsonify({
                'error': 'Invalid Content-Type',
                'message': '请求必须是JSON格式（Content-Type: application/json）',
                'code': 400
            }), 400

        # 解析JSON数据
        data = request.get_json(silent=True)
        if data is None:
            return None, jsonify({
                'error': 'Invalid JSON',
                'message': '无法解析请求体中的JSON数据',
                'code': 400
            }), 400

        # 检查必需字段
        if required_fields:
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                return None, jsonify({
                    'error': 'Missing Fields',
                    'message': f'缺少必需字段: {", ".join(missing_fields)}',
                    'missing_fields': missing_fields,
                    'code': 400
                }), 400

        return data, None, None


    def success_response(data=None, message="操作成功"):
        """
        构建成功响应的统一格式
        
        Args:
            data: 响应数据
            message: 成功消息
            
        Returns:
            dict: 格式化的成功响应
        """
        response = {
            'success': True,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        if data is not None:
            response['data'] = data
        return response


    def error_response(message, code=500, error_type="Error"):
        """
        构建错误响应的统一格式
        
        Args:
            message: 错误消息
            code: HTTP状态码
            error_type: 错误类型标识
            
        Returns:
            tuple: (response_dict, status_code)
        """
        return {
            'success': False,
            'error': error_type,
            'message': message,
            'timestamp': datetime.now().isoformat(),
            'code': code
        }, code


    # ==================== API路由定义 ====================

    @api_bp.route('/health', methods=['GET'])
    def health_check():
        """
        健康检查接口
        
        用于监控服务状态和负载均衡健康检查。
        返回服务状态、组件就绪情况和基本统计信息。
        
        方法: GET
        路径: /api/health
        
        返回示例:
        {
            "status": "healthy",
            "timestamp": "2024-01-01T12:00:00",
            "components": {...}
        }
        """
        try:
            # 检查各组件状态
            components_status = {
                'retriever': 'initialized' if get_retriever_fn() else 'not_initialized',
                'generator': 'initialized' if get_generator_fn() else 'not_initialized',
                'knowledge_base': 'loaded' if get_retriever_fn() and len(get_retriever_fn().vector_store.documents) > 0 else 'empty'
            }

            # 判断整体状态
            all_healthy = all(status != 'not_initialized' for status in components_status.values())

            return jsonify(success_response(data={
                'status': 'healthy' if all_healthy else 'degraded',
                'version': '1.0.0',
                'components': components_status,
                'knowledge_stats': get_retriever_fn().get_stats() if get_retriever_fn() else None
            }, message='服务运行正常')), 200

        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return jsonify(error_response(f"健康检查异常: {str(e)}", 503, "Service Unavailable")), 503


    @api_bp.route('/chat', methods=['POST'])
    def chat():
        """
        智能问答接口 - 核心功能
        
        接收用户问题，通过RAG流程检索相关知识库内容，
        然后调用DeepSeek大模型生成准确的回答。
        
        支持两种模式：
        1. 流式模式（stream=true）：返回SSE数据流，实时显示生成过程
        2. 非流式模式：一次性返回完整回答
        
        方法: POST
        路径: /api/chat
        
        请求体:
        {
            "question": "用户问题（必填）",
            "stream": false,              // 是否使用流式输出，默认false
            "use_rag": true,              // 是否使用知识库检索，默认true
            "history": [                  // 可选的对话历史
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "..."}
            ],
            "temperature": 0.7,           // 生成温度，可选
            "max_tokens": 2000           // 最大token数，可选
        }
        
        响应（非流式）:
        {
            "success": true,
            "data": {
                "answer": "生成的回答...",
                "sources": [...],
                "tokens_used": 150,
                "generation_time": 2.5
            }
        }
        """
        # 验证请求
        data, error_resp, error_code = validate_json_request(['question'])
        if error_resp:
            return error_resp, error_code

        try:
            question = data['question'].strip()
            
            # 参数验证
            if not question:
                return jsonify(error_response("问题不能为空", 400, "Validation Error")), 400

            if len(question) > 10000:
                return jsonify(error_response("问题长度超过限制（最大10000字符）", 400, "Validation Error")), 400

            # 获取可选参数
            stream_mode = data.get('stream', False)  # 是否流式输出
            use_rag = data.get('use_rag', True)     # 是否使用RAG
            history = data.get('history', [])       # 对话历史
            temperature = data.get('temperature', 0.7)
            max_tokens = data.get('max_tokens', 2000)

            logger.info(f"收到问答请求 - 问题长度:{len(question)}, 流式:{stream_mode}, RAG:{use_rag}")

            # 获取组件实例
            generator = get_generator_fn()
            retriever = get_retriever_fn() if use_rag else None

            # ========== 流式模式 ==========
            if stream_mode:
                def generate():
                    """生成器函数：产生SSE数据流"""
                    
                    # RAG检索上下文
                    context = ""
                    if use_rag and retriever:
                        try:
                            context = retriever.get_context_string(question)
                            if not context:
                                context = ""
                                yield f"data: {json.dumps({'type': 'warning', 'content': '未在知识库中找到相关内容，将使用通用知识回答'}, ensure_ascii=False)}\n\n"
                        except Exception as e:
                            logger.warning(f"RAG检索失败: {e}")
                            yield f"data: {json.dumps({'type': 'warning', 'content': f'知识库检索异常: {str(e)}'}, ensure_ascii=False)}\n\n"

                    # 流式生成回答
                    try:
                        full_text = ""
                        for chunk in generator.generate_stream(
                            question=question,
                            context=context,
                            chat_history=history,
                            temperature=temperature,
                            max_tokens=max_tokens
                        ):
                            full_text += chunk
                            sse_data = {
                                'content': chunk,
                                'type': 'chunk',
                                'timestamp': datetime.now().isoformat()
                            }
                            yield f"data: {json.dumps(sse_data, ensure_ascii=False)}\n\n"

                        # 发送完成信号
                        done_data = {
                            'content': '',
                            'type': 'done',
                            'full_text': full_text,
                            'tokens_used': len(full_text) * 2,  # 估算
                            'timestamp': datetime.now().isoformat()
                        }
                        yield f"data: {json.dumps(done_data, ensure_ascii=False)}\n\n"

                    except Exception as e:
                        logger.error(f"流式生成错误: {e}")
                        error_sse = {
                            'type': 'error',
                            'content': f'生成过程出错: {str(e)}',
                            'timestamp': datetime.now().isoformat()
                        }
                        yield f"data: {json.dumps(error_sse, ensure_ascii=False)}\n\n"

                # 返回SSE响应
                return Response(
                    stream_with_context(generate()),
                    mimetype='text/event-stream',
                    headers={
                        'Cache-Control': 'no-cache',
                        'X-Accel-Buffering': 'no',  # 禁用Nginx缓冲
                        'Connection': 'keep-alive'
                    }
                )

            # ========== 非流式模式 ==========
            else:
                # RAG检索
                context = ""
                if use_rag and retriever:
                    try:
                        context = retriever.get_context_string(question)
                        if not context:
                            logger.info("未检索到相关知识")
                    except Exception as e:
                        logger.warning(f"RAG检索失败: {e}")

                # 生成回答
                result = generator.chat(
                    message=question,
                    history=history,
                    use_rag=use_rag and bool(context),
                    retriever=retriever,
                    temperature=temperature,
                    max_tokens=max_tokens
                )

                return jsonify(success_response(data={
                    'answer': result['answer'],
                    'sources': result.get('sources', []),
                    'tokens_used': result.get('tokens_used', 0),
                    'generation_time': result.get('generation_time', 0),
                    'model': result.get('model', 'unknown'),
                    'used_rag': result.get('used_rag', False),
                    'context_length': result.get('context_length', 0)
                }, message='回答生成成功')), 200

        except Exception as e:
            logger.error(f"问答接口异常: {e}", exc_info=True)
            return jsonify(error_response(f"处理请求时发生错误: {str(e)}", 500, "Internal Error")), 500


    @api_bp.route('/knowledge', methods=['GET'])
    def get_knowledge_status():
        """
        获取知识库状态接口
        
        返回当前知识库的统计信息、文档列表等。
        用于监控和管理知识库。
        
        方法: GET
        路径: /api/knowledge
        
        查询参数:
        - detail: 是否返回详细信息（文档列表等），默认false
        
        返回示例:
        {
            "success": true,
            "data": {
                "total_documents": 10,
                "unique_sources": 3,
                "is_initialized": true
            }
        }
        """
        try:
            retriever = get_retriever_fn()
            stats = retriever.get_stats()

            # 检查是否需要详细信息
            show_detail = request.args.get('detail', 'false').lower() == 'true'

            response_data = stats.copy()

            if show_detail:
                # 添加文档列表信息
                documents_info = []
                seen_sources = set()
                
                for i, doc in enumerate(retriever.vector_store.documents[:20]):  # 限制返回数量
                    source = retriever.vector_store.metadata[i]['source']
                    
                    if source not in seen_sources:
                        documents_info.append({
                            'source': source,
                            'preview': doc[:200] + ('...' if len(doc) > 200 else ''),
                            'chunks_count': sum(1 for m in retriever.vector_store.metadata 
                                             if m['source'] == source)
                        })
                        seen_sources.add(source)

                response_data['documents'] = documents_info

            return jsonify(success_response(data=response_data, message='获取知识库状态成功')), 200

        except Exception as e:
            logger.error(f"获取知识库状态失败: {e}")
            return jsonify(error_response(f"获取知识库状态失败: {str(e)}", 500, "Query Error")), 500


    @api_bp.route('/knowledge', methods=['POST'])
    def add_to_knowledge():
        """
        添加文档到知识库接口
        
        支持两种方式添加文档：
        1. 通过文件路径添加本地文件
        2. 触发重新构建整个知识库
        
        方法: POST
        路径: /api/knowledge
        
        请求体（方式1-添加单个文件）:
        {
            "action": "add_file",
            "file_path": "/path/to/document.txt"
        }
        
        请求体（方式2-重建知识库）:
        {
            "action": "rebuild"
        }
        
        返回示例:
        {
            "success": true,
            "data": {
                "chunks_count": 15,
                "status": "success"
            }
        }
        """
        data, error_resp, error_code = validate_json_request(['action'])
        if error_resp:
            return error_resp, error_code

        try:
            action = data['action']
            retriever = get_retriever_fn()

            if action == 'add_file':
                # 添加单个文件
                file_path_str = data.get('file_path')
                if not file_path_str:
                    return jsonify(error_response("缺少file_path参数", 400, "Missing Parameter")), 400

                from pathlib import Path
                file_path = Path(file_path_str)

                if not file_path.exists():
                    return jsonify(error_response(f"文件不存在: {file_path_str}", 404, "File Not Found")), 404

                result = retriever.add_document(file_path)
                
                if result['status'] == 'success':
                    return jsonify(success_response(data=result, message=f"文件 {file_path.name} 添加成功")), 200
                else:
                    return jsonify(error_response(result['message'], 500, "Add Failed")), 500

            elif action == 'rebuild':
                # 重建整个知识库
                directory = data.get('directory')
                if directory:
                    from pathlib import Path
                    directory = Path(directory)
                
                result = retriever.build_knowledge_base(directory)
                
                if result['status'] == 'success':
                    return jsonify(success_response(data=result, message=result['message'])), 200
                else:
                    return jsonify(error_response(result['message'], 500, "Build Failed")), 500

            else:
                return jsonify(error_response(f"不支持的操作类型: {action}", 400, "Invalid Action")), 400

        except Exception as e:
            logger.error(f"知识库操作失败: {e}", exc_info=True)
            return jsonify(error_response(f"知识库操作失败: {str(e)}", 500, "Operation Error")), 500


    @api_bp.route('/knowledge', methods=['DELETE'])
    def clear_knowledge():
        """
        清空知识库接口
        
        清除所有已加载的文档和向量数据。
        此操作不可逆，请谨慎使用！
        
        方法: DELETE
        路径: /api/knowledge
        
        返回示例:
        {
            "success": true,
            "message": "知识库已清空"
        }
        """
        try:
            retriever = get_retriever_fn()

            # 记录清空前的大小
            before_count = len(retriever.vector_store.documents)

            # 清空向量存储
            retriever.vectors = np.array([], dtype=np.float32).reshape(0, retriever.config.VECTOR_DIMENSION)
            retriever.documents = []
            retriever.metadata = []
            retriever._is_initialized = False

            # 尝试删除持久化文件
            import numpy as np
            vector_db_path = retriever.config.VECTOR_DB_PATH.with_suffix('.pkl')
            if vector_db_path.exists():
                vector_db_path.unlink()
                logger.info(f"已删除向量数据库文件: {vector_db_path}")

            logger.info(f"知识库已清空 - 清除了 {before_count} 个文档")

            return jsonify(success_response(message=f"知识库已清空，共清除 {before_count} 个文档")), 200

        except Exception as e:
            logger.error(f"清空知识库失败: {e}")
            return jsonify(error_response(f"清空知识库失败: {str(e)}", 500, "Clear Error")), 500


    @api_bp.route('/test', methods=['POST'])
    def test_endpoint():
        """
        测试接口 - 用于调试和验证API连接
        
        简单的回显接口，返回接收到的数据和服务器状态，
        用于验证API是否正常工作。
        
        方法: POST
        路径: /api/test
        """
        data = request.get_json(silent=True) or {}
        
        return jsonify(success_response(data={
            'received_data': data,
            'request_headers': dict(request.headers),
            'server_time': datetime.now().isoformat(),
            'retriever_available': get_retriever_fn() is not None,
            'generator_available': get_generator_fn() is not None
        }, message='测试接口正常工作')), 200

    logger.info("API路由模块初始化完成")

    return api_bp
