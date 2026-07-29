"""
工具调用执行器
负责工具注册、动态调用、结果聚合等功能
作为Agent与外部工具之间的桥梁
"""

import importlib
import inspect
import json
import time
from typing import Dict, Any, List, Optional, Callable, Type, Union
from dataclasses import dataclass, field
from datetime import datetime
from abc import ABC, abstractmethod

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import tool_config


@dataclass
class ToolResult:
    """
    工具执行结果数据类

    统一封装所有工具的返回结果
    """
    success: bool
    tool_name: str
    result_data: Any = None
    error_message: str = ""
    execution_time: float = 0.0  # 执行时间（秒）
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "success": self.success,
            "tool_name": self.tool_name,
            "result_data": self.result_data,
            "error_message": self.error_message,
            "execution_time": round(self.execution_time, 3),
            "metadata": self.metadata,
            "timestamp": self.timestamp
        }

    def to_string(self) -> str:
        """转换为可读字符串"""
        if self.success:
            if isinstance(self.result_data, (dict, list)):
                return json.dumps(self.result_data, ensure_ascii=False, indent=2)
            else:
                return str(self.result_data)
        else:
            return f"❌ 工具执行失败 [{self.tool_name}]: {self.error_message}"


class BaseTool(ABC):
    """
    工具基类

    所有工具必须继承此类并实现execute方法
    """

    def __init__(self, name: str, description: str):
        """
        初始化工具

        Args:
            name: 工具名称（唯一标识）
            description: 工具功能描述
        """
        self.name = name
        self.description = description
        self.parameters_schema: Dict[str, Any] = {}  # 参数模式定义
        self._execution_count = 0
        self._total_execution_time = 0.0

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """
        执行工具功能（子类必须实现）

        Args:
            **kwargs: 工具参数

        Returns:
            工具执行结果
        """
        pass

    def validate_parameters(self, parameters: Dict[str, Any]) -> tuple[bool, str]:
        """
        验证参数是否有效

        Args:
            parameters: 参数字典

        Returns:
            (是否有效, 错误信息) 元组
        """
        # 基础验证：检查必需参数
        required_params = self.parameters_schema.get("required", [])
        for param in required_params:
            if param not in parameters:
                return False, f"缺少必需参数: {param}"

        return True, ""

    def get_info(self) -> Dict[str, Any]:
        """获取工具信息"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters_schema,
            "execution_count": self._execution_count,
            "avg_execution_time": (
                self._total_execution_time / self._execution_count
                if self._execution_count > 0 else 0
            )
        }


class ToolExecutor:
    """
    工具执行器核心类

    功能：
    1. 工具注册中心 - 管理所有可用工具
    2. 动态调用 - 根据任务需求选择并执行工具
    3. 结果聚合 - 整合多个工具的执行结果
    4. 错误处理与重试机制
    """

    def __init__(self):
        """初始化工具执行器"""
        # 工具注册表：{tool_name: tool_instance}
        self.tools_registry: Dict[str, BaseTool] = {}
        # 工具类别映射：{category: [tool_names]}
        self.tool_categories: Dict[str, List[str]] = {}
        # 执行历史
        self.execution_history: List[ToolResult] = []
        # 统计信息
        self.stats = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "total_execution_time": 0.0
        }

        print("✓ 工具执行器初始化完成")

    def register_tool(self, tool: BaseTool, category: str = "general") -> bool:
        """
        注册工具到执行器

        Args:
            tool: 工具实例
            category: 工具分类

        Returns:
            是否注册成功
        """
        if tool.name in self.tools_registry:
            print(f"⚠ 工具 '{tool.name}' 已存在，将被覆盖")
        
        self.tools_registry[tool.name] = tool
        
        # 添加到分类
        if category not in self.tool_categories:
            self.tool_categories[category] = []
        if tool.name not in self.tool_categories[category]:
            self.tool_categories[category].append(tool.name)

        print(f"✓ 工具已注册: {tool.name} ({category})")
        return True

    def unregister_tool(self, tool_name: str) -> bool:
        """
        注销工具

        Args:
            tool_name: 工具名称

        Returns:
            是否注销成功
        """
        if tool_name in self.tools_registry:
            del self.tools_registry[tool_name]
            
            # 从分类中移除
            for category, tools in self.tool_categories.items():
                if tool_name in tools:
                    tools.remove(tool_name)
            
            print(f"✓ 工具已注销: {tool_name}")
            return True
        else:
            print(f"⚠ 工具不存在: {tool_name}")
            return False

    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """
        获取工具实例

        Args:
            tool_name: 工具名称

        Returns:
            工具实例，如果不存在则返回None
        """
        return self.tools_registry.get(tool_name)

    def list_tools(self, category: str = None) -> List[Dict[str, Any]]:
        """
        列出所有可用工具

        Args:
            category: 可选，按分类过滤

        Returns:
            工具信息列表
        """
        tools_list = []

        if category:
            tool_names = self.tool_categories.get(category, [])
        else:
            tool_names = list(self.tools_registry.keys())

        for name in tool_names:
            tool = self.tools_registry.get(name)
            if tool:
                tools_list.append(tool.get_info())

        return tools_list

    def execute_tool(self, tool_name: str, parameters: Dict[str, Any] = None, retry_on_failure: bool = True) -> ToolResult:
        """
        执行指定工具

        Args:
            tool_name: 要执行的工具名称
            parameters: 工具参数字典
            retry_on_failure: 失败时是否自动重试

        Returns:
            工具执行结果
        """
        if parameters is None:
            parameters = {}

        # 更新统计信息
        self.stats["total_executions"] += 1

        # 获取工具实例
        tool = self.get_tool(tool_name)
        if not tool:
            result = ToolResult(
                success=False,
                tool_name=tool_name,
                error_message=f"工具未找到: {tool_name}"
            )
            self.stats["failed_executions"] += 1
            self.execution_history.append(result)
            return result

        # 验证参数
        is_valid, error_msg = tool.validate_parameters(parameters)
        if not is_valid:
            result = ToolResult(
                success=False,
                tool_name=tool_name,
                error_message=f"参数验证失败: {error_msg}"
            )
            self.stats["failed_executions"] += 1
            self.execution_history.append(result)
            return result

        # 执行工具（带重试机制）
        max_retries = tool_config.max_retries if retry_on_failure else 1
        last_result = None

        for attempt in range(max_retries):
            try:
                start_time = time.time()
                
                print(f"🔧 正在执行工具 [{tool_name}] (尝试 {attempt + 1}/{max_retries})...")
                
                # 调用工具的execute方法
                result = tool.execute(**parameters)
                
                execution_time = time.time() - start_time
                result.execution_time = execution_time
                
                # 更新工具统计
                tool._execution_count += 1
                tool._total_execution_time += execution_time
                
                # 更新全局统计
                self.stats["total_execution_time"] += execution_time
                if result.success:
                    self.stats["successful_executions"] += 1
                else:
                    self.stats["failed_executions"] += 1
                
                # 记录到历史
                self.execution_history.append(result)
                
                if result.success:
                    print(f"✓ 工具执行成功 [{tool_name}] 耗时: {execution_time:.2f}s")
                    return result
                else:
                    last_result = result
                    print(f"⚠ 工具执行失败 [{tool_name}]: {result.error_message}")
                    
            except Exception as e:
                last_result = ToolResult(
                    success=False,
                    tool_name=tool_name,
                    error_message=f"执行异常: {str(e)}"
                )
                print(f"❌ 工具执行异常 [{tool_name}]: {e}")
                
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 1  # 递增等待时间
                    print(f"   ⏳ 等待 {wait_time}s 后重试...")
                    time.sleep(wait_time)

        # 所有重试都失败
        if last_result:
            self.execution_history.append(last_result)
        return last_result or ToolResult(
            success=False,
            tool_name=tool_name,
            error_message="未知错误"
        )

    def execute_task_plan(self, task_plan) -> List[ToolResult]:
        """
        执行完整的任务计划（多个子任务）

        Args:
            task_plan: TaskPlan对象（来自TaskPlanner）

        Returns:
            所有子任务的执行结果列表
        """
        results = []
        accumulated_results = {}  # 用于传递前序任务的结果

        print(f"\n📋 开始执行任务计划: {task_plan.plan_id}")
        print(f"   总共 {len(task_plan.sub_tasks)} 个子任务")

        for i, task_id in enumerate(task_plan.execution_order, 1):
            # 查找对应的子任务
            sub_task = next((st for st in task_plan.sub_tasks if st.task_id == task_id), None)
            if not sub_task:
                print(f"⚠ 子任务未找到: {task_id}")
                continue

            print(f"\n[{i}/{len(task_plan.execution_order)}] 执行子任务: {sub_task.description[:50]}...")

            # 合并参数（包括前序任务的结果）
            parameters = dict(sub_task.parameters)
            parameters.update(accumulated_results)

            # 执行工具
            result = self.execute_tool(sub_task.tool_name, parameters)
            results.append(result)

            # 更新子任务状态
            sub_task.status = "completed" if result.success else "failed"
            sub_task.result = result.result_data
            sub_task.error_message = result.error_message

            # 将结果传递给后续任务
            accumulated_results[f"task_{i-1}_result"] = result.result_data

            # 如果当前任务失败且是关键任务，停止执行
            if not result.success and sub_task.priority == "high":
                print(f"⚠ 关键任务执行失败，终止计划")
                break

        print(f"\n✓ 任务计划执行完成 | 成功: {sum(1 for r in results if r.success)}/{len(results)}")
        return results

    def aggregate_results(self, results: List[ToolResult]) -> Dict[str, Any]:
        """
        聚合多个工具的执行结果

        Args:
            results: 工具执行结果列表

        Returns:
            聚合后的结果字典
        """
        aggregation = {
            "summary": {
                "total_tools": len(results),
                "successful": sum(1 for r in results if r.success),
                "failed": sum(1 for r in results if not r.success),
                "total_time": sum(r.execution_time for r in results)
            },
            "results": [],
            "errors": [],
            "combined_output": ""
        }

        output_parts = []

        for result in results:
            result_dict = result.to_dict()
            aggregation["results"].append(result_dict)

            if result.success:
                # 收集成功的输出
                output_str = result.to_string()
                output_parts.append(f"[{result.tool_name}]:\n{output_str}")
            else:
                aggregation["errors"].append({
                    "tool": result.tool_name,
                    "error": result.error_message
                })

        # 组合输出
        aggregation["combined_output"] = "\n\n".join(output_parts)

        return aggregation

    def get_statistics(self) -> Dict[str, Any]:
        """获取执行器统计信息"""
        return {
            **self.stats,
            "registered_tools": len(self.tools_registry),
            "tool_categories": {
                cat: len(tools) 
                for cat, tools in self.tool_categories.items()
            },
            "history_size": len(self.execution_history),
            "success_rate": (
                self.stats["successful_executions"] / self.stats["total_executions"] * 100
                if self.stats["total_executions"] > 0 else 0
            )
        }

    def clear_history(self):
        """清空执行历史"""
        self.execution_history.clear()
        print("🗑️ 执行历史已清空")


# 示例：创建一个简单的测试工具
class TestTool(BaseTool):
    """测试用工具示例"""

    def __init__(self):
        super().__init__(
            name="test_tool",
            description="用于测试的工具"
        )
        self.parameters_schema = {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "要回显的消息"
                }
            },
            "required": ["message"]
        }

    def execute(self, **kwargs) -> ToolResult:
        message = kwargs.get("message", "")
        return ToolResult(
            success=True,
            tool_name=self.name,
            result_data={"echo": message, "processed": True}
        )


if __name__ == "__main__":
    # 测试工具执行器
    executor = ToolExecutor()

    # 注册测试工具
    test_tool = TestTool()
    executor.register_tool(test_tool, category="testing")

    # 列出工具
    print("\n可用工具:")
    for tool_info in executor.list_tools():
        print(f"  - {tool_info['name']}: {tool_info['description']}")

    # 执行工具
    print("\n执行测试工具:")
    result = executor.execute_tool("test_tool", {"message": "Hello, AI Agent!"})
    print(f"执行结果: {result.to_string()}")

    # 查看统计信息
    stats = executor.get_statistics()
    print(f"\n统计信息:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))
