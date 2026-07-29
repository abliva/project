"""
任务规划器
负责用户意图识别、任务拆解、子任务依赖排序等功能
将复杂用户需求分解为可执行的子任务链
"""

import re
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class TaskType(Enum):
    """任务类型枚举"""
    INFO_QUERY = "info_query"           # 信息查询
    TEXT_GENERATION = "text_generator"  # 文案生成
    DATA_ANALYSIS = "data_analyzer"     # 数据分析
    SCHEDULING = "scheduler"            # 日程管理
    COMPLEX = "complex"                 # 复合任务（需要多个工具）
    UNKNOWN = "unknown"                 # 未知类型


class TaskPriority(Enum):
    """任务优先级"""
    HIGH = "high"      # 高优先级
    MEDIUM = "medium"  # 中优先级
    LOW = "low"        # 低优先级


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"       # 待执行
    IN_PROGRESS = "in_progress"  # 执行中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 执行失败
    SKIPPED = "skipped"       # 已跳过


@dataclass
class SubTask:
    """
    子任务数据类

    表示从主任务拆解出的单个可执行步骤
    """
    task_id: str
    task_type: TaskType
    description: str
    tool_name: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    dependencies: List[str] = field(default_factory=list)  # 依赖的其他任务ID
    result: Any = None
    error_message: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "description": self.description,
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "priority": self.priority.value,
            "status": self.status.value,
            "dependencies": self.dependencies,
            "result": str(self.result) if self.result else None,
            "error_message": self.error_message,
            "created_at": self.created_at
        }


@dataclass
class TaskPlan:
    """
    任务计划

    包含完整的任务拆解结果和执行计划
    """
    plan_id: str
    user_intent: str                    # 用户原始意图
    main_task: str                      # 主任务描述
    sub_tasks: List[SubTask] = field(default_factory=list)  # 子任务列表
    execution_order: List[str] = field(default_factory=list)  # 执行顺序（考虑依赖）
    estimated_steps: int = 0             # 预估步骤数
    requires_tools: List[str] = field(default_factory=list)  # 需要的工具列表
    confidence_score: float = 0.0        # 意图识别置信度
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "plan_id": self.plan_id,
            "user_intent": self.user_intent,
            "main_task": self.main_task,
            "sub_task_count": len(self.sub_tasks),
            "sub_tasks": [st.to_dict() for st in self.sub_tasks],
            "execution_order": self.execution_order,
            "estimated_steps": self.estimated_steps,
            "requires_tools": self.requires_tools,
            "confidence_score": self.confidence_score,
            "created_at": self.created_at
        }


class TaskPlanner:
    """
    任务规划器

    核心功能：
    1. 用户意图识别与分类
    2. 复杂任务自动拆解为子任务链
    3. 子任务依赖关系分析与排序
    4. 执行计划生成与优化
    """

    # 意图识别关键词映射
    INTENT_KEYWORDS = {
        TaskType.INFO_QUERY: [
            "查询", "搜索", "天气", "温度", "湿度", "新闻",
            "天气如何", "怎么样了", "了解", "告诉我关于"
        ],
        TaskType.TEXT_GENERATION: [
            "写", "生成", "创作", "撰写", "编写", "起草",
            "文案", "邮件", "总结", "摘要", "报告", "文章",
            "帮我写", "请写", "生成一份"
        ],
        TaskType.DATA_ANALYSIS: [
            "分析", "解读", "统计", "数据", "图表", "CSV",
            "JSON", "Excel", "文件", "读取", "计算", "趋势"
        ],
        TaskType.SCHEDULING: [
            "日程", "提醒", "安排", "会议", "计划", "预约",
            "待办", "事项", "添加", "删除", "修改", "查看日程"
        ]
    }

    def __init__(self):
        """初始化任务规划器"""
        self.plan_history: List[TaskPlan] = []
        self._plan_counter = 0
        print("✓ 任务规划器初始化完成")

    def analyze_intent(self, user_input: str) -> Tuple[TaskType, float]:
        """
        分析用户输入，识别意图类型

        Args:
            user_input: 用户输入文本

        Returns:
            (任务类型, 置信度分数) 元组
        """
        user_input_lower = user_input.lower()
        scores = {}

        # 计算每种意图类型的匹配得分
        for task_type, keywords in self.INTENT_KEYWORDS.items():
            score = 0
            for keyword in keywords:
                if keyword in user_input_lower:
                    # 关键词越长，权重越高
                    score += len(keyword) * 2
                    # 完全匹配额外加分
                    if keyword == user_input_lower.strip():
                        score += 10
            scores[task_type] = score

        # 找出最高分的意图类型
        if not any(scores.values()):
            return TaskType.UNKNOWN, 0.0

        best_type = max(scores.keys(), key=lambda k: scores[k])
        best_score = scores[best_type]

        # 归一化置信度分数 (0-1)
        max_possible_score = sum(len(kw) * 2 for kw in self.INTENT_KEYWORDS.get(best_type, []))
        confidence = min(best_score / max(max_possible_score, 1), 1.0)

        return best_type, confidence

    def decompose_task(self, user_input: str, intent: TaskType, confidence: float) -> TaskPlan:
        """
        将用户输入拆解为可执行的子任务链

        Args:
            user_input: 用户原始输入
            intent: 识别出的意图类型
            confidence: 意图识别置信度

        Returns:
            完整的任务计划对象
        """
        self._plan_counter += 1
        plan_id = f"plan_{self._plan_counter:04d}"

        # 创建基础任务计划
        plan = TaskPlan(
            plan_id=plan_id,
            user_intent=user_input,
            main_task=self._extract_main_task(user_input),
            confidence_score=confidence
        )

        # 根据意图类型进行不同的任务拆解策略
        if intent == TaskType.COMPLEX or self._is_complex_request(user_input):
            # 复合任务：需要多个工具协作
            sub_tasks = self._decompose_complex_task(user_input)
        else:
            # 简单任务：单一工具即可完成
            sub_tasks = self._create_simple_task(user_input, intent)

        plan.sub_tasks = sub_tasks
        plan.estimated_steps = len(sub_tasks)
        plan.requires_tools = list(set(st.tool_name for st in sub_tasks))

        # 分析依赖关系并确定执行顺序
        plan.execution_order = self._resolve_dependencies(sub_tasks)

        # 保存到历史记录
        self.plan_history.append(plan)

        print(f"✓ 任务已拆解 | 计划ID: {plan_id} | 子任务数: {len(sub_tasks)}")
        return plan

    def _extract_main_task(self, user_input: str) -> str:
        """提取主要任务描述"""
        # 移除多余的空白字符
        task = " ".join(user_input.split())
        # 截断过长的描述
        if len(task) > 100:
            task = task[:100] + "..."
        return task

    def _is_complex_request(self, user_input: str) -> bool:
        """
        判断是否为复杂请求（需要多个工具）

        复杂请求的特征：
        - 包含多个不同类型的意图关键词
        - 使用连接词（并且、然后、还要等）
        - 明确提到多个操作
        """
        complex_indicators = ["并且", "然后", "还要", "另外", "同时", "之后", "接着"]
        indicator_count = sum(1 for ind in complex_indicators if ind in user_input)

        # 统计匹配到的意图类型数量
        matched_types = set()
        for task_type, keywords in self.INTENT_KEYWORDS.items():
            for kw in keywords:
                if kw in user_input:
                    matched_types.add(task_type)
                    break

        return indicator_count >= 1 or len(matched_types) >= 2

    def _decompose_complex_task(self, user_input: str) -> List[SubTask]:
        """
        拆解复合任务为多个子任务

        Args:
            user_input: 用户输入

        Returns:
            子任务列表
        """
        sub_tasks = []
        task_num = 1

        # 尝试按连接词分割请求
        parts = re.split(r'(?:并且|然后|还要|另外|同时|之后|接着)[，,、\s]*', user_input)

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # 识别每个部分的意图
            intent, confidence = self.analyze_intent(part)
            if intent == TaskType.UNKNOWN:
                continue

            # 创建子任务
            sub_task = SubTask(
                task_id=f"{sub_tasks[0].task_id.split('_')[0] if sub_tasks else 'task'}_{task_num:02d}",
                task_type=intent,
                description=part,
                tool_name=intent.value,
                priority=TaskPriority.MEDIUM,
                parameters={"query": part}
            )
            sub_tasks.append(sub_task)
            task_num += 1

        # 如果无法分割，创建一个通用分析任务
        if not sub_tasks:
            sub_tasks.append(SubTask(
                task_id="task_01",
                task_type=TaskType.INFO_QUERY,
                description=user_input,
                tool_name="info_query",
                parameters={"query": user_input}
            ))

        return sub_tasks

    def _create_simple_task(self, user_input: str, intent: TaskType) -> List[SubTask]:
        """
        创建简单任务的子任务列表

        Args:
            user_input: 用户输入
            intent: 意图类型

        Returns:
            包含单个子任务的列表
        """
        # 根据意图类型提取参数
        parameters = self._extract_parameters(user_input, intent)

        sub_task = SubTask(
            task_id="task_01",
            task_type=intent,
            description=user_input,
            tool_name=intent.value,
            parameters=parameters,
            priority=self._determine_priority(user_input)
        )

        return [sub_task]

    def _extract_parameters(self, user_input: str, intent: TaskType) -> Dict[str, Any]:
        """
        从用户输入中提取工具参数

        Args:
            user_input: 用户输入
            intent: 意图类型

        Returns:
            参数字典
        """
        parameters = {"query": user_input}

        # 根据意图类型设置query_type（关键修复）
        if intent == TaskType.INFO_QUERY:
            parameters["query_type"] = "general"  # 默认为通用查询
            
            # 进一步判断具体的查询类型
            if any(word in user_input for word in ["天气", "温度", "下雨", "晴天", "气候"]):
                parameters["query_type"] = "weather"
            elif any(word in user_input for word in ["搜索", "查找", "找一找"]):
                parameters["query_type"] = "search"
            elif any(word in user_input for word in ["新闻", "资讯", "动态"]):
                parameters["query_type"] = "news"
            
            # 提取地点信息（用于天气查询）
            location_patterns = [
                r"(\w+市|\w+省|\w+区|北京|上海|广州|深圳|杭州|成都)"
            ]
            for pattern in location_patterns:
                match = re.search(pattern, user_input)
                if match:
                    parameters["location"] = match.group(1)
                    break
            # 如果是天气查询但没有明确地点，尝试智能推断
            if parameters["query_type"] == "weather" and "location" not in parameters:
                # 常见城市名检测
                for city in ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "西安"]:
                    if city in user_input:
                        parameters["location"] = city
                        break

        elif intent == TaskType.TEXT_GENERATION:
            parameters["query_type"] = "generate"
            
            # 判断文案类型
            if any(word in user_input for word in ["邮件", "email"]):
                parameters["content_type"] = "email"
            elif any(word in user_input for word in ["报告", "总结", "汇报"]):
                parameters["content_type"] = "report"
            elif any(word in user_input for word in ["文案", "营销", "广告"]):
                parameters["content_type"] = "copywriting"

        elif intent == TaskType.SCHEDULING:
            parameters["query_type"] = "schedule"
            
            # 提取时间信息
            time_patterns = [
                r"(今天|明天|后天|下周一?|\d+月\d+日?\s*[上下]午?\s*\d+[点时:]?\d*)",
                r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})"
            ]
            for pattern in time_patterns:
                match = re.search(pattern, user_input)
                if match:
                    parameters["time"] = match.group(1)
                    break

        elif intent == TaskType.DATA_ANALYSIS:
            parameters["query_type"] = "analyze"
            
            # 提取文件路径或数据源
            file_patterns = [r'(["\']?[\w\-./]+\.(?:csv|json|xlsx)["\']?)']
            for pattern in file_patterns:
                match = re.search(pattern, user_input, re.IGNORECASE)
                if match:
                    parameters["file_path"] = match.group(1).strip('"\'')
                    break

        return parameters

    def _determine_priority(self, user_input: str) -> TaskPriority:
        """
        根据用户输入判断任务优先级

        Args:
            user_input: 用户输入

        Returns:
            任务优先级
        """
        high_priority_keywords = ["紧急", "重要", "立即", "马上", "尽快"]
        low_priority_keywords = ["有空", "方便时", "不急"]

        for kw in high_priority_keywords:
            if kw in user_input:
                return TaskPriority.HIGH

        for kw in low_priority_keywords:
            if kw in user_input:
                return TaskPriority.LOW

        return TaskPriority.MEDIUM

    def _resolve_dependencies(self, sub_tasks: List[SubTask]) -> List[str]:
        """
        解析子任务之间的依赖关系并返回执行顺序

        使用拓扑排序算法处理依赖关系

        Args:
            sub_tasks: 子任务列表

        Returns:
            按依赖关系排序的任务ID列表
        """
        if len(sub_tasks) <= 1:
            return [st.task_id for st in sub_tasks]

        # 构建依赖图（简化版：按顺序依赖）
        for i in range(1, len(sub_tasks)):
            # 当前任务依赖于前一个任务
            sub_tasks[i].dependencies.append(sub_tasks[i-1].task_id)

        # 拓扑排序
        execution_order = []
        visited = set()

        def visit(task_id: str):
            if task_id in visited:
                return
            visited.add(task_id)
            execution_order.append(task_id)

        for st in sub_tasks:
            visit(st.task_id)

        return execution_order

    def get_plan_by_id(self, plan_id: str) -> Optional[TaskPlan]:
        """
        根据计划ID获取任务计划

        Args:
            plan_id: 计划ID

        Returns:
            任务计划对象，如果不存在则返回None
        """
        for plan in self.plan_history:
            if plan.plan_id == plan_id:
                return plan
        return None

    def get_recent_plans(self, count: int = 5) -> List[TaskPlan]:
        """
        获取最近的任务计划

        Args:
            count: 返回的计划数量

        Returns:
            最近的任务计划列表
        """
        return self.plan_history[-count:]

    def update_task_status(self, plan_id: str, task_id: str, status: TaskStatus, result: Any = None, error: str = ""):
        """
        更新子任务状态

        Args:
            plan_id: 计划ID
            task_id: 任务ID
            status: 新状态
            result: 执行结果
            error: 错误信息
        """
        plan = self.get_plan_by_id(plan_id)
        if plan:
            for sub_task in plan.sub_tasks:
                if sub_task.task_id == task_id:
                    sub_task.status = status
                    sub_task.result = result
                    sub_task.error_message = error
                    break


if __name__ == "__main__":
    # 测试任务规划器
    planner = TaskPlanner()

    # 测试简单任务
    test_inputs = [
        "查询一下北京今天的天气",
        "帮我写一封工作汇报邮件",
        "分析这个sales.csv文件的销售趋势",
        "明天下午3点提醒我开会"
    ]

    print("\n===== 测试任务拆解 =====\n")
    for input_text in test_inputs:
        intent, confidence = planner.analyze_intent(input_text)
        plan = planner.decompose_task(input_text, intent, confidence)

        print(f"📝 用户输入: {input_text}")
        print(f"   意图类型: {intent.value} (置信度: {confidence:.2f})")
        print(f"   子任务数: {len(plan.sub_tasks)}")
        print(f"   执行顺序: {plan.execution_order}")
        print()

    # 测试复合任务
    complex_input = "先查询上海天气，然后帮我写一篇天气预报的文案"
    intent, confidence = planner.analyze_intent(complex_input)
    plan = planner.decompose_task(complex_input, intent, confidence)

    print(f"\n📝 复合任务测试:")
    print(f"   输入: {complex_input}")
    print(f"   拆分为 {len(plan.sub_tasks)} 个子任务:")
    for i, st in enumerate(plan.sub_tasks, 1):
        print(f"     {i}. [{st.tool_name}] {st.description[:50]}...")
