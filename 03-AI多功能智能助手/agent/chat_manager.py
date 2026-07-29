"""
多轮对话管理器
负责维护对话历史、上下文窗口管理、会话摘要等功能
支持多轮对话的上下文保持和智能截断
"""

import json
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import os
import sys

# 添加父目录到路径以导入配置
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import chat_config


@dataclass
class Message:
    """消息数据类"""
    role: str  # 'system', 'user', 'assistant', 'tool'
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    message_id: str = field(default="")
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """初始化消息ID"""
        if not self.message_id:
            # 使用内容哈希生成唯一ID
            content_hash = hashlib.md5(
                f"{self.role}{self.content}{self.timestamp}".encode()
            ).hexdigest()[:12]
            self.message_id = f"msg_{content_hash}"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "message_id": self.message_id,
            "metadata": self.metadata
        }


class ChatManager:
    """
    多轮对话管理器

    功能：
    1. 维护对话历史记录
    2. 管理上下文窗口（滑动窗口机制）
    3. 自动生成会话摘要
    4. 支持多会话管理
    """

    def __init__(self, session_id: str = "default"):
        """
        初始化对话管理器

        Args:
            session_id: 会话ID，用于区分不同对话会话
        """
        self.session_id = session_id
        # 消息历史列表
        self.messages: List[Message] = []
        # 会话摘要
        self.session_summary: str = ""
        # 摘要更新时间
        self.last_summary_time: Optional[datetime] = None
        # 当前上下文token数估算
        self.current_token_count: int = 0
        # 系统提示词
        self.system_prompt: str = self._load_system_prompt()

        print(f"✓ 对话管理器初始化完成 | 会话ID: {session_id}")

    def _load_system_prompt(self) -> str:
        """
        从文件加载系统提示词

        Returns:
            系统提示词字符串
        """
        prompt_file = chat_config.system_prompt_file
        if os.path.exists(prompt_file):
            try:
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                print(f"⚠ 加载系统提示词失败: {e}")
                return self._get_default_system_prompt()
        else:
            print(f"⚠ 系统提示词文件不存在: {prompt_file}，使用默认提示词")
            return self._get_default_system_prompt()

    def _get_default_system_prompt(self) -> str:
        """获取默认系统提示词"""
        return """你是一个多功能AI智能助手，具备以下能力：

1. **信息查询**：可以查询天气、搜索信息等
2. **文案生成**：可以生成营销文案、邮件、总结等文本
3. **数据分析**：可以读取和分析CSV/JSON等数据文件
4. **日程管理**：可以帮助用户管理日程和提醒

请根据用户的需求，选择合适的工具来完成任务。如果需要调用工具，请明确说明。
回答时要简洁、专业、有帮助性。"""

    def add_message(self, role: str, content: str, **metadata) -> Message:
        """
        添加消息到对话历史

        Args:
            role: 消息角色 ('user', 'assistant', 'system', 'tool')
            content: 消息内容
            metadata: 额外的元数据

        Returns:
            创建的消息对象
        """
        message = Message(role=role, content=content, **metadata)
        self.messages.append(message)

        # 更新token计数（简单估算：每个字符约0.5个token）
        estimated_tokens = len(content) // 2
        self.current_token_count += estimated_tokens

        # 检查是否需要触发摘要
        if chat_config.enable_summary and len(self.messages) >= chat_config.summary_threshold:
            self._check_and_summarize()

        # 检查是否超出上下文窗口限制
        if self.current_token_count > chat_config.context_window_size:
            self._trim_context()

        return message

    def get_context_messages(self, include_system: bool = True) -> List[Dict[str, str]]:
        """
        获取用于LLM调用的上下文消息列表

        Args:
            include_system: 是否包含系统提示词

        Returns:
            格式化后的消息列表，符合OpenAI API格式
        """
        messages = []

        # 添加系统提示词
        if include_system:
            system_content = self.system_prompt
            if self.session_summary:
                system_content += f"\n\n【会话摘要】\n{self.session_summary}"
            messages.append({"role": "system", "content": system_content})

        # 添加历史消息
        for msg in self.messages:
            messages.append({
                "role": msg.role,
                "content": msg.content
            })

        return messages

    def _check_and_summarize(self):
        """检查并执行会话摘要"""
        if not chat_config.enable_summary:
            return

        # 距离上次摘要时间超过阈值或首次摘要
        should_summarize = (
            self.last_summary_time is None or
            len(self.messages) >= chat_config.summary_threshold * 1.5
        )

        if should_summarize:
            self._generate_summary()

    def _generate_summary(self):
        """
        生成会话摘要
        将较长的对话历史压缩为关键信息摘要
        """
        if len(self.messages) < 5:
            return

        try:
            # 收集最近的对话内容用于生成摘要
            recent_messages = self.messages[-chat_config.summary_threshold:]
            conversation_text = "\n".join([
                f"{msg.role}: {msg.content[:200]}"  # 截断长消息
                for msg in recent_messages
            ])

            # 这里简化处理：实际应用中应该调用LLM生成摘要
            # 当前使用简单的关键词提取方式
            summary_parts = []
            user_msgs = [m.content for m in recent_messages if m.role == "user"]
            assistant_msgs = [m.content for m in recent_messages if m.role == "assistant"]

            if user_msgs:
                summary_parts.append(f"用户提出了{len(user_msgs)}个问题")
            if assistant_msgs:
                summary_parts.append(f"助手进行了{len(assistant_msgs)}次回复")

            # 提取主要话题
            topics = set()
            for msg in user_msgs[:3]:
                # 简单提取前20个字符作为话题标识
                topic = msg[:30].replace("\n", " ")
                topics.add(topic)

            if topics:
                summary_parts.append(f"主要话题包括: {'; '.join(list(topics)[:3])}")

            self.session_summary = " | ".join(summary_parts)
            self.last_summary_time = datetime.now()

            print(f"💡 已更新会话摘要: {self.session_summary[:100]}...")

        except Exception as e:
            print(f"⚠ 生成摘要失败: {e}")

    def _trim_context(self):
        """
        修剪上下文窗口
        当超出最大token限制时，移除最早的消息
        保留系统消息和最近的消息
        """
        if len(self.messages) <= chat_config.max_history_messages:
            return

        # 计算需要移除的消息数量
        excess_tokens = self.current_token_count - chat_config.context_window_size
        tokens_to_remove = excess_tokens + (chat_config.context_window_size // 4)  # 多移除25%作为缓冲

        removed_count = 0
        while self.messages and tokens_to_remove > 0 and len(self.messages) > chat_config.max_history_messages // 2:
            oldest_msg = self.messages.pop(0)
            removed_tokens = len(oldest_msg.content) // 2
            tokens_to_remove -= removed_tokens
            self.current_token_count -= removed_tokens
            removed_count += 1

        if removed_count > 0:
            print(f"📝 上下文窗口已修剪，移除了{removed_count}条早期消息")

    def get_chat_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取聊天历史记录

        Args:
            limit: 返回的最大消息数

        Returns:
            消息字典列表
        """
        history = [msg.to_dict() for msg in self.messages[-limit:]]
        return history

    def get_recent_messages(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取最近的消息（用于LLM调用）

        Args:
            limit: 返回的最大消息数

        Returns:
            消息字典列表（仅包含role和content）
        """
        recent = []
        for msg in self.messages[-limit:]:
            recent.append({
                "role": msg.role,
                "content": msg.content
            })
        return recent

    def clear_history(self):
        """清空对话历史"""
        self.messages.clear()
        self.current_token_count = 0
        self.session_summary = ""
        self.last_summary_time = None
        print("🗑️ 对话历史已清空")

    def export_session(self, filepath: str) -> bool:
        """
        导出会话记录到文件

        Args:
            filepath: 导出文件路径

        Returns:
            是否导出成功
        """
        try:
            session_data = {
                "session_id": self.session_id,
                "export_time": datetime.now().isoformat(),
                "summary": self.session_summary,
                "message_count": len(self.messages),
                "messages": [msg.to_dict() for msg in self.messages]
            }

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)

            print(f"✓ 会话已导出到: {filepath}")
            return True

        except Exception as e:
            print(f"❌ 导出会话失败: {e}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取会话统计信息

        Returns:
            统计信息字典
        """
        user_msg_count = len([m for m in self.messages if m.role == "user"])
        assistant_msg_count = len([m for m in self.messages if m.role == "assistant"])
        tool_msg_count = len([m for m in self.messages if m.role == "tool"])

        return {
            "session_id": self.session_id,
            "total_messages": len(self.messages),
            "user_messages": user_msg_count,
            "assistant_messages": assistant_msg_count,
            "tool_calls": tool_msg_count,
            "estimated_tokens": self.current_token_count,
            "has_summary": bool(self.session_summary),
            "summary_length": len(self.session_summary),
            "created_at": self.messages[0].timestamp if self.messages else None
        }

    def __len__(self) -> int:
        """返回消息数量"""
        return len(self.messages)

    def __repr__(self) -> str:
        return f"ChatManager(session='{self.session_id}', messages={len(self.messages)})"


if __name__ == "__main__":
    # 测试对话管理器
    manager = ChatManager(session_id="test_session")

    # 添加测试消息
    manager.add_message("user", "你好，我想查询一下北京的天气")
    manager.add_message("assistant", "好的，我来帮您查询北京今天的天气情况...")
    manager.add_message("user", "另外帮我写一封邮件")

    # 获取上下文
    context = manager.get_context_messages()
    print(f"\n当前上下文包含 {len(context)} 条消息")

    # 查看统计信息
    stats = manager.get_statistics()
    print(f"\n会话统计:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))
