"""
AI多功能智能助手 - 主程序入口

提供交互式命令行界面，集成所有核心功能：
- 多轮对话管理（基于SenseNova大模型）
- 任务自动规划与拆解
- 工具调用执行
- 安全过滤检查

使用方法:
    python main.py
    
交互命令:
    - 直接输入: 与AI助手对话
    - /help: 显示帮助信息
    - /clear: 清空对话历史
    - /stats: 查看统计信息
    - /export: 导出会话记录
    - /quit 或 /exit: 退出程序
"""

import sys
import os
import json
from datetime import datetime

# 添加项目根目录到系统路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入核心模块
from config import load_config_from_env, get_all_configs, llm_config
from agent.chat_manager import ChatManager
from agent.task_planner import TaskPlanner
from agent.tool_executor import ToolExecutor
from agent.safety_filter import SafetyFilter

# 导入工具模块
from tools.info_query import InfoQueryTool
from tools.text_generator import TextGeneratorTool
from tools.data_analyzer import DataAnalyzerTool
from tools.scheduler import SchedulerTool

# LLM API客户端（OpenAI兼容接口）
try:
    from openai import OpenAI
except ImportError:
    print("⚠️ 请先安装openai库: pip install openai")
    sys.exit(1)


class AIAgent:
    """
    AI智能助手主类
    
    整合所有组件，提供统一的交互接口
    集成SenseNova大模型实现智能对话
    """
    
    def __init__(self):
        """初始化AI助手"""
        print("\n" + "="*60)
        print("🤖 AI多功能智能助手")
        print("="*60)
        
        # 加载配置
        load_config_from_env()
        
        # 初始化LLM客户端（SenseNova - OpenAI兼容接口）
        self._init_llm_client()
        
        # 初始化核心组件
        self.chat_manager = ChatManager(session_id=f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        self.task_planner = TaskPlanner()
        self.tool_executor = ToolExecutor()
        self.safety_filter = SafetyFilter()
        
        # 注册所有工具
        self._register_tools()
        
        # 运行统计
        self.session_stats = {
            "start_time": datetime.now(),
            "total_interactions": 0,
            "successful_tasks": 0,
            "failed_tasks": 0,
            "llm_calls": 0
        }
        
        # 显示启动信息
        self._show_welcome()

    def _init_llm_client(self):
        """初始化LLM API客户端"""
        try:
            self.llm_client = OpenAI(
                api_key=llm_config.api_key,
                base_url=llm_config.base_url
            )
            print(f"✓ LLM客户端初始化完成 | 模型: {llm_config.model_name}")
        except Exception as e:
            print(f"⚠️ LLM客户端初始化失败: {e}")
            self.llm_client = None

    def _call_llm(self, messages: list, system_prompt: str = None) -> str:
        """
        调用LLM API生成回复
        
        Args:
            messages: 对话消息列表
            system_prompt: 可选的系统提示词
            
        Returns:
            LLM生成的回复文本
        """
        if not self.llm_client:
            return "抱歉，AI模型暂时不可用，请稍后重试。"
        
        try:
            # 构建完整的消息列表
            full_messages = []
            
            # 添加系统提示词
            if system_prompt:
                full_messages.append({"role": "system", "content": system_prompt})
            else:
                full_messages.append({
                    "role": "system", 
                    "content": """你是一个专业的AI多功能智能助手，具有以下能力：
1. 信息查询：天气、搜索、新闻等
2. 文案生成：邮件、报告、文案等
3. 数据分析：CSV、JSON文件分析
4. 日程管理：提醒、日程安排

请用友好、专业的方式回应用户。当用户需要使用工具时，你会自动调用相应的功能。
回答要简洁明了，使用中文。"""
                })
            
            # 添加对话历史
            full_messages.extend(messages)
            
            # 调用API
            self.session_stats["llm_calls"] += 1
            response = self.llm_client.chat.completions.create(
                model=llm_config.model_name,
                messages=full_messages,
                max_tokens=llm_config.max_tokens,
                temperature=llm_config.temperature,
                timeout=llm_config.timeout
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"❌ LLM调用失败: {e}")
            return f"抱歉，处理请求时出现错误：{str(e)}"

    def _register_tools(self):
        """注册所有可用工具到执行器"""
        print("\n⚙️ 正在初始化工具集...")
        
        # 创建并注册工具实例
        tools = [
            (InfoQueryTool(), "information", "信息查询"),
            (TextGeneratorTool(), "creation", "文案生成"),
            (DataAnalyzerTool(), "analysis", "数据分析"),
            (SchedulerTool("data/schedules.json"), "management", "日程管理")
        ]
        
        for tool_instance, category, description in tools:
            self.tool_executor.register_tool(tool_instance, category=category)
            print(f"   ✓ {description}: {tool_instance.name}")
    
    def _show_welcome(self):
        """显示欢迎信息和帮助"""
        welcome_text = f"""
╔════════════════════════════════════════╗
║                                        ║
║   🎉 欢迎使用 AI 多功能智能助手！       ║
║                                        ║
║   我可以帮您：                          ║
║   🔍 查询天气、搜索信息                 ║
║   ✍️ 生成各类文案（邮件、报告等）         ║
║   📊 分析数据文件                       ║
║   📅 管理您的日程安排                    ║
║                                        ║
║   输入 /help 查看更多命令               ║
╚════════════════════════════════════════╝

💡 会话ID: {self.chat_manager.session_id}
🧠 当前模型: {llm_config.model_name}

"""
        print(welcome_text)

    def process_input(self, user_input: str) -> str:
        """
        处理用户输入的主流程
        
        Args:
            user_input: 用户输入的文本
            
        Returns:
            助手的回复文本
        """
        # 更新统计
        self.session_stats["total_interactions"] += 1
        
        try:
            # 1. 安全过滤检查
            safety_result = self.safety_filter.check_input(user_input)
            
            if not safety_result.is_safe:
                response = self._generate_safety_warning(safety_result)
                return response
            
            # 2. 添加用户消息到对话历史
            self.chat_manager.add_message(role="user", content=user_input)
            
            # 3. 意图识别与任务规划
            intent, confidence = self.task_planner.analyze_intent(user_input)
            
            print(f"🔍 意图识别: {intent.value} | 置信度: {confidence:.2f}")
            
            # 4. 根据意图类型决定处理策略
            # 只有当意图为unknown且置信度为0时才走纯对话模式
            # 其他情况都尝试使用工具 + LLM结合模式
            if intent.value == "unknown" and confidence == 0.0:
                print("⚠️ 走纯对话模式（完全无法识别意图）")
                assistant_response = self._generate_llm_response(user_input, use_tools=False)
            else:
                # 有明确意图（即使置信度较低），尝试使用工具 + LLM结合模式
                task_plan = self.task_planner.decompose_task(user_input, intent, confidence)
                
                print(f"📋 任务计划: 需要{len(task_plan.sub_tasks)}个子任务 | 工具: {task_plan.requires_tools}")
                
                if task_plan.requires_tools and len(task_plan.sub_tasks) > 0:
                    # 需要调用工具，先执行工具获取结果
                    print("🔧 开始调用真实API...")
                    results = self.tool_executor.execute_task_plan(task_plan)
                    
                    # 聚合结果
                    aggregated = self.tool_executor.aggregate_results(results)
                    
                    print(f"📊 工具执行结果: 成功{aggregated['summary']['successful']}/{aggregated['summary']['total_tools']}")
                    
                    if aggregated['summary']['successful'] > 0:
                        # 工具成功，使用LLM基于真实数据生成回复
                        print("✅ 工具调用成功，正在让AI整合数据...")
                        assistant_response = self._generate_llm_with_tool_context(
                            user_input, aggregated, task_plan
                        )
                        self.session_stats["successful_tasks"] += 1
                    else:
                        # 工具失败，让LLM说明情况
                        print("❌ 工具调用失败，让AI解释...")
                        error_context = f"""【系统提示】用户请求了天气/信息查询，但工具调用失败了。

错误信息：
{json.dumps(aggregated.get('errors', []), ensure_ascii=False, indent=2)}

请向用户友好地说明情况，并建议其他方式。使用中文回答。"""
                        
                        assistant_response = self._call_llm(
                            messages=[{"role": "user", "content": user_input}],
                            system_prompt=error_context
                        )
                        self.session_stats["failed_tasks"] += 1
                else:
                    # 无需工具，使用纯LLM对话
                    print("💬 无需工具，走纯对话模式")
                    assistant_response = self._generate_llm_response(user_input, intent=intent)
            
            # 5. 输出安全检查（放宽限制）
            output_safety = self.safety_filter.check_output(assistant_response)
            if not output_safety.is_safe:
                # 只在检测到高风险内容时才拦截
                if output_safety.risk_level in ["high", "critical"]:
                    print(f"⛔ 输出安全检查未通过: {output_safety.violation_type}")
                    assistant_response = "抱歉，生成的内容需要调整，请尝试重新表述您的问题。"
                else:
                    # 低风险警告，仍然显示内容
                    print(f"⚠️ 输出存在轻微问题: {output_safety.violation_type} (已忽略)")
            
            # 6. 添加助手回复到历史
            self.chat_manager.add_message(role="assistant", content=assistant_response)
            
            return assistant_response
            
        except Exception as e:
            error_msg = f"❌ 处理过程中出现错误: {str(e)}"
            print(error_msg)
            self.session_stats["failed_tasks"] += 1
            return error_msg

    def _generate_llm_response(self, user_input: str, use_tools: bool = True, intent=None) -> str:
        """
        使用LLM生成智能回复（纯对话模式）
        
        Args:
            user_input: 用户输入
            use_tools: 是否在提示词中提及工具能力
            intent: 已识别的意图（可选）
            
        Returns:
            LLM生成的回复
        """
        # 获取最近的对话历史（限制数量以控制token）
        recent_messages = self.chat_manager.get_recent_messages(limit=10)
        
        # 转换为OpenAI格式
        messages = []
        for msg in recent_messages[-6:]:  # 只取最近6条消息
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })
        
        # 调用LLM
        response = self._call_llm(messages)
        return response

    def _generate_llm_with_tool_context(self, user_input: str, tool_results: dict, task_plan) -> str:
        """
        基于工具执行结果，使用LLM生成智能回复
        
        这是核心方法：确保所有回复都通过LLM生成，消耗token
        将真实API数据作为上下文传给LLM，让AI智能整合回复
        
        Args:
            user_input: 用户原始输入
            tool_results: 工具聚合结果
            task_plan: 任务计划
            
        Returns:
            LLM生成的整合回复
        """
        print("🤖 正在调用LLM生成智能回复...")
        
        # 构建工具结果的上下文（包含真实数据）
        tool_context = f"""【系统提示】你是一个专业的AI助手。现在需要你根据以下【真实数据】，用友好、专业的方式回应用户。

重要要求：
1. 必须基于提供的【真实数据】回答，不要编造信息
2. 回答要自然流畅，像真人在对话
3. 适当添加温馨提示或建议
4. 使用中文回答
5. 数据来源要明确标注

【用户原始问题】
{user_input}

【工具返回的真实数据】
"""
        
        # 添加详细的工具结果
        if tool_results.get('results'):
            for i, result in enumerate(tool_results['results'], 1):
                tool_context += f"\n--- 工具{i}执行结果 ---\n"
                tool_context += json.dumps(result, ensure_ascii=False, indent=2)
                tool_context += "\n"
        
        # 添加执行摘要
        if tool_results.get('summary'):
            summary = tool_results['summary']
            tool_context += f"\n【执行摘要】"
            tool_context += f"\n- 调用工具数: {summary.get('total_tools', 0)}"
            tool_context += f"\n- 成功: {summary.get('successful', 0)} | 失败: {summary.get('failed', 0)}"
            if tool_results.get('errors'):
                tool_context += f"\n【错误信息】\n"
                for error in tool_results['errors'][:2]:
                    tool_context += f"- [{error.get('tool', 'unknown')}] {error.get('error', '')}\n"
        
        # 判断是否有真实数据
        has_real_data = any(
            r.get('metadata', {}).get('is_real_data', False) 
            for r in tool_results.get('results', [])
        )
        
        if not has_real_data and tool_results.get('errors'):
            tool_context += "\n\n⚠️ 注意：工具调用失败，请向用户说明情况并提供建议。"
        elif has_real_data:
            tool_context += "\n\n✅ 以上数据来自真实API调用，请据此生成专业、准确的回复。"
        
        tool_context += "\n\n请直接生成回复内容（不要包含任何解释性文字）："
        
        # 调用LLM生成回复
        response = self._call_llm(
            messages=[{"role": "user", "content": user_input}],
            system_prompt=tool_context
        )
        
        print(f"✓ LLM回复生成完成 (已消耗token)")
        return response

    def _generate_safety_warning(self, safety_result) -> str:
        """生成安全警告响应"""
        warning_templates = {
            "sensitive_word": "⚠️ 您的输入包含敏感内容，请调整措辞后重新提问。",
            "injection": "🛡️ 检测到不安全的输入模式，为了安全考虑无法处理此请求。",
            "pii_detected": "🔒 为了保护隐私安全，请勿在对话中分享个人敏感信息。",
            "format_issue": "⚠️ 输入格式存在问题，请检查后重试。"
        }
        
        base_msg = warning_templates.get(
            safety_result.violation_type, 
            "⚠️ 您的输入未通过安全检查。"
        )
        
        if safety_result.suggestions:
            suggestions = "\n".join([f"   • {s}" for s in safety_result.suggestions[:2]])
            return f"{base_msg}\n\n建议:\n{suggestions}"
        
        return base_msg

    def _format_tool_response(self, aggregated: dict, task_plan) -> str:
        """格式化工具调用结果为用户友好的回复"""
        summary = aggregated["summary"]
        combined = aggregated.get("combined_output", "")
        
        # 构建结构化回复
        response_parts = []
        
        # 开头
        response_parts.append("✨ 已为您完成任务：\n")
        
        # 主要结果
        if combined:
            response_parts.append(combined)
        
        # 执行摘要
        response_parts.append(f"\n{'─'*40}")
        response_parts.append(f"📊 执行摘要:")
        response_parts.append(f"   • 调用工具数: {summary['total_tools']}")
        response_parts.append(f"   • 成功: {summary['successful']} | 失败: {summary['failed']}")
        response_parts.append(f"   • 总耗时: {summary['total_time']:.2f}秒")
        
        # 错误信息（如果有）
        if aggregated.get("errors"):
            response_parts.append(f"\n⚠️ 部分操作遇到问题:")
            for error in aggregated["errors"][:2]:
                response_parts.append(f"   • [{error['tool']}] {error['error']}")
        
        # 建议
        response_parts.append(f"\n💡 还需要其他帮助吗？随时告诉我！")
        
        return "\n".join(response_parts)

    def _generate_conversational_response(self, user_input: str, intent) -> str:
        """生成纯对话模式的回复（当不需要调用工具时）"""
        # 这里简化处理，实际应用中应调用LLM API
        # 基于意图类型生成相应的引导性回复
        
        intent_responses = {
            "unknown": (
                "您好！我是AI智能助手，很高兴为您服务。\n\n"
                "我可以帮您：\n"
                "• 🔍 查询天气、搜索信息\n"
                "• ✍️ 生成文案、邮件、总结\n"
                "• 📊 分析数据文件\n"
                "• 📅 管理日程安排\n\n"
                "请告诉我您需要什么帮助？"
            ),
            "greeting": (
                "您好！😊 很高兴见到您！\n\n"
                "今天有什么我可以帮您的吗？\n"
                "无论是查询信息、生成文档还是管理日程，我都在这里为您服务！"
            ),
            "thanks": (
                "不客气！😊 能帮到您是我的荣幸。\n\n"
                "如果还有其他问题，随时都可以问我哦～"
            )
        }
        
        # 简单的关键词匹配
        user_lower = user_input.lower().strip()
        
        if any(word in user_lower for word in ["你好", "hi", "hello", "嗨"]):
            return intent_responses["greeting"]
        elif any(word in user_lower for word in ["谢谢", "感谢", "thanks"]):
            return intent_responses["thanks"]
        else:
            # 默认回复，引导用户明确需求
            return intent_responses["unknown"]

    def handle_command(self, command: str) -> bool:
        """
        处理特殊命令
        
        Args:
            command: 命令字符串
            
        Returns:
            是否应该继续运行（False表示退出）
        """
        cmd = command.strip().lower()
        
        if cmd in ["/quit", "/exit", "/q"]:
            print("\n👋 感谢使用AI智能助手，再见！")
            self._show_session_summary()
            return False
        
        elif cmd == "/help":
            self._show_help()
        
        elif cmd == "/clear":
            self.chat_manager.clear_history()
            print("✓ 对话历史已清空，开始新的对话吧！")
        
        elif cmd == "/stats":
            self._show_statistics()
        
        elif cmd == "/export":
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"session_{timestamp}.json"
            success = self.chat_manager.export_session(filename)
            if success:
                print(f"✓ 会话已导出到: {filename}")
        
        elif cmd == "/tools":
            self._show_available_tools()
        
        elif cmd.startswith("/search "):
            query = cmd[8:].strip()
            result = self.tool_executor.execute_tool("info_query", {"query_type": "search", "keyword": query})
            print(result.to_string())
        
        else:
            print(f"❓ 未知命令: {command}")
            print("输入 /help 查看可用命令")
        
        return True

    def _show_help(self):
        """显示帮助信息"""
        help_text = """
📖 帮助信息
═══════════════════════════════

【基本用法】
直接输入文字即可与我对话交流

【支持的对话类型】
• 信息查询: "查询北京天气"、"搜索人工智能"
• 文案生成: "帮我写一封邮件"、"生成营销文案"
• 数据分析: "分析这个CSV文件"、"读取数据"
• 日程管理: "添加明天会议"、"查看我的日程"

【系统命令】
/help      显示此帮助信息
/clear     清空对话历史
/stats     查看使用统计
/tools     查看可用工具列表
/export    导出当前会话记录
/search ×  快速搜索信息
/quit      退出程序

【示例】
> 你好
> 查询上海明天的天气
> 帮我写一封请假邮件
> 分析data.csv这个文件
> 添加明天下午3点的项目会议

═══════════════════════════════
"""
        print(help_text)

    def _show_statistics(self):
        """显示使用统计"""
        stats = self.chat_manager.get_statistics()
        tool_stats = self.tool_executor.get_statistics()
        safety_stats = self.safety_filter.get_statistics()
        
        print("\n📊 使用统计报告")
        print("=" * 50)
        
        print(f"\n🗣️ 对话统计:")
        print(f"   • 总消息数: {stats['total_messages']}")
        print(f"   • 用户消息: {stats['user_messages']}")
        print(f"   • 助手回复: {stats['assistant_messages']}")
        print(f"   • 工具调用: {stats['tool_calls']}")
        print(f"   • 估算Token: {stats['estimated_tokens']}")
        
        print(f"\n🔧 工具统计:")
        print(f"   • 总执行次数: {tool_stats['total_executions']}")
        print(f"   • 成功率: {tool_stats['success_rate']:.1f}%")
        print(f"   • 注册工具数: {tool_stats['registered_tools']}")
        
        print(f"\n🛡️ 安全统计:")
        print(f"   • 总检查次数: {safety_stats['total_checks']}")
        print(f"   • 拦截次数: {safety_stats['blocked_count']}")
        print(f"   • 通过率: {safety_stats['passed_count'] / max(safety_stats['total_checks'], 1) * 100:.1f}%")
        
        session_duration = datetime.now() - self.session_stats["start_time"]
        print(f"\n⏱️ 本会话时长: {str(session_duration).split('.')[0]}")
        print("=" * 50)

    def _show_available_tools(self):
        """显示可用工具列表"""
        tools_list = self.tool_executor.list_tools()
        
        print("\n🔧 可用工具列表")
        print("=" * 50)
        
        for i, tool in enumerate(tools_list, 1):
            print(f"\n{i}. 【{tool['name']}】")
            print(f"   描述: {tool['description']}")
            if tool.get('execution_count', 0) > 0:
                print(f"   使用次数: {tool['execution_count']}")
        
        print("\n" + "=" * 50)

    def _show_session_summary(self):
        """显示会话结束摘要"""
        duration = datetime.now() - self.session_stats["start_time"]
        
        print(f"\n📋 本次会话摘要")
        print("-" * 40)
        print(f"   ⏱️ 会话时长: {str(duration).split('.')[0]}")
        print(f"   💬 交互次数: {self.session_stats['total_interactions']}")
        print(f"   ✅ 成功任务: {self.session_stats['successful_tasks']}")
        print(f"   ❌ 失败任务: {self.session_stats['failed_tasks']}")
        print("-" * 40)


def main():
    """主函数 - 程序入口点"""
    try:
        # 创建AI助手实例
        agent = AIAgent()
        
        # 主循环
        while True:
            try:
                # 获取用户输入
                user_input = input("\n👤 您: ").strip()
                
                # 检查是否为空输入
                if not user_input:
                    continue
                
                # 检查是否为命令
                if user_input.startswith("/"):
                    should_continue = agent.handle_command(user_input)
                    if not should_continue:
                        break
                    continue
                
                # 处理普通输入
                response = agent.process_input(user_input)
                
                # 显示回复
                print(f"\n🤖 助手:\n{response}")
                
            except KeyboardInterrupt:
                print("\n\n检测到中断信号...")
                break
            except Exception as e:
                print(f"\n❌ 发生错误: {e}")
                continue
    
    except Exception as e:
        print(f"\n❌ 程序启动失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
