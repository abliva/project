"""
日程管理工具
提供日程的增删查改、提醒设置、时间管理等功能
支持多种视图和智能 scheduling 能力
"""

import json
import os
import re
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.tool_executor import BaseTool, ToolResult


class TaskPriority(Enum):
    """任务优先级"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"           # 待处理
    IN_PROGRESS = "in_progress"   # 进行中
    COMPLETED = "completed"       # 已完成
    CANCELLED = "cancelled"       # 已取消
    DEFERRED = "deferred"         # 已延期


@dataclass
class ScheduleItem:
    """
    日程项数据结构
    
    表示一个具体的日程/任务/事件
    """
    id: str                          # 唯一ID
    title: str                       # 标题
    description: str = ""            # 描述详情
    start_time: str = ""             # 开始时间 (ISO格式)
    end_time: str = ""               # 结束时间 (ISO格式)
    priority: int = TaskPriority.MEDIUM.value  # 优先级(1-4)
    status: str = TaskStatus.PENDING.value     # 状态
    category: str = "general"        # 分类：work, personal, study, etc.
    tags: List[str] = field(default_factory=list)  # 标签列表
    reminder_time: str = ""          # 提醒时间
    is_recurring: bool = False       # 是否重复
    recurring_rule: str = ""         # 重复规则（如"weekly","monthly"）
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)  # 扩展元数据
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    def is_overdue(self) -> bool:
        """检查是否已过期"""
        if not self.start_time or self.status in [TaskStatus.COMPLETED.value, TaskStatus.CANCELLED.value]:
            return False
        try:
            start_dt = datetime.fromisoformat(self.start_time)
            return datetime.now() > start_dt and self.status == TaskStatus.PENDING.value
        except:
            return False
    
    def time_until(self) -> timedelta:
        """计算距离开始时间的剩余时间"""
        if not self.start_time:
            return timedelta(0)
        try:
            start_dt = datetime.fromisoformat(self.start_time)
            delta = start_dt - datetime.now()
            return max(delta, timedelta(0))
        except:
            return timedelta(0)


class SchedulerTool(BaseTool):
    """
    日程管理工具
    
    功能：
    1. 日程CRUD - 创建、读取、更新、删除日程
    2. 智能查询 - 按日期、分类、状态等条件筛选
    3. 提醒管理 - 设置和管理提醒
    4. 时间分析 - 统计时间分配和使用情况
    5. 导入导出 - 数据备份和迁移
    """
    
    # 默认存储文件路径
    DEFAULT_STORAGE_FILE = "data/schedules.json"
    
    # 操作类型定义
    OPERATIONS = {
        "create": "创建新日程",
        "read": "查询日程",
        "update": "更新日程",
        "delete": "删除日程",
        "list": "列出日程",
        "search": "搜索日程",
        "stats": "获取统计信息",
        "remind": "设置提醒",
        "complete": "标记完成"
    }
    
    # 分类定义
    CATEGORIES = {
        "work": {"name": "工作", "icon": "💼", "color": "#3498db"},
        "personal": {"name": "个人", "icon": "🏠", "color": "#e74c3c"},
        "study": {"name": "学习", "icon": "📚", "color": "#9b59b6"},
        "health": {"name": "健康", "icon": "💪", "color": "#27ae60"},
        "social": {"name": "社交", "icon": "👥", "color": "#f39c12"},
        "general": {"name": "通用", "icon": "📌", "color": "#95a5a6"}
    }

    def __init__(self, storage_file: str = None):
        """
        初始化日程管理工具
        
        Args:
            storage_file: 数据存储文件路径，默认使用DEFAULT_STORAGE_FILE
        """
        super().__init__(
            name="scheduler",
            description="日程管理工具，支持创建、查询、修改、删除日程及提醒功能"
        )
        
        self.storage_file = storage_file or self.DEFAULT_STORAGE_FILE
        self.schedules: Dict[str, ScheduleItem] = {}  # {id: ScheduleItem}
        
        # 参数模式
        self.parameters_schema = {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": list(self.OPERATIONS.keys()),
                    "description": f"操作类型: {', '.join(self.OPERATIONS.keys())}"
                },
                "schedule_id": {
                    "type": "string",
                    "description": "日程ID（用于read/update/delete等操作）"
                },
                "title": {
                    "type": "string",
                    "description": "日程标题"
                },
                "description": {
                    "type": "string",
                    "description": "日程详细描述"
                },
                "start_time": {
                    "type": "string",
                    "description": "开始时间，格式: YYYY-MM-DD HH:MM 或 ISO格式"
                },
                "end_time": {
                    "type": "string",
                    "description": "结束时间"
                },
                "priority": {
                    "type": "integer",
                    "enum": [1, 2, 3, 4],
                    "default": 2,
                    "description": "优先级: 1-低, 2-中, 3-高, 4-紧急"
                },
                "category": {
                    "type": "string",
                    "enum": list(self.CATEGORIES.keys()),
                    "default": "general",
                    "description": "日程分类"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "标签列表"
                },
                "filters": {
                    "type": "object",
                    "description": "筛选条件，如 {'status': 'pending', 'category': 'work'}"
                },
                "limit": {
                    "type": "integer",
                    "default": 20,
                    "description": "返回结果数量限制"
                }
            },
            "required": ["operation"]
        }
        
        # 加载已有数据
        self._load_data()
        
        print(f"✓ 日程管理工具初始化完成 | 已加载 {len(self.schedules)} 条日程")

    def execute(self, **kwargs) -> ToolResult:
        """
        执行日程管理操作
        
        Args:
            **kwargs: 操作参数
            
        Returns:
            操作结果
        """
        operation = kwargs.get("operation")
        
        if not operation:
            return ToolResult(
                success=False,
                tool_name=self.name,
                error_message="请指定操作类型(operation)"
            )
        
        try:
            # 路由到对应的处理方法
            handler_map = {
                "create": self._create_schedule,
                "read": self._read_schedule,
                "update": self._update_schedule,
                "delete": self._delete_schedule,
                "list": self._list_schedules,
                "search": self._search_schedules,
                "stats": self._get_statistics,
                "remind": self._set_reminder,
                "complete": self._mark_complete
            }
            
            handler = handler_map.get(operation)
            if not handler:
                return ToolResult(
                    success=False,
                    tool_name=self.name,
                    error_message=f"不支持的操作类型: {operation}"
                )
            
            result_data = handler(**kwargs)
            
            # 如果是修改操作，保存数据
            if operation in ["create", "update", "delete", "complete"]:
                self._save_data()
            
            return ToolResult(
                success=True,
                tool_name=self.name,
                result_data=result_data,
                metadata={"operation": operation}
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                tool_name=self.name,
                error_message=f"操作执行失败: {str(e)}"
            )

    def _generate_id(self) -> str:
        """生成唯一ID"""
        import uuid
        return f"sched_{uuid.uuid4().hex[:8]}"

    def _parse_time(self, time_str: str) -> str:
        """
        解析并标准化时间字符串
        
        支持多种格式的输入：
        - "2024-01-15 14:30"
        - "明天下午3点"
        - "下周一上午"
        - ISO格式
        """
        if not time_str:
            return ""
        
        # 尝试直接解析为ISO格式
        try:
            dt = datetime.fromisoformat(time_str)
            return dt.isoformat()
        except:
            pass
        
        # 尝试解析常见中文表达
        now = datetime.now()
        
        # 相对时间关键词
        relative_map = {
            "今天": now,
            "明天": now + timedelta(days=1),
            "后天": now + timedelta(days=2),
            "昨天": now - timedelta(days=1)
        }
        
        for keyword, base_date in relative_map.items():
            if keyword in time_str:
                remaining = time_str.replace(keyword, "").strip()
                
                # 解析时段
                hour = 12  # 默认中午
                if "上午" in remaining or "早上" in remaining:
                    hour = 9
                elif "下午" in remaining:
                    hour = 14
                elif "晚上" in remaining:
                    hour = 19
                
                # 尝试提取具体小时
                time_match = re.search(r'(\d+)[点时:：](\d*)', remaining)
                if time_match:
                    hour = int(time_match.group(1))
                    minute = int(time_match.group(2)) if time_match.group(2) else 0
                else:
                    minute = 0
                
                target_dt = base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                return target_dt.isoformat()
        
        # 尝试解析标准日期格式
        date_patterns = [
            r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})[日]?\s*(\d{1,2})?[点时:：]?(\d{2})?',
            r'(\d{1,2})[-/月](\d{1,2})[日]?\s*(\d{1,2})?[点时:：]?(\d{2})?'
        ]
        
        for pattern in date_patterns:
            match = re.match(pattern, time_str.strip())
            if match:
                groups = match.groups()
                try:
                    if len(groups) >= 3 and groups[0]:  # 完整日期
                        year = int(groups[0]) if len(groups[0]) == 4 else now.year
                        month = int(groups[1])
                        day = int(groups[2])
                        hour = int(groups[3]) if groups[3] and len(str(int(groups[3]))) <= 2 else 12
                        minute = int(groups[4]) if groups[4] else 0
                        
                        dt = datetime(year=year, month=month, day=day, 
                                     hour=hour, minute=minute)
                        return dt.isoformat()
                except (ValueError, IndexError):
                    continue
        
        # 无法解析则返回原始字符串
        print(f"⚠ 无法完全解析时间: {time_str}，将使用原始值")
        return time_str

    def _create_schedule(self, **kwargs) -> Dict[str, Any]:
        """创建新日程"""
        title = kwargs.get("title")
        if not title:
            raise ValueError("创建日程必须提供标题(title)")
        
        schedule_id = self._generate_id()
        
        # 创建日程对象
        schedule = ScheduleItem(
            id=schedule_id,
            title=title,
            description=kwargs.get("description", ""),
            start_time=self._parse_time(kwargs.get("start_time", "")),
            end_time=self._parse_time(kwargs.get("end_time", "")),
            priority=kwargs.get("priority", 2),
            category=kwargs.get("category", "general"),
            tags=kwargs.get("tags", [])
        )
        
        # 存储日程
        self.schedules[schedule_id] = schedule
        
        output = f"""✅ 日程已成功创建！

📋 日程信息：
━━━━━━━━━━━━━━━━━━
🆔 ID: {schedule_id}
📌 标题: {schedule.title}
📝 描述: {schedule.description or '(无)'}
⏰ 时间: {schedule.start_time or '未设定'}
⏱️ 结束: {schedule.end_time or '未设定'}
🎯 优先级: {'⭐⭐⭐⭐ 紧急' if schedule.priority == 4 else '⭐⭐⭐ 高' if schedule.priority == 3 else '⭐⭐ 中' if schedule.priority == 2 else '⭐ 低'}
📂 分类: {self.CATEGORIES.get(schedule.category, {}).get('name', schedule.category)}
🏷️ 标签: {', '.join(schedule.tags) if schedule.tags else '(无)'}
🕐 创建时间: {schedule.created_at[:16]}
━━━━━━━━━━━━━━━━━━"""
        
        return {
            "operation": "create",
            "success": True,
            "schedule": schedule.to_dict(),
            "message": output
        }

    def _read_schedule(self, **kwargs) -> Dict[str, Any]:
        """读取单个日程"""
        schedule_id = kwargs.get("schedule_id")
        
        if not schedule_id:
            raise ValueError("请提供日程ID(schedule_id)")
        
        schedule = self.schedules.get(schedule_id)
        if not schedule:
            raise ValueError(f"日程不存在: {schedule_id}")
        
        # 计算附加信息
        is_overdue = schedule.is_overdue()
        time_left = schedule.time_until()
        
        output = f"""📋 日程详情
{'='*40}

🆔 ID: {schedule.id}
📌 标题: {schedule.title}
📝 描述: {schedule.description or '(无)'}

⏰ 时间安排:
   开始: {schedule.start_time or '未设定'}
   结束: {schedule.end_time or '未设定'}

📊 状态信息:
   当前状态: {self._status_emoji(schedule.status)} {schedule.status}
   优先级: {self._priority_text(schedule.priority)}
   分类: {self.CATEGORIES.get(schedule.category, {}).get('name', schedule.category)}
   
{'⚠️ 该日程已逾期！' if is_overdue else ''}{'⏳ 剩余时间: ' + str(time_left).split('.')[0] if time_left.total_seconds() > 0 and schedule.start_time else ''}

🏷️ 标签: {', '.join(schedule.tags) if schedule.tags else '(无)'}

📅 时间戳:
   创建: {schedule.created_at[:16]}
   更新: {schedule.updated_at[:16]}
{'='*40}"""
        
        return {
            "operation": "read",
            "schedule": schedule.to_dict(),
            "is_overdue": is_overdue,
            "time_remaining": str(time_left).split('.')[0],
            "formatted_output": output
        }

    def _update_schedule(self, **kwargs) -> Dict[str, Any]:
        """更新日程"""
        schedule_id = kwargs.get("schedule_id")
        
        if not schedule_id:
            raise ValueError("请提供日程ID(schedule_id)")
        
        schedule = self.schedules.get(schedule_id)
        if not schedule:
            raise ValueError(f"日程不存在: {schedule_id}")
        
        # 更新提供的字段
        update_fields = ['title', 'description', 'start_time', 'end_time', 
                        'priority', 'category', 'tags']
        
        updated_fields = []
        for field_name in update_fields:
            value = kwargs.get(field_name)
            if value is not None:
                if field_name in ['start_time', 'end_time']:
                    value = self._parse_time(value)
                setattr(schedule, field_name, value)
                updated_fields.append(field_name)
        
        # 更新时间戳
        schedule.updated_at = datetime.now().isoformat()
        
        output = f"""✅ 日程已更新！

📌 日程ID: {schedule_id}
✏️ 更新的字段: {', '.join(updated_fields)}
🔄 更新时间: {schedule.updated_at[:16]}

📋 更新后的日程:
   标题: {schedule.title}
   时间: {schedule.start_time or '未设定'}
   优先级: {self._priority_text(schedule.priority)}"""
        
        return {
            "operation": "update",
            "success": True,
            "updated_fields": updated_fields,
            "schedule": schedule.to_dict(),
            "message": output
        }

    def _delete_schedule(self, **kwargs) -> Dict[str, Any]:
        """删除日程"""
        schedule_id = kwargs.get("schedule_id")
        
        if not schedule_id:
            raise ValueError("请提供日程ID(schedule_id)")
        
        if schedule_id not in self.schedules:
            raise ValueError(f"日程不存在: {schedule_id}")
        
        deleted_schedule = self.schedules.pop(schedule_id)
        
        return {
            "operation": "delete",
            "success": True,
            "deleted_id": schedule_id,
            "deleted_title": deleted_schedule.title,
            "message": f"🗑️ 日程已删除: [{deleted_schedule.title}] (ID: {schedule_id})"
        }

    def _list_schedules(self, **kwargs) -> Dict[str, Any]:
        """列出日程"""
        limit = kwargs.get("limit", 20)
        filters = kwargs.get("filters", {})
        
        # 应用过滤器
        filtered_schedules = self._apply_filters(filters)
        
        # 排序（按优先级和时间）
        sorted_schedules = sorted(
            filtered_schedules.values(),
            key=lambda x: (-x.priority, x.start_time or '9999')
        )
        
        # 限制数量
        displayed = sorted_schedules[:limit]
        
        # 格式化输出
        output_lines = [f"📅 日程列表 (共{len(filtered_schedules)}条, 显示前{len(displayed)}条)\n"]
        output_lines.append("=" * 50 + "\n")
        
        for i, sched in enumerate(displayed, 1):
            status_icon = self._status_emoji(sched.status)
            priority_icon = self._priority_emoji(sched.priority)
            category_info = self.CATEGORIES.get(sched.category, {})
            
            time_display = sched.start_time[:16] if sched.start_time else "未设定"
            
            overdue_warning = " ⚠️逾期" if sched.is_overdue() else ""
            
            line = f"{i}. {status_icon} {priority_icon} {sched.title}"
            line += f"\n   📂 {category_info.get('name', sched.category)}"
            line += f" | ⏰ {time_display}{overdue_warning}"
            
            if sched.tags:
                line += f"\n   🏷️ {', '.join(sched.tags[:3])}"
            
            output_lines.append(line + "\n")
        
        if not displayed:
            output_lines.append("暂无符合条件的日程\n")
        
        return {
            "operation": "list",
            "total_count": len(filtered_schedules),
            "displayed_count": len(displayed),
            "schedules": [s.to_dict() for s in displayed],
            "formatted_output": "\n".join(output_lines)
        }

    def _search_schedules(self, **kwargs) -> Dict[str, Any]:
        """搜索日程"""
        query = kwargs.get("query", kwargs.get("title", ""))
        limit = kwargs.get("limit", 10)
        
        if not query:
            raise ValueError("请提供搜索关键词(query或title)")
        
        results = []
        query_lower = query.lower()
        
        for schedule in self.schedules.values():
            # 在标题、描述、标签中搜索
            searchable_text = f"{schedule.title} {schedule.description} {' '.join(schedule.tags)}".lower()
            
            if query_lower in searchable_text:
                # 计算相关度分数（简单实现）
                score = 0
                if query_lower in schedule.title.lower():
                    score += 10
                if query_lower in schedule.description.lower():
                    score += 5
                if any(query_lower in tag.lower() for tag in schedule.tags):
                    score += 3
                
                results.append((score, schedule))
        
        # 按相关度排序
        results.sort(key=lambda x: x[0], reverse=True)
        top_results = [r[1] for r in results[:limit]]
        
        output_lines = [f"🔍 搜索结果: \"{query}\" (找到{len(results)}条匹配)\n"]
        
        for i, sched in enumerate(top_results, 1):
            output_lines.append(f"{i}. {sched.title}")
            output_lines.append(f"   📝 {sched.description[:80]}..." if len(sched.description) > 80 else f"   📝 {sched.description}")
            output_lines.append("")
        
        if not top_results:
            output_lines.append("未找到匹配的日程\n")
        
        return {
            "operation": "search",
            "query": query,
            "total_matches": len(results),
            "results": [s.to_dict() for s in top_results],
            "formatted_output": "\n".join(output_lines)
        }

    def _get_statistics(self, **kwargs) -> Dict[str, Any]:
        """获取统计信息"""
        total = len(self.schedules)
        
        if total == 0:
            return {
                "operation": "stats",
                "statistics": {
                    "total_schedules": 0,
                    "message": "暂无日程数据"
                }
            }
        
        # 按状态统计
        by_status = {}
        for s in self.schedules.values():
            status = s.status
            by_status[status] = by_status.get(status, 0) + 1
        
        # 按分类统计
        by_category = {}
        for s in self.schedules.values():
            cat = s.category
            by_category[cat] = by_category.get(cat, 0) + 1
        
        # 按优先级统计
        by_priority = {}
        for s in self.schedules.values():
            p = s.priority
            by_priority[p] = by_priority.get(p, 0) + 1
        
        # 逾期统计
        overdue_count = sum(1 for s in self.schedules.values() if s.is_overdue())
        
        # 今日日程
        today = datetime.now().strftime("%Y-%m-%d")
        today_count = sum(
            1 for s in self.schedules.values() 
            if s.start_time and s.start_time.startswith(today)
        )
        
        # 本周完成率
        week_ago = datetime.now() - timedelta(days=7)
        recent_completed = sum(
            1 for s in self.schedules.values() 
            if s.status == "completed" and s.updated_at >= week_ago.isoformat()
        )
        recent_total = sum(
            1 for s in self.schedules.values() 
            if s.created_at >= week_ago.isoformat()
        )
        completion_rate = (recent_completed / recent_total * 100) if recent_total > 0 else 0
        
        stats = {
            "total_schedules": total,
            "by_status": by_status,
            "by_category": by_category,
            "by_priority": by_priority,
            "overdue_count": overdue_count,
            "today_count": today_count,
            "week_completion_rate": round(completion_rate, 1)
        }
        
        # 格式化输出
        output = f"""📊 日程统计分析报告
{'='*45}

📈 总体概况
─────────────
• 总日程数: {total}
• 今日日程: {today_count}
• 逾期数量: {overdue_count} {'⚠️' if overdue_count > 0 else ''}
• 本周完成率: {completion_rate:.1f}%

📊 状态分布
─────────────"""
        
        status_icons = {
            "pending": "⏳ 待处理",
            "in_progress": "🔧 进行中",
            "completed": "✅ 已完成",
            "cancelled": "❌ 已取消",
            "deferred": "⏸️ 已延期"
        }
        
        for status, count in sorted(by_status.items()):
            icon_text = status_icons.get(status, status)
            pct = count / total * 100
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            output += f"\n  {icon_text}: {count:3d} ({pct:5.1f}%) {bar}"
        
        output += f"""
📂 分类分布
─────────────"""
        
        for cat, count in sorted(by_category.items(), key=lambda x: -x[1]):
            cat_name = self.CATEGORIES.get(cat, {}).get('name', cat)
            icon = self.CATEGORIES.get(cat, {}).get('icon', '📌')
            output += f"\n  {icon} {cat_name}: {count}"
        
        output += f"""
🎯 优先级分布
─────────────"""
        
        priority_labels = {1: "低", 2: "中", 3: "高", 4: "紧急"}
        for p in sorted(by_priority.keys(), reverse=True):
            label = priority_labels.get(p, str(p))
            stars = "⭐" * p
            output += f"\n  {stars} {label}({p}): {by_priority[p]}"
        
        output += f"\n{'='*45}"
        
        return {
            "operation": "stats",
            "statistics": stats,
            "formatted_output": output
        }

    def _set_reminder(self, **kwargs) -> Dict[str, Any]:
        """设置提醒"""
        schedule_id = kwargs.get("schedule_id")
        reminder_time = kwargs.get("reminder_time", "")
        
        if not schedule_id:
            raise ValueError("请提供日程ID(schedule_id)")
        
        schedule = self.schedules.get(schedule_id)
        if not schedule:
            raise ValueError(f"日程不存在: {schedule_id}")
        
        # 解析提醒时间
        parsed_reminder = self._parse_time(reminder_time) if reminder_time else ""
        
        schedule.reminder_time = parsed_reminder
        schedule.updated_at = datetime.now().isoformat()
        
        return {
            "operation": "remind",
            "success": True,
            "schedule_id": schedule_id,
            "reminder_time": parsed_reminder or "未设定",
            "message": f"⏰ 已为日程「{schedule.title}」设置提醒: {parsed_reminder or '使用默认提醒'}"
        }

    def _mark_complete(self, **kwargs) -> Dict[str, Any]:
        """标记日程为已完成"""
        schedule_id = kwargs.get("schedule_id")
        
        if not schedule_id:
            raise ValueError("请提供日程ID(schedule_id)")
        
        schedule = self.schedules.get(schedule_id)
        if not schedule:
            raise ValueError(f"日程不存在: {schedule_id}")
        
        old_status = schedule.status
        schedule.status = TaskStatus.COMPLETED.value
        schedule.updated_at = datetime.now().isoformat()
        
        return {
            "operation": "complete",
            "success": True,
            "schedule_id": schedule_id,
            "old_status": old_status,
            "new_status": schedule.status,
            "message": f"✅ 日程「{schedule.title}」已标记为完成！"
        }

    def _apply_filters(self, filters: Dict[str, Any]) -> Dict[str, ScheduleItem]:
        """应用过滤条件"""
        if not filters:
            return self.schedules
        
        filtered = {}
        
        for sid, schedule in self.schedules.items():
            include = True
            
            for key, value in filters.items():
                if key == "status" and schedule.status != value:
                    include = False
                elif key == "category" and schedule.category != value:
                    include = False
                elif key == "priority" and schedule.priority != value:
                    include = False
                elif key == "is_overdue" and not schedule.is_overdue():
                    include = False
                elif key == "has_tag" and value not in schedule.tags:
                    include = False
            
            if include:
                filtered[sid] = schedule
        
        return filtered

    def _status_emoji(self, status: str) -> str:
        """状态图标映射"""
        emoji_map = {
            "pending": "⏳",
            "in_progress": "🔧",
            "completed": "✅",
            "cancelled": "❌",
            "deferred": "⏸️"
        }
        return emoji_map.get(status, "❓")

    def _priority_emoji(self, priority: int) -> str:
        """优先级图标"""
        emoji_map = {1: "🟢", 2: "🟡", 3: "🟠", 4: "🔴"}
        return emoji_map.get(priority, "⚪")

    def _priority_text(self, priority: int) -> str:
        """优先级文字"""
        text_map = {
            1: "⭐ 低优先级",
            2: "⭐⭐ 中优先级",
            3: "⭐⭐⭐ 高优先级",
            4: "⭐⭐⭐⭐ 紧急"
        }
        return text_map.get(priority, "未知")

    def _load_data(self):
        """从文件加载数据"""
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for item_data in data.get("schedules", []):
                    schedule = ScheduleItem(**item_data)
                    self.schedules[schedule.id] = schedule
                
                print(f"  从文件加载了 {len(self.schedules)} 条日程记录")
                
            except Exception as e:
                print(f"  ⚠ 加载数据文件失败: {e}")

    def _save_data(self):
        """保存数据到文件"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
            
            data = {
                "version": "1.0",
                "last_updated": datetime.now().isoformat(),
                "total_count": len(self.schedules),
                "schedules": [s.to_dict() for s in self.schedules.values()]
            }
            
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
        except Exception as e:
            print(f"  ❌ 保存数据失败: {e}")

    def export_data(self, filepath: str) -> bool:
        """导出数据到指定文件"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    "export_time": datetime.now().isoformat(),
                    "schedules": [s.to_dict() for s in self.schedules.values()]
                }, f, ensure_ascii=False, indent=2)
            print(f"✓ 日程数据已导出到: {filepath}")
            return True
        except Exception as e:
            print(f"❌ 导出失败: {e}")
            return False


if __name__ == "__main__":
    # 测试日程管理工具
    scheduler = SchedulerTool(storage_file="test_schedules.json")
    
    print("\n===== 测试日程管理工具 =====\n")
    
    # 测试创建日程
    print("1. 创建测试日程:")
    result = scheduler.execute(
        operation="create",
        title="项目周会",
        description="讨论本周项目进度和下周计划",
        start_time="2024-01-20 14:00",
        end_time="2024-01-20 15:30",
        priority=3,
        category="work",
        tags=["会议", "周会", "重要"]
    )
    print(result.result_data["message"])
    
    # 测试再创建几个
    test_schedules = [
        {"title": "健身锻炼", "start_time": "明天晚上7点", "category": "health", "priority": 2},
        {"title": "学习Python", "start_time=": "后天下午", "category": "study", "priority": 2},
        {"title": "提交报告", "start_time": "2024-01-22 09:00", "category": "work", "priority": 4}
    ]
    
    for params in test_schedules:
        scheduler.execute(operation="create", **params)
    
    # 测试列出日程
    print("\n2. 列出所有日程:")
    result = scheduler.execute(operation="list")
    print(result.result_data["formatted_output"][:800])
    
    # 测试统计
    print("\n3. 查看统计:")
    result = scheduler.execute(operation="stats")
    print(result.result_data["formatted_output"])
    
    # 清理测试文件
    if os.path.exists("test_schedules.json"):
        os.remove("test_schedules.json")
        if os.path.exists("data"):
            import shutil
            shutil.rmtree("data", ignore_errors=True)
        print("\n✓ 测试文件已清理")
