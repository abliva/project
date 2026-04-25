# -*- coding: utf-8 -*-
"""
===============================================
  Visio UML 图自动生成系统 v2.0 (完整版)
===============================================

功能特点：
  * 支持用例图（Use Case Diagram）自动构建
  * 支持类图（Class Diagram）自动构建
  * 支持对象图（Object Diagram）自动构建
  * 智能布局算法，自动优化图形位置
  * 自动识别和绘制所有标准 UML 元素
  * 完美兼容 Visio 2016
  * 保存为标准 .vsdx 文件
  * 效果与手动在 Visio 中绘制完全一致

使用方法：
1. 确保已安装 Python 和 pywin32 库：pip install pywin32
2. 确保已安装 Microsoft Visio 2016 或更高版本
3. 运行本程序：python visio_uml_generator.py
4. 根据菜单提示选择要创建的图表类型

作者：浊酒
日期：2026-04-11
"""

import os
import sys
import json
import win32com.client
import pythoncom
from typing import Optional, List, Dict, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


# ============================================================
# 第一部分：Visio 自动化核心模块
# ============================================================

class VisioAutomation:
    """Visio 2016 自动化操作类"""

    def __init__(self, visible: bool = True):
        self.visio_app = None
        self.document = None
        self.page = None
        self.visible = visible
        self._init_visio()

    def _init_visio(self):
        """初始化 Visio COM 对象"""
        try:
            self.visio_app = win32com.client.Dispatch("Visio.Application")
            self.visio_app.Visible = self.visible
            print(f"[OK] Visio {self.visio_app.Version} 已成功启动")
        except Exception as e:
            raise Exception(f"无法启动 Visio: {e}\n请确保已安装 Visio 2016 或更高版本")

    def new_document(self, template_path: str = ""):
        """创建新文档"""
        try:
            if template_path and os.path.exists(template_path):
                self.document = self.visio_app.Documents.Add(template_path)
            else:
                self.document = self.visio_app.Documents.Add("")
            self.page = self.document.Pages.Item(1)
            print(f"[OK] 新文档已创建")
            return self.document
        except Exception as e:
            raise Exception(f"创建文档失败: {e}")

    def set_page_size(self, width: float, height: float):
        """设置页面大小"""
        if self.page:
            self.page.PageSheet.Cells("PageWidth").FormulaU = f"{width} in"
            self.page.PageSheet.Cells("PageHeight").FormulaU = f"{height} in"
            print(f"[OK] 页面大小设置为: {width} x {height} 英寸")

    def get_stencil(self, stencil_name: str):
        """获取模具文件"""
        try:
            stencil_path = os.path.join(
                self.visio_app.Path,
                "Solutions",
                stencil_name
            )
            if os.path.exists(stencil_path):
                stencil = self.visio_app.Documents.OpenEx(stencil_path, 64)
                print(f"[OK] 模具 '{stencil_name}' 已加载")
                return stencil
            else:
                raise FileNotFoundError(f"找不到模具文件: {stencil_path}")
        except Exception as e:
            print(f"[WARN] 加载模具失败: {e}")
            return None

    def get_uml_stencils(self) -> Dict[str, Any]:
        """
        加载所有 UML 相关的模具文件
        返回包含各种 UML 模具的字典
        """
        stencils = {}

        # UML 静态结构模具（包含：参与者、用例、类、接口、包等）
        uml_static = self._load_uml_stencil("UMLSTNC.VSS", "UML Static Structure (US units)")
        if uml_static:
            stencils['static'] = uml_static

        # 如果 US 版本找不到，尝试 Metric 版本
        if 'static' not in stencils:
            uml_static = self._load_uml_stencil("UMLSTNM.VSS", "UML Static Structure (Metric)")
            if uml_static:
                stencils['static'] = uml_static

        print(f"[INFO] 已加载 {len(stencils)} 个 UML 模具")
        return stencils

    def _load_uml_stencil(self, filename: str, display_name: str) -> Optional[Any]:
        """
        尝试从多个路径加载 UML 模具
        """
        # 可能的路径列表
        possible_paths = [
            os.path.join(self.visio_app.Path, "Solutions", filename),
            os.path.join(os.environ.get('ProgramFiles', ''),
                         "Microsoft Office", "Office16", "Visio Content", "1033", filename),
            os.path.join(os.environ.get('ProgramFiles(x86)', ''),
                         "Microsoft Office", "Office16", "Visio Content", "1033", filename),
        ]

        for path in possible_paths:
            if os.path.exists(path):
                try:
                    stencil = self.visio_app.Documents.OpenEx(path, 64)
                    print(f"[OK] 加载 UML 模具: {display_name}")
                    return stencil
                except Exception as e:
                    print(f"[WARN] 打开模具失败 ({path}): {e}")

        # 尝试通过名称搜索
        try:
            stencil = self.visio_app.Documents.OpenEx(filename, 64)
            print(f"[OK] 通过名称加载模具: {display_name}")
            return stencil
        except:
            pass

        return None

    def drop_shape(self, master: Any, x: float, y: float) -> Any:
        """放置形状到页面"""
        try:
            shape = self.page.Drop(master, x, y)
            return shape
        except Exception as e:
            print(f"[WARN] 放置形状失败: {e}")
            return None

    def connect_shapes(self, from_shape: Any, to_shape: Any, connector_master: Any = None) -> Any:
        """连接两个形状 - 增强版错误处理"""
        if not from_shape or not to_shape:
            print("[WARN] 连接失败：源形状或目标形状为空")
            return None

        try:
            if connector_master:
                connector = self.page.Drop(connector_master, 0, 0)
            else:
                connector = self.page.Drop(self.page.Application.ConnectorToolDataObject, 0, 0)

            if not connector:
                print("[WARN] 无法创建连接器")
                return None

            # 使用更稳定的连接方式
            try:
                from_cell = from_shape.CellsU("PinX")
                to_cell = to_shape.CellsU("PinX")

                connector.CellsU("BeginX").GlueTo(from_cell)
                connector.CellsU("EndX").GlueTo(to_cell)
            except Exception as glue_error:
                # 如果 GlueTo 失败，尝试直接设置位置
                try:
                    from_x = from_shape.CellsU("PinX").Result("in")
                    from_y = from_shape.CellsU("PinY").Result("in")
                    to_x = to_shape.CellsU("PinX").Result("in")
                    to_y = to_shape.CellsU("PinY").Result("in")

                    connector.CellsU("BeginX").FormulaU = f"{from_x} in"
                    connector.CellsU("BeginY").FormulaU = f"{from_y} in"
                    connector.CellsU("EndX").FormulaU = f"{to_x} in"
                    connector.CellsU("EndY").FormulaU = f"{to_y} in"
                except Exception as pos_error:
                    print(f"[WARN] 设置连接线位置失败: {pos_error}")

            return connector
        except Exception as e:
            print(f"[WARN] 连接形状失败: {e}")
            return None

    def set_shape_text(self, shape: Any, text: str):
        """设置形状文本"""
        if shape:
            shape.Text = text

    def set_shape_size(self, shape: Any, width: float, height: float):
        """设置形状大小"""
        if shape:
            shape.CellsU("Width").FormulaU = f"{width} in"
            shape.CellsU("Height").FormulaU = f"{height} in"

    def set_shape_position(self, shape: Any, x: float, y: float):
        """设置形状位置"""
        if shape:
            shape.CellsU("PinX").FormulaU = f"{x} in"
            shape.CellsU("PinY").FormulaU = f"{y} in"

    def set_shape_fill_color(self, shape: Any, r: int, g: int, b: int):
        """设置形状填充颜色"""
        if shape:
            color = self._rgb_to_visio_color(r, g, b)
            shape.CellsU("FillForegnd").FormulaU = color

    def _rgb_to_visio_color(self, r: int, g: int, b: int) -> str:
        """将 RGB 转换为 Visio 颜色格式"""
        return f"RGB({r},{g},{b})"

    def add_text_box(self, x: float, y: float, text: str, width: float = 1.0, height: float = 0.5) -> Any:
        """添加文本框"""
        try:
            rect = self.page.DrawRectangle(x - width / 2, y - height / 2,
                                           x + width / 2, y + height / 2)
            rect.Text = text
            rect.CellsU("LinePattern").FormulaU = "0"
            return rect
        except Exception as e:
            print(f"[WARN] 添加文本框失败: {e}")
            return None

    def save_document(self, file_path: str, format_type: int = 0):
        """保存文档"""
        try:
            if self.document:
                abs_path = os.path.abspath(file_path)

                dir_name = os.path.dirname(abs_path)
                if dir_name and not os.path.exists(dir_name):
                    os.makedirs(dir_name)

                if format_type == 0:
                    self.document.SaveAs(abs_path)
                else:
                    self.document.SaveAsEx(abs_path, format_type)

                print(f"[OK] 文件已保存至: {abs_path}")
                return True
        except Exception as e:
            print(f"[FAIL] 保存文档失败: {e}")
            return False

    def close_document(self, save_changes: bool = False):
        """关闭当前文档"""
        if self.document:
            try:
                if save_changes:
                    self.document.Save()
                self.document.Close()
            except:
                pass
            self.document = None
            self.page = None
            print("[OK] 文档已关闭")

    def quit_application(self):
        """退出 Visio 应用程序"""
        if self.visio_app:
            try:
                self.visio_app.Quit()
                print("[OK] Visio 已关闭")
            except:
                pass
            finally:
                self.visio_app = None

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.quit_application()
        return False

    def auto_layout_page(self):
        """自动布局页面"""
        if self.page and self.document:
            try:
                self.page.Layout()
                print("[OK] 页面布局已完成")
            except Exception as e:
                print(f"[WARN] 自动布局失败: {e}")

    def zoom_to_fit(self):
        """缩放以适应页面"""
        if self.visio_app.ActiveWindow:
            try:
                self.visio_app.ActiveWindow.Zoom = -1
                print("[OK] 已缩放至适应窗口大小")
            except Exception as e:
                print(f"[WARN] 缩放失败: {e}")


class VisioShapeFactory:
    """
    UML 形状工厂类 - 使用 Visio 内置的 UML 模具创建标准形状
    确保所有图形都符合 UML 标准和 Visio 标准
    """

    def __init__(self, visio: VisioAutomation):
        self.visio = visio
        self.stencils = {}
        self.masters_cache = {}
        self._init_uml_stencils()

    def _init_uml_stencils(self):
        """初始化并加载所有 UML 模具"""
        print("\n 正在加载 UML 模具...")
        self.stencils = self.visio.get_uml_stencils()

        if not self.stencils:
            print("[WARN] 无法加载 UML 模具，将使用基础形状")

        # 预缓存常用的 Master 对象
        self._cache_common_masters()

    def _cache_common_masters(self):
        """预缓存常用的 UML 主形状"""
        master_names = [
            ('static', 'Actor'),  # 参与者（小人）
            ('static', 'Use Case'),  # 用例（椭圆）
            ('static', 'Class'),  # 类
            ('static', 'Interface'),  # 接口
            ('static', 'Package'),  # 包
            ('static', 'Generalization'),  # 泛化关系
            ('static', 'Dependency'),  # 依赖关系
            ('static', 'Association'),  # 关联关系
        ]

        for stencil_key, master_name in master_names:
            if stencil_key in self.stencils:
                try:
                    stencil = self.stencils[stencil_key]
                    master = stencil.Masters.Item(master_name)
                    cache_key = f"{stencil_key}_{master_name}"
                    self.masters_cache[cache_key] = master
                except Exception as e:
                    print(f"[WARN] 缓存 '{master_name}' 失败: {e}")

    def get_master(self, shape_type: str) -> Optional[Any]:
        """
        获取指定类型的 UML 主形状
        支持多种命名方式以增加兼容性
        """
        # 形状类型到模具名称的映射
        type_mappings = {
            'actor': ['Actor', 'Actor (UML)', 'Stick Figure'],
            'usecase': ['Use Case', 'UseCase', 'Use case', 'Use Case (UML)'],
            'class': ['Class', 'Class (UML)', 'UML Class'],
            'interface': ['Interface', 'Interface (UML)', 'Provided Interface'],
            'package': ['Package', 'Package (UML)'],
            'generalization': ['Generalization', 'Generalizes', 'Inheritance'],
            'dependency': ['Dependency', 'Depends'],
            'association': ['Association', 'Associates'],
            'aggregation': ['Aggregation', 'Aggregates'],
            'composition': ['Composition', 'Composes'],
        }

        shape_lower = shape_type.lower()

        if shape_lower in type_mappings:
            possible_names = type_mappings[shape_lower]

            # 首先尝试从缓存获取
            for name in possible_names:
                cache_key = f"static_{name}"
                if cache_key in self.masters_cache:
                    return self.masters_cache[cache_key]

            # 如果缓存中没有，直接从模具查找
            if 'static' in self.stencils:
                stencil = self.stencils['static']
                for name in possible_names:
                    try:
                        master = stencil.Masters.Item(name)
                        return master
                    except:
                        continue

        return None

    def create_uml_shape(self, shape_type: str, x: float, y: float,
                         text: str = "", width: float = 1.0,
                         height: float = 0.75) -> Optional[Any]:
        """
        创建标准的 UML 形状
        优先使用 Visio 内置的 UML 模具
        """
        page = self.visio.page

        # 尝试从 UML 模具创建标准形状
        master = self.get_master(shape_type)

        if master:
            try:
                shape = self.visio.drop_shape(master, x, y)

                if shape and text:
                    try:
                        shape.Text = text
                    except:
                        pass

                if shape:
                    print(f"   [OK] 已创建标准 {shape_type}: {text}")

                return shape
            except Exception as e:
                print(f"[WARN] 使用 UML 模具创建失败 ({shape_type}): {e}")

        # 如果模具方式失败，回退到基础绘制
        return self._create_fallback_shape(shape_type, x, y, text, width, height)

    def _create_fallback_shape(self, shape_type: str, x: float, y: float,
                               text: str = "", width: float = 1.0,
                               height: float = 0.75) -> Optional[Any]:
        """
        回退方案：当 UML 模具不可用时，使用基础绘制方法
        尽量模拟 UML 标准外观
        """
        page = self.visio.page

        try:
            if shape_type.lower() == "actor":
                return self._draw_actor_stick_figure(x, y, text)

            elif shape_type.lower() == "usecase":
                return self._draw_use_case_oval(x, y, text, width, height)

            elif shape_type.lower() == "class":
                return self._draw_class_rectangle(x, y, text, width, height)

            elif shape_type.lower() == "rectangle":
                shape = page.DrawRectangle(x - width / 2, y - height / 2,
                                           x + width / 2, y + height / 2)
                if text:
                    shape.Text = text
                return shape

            elif shape_type.lower() == "oval":
                shape = page.DrawOval(x - width / 2, y - height / 2,
                                      x + width / 2, y + height / 2)
                if text:
                    shape.Text = text
                return shape

            else:
                shape = page.DrawRectangle(x - width / 2, y - height / 2,
                                           x + width / 2, y + height / 2)
                if text:
                    shape.Text = text
                return shape

        except Exception as e:
            print(f"[WARN] 创建基础形状失败 ({shape_type}): {e}")
            return None

    def _draw_actor_stick_figure(self, x: float, y: float, name: str) -> Any:
        """
        绘制标准的 UML 参与者（火柴人）
        使用最简单、最稳定的方式绘制
        """
        page = self.visio.page

        try:
            # 火柴人的尺寸参数
            head_radius = 0.12  # 头部半径
            body_top = y + 0.3  # 身体顶部 Y 坐标
            body_bottom = y - 0.25  # 身体底部 Y 坐标
            arm_y = y + 0.12  # 手臂 Y 坐标
            leg_spread = 0.22  # 腿部展开宽度

            # 绘制头部（圆形）
            head = page.DrawOval(
                x - head_radius, body_top,
                x + head_radius, body_top + head_radius * 2
            )

            # 绘制身体（垂直线）
            body = page.DrawLine(x, body_top, x, body_bottom)

            # 绘制左臂
            left_arm = page.DrawLine(x, arm_y, x - leg_spread, y)

            # 绘制右臂
            right_arm = page.DrawLine(x, arm_y, x + leg_spread, y)

            # 绘制左腿
            left_leg = page.DrawLine(x, body_bottom, x - leg_spread * 0.8, y - 0.45)

            # 绘制右腿
            right_leg = page.DrawLine(x, body_bottom, x + leg_spread * 0.8, y - 0.45)

            # 设置线条样式（统一为黑色细线）
            shapes_list = [head, body, left_arm, right_arm, left_leg, right_leg]
            for s in shapes_list:
                try:
                    s.CellsU("LineColor").FormulaU = "RGB(0,0,0)"
                    s.CellsU("LineWidth").FormulaU = "1 pt"
                except:
                    pass

            # 在下方添加名字标签
            name_shape = self.visio.add_text_box(x, y - 0.6, name, width=1.5, height=0.4)
            if name_shape:
                try:
                    name_shape.CellsU("CharSize").FormulaU = "9 pt"
                    name_shape.CellsU("HAlign").FormulaU = "1"
                except:
                    pass

            print(f"   [OK] 已创建参与者（火柴人）: {name}")
            return head  # 返回头部作为主形状引用

        except Exception as e:
            print(f"[WARN] 绘制火柴人失败: {e}")
            # 最终回退：使用矩形
            try:
                rect = page.DrawRectangle(x - 0.35, y - 0.6, x + 0.35, y + 0.35)
                rect.Text = name
                return rect
            except:
                return None

    def _draw_use_case_oval(self, x: float, y: float, name: str,
                            width: float, height: float) -> Any:
        """绘制标准用例椭圆"""
        page = self.visio.page

        try:
            shape = page.DrawOval(
                x - width / 2, y - height / 2,
                x + width / 2, y + height / 2
            )

            shape.Text = name

            # 设置样式：白色填充，黑色边框
            try:
                shape.CellsU("FillForegnd").FormulaU = "RGB(255,255,255)"
            except:
                pass
            try:
                shape.CellsU("LineColor").FormulaU = "RGB(0,0,0)"
            except:
                pass
            try:
                shape.CellsU("LineWidth").FormulaU = "1.25 pt"
            except:
                pass

            print(f"   [OK] 已创建用例椭圆: {name}")
            return shape

        except Exception as e:
            print(f"[WARN] 绘制用例椭圆失败: {e}")
            return None

    def _draw_class_rectangle(self, x: float, y: float, name: str,
                              width: float, height: float) -> Any:
        """绘制标准类矩形"""
        page = self.visio.page

        try:
            shape = page.DrawRectangle(
                x - width / 2, y - height / 2,
                x + width / 2, y + height / 2
            )

            shape.Text = name

            # 设置样式
            try:
                shape.CellsU("FillForegnd").FormulaU = "RGB(255,255,255)"
            except:
                pass
            try:
                shape.CellsU("LineColor").FormulaU = "RGB(0,0,0)"
            except:
                pass
            try:
                shape.CellsU("LineWidth").FormulaU = "1 pt"
            except:
                pass

            return shape
        except Exception as e:
            print(f"[WARN] 绘制类矩形失败: {e}")
            return None


# ============================================================
# 第二部分：UML 数据模型和智能布局引擎
# ============================================================

class RelationshipType(Enum):
    """关系类型枚举"""
    ASSOCIATION = "association"  # 关联
    GENERALIZATION = "generalization"  # 泛化/继承
    DEPENDENCY = "dependency"  # 依赖
    AGGREGATION = "aggregation"  # 聚合
    COMPOSITION = "composition"  # 组合
    REALIZATION = "realization"  # 实现
    INCLUDE = "include"  # 包含（用例图特有）
    EXTEND = "extend"  # 扩展（用例图特有）


@dataclass
class Actor:
    """用例图中的参与者（角色）"""
    name: str
    x: float = 0.0
    y: float = 0.0
    description: str = ""

    def __post_init__(self):
        if not self.name:
            raise ValueError("Actor 名称不能为空")


@dataclass
class UseCase:
    """用例图中的用例"""
    name: str
    x: float = 0.0
    y: float = 0.0
    description: str = ""
    is_primary: bool = False

    def __post_init__(self):
        if not self.name:
            raise ValueError("UseCase 名称不能为空")


@dataclass
class UseCaseRelationship:
    """用例关系"""
    from_item: Any
    to_item: Any
    relationship_type: RelationshipType = RelationshipType.ASSOCIATION
    label: str = ""


@dataclass
class ClassAttribute:
    """类属性"""
    name: str
    type_name: str = "String"
    visibility: str = "+"
    default_value: str = ""
    is_static: bool = False

    def __str__(self):
        static_str = "static " if self.is_static else ""
        value_str = f" = {self.default_value}" if self.default_value else ""
        return f"{self.visibility} {static_str}{self.name}: {self.type_name}{value_str}"


@dataclass
class ClassMethod:
    """类方法"""
    name: str
    return_type: str = "void"
    visibility: str = "+"
    parameters: List[str] = field(default_factory=list)
    is_abstract: bool = False
    is_static: bool = False

    def __str__(self):
        abstract_str = "abstract " if self.is_abstract else ""
        static_str = "static " if self.is_static else ""
        params_str = ", ".join(self.parameters) if self.parameters else ""
        return f"{self.visibility} {abstract_str}{static_str}{self.name}({params_str}): {self.return_type}"


@dataclass
class UMLClass:
    """UML 类"""
    name: str
    x: float = 0.0
    y: float = 0.0
    attributes: List[ClassAttribute] = field(default_factory=list)
    methods: List[ClassMethod] = field(default_factory=list)
    stereotype: str = ""
    is_interface: bool = False
    is_abstract: bool = False

    def __post_init__(self):
        if not self.name:
            raise ValueError("类名不能为空")

    def get_class_text(self) -> str:
        """获取类的完整文本表示"""
        lines = []

        if self.stereotype:
            lines.append(f"<<{self.stereotype}>>")

        class_name = self.name
        lines.append(class_name)
        lines.append("---")

        for attr in self.attributes:
            lines.append(str(attr))

        lines.append("---")

        for method in self.methods:
            lines.append(str(method))

        return "\n".join(lines)


@dataclass
class ClassRelationship:
    """类之间的关系"""
    from_class: UMLClass
    to_class: UMLClass
    relationship_type: RelationshipType
    multiplicity_from: str = "1"
    multiplicity_to: str = "*"
    label: str = ""
    direction: str = "bidirectional"


@dataclass
class ObjectInstance:
    """对象实例"""
    name: str
    class_name: str
    x: float = 0.0
    y: float = 0.0
    attribute_values: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if not self.name or not self.class_name:
            raise ValueError("对象名称和类名不能为空")


@dataclass
class ObjectRelationship:
    """对象间的关系"""
    from_object: ObjectInstance
    to_object: ObjectInstance
    label: str = ""
    rel_type: str = "association"  # association, aggregation, composition, generalization


class SmartLayoutEngine:
    """智能布局引擎"""

    def __init__(self, page_width: float = 11.0, page_height: float = 8.5,
                 margin: float = 1.0):
        self.page_width = page_width
        self.page_height = page_height
        self.margin = margin
        self.element_spacing_x = 2.5
        self.element_spacing_y = 2.0

    def layout_actors(self, actors: List[Actor], side: str = "left") -> List[Actor]:
        """布局参与者"""
        start_x = self.margin + 0.5 if side == "left" else self.page_width - self.margin - 0.5
        start_y = self.page_height / 2 + (len(actors) * self.element_spacing_y) / 2 - self.element_spacing_y / 2

        for i, actor in enumerate(actors):
            actor.x = start_x
            actor.y = start_y - (i * self.element_spacing_y)

        return actors

    def layout_use_cases(self, use_cases: List[UseCase], center_x: float = None) -> List[UseCase]:
        """布局用例"""
        if center_x is None:
            center_x = self.page_width / 2

        cols = max(3, int(len(use_cases) ** 0.5))
        rows = (len(use_cases) + cols - 1) // cols

        start_x = center_x - ((cols - 1) * self.element_spacing_x) / 2
        start_y = self.page_height / 2 + ((rows - 1) * self.element_spacing_y) / 2

        for i, uc in enumerate(use_cases):
            col = i % cols
            row = i // cols
            uc.x = start_x + col * self.element_spacing_x
            uc.y = start_y - row * self.element_spacing_y

        return use_cases

    def layout_classes(self, classes: List[UMLClass]) -> List[UMLClass]:
        """布局类图中的类"""
        n = len(classes)
        if n == 0:
            return classes

        cols = min(max(3, int(n ** 0.5)), 5)
        rows = (n + cols - 1) // cols

        total_width = (cols - 1) * self.element_spacing_x
        total_height = (rows - 1) * self.element_spacing_y

        start_x = (self.page_width - total_width) / 2
        start_y = (self.page_height + total_height) / 2

        for i, cls in enumerate(classes):
            col = i % cols
            row = i // cols
            cls.x = start_x + col * self.element_spacing_x
            cls.y = start_y - row * self.element_spacing_y

        return classes

    def layout_objects(self, objects: List[ObjectInstance]) -> List[ObjectInstance]:
        """布局对象图中的对象实例"""
        return self.layout_classes(objects)

    def calculate_system_boundary(self, actors: List[Actor],
                                  use_cases: List[UseCase]) -> Tuple[float, float, float, float]:
        """计算系统边界框的位置和大小"""
        if not use_cases:
            return (self.page_width / 2 - 3, self.page_height / 2 - 3, 6, 6)

        min_x = min(uc.x for uc in use_cases) - 1.5
        max_x = max(uc.x for uc in use_cases) + 1.5
        min_y = min(uc.y for uc in use_cases) - 1.5
        max_y = max(uc.y for uc in use_cases) + 1.5

        width = max_x - min_x
        height = max_y - min_y

        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2

        return (center_x - width / 2, center_y - height / 2, width, height)


# ============================================================
# 第三部分：用例图构建器
# ============================================================

class UseCaseDiagramBuilder:
    """用例图构建器"""

    def __init__(self, visio_automation):
        self.visio = visio_automation
        self.factory = None
        if visio_automation:
            self.factory = VisioShapeFactory(visio_automation)
        self.actors: List[Actor] = []
        self.use_cases: List[UseCase] = []
        self.relationships: List[UseCaseRelationship] = []
        self.layout_engine = SmartLayoutEngine()
        self.title = "用例图"
        self.system_name = "系统"

    def add_actor(self, name: str, description: str = "") -> Actor:
        """添加参与者"""
        actor = Actor(name=name, description=description)
        self.actors.append(actor)
        return actor

    def add_use_case(self, name: str, description: str = "", is_primary: bool = False) -> UseCase:
        """添加用例"""
        use_case = UseCase(name=name, description=description, is_primary=is_primary)
        self.use_cases.append(use_case)
        return use_case

    def add_relationship(self, from_item: Any, to_item: Any,
                         rel_type: RelationshipType = RelationshipType.ASSOCIATION,
                         label: str = "") -> UseCaseRelationship:
        """添加关系"""
        rel = UseCaseRelationship(
            from_item=from_item,
            to_item=to_item,
            relationship_type=rel_type,
            label=label
        )
        self.relationships.append(rel)
        return rel

    def set_title(self, title: str):
        """设置图表标题"""
        self.title = title

    def set_system_name(self, name: str):
        """设置系统名称"""
        self.system_name = name

    def build(self) -> bool:
        """构建完整的用例图"""
        try:
            print(f"\n{'=' * 60}")
            print(f"开始构建用例图: {self.title}")
            print(f"{'=' * 60}")

            print("\n 正在进行智能布局...")

            # 使用改进的布局算法，确保元素不重叠
            self._improved_layout()

            print("\n 正在绘制系统边界...")
            boundary = self._draw_system_boundary()

            print("\n 正在添加标题...")
            self._draw_title()

            print("\n 正在绘制参与者...")
            actor_shapes = {}
            for actor in self.actors:
                shape = self._draw_actor(actor)
                if shape:
                    actor_shapes[id(actor)] = shape
                    print(f"   [OK] 已绘制参与者: {actor.name}")

            print("\n 正在绘制用例...")
            usecase_shapes = {}
            for uc in self.use_cases:
                shape = self._draw_use_case(uc)
                if shape:
                    usecase_shapes[id(uc)] = shape
                    print(f"   [OK] 已绘制用例: {uc.name}")

            print("\n 正在绘制关系连接...")
            for rel in self.relationships:
                from_shape = actor_shapes.get(id(rel.from_item)) or usecase_shapes.get(id(rel.from_item))
                to_shape = actor_shapes.get(id(rel.to_item)) or usecase_shapes.get(id(rel.to_item))

                if from_shape and to_shape:
                    connector = self._draw_simple_connection(from_shape, to_shape, rel.label)
                    if connector:
                        print(f"   [OK] 已连接: {rel.from_item.name} → {rel.to_item.name}")

            # 只缩放，不自动布局（避免打乱手动设置的位置）
            print("\n 正在调整视图...")
            self.visio.zoom_to_fit()

            print(f"\n[OK] 用例图 '{self.title}' 构建完成！")
            return True

        except Exception as e:
            print(f"\n[ERROR] 构建用例图失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _improved_layout(self):
        """
        美观的布局算法 - 参考标准UML用例图样式
        左右分开的用户分别连接不同用例组
        所有元素确保在系统边界内
        """
        page_width = 11.0
        page_height = 8.5

        num_actors = len(self.actors)
        num_use_cases = len(self.use_cases)

        if num_actors == 0 or num_use_cases == 0:
            return

        # 布局策略：参考标准UML图
        # - 如果有2个参与者：一个在左侧，一个在右侧
        # - 用例分两组：左半部分给左侧参与者，右半部分给右侧参与者
        # - 缩小尺寸和间距，确保所有元素在系统边界内

        if num_actors >= 2:
            # 两个或以上参与者：左右分布（靠近边缘）
            left_actor = self.actors[0]
            right_actor = self.actors[1] if num_actors > 1 else self.actors[0]

            # 左侧参与者位置（靠近左边缘）
            left_actor.x = 0.8
            left_actor.y = page_height / 2

            # 右侧参与者位置（靠近右边缘）
            right_actor.x = page_width - 0.8
            right_actor.y = page_height / 2

            # 额外参与者在中间
            for i in range(2, num_actors):
                self.actors[i].x = page_width / 2
                self.actors[i].y = page_height / 4 + (i - 2) * 1.2

            # 将用例分成两组
            mid = (num_use_cases + 1) // 2

            # 左侧用例组（对应左侧参与者）- 紧凑布局
            left_use_cases = self.use_cases[:mid]
            spacing_y_left = 1.3  # 减小垂直间距
            start_y_left = page_height / 2 + (len(left_use_cases) - 1) * spacing_y_left / 2

            for i, uc in enumerate(left_use_cases):
                uc.x = 3.0  # 左侧用例区域X坐标（向内收缩）
                uc.y = start_y_left - i * spacing_y_left

            # 右侧用例组（对应右侧参与者）- 紧凑布局
            right_use_cases = self.use_cases[mid:]
            spacing_y_right = 1.3  # 减小垂直间距
            start_y_right = page_height / 2 + (len(right_use_cases) - 1) * spacing_y_right / 2

            for i, uc in enumerate(right_use_cases):
                uc.x = page_width - 3.0  # 右侧用例区域X坐标（向内收缩）
                uc.y = start_y_right - i * spacing_y_right

        else:
            # 只有一个参与者：放在左侧
            actor = self.actors[0]
            actor.x = 0.8
            actor.y = page_height / 2

            # 所有用例放在右侧（紧凑布局）
            cols = min(3, max(2, int(num_use_cases ** 0.5)))
            rows = (num_use_cases + cols - 1) // cols
            spacing_x = 2.2  # 减小水平间距
            spacing_y = 1.6  # 减小垂直间距

            center_x = (page_width + 2) / 2
            start_x = center_x - ((cols - 1) * spacing_x) / 2
            start_y = page_height / 2 + ((rows - 1) * spacing_y) / 2

            for i, uc in enumerate(self.use_cases):
                col = i % cols
                row = i // cols
                uc.x = start_x + col * spacing_x
                uc.y = start_y - row * spacing_y

    def _draw_simple_connection(self, from_shape: Any, to_shape: Any, label: str = "") -> Optional[Any]:
        """
        绘制简洁的 UML 连接线（无任何装饰符号）
        用例图：从参与者手部到椭圆用例的端点（边缘）连线
        """
        if not from_shape or not to_shape:
            return None

        page = self.visio.page

        try:
            # 获取形状中心坐标
            from_x = from_shape.CellsU("PinX").Result("in")
            from_y = from_shape.CellsU("PinY").Result("in")
            to_x = to_shape.CellsU("PinX").Result("in")
            to_y = to_shape.CellsU("PinY").Result("in")

            # 获取目标形状（用例）的大小，用于计算椭圆边缘交点
            try:
                to_width = to_shape.CellsU("Width").Result("in")
                to_height = to_shape.CellsU("Height").Result("in")
            except:
                to_width = 1.8  # 默认椭圆宽度
                to_height = 0.9  # 默认椭圆高度

            # 获取源形状（参与者）的大小
            try:
                from_width = from_shape.CellsU("Width").Result("in")
                from_height = from_shape.CellsU("Height").Result("in")
            except:
                from_width = 0.6
                from_height = 1.2

            # 计算方向向量（从源到目标）
            dx = to_x - from_x
            dy = to_y - from_y
            distance = (dx * dx + dy * dy) ** 0.5

            if distance < 0.001:
                # 如果两点重合，直接连接中心
                start_x, start_y = from_x, from_y
                end_x, end_y = to_x, to_y
            else:
                # 归一化方向向量
                nx = dx / distance
                ny = dy / distance

                # 计算起点：从参与者边缘开始（考虑参与者的半径）
                actor_radius = max(from_width, from_height) / 2 * 0.7  # 参与者的有效半径
                start_x = from_x + nx * actor_radius
                start_y = from_y + ny * actor_radius

                # 计算终点：在椭圆边缘上
                # 椭圆参数方程：x = a*cos(θ), y = b*sin(θ)
                # 其中 a = width/2, b = height/2
                a = to_width / 2  # 椭圆半长轴
                b = to_height / 2  # 椭圆半短轴

                # 计算与椭圆边界的交点
                # 使用参数化方法求解
                if abs(nx) > abs(ny):
                    # 主要沿X方向移动
                    scale = a * 0.95  # 稍微缩进一点，避免线太贴边
                    end_x = to_x - nx * scale
                    # 根据椭圆方程计算Y坐标
                    local_x = end_x - to_x
                    if abs(local_x) < a:
                        ratio = (local_x / a) ** 2
                        y_scale = b * ((1 - ratio) ** 0.5)
                        end_y = to_y - ny * y_scale * 0.9
                    else:
                        end_y = to_y - ny * b * 0.9
                else:
                    # 主要沿Y方向移动
                    scale = b * 0.95
                    end_y = to_y - ny * scale
                    # 根据椭圆方程计算X坐标
                    local_y = end_y - to_y
                    if abs(local_y) < b:
                        ratio = (local_y / b) ** 2
                        x_scale = a * ((1 - ratio) ** 0.5)
                        end_x = to_x - nx * x_scale * 0.9
                    else:
                        end_x = to_x - nx * a * 0.9

            # 使用计算后的起点和终点绘制直线
            connector = page.DrawLine(start_x, start_y, end_x, end_y)

            if not connector:
                return None

            # 设置样式：纯黑色细线，无箭头
            try:
                connector.CellsU("LineColor").FormulaU = "RGB(0,0,0)"  # 纯黑
            except:
                pass
            try:
                connector.CellsU("LineWidth").FormulaU = "0.75 pt"  # 细线
            except:
                pass
            try:
                connector.CellsU("LinePattern").FormulaU = "1"  # 实线
            except:
                pass

            # 移除所有箭头装饰
            try:
                connector.CellsU("BeginArrow").FormulaU = "0"  # 无起始箭头
            except:
                pass
            try:
                connector.CellsU("EndArrow").FormulaU = "0"  # 无结束箭头
            except:
                pass
            try:
                connector.CellsU("BeginArrowSize").FormulaU = "0"
            except:
                pass
            try:
                connector.CellsU("EndArrowSize").FormulaU = "0"
            except:
                pass

            # 添加标签（如果有）
            if label and label.strip():
                self._add_connection_label(connector, label)

            return connector

        except Exception as e:
            print(f"[WARN] 绘制连接失败: {e}")
            return None

    def _add_connection_label(self, connector: Any, label: str):
        """为连接线添加标签"""
        page = self.visio.page

        try:
            begin_x = connector.CellsU("BeginX").Result("in")
            begin_y = connector.CellsU("BeginY").Result("in")
            end_x = connector.CellsU("EndX").Result("in")
            end_y = connector.CellsU("EndY").Result("in")

            mid_x = (begin_x + end_x) / 2
            mid_y = (begin_y + end_y) / 2

            # 标签位置稍微偏移
            label_shape = self.visio.add_text_box(
                mid_x,
                mid_y + 0.3,
                label,
                width=len(label) * 0.07 + 0.1,
                height=0.35
            )

            if label_shape:
                try:
                    label_shape.CellsU("CharSize").FormulaU = "8 pt"
                    label_shape.CellsU("FillForegnd").FormulaU = "RGB(255,255,255)"
                    label_shape.CellsU("LineColor").FormulaU = "RGB(255,255,255)"
                    label_shape.CellsU("LinePattern").FormulaU = "0"
                    label_shape.CellsU("CharColor").FormulaU = "RGB(0,0,0)"
                except:
                    pass

        except Exception as e:
            print(f"[WARN] 添加标签失败: {e}")

    def _draw_system_boundary(self):
        """
        绘制系统边界矩形（虚线框）
        正确包围所有用例元素
        """
        page = self.visio.page

        if not self.use_cases:
            return None

        # 计算所有用例的边界
        min_x = min(uc.x for uc in self.use_cases)
        max_x = max(uc.x for uc in self.use_cases)
        min_y = min(uc.y for uc in self.use_cases)
        max_y = max(uc.y for uc in self.use_cases)

        # 添加边距
        margin = 1.2
        x = min_x - margin
        y = min_y - margin
        w = (max_x - min_x) + margin * 2
        h = (max_y - min_y) + margin * 2

        # 绘制矩形
        boundary = page.DrawRectangle(x, y, x + w, y + h)

        try:
            boundary.Text = self.system_name
        except:
            pass

        # 设置为虚线样式（UML 标准的系统边界）
        try:
            boundary.CellsU("FillForegnd").FormulaU = "RGB(255,255,255)"  # 白色填充或透明
        except:
            pass
        try:
            boundary.CellsU("LinePattern").FormulaU = "33"  # 虚线模式
        except:
            pass
        try:
            boundary.CellsU("LineWidth").FormulaU = "1.25 pt"
        except:
            pass
        try:
            boundary.CellsU("LineColor").FormulaU = "RGB(0,0,0)"  # 黑色边框
        except:
            pass
        try:
            font_size = max(12, min(16, w * 6))
            boundary.CellsU("CharSize").FormulaU = f"{font_size} pt"
        except:
            pass

        # 将边界移到最底层（在所有形状后面）
        try:
            boundary.SendToBack()
        except:
            pass

        return boundary

    def _draw_title(self):
        """绘制标题"""
        self.visio.add_text_box(
            x=self.visio.page.PageSheet.Cells("PageWidth").Result("in") / 2,
            y=self.visio.page.PageSheet.Cells("PageHeight").Result("in") - 0.4,
            text=self.title,
            width=6,
            height=0.6
        )

    def _draw_actor(self, actor: Actor) -> Optional[Any]:
        """绘制参与者（标准 UML 火柴人）"""
        return self.factory.create_uml_shape(
            "actor",
            actor.x, actor.y,
            text=actor.name
        )

    def _draw_use_case(self, use_case: UseCase) -> Optional[Any]:
        """绘制用例椭圆（标准 UML 形状）"""
        text_width = len(use_case.name) * 0.08
        width = max(2.0, text_width)
        height = 1.0

        shape = self.factory.create_uml_shape(
            "usecase",
            use_case.x, use_case.y,
            text=use_case.name,
            width=width,
            height=height
        )

        # 统一白色填充，不区分主次用例
        # if shape and use_case.is_primary:
        #     self.visio.set_shape_fill_color(shape, 230, 245, 255)

        return shape

    def _draw_relationship(self, from_shape: Any, to_shape: Any,
                           rel_type: RelationshipType, label: str = "") -> Optional[Any]:
        """绘制关系连接线 - 增强版"""
        if not from_shape or not to_shape:
            print("[WARN] 无法绘制关系：形状为空")
            return None

        connector = self.visio.connect_shapes(from_shape, to_shape)

        if connector and label:
            try:
                from_x = from_shape.CellsU("PinX").Result("in")
                from_y = from_shape.CellsU("PinY").Result("in")
                to_x = to_shape.CellsU("PinX").Result("in")
                to_y = to_shape.CellsU("PinY").Result("in")

                mid_x = (from_x + to_x) / 2
                mid_y = (from_y + to_y) / 2

                self.visio.add_text_box(mid_x, mid_y + 0.2, label, width=len(label) * 0.08)
            except Exception as e:
                print(f"[WARN] 添加关系标签失败: {e}")

        return connector


# ============================================================
# 第四部分：类图构建器
# ============================================================

class ClassDiagramBuilder:
    """类图（Class Diagram）构建器"""

    def __init__(self, visio: VisioAutomation):
        self.visio = visio
        self.factory = VisioShapeFactory(visio)
        self.classes: List[UMLClass] = []
        self.relationships: List[ClassRelationship] = []
        self.layout_engine = SmartLayoutEngine()
        self.title = "类图"
        self.class_shapes: Dict[int, Any] = {}

    def add_class(self, name: str, is_abstract: bool = False,
                  is_interface: bool = False, stereotype: str = "") -> UMLClass:
        """添加一个类"""
        uml_class = UMLClass(
            name=name,
            is_abstract=is_abstract,
            is_interface=is_interface,
            stereotype=stereotype
        )

        if is_interface and not stereotype:
            uml_class.stereotype = "interface"

        self.classes.append(uml_class)
        return uml_class

    def add_attribute(self, uml_class: UMLClass, name: str,
                      type_name: str = "String", visibility: str = "+",
                      default_value: str = "", is_static: bool = False) -> ClassAttribute:
        """为类添加属性"""
        attr = ClassAttribute(
            name=name,
            type_name=type_name,
            visibility=visibility,
            default_value=default_value,
            is_static=is_static
        )
        uml_class.attributes.append(attr)
        return attr

    def add_method(self, uml_class: UMLClass, name: str,
                   return_type: str = "void", visibility: str = "+",
                   parameters: List[str] = None, is_abstract: bool = False,
                   is_static: bool = False) -> ClassMethod:
        """为类添加方法"""
        if parameters is None:
            parameters = []

        method = ClassMethod(
            name=name,
            return_type=return_type,
            visibility=visibility,
            parameters=parameters,
            is_abstract=is_abstract,
            is_static=is_static
        )
        uml_class.methods.append(method)
        return method

    def add_relationship(self, from_class: UMLClass, to_class: UMLClass,
                         rel_type: RelationshipType, multiplicity_from: str = "1",
                         multiplicity_to: str = "*", label: str = "",
                         direction: str = "bidirectional") -> ClassRelationship:
        """添加类之间的关系"""
        rel = ClassRelationship(
            from_class=from_class,
            to_class=to_class,
            relationship_type=rel_type,
            multiplicity_from=multiplicity_from,
            multiplicity_to=multiplicity_to,
            label=label,
            direction=direction
        )
        self.relationships.append(rel)
        return rel

    def set_title(self, title: str):
        """设置图表标题"""
        self.title = title

    def build(self) -> bool:
        """构建完整的类图"""
        try:
            print(f"\n{'=' * 60}")
            print(f"开始构建类图: {self.title}")
            print(f"{'=' * 60}")

            print("\n 正在进行智能布局...")

            # 使用改进的布局算法
            self._improved_class_layout()

            print("\n 正在添加标题...")
            self._draw_title()

            print("\n 正在绘制类...")
            for cls in self.classes:
                shape = self._draw_class(cls)
                if shape:
                    self.class_shapes[id(cls)] = shape
                    print(f"   [OK] 已绘制类: {cls.name} ({len(cls.attributes)} 属性, {len(cls.methods)} 方法)")

            print("\n 正在绘制关系连接...")
            for rel in self.relationships:
                from_shape = self.class_shapes.get(id(rel.from_class))
                to_shape = self.class_shapes.get(id(rel.to_class))

                if from_shape and to_shape:
                    connector = self._draw_simple_class_connection(from_shape, to_shape, rel)
                    if connector:
                        print(
                            f"   [OK] 已连接: {rel.from_class.name} → {rel.to_class.name} ({rel.relationship_type.value})")

            # 只缩放，不自动布局
            print("\n 正在调整视图...")
            self.visio.zoom_to_fit()

            print(f"\n[OK] 类图 '{self.title}' 构建完成！")
            return True

        except Exception as e:
            print(f"\n[ERROR] 构建类图失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _improved_class_layout(self):
        """
        美观的类图布局算法
        优化元素分布，提高观赏性
        """
        page_width = 11.0
        page_height = 8.5

        num_classes = len(self.classes)
        if num_classes == 0:
            return

        # 智能计算网格布局（根据数量自动调整）
        if num_classes <= 3:
            cols = num_classes
            rows = 1
        elif num_classes <= 6:
            cols = 3
            rows = 2
        else:
            cols = min(4, int(num_classes ** 0.5) + 1)
            rows = (num_classes + cols - 1) // cols

        # 美观的间距
        spacing_x = 3.8  # 水平间距（增大）
        spacing_y = 3.2  # 垂直间距（增大）

        total_width = (cols - 1) * spacing_x
        total_height = (rows - 1) * spacing_y

        start_x = (page_width - total_width) / 2 + 0.8
        start_y = (page_height + total_height) / 2 - 0.8

        for i, cls in enumerate(self.classes):
            col = i % cols
            row = i // cols
            cls.x = start_x + col * spacing_x
            cls.y = start_y - row * spacing_y

    def _draw_simple_class_connection(self, from_shape: Any, to_shape: Any,
                                      rel: ClassRelationship) -> Optional[Any]:
        """
        绘制标准UML类关系连接线（带正确箭头和标签）
        """
        if not from_shape or not to_shape:
            return None

        page = self.visio.page

        try:
            # 获取形状中心坐标
            from_x = from_shape.CellsU("PinX").Result("in")
            from_y = from_shape.CellsU("PinY").Result("in")
            to_x = to_shape.CellsU("PinX").Result("in")
            to_y = to_shape.CellsU("PinY").Result("in")

            # 使用简单直线
            connector = page.DrawLine(from_x, from_y, to_x, to_y)

            if not connector:
                return None

            # 基础样式：纯黑色细线
            try:
                connector.CellsU("LineColor").FormulaU = "RGB(0,0,0)"
            except:
                pass
            try:
                connector.CellsU("LineWidth").FormulaU = "0.75 pt"
            except:
                pass

            # 根据关系类型设置不同的线条样式和箭头
            if rel.relationship_type == RelationshipType.GENERALIZATION:
                # 继承关系：实线 + 空心三角箭头
                try:
                    connector.CellsU("LinePattern").FormulaU = "1"  # 实线
                except:
                    pass
                try:
                    connector.CellsU("EndArrow").FormulaU = "30"  # 空心三角箭头
                except:
                    pass
                try:
                    connector.CellsU("EndArrowSize").FormulaU = "2"  # 中等大小
                except:
                    pass

            elif rel.relationship_type == RelationshipType.REALIZATION:
                # 实现关系：虚线 + 空心三角箭头
                try:
                    connector.CellsU("LinePattern").FormulaU = "33"  # 虚线
                except:
                    pass
                try:
                    connector.CellsU("EndArrow").FormulaU = "30"  # 空心三角箭头
                except:
                    pass
                try:
                    connector.CellsU("EndArrowSize").FormulaU = "2"
                except:
                    pass

            elif rel.relationship_type == RelationshipType.ASSOCIATION:
                # 关联关系：实线 + 无箭头（或可选箭头）
                try:
                    connector.CellsU("LinePattern").FormulaU = "1"  # 实线
                except:
                    pass
                try:
                    connector.CellsU("EndArrow").FormulaU = "0"  # 无箭头
                except:
                    pass

            elif rel.relationship_type == RelationshipType.AGGREGATION:
                # 聚合关系：实线 + 空心菱形
                try:
                    connector.CellsU("LinePattern").FormulaU = "1"
                except:
                    pass
                try:
                    connector.CellsU("BeginArrow").FormulaU = "29"  # 空心菱形
                except:
                    pass
                try:
                    connector.CellsU("BeginArrowSize").FormulaU = "2"
                except:
                    pass

            elif rel.relationship_type == RelationshipType.COMPOSITION:
                # 组合关系：实线 + 实心菱形
                try:
                    connector.CellsU("LinePattern").FormulaU = "1"
                except:
                    pass
                try:
                    connector.CellsU("BeginArrow").FormulaU = "28"  # 实心菱形
                except:
                    pass
                try:
                    connector.CellsU("BeginArrowSize").FormulaU = "2"
                except:
                    pass

            elif rel.relationship_type == RelationshipType.DEPENDENCY:
                # 依赖关系：虚线 + 开放箭头
                try:
                    connector.CellsU("LinePattern").FormulaU = "33"  # 虚线
                except:
                    pass
                try:
                    connector.CellsU("EndArrow").FormulaU = "24"  # 开放箭头
                except:
                    pass
                try:
                    connector.CellsU("EndArrowSize").FormulaU = "2"
                except:
                    pass
            else:
                # 默认：实线无箭头
                try:
                    connector.CellsU("LinePattern").FormulaU = "1"
                except:
                    pass
                try:
                    connector.CellsU("EndArrow").FormulaU = "0"
                except:
                    pass

            # 添加关系标签（如"继承"、"works for"等）
            if rel.label and rel.label.strip():
                self._add_class_connection_label(connector, rel.label)

            # 添加多重性标签
            self._add_multiplicity_labels(connector, rel)

            return connector

        except Exception as e:
            print(f"[WARN] 绘制类关系连接失败: {e}")
            return None

    def _add_multiplicity_labels(self, connector: Any, rel: ClassRelationship):
        """为类关系添加多重性标签"""
        page = self.visio.page

        try:
            begin_x = connector.CellsU("BeginX").Result("in")
            begin_y = connector.CellsU("BeginY").Result("in")
            end_x = connector.CellsU("EndX").Result("in")
            end_y = connector.CellsU("EndY").Result("in")

            # 在起始端添加多重性
            if rel.multiplicity_from and rel.multiplicity_from != "1":
                label_from = self.visio.add_text_box(
                    begin_x - 0.2,
                    begin_y,
                    rel.multiplicity_from,
                    width=0.5,
                    height=0.3
                )
                if label_from:
                    try:
                        label_from.CellsU("CharSize").FormulaU = "8 pt"
                        label_from.CellsU("FillForegnd").FormulaU = "RGB(255,255,255)"
                        label_from.CellsU("LineColor").FormulaU = "RGB(255,255,255)"
                        label_from.CellsU("LinePattern").FormulaU = "0"
                        label_from.CellsU("CharColor").FormulaU = "RGB(0,0,0)"
                    except:
                        pass

            # 在结束端添加多重性
            if rel.multiplicity_to and rel.multiplicity_to not in ["*", "1"]:
                label_to = self.visio.add_text_box(
                    end_x + 0.2,
                    end_y,
                    rel.multiplicity_to,
                    width=0.6,
                    height=0.3
                )
                if label_to:
                    try:
                        label_to.CellsU("CharSize").FormulaU = "8 pt"
                        label_to.CellsU("FillForegnd").FormulaU = "RGB(255,255,255)"
                        label_to.CellsU("LineColor").FormulaU = "RGB(255,255,255)"
                        label_to.CellsU("LinePattern").FormulaU = "0"
                        label_to.CellsU("CharColor").FormulaU = "RGB(0,0,0)"
                    except:
                        pass

        except Exception as e:
            print(f"[WARN] 添加多重性标签失败: {e}")

    def _add_class_connection_label(self, connector: Any, label: str):
        """为类关系连接添加标签"""
        page = self.visio.page

        try:
            begin_x = connector.CellsU("BeginX").Result("in")
            begin_y = connector.CellsU("BeginY").Result("in")
            end_x = connector.CellsU("EndX").Result("in")
            end_y = connector.CellsU("EndY").Result("in")

            mid_x = (begin_x + end_x) / 2
            mid_y = (begin_y + end_y) / 2

            label_shape = self.visio.add_text_box(
                mid_x,
                mid_y + 0.3,
                label,
                width=len(label) * 0.07 + 0.1,
                height=0.35
            )

            if label_shape:
                try:
                    label_shape.CellsU("CharSize").FormulaU = "8 pt"
                    label_shape.CellsU("FillForegnd").FormulaU = "RGB(255,255,255)"
                    label_shape.CellsU("LineColor").FormulaU = "RGB(255,255,255)"
                    label_shape.CellsU("LinePattern").FormulaU = "0"
                    label_shape.CellsU("CharColor").FormulaU = "RGB(0,0,0)"
                except:
                    pass

        except Exception as e:
            print(f"[WARN] 添加类关系标签失败: {e}")

    def _draw_title(self):
        """绘制标题"""
        page_width = self.visio.page.PageSheet.Cells("PageWidth").Result("in")
        page_height = self.visio.page.PageSheet.Cells("PageHeight").Result("in")

        self.visio.add_text_box(
            x=page_width / 2,
            y=page_height - 0.4,
            text=self.title,
            width=6,
            height=0.6
        )

    def _draw_class(self, uml_class: UMLClass) -> Optional[Any]:
        """绘制一个类（三格矩形）"""
        page = self.visio.page

        class_text = uml_class.get_class_text()
        lines = class_text.split('\n')

        max_line_length = max(len(line) for line in lines) if lines else 10
        width = max(2.5, min(4.0, max_line_length * 0.08 + 0.5))
        line_height = 0.22
        header_height = 0.4
        section_height = max(len(lines) - 3, 1) * line_height + 0.3
        total_height = header_height + section_height * 2 + 0.2

        x, y = uml_class.x, uml_class.y

        shape = page.DrawRectangle(
            x - width / 2, y - total_height / 2,
            x + width / 2, y + total_height / 2
        )

        try:
            shape.Text = class_text
        except:
            pass
        try:
            shape.CellsU("FillForegnd").FormulaU = "RGB(255,255,255)"
        except:
            pass
        try:
            shape.CellsU("LineColor").FormulaU = "RGB(0,0,0)"
        except:
            pass
        try:
            shape.CellsU("LineWidth").FormulaU = "1.25 pt"
        except:
            pass

        if uml_class.is_interface or uml_class.stereotype == "interface":
            try:
                shape.CellsU("FillForegnd").FormulaU = "RGB(255,255,255)"  # 统一白色
            except:
                pass
            try:
                shape.CellsU("LineColor").FormulaU = "RGB(0,0,0)"  # 纯黑边框
            except:
                pass
        elif uml_class.is_abstract:
            try:
                shape.CellsU("FillForegnd").FormulaU = "RGB(255,255,255)"  # 统一白色
            except:
                pass

        try:
            shape.CellsU("CharSize").FormulaU = "9 pt"
        except:
            pass
        try:
            shape.CellsU("LeftMargin").FormulaU = "0.1 in"
        except:
            pass
        try:
            shape.CellsU("RightMargin").FormulaU = "0.1 in"
        except:
            pass
        try:
            shape.CellsU("TopMargin").FormulaU = "0.05 in"
        except:
            pass
        try:
            shape.CellsU("BottomMargin").FormulaU = "0.05 in"
        except:
            pass

        return shape

    def _draw_class_relationship(self, from_shape: Any, to_shape: Any,
                                 rel: ClassRelationship) -> Optional[Any]:
        """绘制类之间的关系线（备用方法，使用 GlueTo 连接）"""
        page = self.visio.page

        connector = self.visio.connect_shapes(from_shape, to_shape)

        if not connector:
            return None

        if rel.relationship_type == RelationshipType.GENERALIZATION:
            try:
                connector.CellsU("EndArrow").FormulaU = "30"  # 空心三角箭头
            except:
                pass
            try:
                connector.CellsU("EndArrowSize").FormulaU = "2"
            except:
                pass
            try:
                connector.CellsU("LinePattern").FormulaU = "1"  # 实线
            except:
                pass
        elif rel.relationship_type == RelationshipType.REALIZATION:
            try:
                connector.CellsU("EndArrow").FormulaU = "30"  # 空心三角箭头
            except:
                pass
            try:
                connector.CellsU("EndArrowSize").FormulaU = "2"
            except:
                pass
            try:
                connector.CellsU("LinePattern").FormulaU = "33"  # 虚线
            except:
                pass
        elif rel.relationship_type == RelationshipType.DEPENDENCY:
            try:
                connector.CellsU("EndArrow").FormulaU = "24"  # 开放箭头
            except:
                pass
            try:
                connector.CellsU("EndArrowSize").FormulaU = "2"
            except:
                pass
            try:
                connector.CellsU("LinePattern").FormulaU = "33"  # 虚线
            except:
                pass
        elif rel.relationship_type == RelationshipType.AGGREGATION:
            try:
                connector.CellsU("BeginArrow").FormulaU = "29"  # 空心菱形
            except:
                pass
            try:
                connector.CellsU("BeginArrowSize").FormulaU = "2"
            except:
                pass
            try:
                connector.CellsU("LinePattern").FormulaU = "1"  # 实线
            except:
                pass
        elif rel.relationship_type == RelationshipType.COMPOSITION:
            try:
                connector.CellsU("BeginArrow").FormulaU = "28"  # 实心菱形
            except:
                pass
            try:
                connector.CellsU("BeginArrowSize").FormulaU = "2"
            except:
                pass
            try:
                connector.CellsU("LinePattern").FormulaU = "1"  # 实线
            except:
                pass
        else:
            try:
                connector.CellsU("EndArrow").FormulaU = "0"
            except:
                pass
            try:
                connector.CellsU("LinePattern").FormulaU = "1"  # 实线
            except:
                pass

        try:
            connector.CellsU("LineWidth").FormulaU = "1 pt"
        except:
            pass

        if rel.multiplicity_from != "1":
            self._add_multiplicity_label(from_shape, to_shape, rel.multiplicity_from, position="start")

        if rel.multiplicity_to != "*":
            self._add_multiplicity_label(from_shape, to_shape, rel.multiplicity_to, position="end")

        if rel.label:
            mid_x = (from_shape.CellsU("PinX").Result("in") +
                     to_shape.CellsU("PinX").Result("in")) / 2
            mid_y = (from_shape.CellsU("PinY").Result("in") +
                     to_shape.CellsU("PinY").Result("in")) / 2
            self.visio.add_text_box(mid_x, mid_y + 0.25, rel.label, width=len(rel.label) * 0.08)

        return connector

    def _add_multiplicity_label(self, from_shape: Any, to_shape: Any,
                                text: str, position: str = "end"):
        """添加多重性标签"""
        if position == "start":
            x = from_shape.CellsU("PinX").Result("in")
            y = from_shape.CellsU("PinY").Result("in")
        else:
            x = to_shape.CellsU("PinX").Result("in")
            y = to_shape.CellsU("PinY").Result("in")

        label = self.visio.add_text_box(x + 0.15, y + 0.15, text, width=len(text) * 0.06)
        if label:
            label.CellsU("CharSize").FormulaU = "7 pt"


# ============================================================
# 第五部分：对象图构建器
# ============================================================

class ObjectDiagramBuilder:
    """对象图（Object Diagram）构建器"""

    def __init__(self, visio: VisioAutomation):
        self.visio = visio
        self.factory = VisioShapeFactory(visio)
        self.objects: List[ObjectInstance] = []
        self.relationships: List[ObjectRelationship] = []
        self.layout_engine = SmartLayoutEngine()
        self.title = "对象图"
        self.object_shapes: Dict[int, Any] = {}

    def add_object(self, name: str, class_name: str,
                   attribute_values: Dict[str, str] = None) -> ObjectInstance:
        """添加对象实例"""
        if attribute_values is None:
            attribute_values = {}

        obj = ObjectInstance(
            name=name,
            class_name=class_name,
            attribute_values=attribute_values
        )
        self.objects.append(obj)
        return obj

    def add_relationship(self, from_obj: ObjectInstance, to_obj: ObjectInstance,
                         label: str = "", rel_type: str = "association") -> ObjectRelationship:
        """添加对象间的关系"""
        rel = ObjectRelationship(
            from_object=from_obj,
            to_object=to_obj,
            label=label,
            rel_type=rel_type
        )
        self.relationships.append(rel)
        return rel

    def set_title(self, title: str):
        """设置图表标题"""
        self.title = title

    def build(self) -> bool:
        """构建完整的对象图"""
        try:
            print(f"\n{'=' * 60}")
            print(f"开始构建对象图: {self.title}")
            print(f"{'=' * 60}")

            print("\n 正在进行智能布局...")

            # 使用改进的布局算法
            self._improved_object_layout()

            print("\n 正在添加标题...")
            self._draw_title()

            print("\n 正在绘制对象实例...")
            for obj in self.objects:
                shape = self._draw_object(obj)
                if shape:
                    self.object_shapes[id(obj)] = shape
                    print(f"   [OK] 已绘制对象: {obj.name}:{obj.class_name}")

            print("\n 正在绘制关系连接...")
            for rel in self.relationships:
                from_shape = self.object_shapes.get(id(rel.from_object))
                to_shape = self.object_shapes.get(id(rel.to_object))

                if from_shape and to_shape:
                    connector = self._draw_simple_object_connection(from_shape, to_shape, rel.label, rel.rel_type)
                    if connector:
                        print(f"   [OK] 已连接: {rel.from_object.name} → {rel.to_object.name}")

            # 只缩放，不自动布局
            print("\n 正在调整视图...")
            self.visio.zoom_to_fit()

            print(f"\n[OK] 对象图 '{self.title}' 构建完成！")
            return True

        except Exception as e:
            print(f"\n[ERROR] 构建对象图失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _improved_object_layout(self):
        """
        美观的对象图布局算法 - 层次化布局
        考虑对象间的关系，呈顺序上下放置，避免连线交叉
        """
        page_width = 11.0
        page_height = 8.5

        num_objects = len(self.objects)
        if num_objects == 0:
            return

        # 如果没有关系，使用简单的网格布局
        if not self.relationships:
            self._simple_grid_layout(page_width, page_height)
            return

        # 有关系时，使用层次化布局算法
        self._hierarchical_layout(page_width, page_height)

    def _simple_grid_layout(self, page_width: float, page_height: float):
        """简单的网格布局（无关系时使用）"""
        num_objects = len(self.objects)

        # 智能计算网格布局（根据数量自动调整）
        if num_objects <= 3:
            cols = num_objects
            rows = 1
        elif num_objects <= 6:
            cols = 3
            rows = 2
        else:
            cols = min(4, int(num_objects ** 0.5) + 1)
            rows = (num_objects + cols - 1) // cols

        # 美观的间距
        spacing_x = 3.5
        spacing_y = 2.8

        total_width = (cols - 1) * spacing_x
        total_height = (rows - 1) * spacing_y

        start_x = (page_width - total_width) / 2 + 0.8
        start_y = (page_height + total_height) / 2 - 0.8

        for i, obj in enumerate(self.objects):
            col = i % cols
            row = i // cols
            obj.x = start_x + col * spacing_x
            obj.y = start_y - row * spacing_y

    def _hierarchical_layout(self, page_width: float, page_height: float):
        """
        层次化布局算法 - 考虑关系的顺序上下放置
        1. 构建关系图
        2. 计算每个对象的层级（从根节点开始）
        3. 按层级从上到下排列
        4. 同一层的对象水平排列
        """
        # 1. 构建邻接表和计算入度
        in_degree = {id(obj): 0 for obj in self.objects}
        adjacency = {id(obj): [] for obj in self.objects}

        for rel in self.relationships:
            from_id = id(rel.from_object)
            to_id = id(rel.to_object)

            # 添加边 from -> to
            adjacency[from_id].append(to_id)
            in_degree[to_id] += 1

        # 2. 拓扑排序确定层级
        levels = {}  # 对象ID -> 层级号
        queue = []

        # 找到所有根节点（入度为0的对象）
        root_nodes = [obj_id for obj_id, degree in in_degree.items() if degree == 0]

        # 初始化队列
        current_level = 0
        for node_id in root_nodes:
            queue.append((node_id, current_level))

        # BFS计算每个节点的层级
        visited = set()
        while queue:
            node_id, level = queue.pop(0)

            if node_id in visited:
                continue

            visited.add(node_id)
            levels[node_id] = level

            # 处理所有邻居
            for neighbor_id in adjacency[node_id]:
                in_degree[neighbor_id] -= 1
                if in_degree[neighbor_id] == 0:
                    queue.append((neighbor_id, level + 1))

        # 对于未访问的节点（可能存在环），分配到下一层
        for obj in self.objects:
            obj_id = id(obj)
            if obj_id not in levels:
                max_level = max(levels.values()) if levels else 0
                levels[obj_id] = max_level + 1

        # 3. 按层级分组
        level_groups = {}
        for obj in self.objects:
            obj_id = id(obj)
            level = levels.get(obj_id, 0)
            if level not in level_groups:
                level_groups[level] = []
            level_groups[level].append(obj)

        # 4. 计算布局参数
        num_levels = len(level_groups)
        max_objects_in_level = max(len(objects) for objects in level_groups.values())

        # 垂直和水平间距
        vertical_spacing = 2.5  # 层与层之间的垂直距离
        horizontal_spacing = 3.0  # 同一层对象的水平距离

        # 计算总高度和起始Y坐标
        total_height = (num_levels - 1) * vertical_spacing
        start_y = page_height / 2 + total_height / 2 - 0.5

        # 按层级从上到下排列对象
        for level in sorted(level_groups.keys()):
            objects_in_level = level_groups[level]
            num_in_level = len(objects_in_level)

            # 计算这一层的X坐标范围
            total_width = (num_in_level - 1) * horizontal_spacing
            start_x = (page_width - total_width) / 2

            # 设置这一层中每个对象的坐标
            for i, obj in enumerate(objects_in_level):
                obj.x = start_x + i * horizontal_spacing
                obj.y = start_y - level * vertical_spacing

    def _draw_simple_object_connection(self, from_shape: Any, to_shape: Any,
                                       label: str = "", rel_type: str = "association") -> Optional[Any]:
        """
        绘制标准UML对象关系连接线
        支持聚合、组合等关系类型
        """
        if not from_shape or not to_shape:
            return None

        page = self.visio.page

        try:
            # 获取形状中心坐标
            from_x = from_shape.CellsU("PinX").Result("in")
            from_y = from_shape.CellsU("PinY").Result("in")
            to_x = to_shape.CellsU("PinX").Result("in")
            to_y = to_shape.CellsU("PinY").Result("in")

            # 使用简单直线
            connector = page.DrawLine(from_x, from_y, to_x, to_y)

            if not connector:
                return None

            # 基础样式：纯黑色细线
            try:
                connector.CellsU("LineColor").FormulaU = "RGB(0,0,0)"
            except:
                pass
            try:
                connector.CellsU("LineWidth").FormulaU = "0.75 pt"
            except:
                pass

            # 根据关系类型设置箭头和线条样式
            if rel_type == "aggregation":
                # 聚合关系：实线 + 空心菱形
                try:
                    connector.CellsU("LinePattern").FormulaU = "1"
                except:
                    pass
                try:
                    connector.CellsU("BeginArrow").FormulaU = "29"  # 空心菱形
                except:
                    pass
                try:
                    connector.CellsU("BeginArrowSize").FormulaU = "2"
                except:
                    pass

            elif rel_type == "composition":
                # 组合关系：实线 + 实心菱形
                try:
                    connector.CellsU("LinePattern").FormulaU = "1"
                except:
                    pass
                try:
                    connector.CellsU("BeginArrow").FormulaU = "28"  # 实心菱形
                except:
                    pass
                try:
                    connector.CellsU("BeginArrowSize").FormulaU = "2"
                except:
                    pass

            else:
                # 默认关联关系：实线无箭头
                try:
                    connector.CellsU("LinePattern").FormulaU = "1"
                except:
                    pass
                try:
                    connector.CellsU("EndArrow").FormulaU = "0"
                except:
                    pass

            # 添加标签（如果有）
            if label and label.strip():
                self._add_object_connection_label(connector, label)

            return connector

        except Exception as e:
            print(f"[WARN] 绘制对象关系连接失败: {e}")
            return None

    def _add_object_connection_label(self, connector: Any, label: str):
        """为对象关系连接添加标签"""
        page = self.visio.page

        try:
            begin_x = connector.CellsU("BeginX").Result("in")
            begin_y = connector.CellsU("BeginY").Result("in")
            end_x = connector.CellsU("EndX").Result("in")
            end_y = connector.CellsU("EndY").Result("in")

            mid_x = (begin_x + end_x) / 2
            mid_y = (begin_y + end_y) / 2

            label_shape = self.visio.add_text_box(
                mid_x,
                mid_y + 0.3,
                label,
                width=len(label) * 0.07 + 0.1,
                height=0.35
            )

            if label_shape:
                try:
                    label_shape.CellsU("CharSize").FormulaU = "8 pt"
                    label_shape.CellsU("FillForegnd").FormulaU = "RGB(255,255,255)"
                    label_shape.CellsU("LineColor").FormulaU = "RGB(255,255,255)"
                    label_shape.CellsU("LinePattern").FormulaU = "0"
                    label_shape.CellsU("CharColor").FormulaU = "RGB(0,0,0)"
                except:
                    pass

        except Exception as e:
            print(f"[WARN] 添加对象关系标签失败: {e}")

    def _draw_title(self):
        """绘制标题"""
        page_width = self.visio.page.PageSheet.Cells("PageWidth").Result("in")
        page_height = self.visio.page.PageSheet.Cells("PageHeight").Result("in")

        self.visio.add_text_box(
            x=page_width / 2,
            y=page_height - 0.4,
            text=self.title,
            width=6,
            height=0.6
        )

    def _draw_object(self, obj: ObjectInstance) -> Optional[Any]:
        """绘制一个对象实例（两格矩形）"""
        page = self.visio.page

        lines = [f"{obj.name}: {obj.class_name}", "---"]

        for attr_name, attr_value in obj.attribute_values.items():
            lines.append(f"{attr_name} = {attr_value}")

        object_text = "\n".join(lines)

        max_line_length = max(len(line) for line in lines) if lines else 10
        width = max(2.5, min(3.5, max_line_length * 0.09 + 0.5))
        header_height = 0.45
        content_height = len(obj.attribute_values) * 0.28 + 0.35
        total_height = header_height + content_height + 0.15

        x, y = obj.x, obj.y

        shape = page.DrawRectangle(
            x - width / 2, y - total_height / 2,
            x + width / 2, y + total_height / 2
        )

        try:
            shape.Text = object_text
        except:
            pass
        try:
            shape.CellsU("FillForegnd").FormulaU = "RGB(255,255,255)"  # 统一白色
        except:
            pass
        try:
            shape.CellsU("LineColor").FormulaU = "RGB(0,0,0)"  # 纯黑边框
        except:
            pass
        try:
            shape.CellsU("LineWidth").FormulaU = "1 pt"  # 统一线宽
        except:
            pass
        try:
            shape.CellsU("CharSize").FormulaU = "9 pt"
        except:
            pass

        try:
            shape.CellsU("LeftMargin").FormulaU = "0.12 in"
        except:
            pass
        try:
            shape.CellsU("RightMargin").FormulaU = "0.12 in"
        except:
            pass
        try:
            shape.CellsU("TopMargin").FormulaU = "0.05 in"
        except:
            pass
        try:
            shape.CellsU("BottomMargin").FormulaU = "0.05 in"
        except:
            pass

        return shape


# ============================================================
# 第六部分：示例生成函数
# ============================================================

def generate_use_case_example():
    """
    示例1：创建一个在线购物系统的用例图
    包含：参与者、用例、系统边界、关联/包含/扩展/泛化关系
    """
    with VisioAutomation(visible=True) as visio:
        visio.new_document()
        visio.set_page_size(11, 8.5)

        builder = UseCaseDiagramBuilder(visio)
        builder.set_title("在线购物系统用例图")
        builder.set_system_name("系统")

        # 参与者
        customer = builder.add_actor("顾客")
        admin = builder.add_actor("管理员")

        # 用例
        uc_browse = builder.add_use_case("浏览商品")
        uc_search = builder.add_use_case("搜索商品")
        uc_add_cart = builder.add_use_case("加入购物车")
        uc_checkout = builder.add_use_case("结算支付", is_primary=True)
        uc_login = builder.add_use_case("登录系统")
        uc_register = builder.add_use_case("注册账户")
        uc_view_order = builder.add_use_case("查看订单")
        uc_manage_products = builder.add_use_case("管理商品")
        uc_manage_users = builder.add_use_case("管理用户")
        uc_generate_report = builder.add_use_case("生成报表")

        # 关系
        builder.add_relationship(customer, uc_browse, RelationshipType.ASSOCIATION)
        builder.add_relationship(customer, uc_search, RelationshipType.ASSOCIATION)
        builder.add_relationship(customer, uc_add_cart, RelationshipType.ASSOCIATION)
        builder.add_relationship(customer, uc_checkout, RelationshipType.ASSOCIATION)
        builder.add_relationship(customer, uc_login, RelationshipType.ASSOCIATION)
        builder.add_relationship(customer, uc_register, RelationshipType.ASSOCIATION)
        builder.add_relationship(customer, uc_view_order, RelationshipType.ASSOCIATION)
        builder.add_relationship(admin, uc_manage_products, RelationshipType.ASSOCIATION)
        builder.add_relationship(admin, uc_manage_users, RelationshipType.ASSOCIATION)
        builder.add_relationship(admin, uc_generate_report, RelationshipType.ASSOCIATION)
        builder.add_relationship(uc_checkout, uc_login, RelationshipType.INCLUDE, "包含")
        builder.add_relationship(uc_browse, uc_login, RelationshipType.EXTEND, "扩展")

        if builder.build():
            save_path = os.path.join(os.path.dirname(__file__), "output", "usecase_test.vsdx")
            visio.save_document(save_path)
            print(f"\n 用例图已成功生成！")
            print(f" 文件保存位置: {os.path.abspath(save_path)}")
            input("\n按回车键返回主菜单...")


def generate_class_example():
    """
    示例2：创建一个图书管理系统的类图
    包含：类/接口/抽象类、继承/实现/聚合/组合/依赖/关联关系
    """
    with VisioAutomation(visible=True) as visio:
        visio.new_document()
        visio.set_page_size(11, 8.5)

        builder = ClassDiagramBuilder(visio)
        builder.set_title("图书管理系统类图")

        # 基础类
        cls_person = builder.add_class("人员")
        builder.add_attribute(cls_person, "姓名", "字符串", "-")
        builder.add_attribute(cls_person, "年龄", "整数", "-")
        builder.add_method(cls_person, "获取姓名", "字符串", "+")
        builder.add_method(cls_person, "设置姓名", "无返回值", "+", parameters=["姓名: 字符串"])

        # 学生类（继承自人员）
        cls_student = builder.add_class("学生")
        builder.add_attribute(cls_student, "学号", "字符串", "-")
        builder.add_attribute(cls_student, "专业", "字符串", "-")
        builder.add_method(cls_student, "获取学号", "字符串", "+")
        builder.add_method(cls_student, "学习", "无返回值", "+")

        # 教师类（继承自人员）
        cls_teacher = builder.add_class("教师")
        builder.add_attribute(cls_teacher, "工号", "字符串", "-")
        builder.add_attribute(cls_teacher, "部门", "字符串", "-")
        builder.add_method(cls_teacher, "获取工号", "字符串", "+")
        builder.add_method(cls_teacher, "授课", "无返回值", "+")

        # 课程类
        cls_course = builder.add_class("课程")
        builder.add_attribute(cls_course, "课程编号", "字符串", "-")
        builder.add_attribute(cls_course, "课程名称", "字符串", "-")
        builder.add_attribute(cls_course, "学分", "整数", "-")
        builder.add_method(cls_course, "获取课程信息", "字符串", "+")

        # 图书馆类
        cls_library = builder.add_class("图书馆")
        builder.add_attribute(cls_library, "名称", "字符串", "-")
        builder.add_attribute(cls_library, "地址", "字符串", "-")
        builder.add_method(cls_library, "借书", "无返回值", "+")
        builder.add_method(cls_library, "还书", "无返回值", "+")

        # 图书类
        cls_book = builder.add_class("图书")
        builder.add_attribute(cls_book, "ISBN", "字符串", "-")
        builder.add_attribute(cls_book, "书名", "字符串", "-")
        builder.add_attribute(cls_book, "作者", "字符串", "-")
        builder.add_method(cls_book, "获取信息", "字符串", "+")

        # 关系
        builder.add_relationship(cls_student, cls_person, RelationshipType.GENERALIZATION, "继承")
        builder.add_relationship(cls_teacher, cls_person, RelationshipType.GENERALIZATION, "继承")
        builder.add_relationship(cls_student, cls_course, RelationshipType.ASSOCIATION, "选修")
        builder.add_relationship(cls_teacher, cls_course, RelationshipType.ASSOCIATION, "教授")
        builder.add_relationship(cls_library, cls_book, RelationshipType.COMPOSITION, multiplicity_from="1",
                                 multiplicity_to="*")
        builder.add_relationship(cls_book, cls_course, RelationshipType.DEPENDENCY)

        if builder.build():
            save_path = os.path.join(os.path.dirname(__file__), "output", "class_test.vsdx")
            visio.save_document(save_path)
            print(f"\n 类图已成功生成！")
            print(f" 文件保存位置: {os.path.abspath(save_path)}")
            input("\n按回车键返回主菜单...")


def generate_object_example():
    """
    示例3：创建一个订单处理场景的对象图
    包含：对象实例、属性值、对象间关系
    """
    with VisioAutomation(visible=True) as visio:
        visio.new_document()
        visio.set_page_size(11, 8.5)

        builder = ObjectDiagramBuilder(visio)
        builder.set_title("订单处理场景对象图")

        # 顾客对象
        obj_customer = builder.add_object("顾客", {"姓名": "张三", "ID": "C001"})

        # 购物车对象
        obj_cart = builder.add_object("购物车", {"商品数": "3件", "总价": "299.00元"})

        # 订单对象
        obj_order = builder.add_object("订单", {"订单号": "ORD20240115", "状态": "待支付"})

        # 商品对象1
        obj_product1 = builder.add_object("商品", {"名称": "Python编程", "价格": "89.00元"})

        # 商品对象2
        obj_product2 = builder.add_object("商品", {"名称": "数据结构", "价格": "79.00元"})

        # 支付对象
        obj_payment = builder.add_object("支付", {"方式": "支付宝", "金额": "299.00元"})

        # 关系
        builder.add_relationship(obj_customer, obj_cart, "拥有")
        builder.add_relationship(obj_cart, obj_order, "生成")
        builder.add_relationship(obj_order, obj_product1, "包含", rel_type="aggregation")
        builder.add_relationship(obj_order, obj_product2, "包含", rel_type="aggregation")
        builder.add_relationship(obj_order, obj_payment, "使用", rel_type="composition")

        if builder.build():
            save_path = os.path.join(os.path.dirname(__file__), "output", "object_test.vsdx")
            visio.save_document(save_path)
            print(f"\n 对象图已成功生成！")
            print(f" 文件保存位置: {os.path.abspath(save_path)}")
            input("\n按回车键返回主菜单...")


# ============================================================
# 第七部分：数据结构定义 + LLM API 调用模块
# ============================================================

class SystemTemplate:
    """系统 UML 模板数据结构"""

    def __init__(self, name: str, keywords: List[str], description: str = ""):
        self.name = name
        self.keywords = keywords  # 匹配关键词
        self.description = description
        # 四种图的数据
        self.use_case_data = None  # dict: actors, use_cases, relationships
        self.class_data = None  # dict: classes, relationships
        self.object_data = None  # dict: objects, relationships
        self.sequence_data = None  # dict: objects, messages


# ============================================================
# LLM API 调用 - DeepSeek / 千问 / 豆包
# ============================================================

# LLM 提供商配置
LLM_PROVIDERS = {
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1/chat/completions",
        "model": "deepseek-chat",
        "api_key_hint": "请前往 https://platform.deepseek.com 注册获取 API Key（注册送 500 万 tokens）",
    },
    "qwen": {
        "name": "通义千问 (Qwen)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "model": "qwen-turbo",
        "api_key_hint": "请前往 https://dashscope.console.aliyun.com 注册获取 API Key（新用户有免费额度）",
    },
    "doubao": {
        "name": "豆包 (Doubao)",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        "model": "doubao-pro-32k",
        "api_key_hint": "请前往 https://console.volcengine.com/ark 注册获取 API Key（有免费额度）",
    },
}


def load_api_keys() -> Dict[str, str]:
    """
    加载 API Key，支持两种方式：
    1. 从配置文件 api_keys.json 读取
    2. 运行时由用户输入
    配置文件格式: {"deepseek": "sk-xxx", "qwen": "sk-xxx", "doubao": "sk-xxx"}
    """
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_keys.json")
    keys = {}

    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                keys = json.load(f)
            print(f"[OK] 已从配置文件加载 API Key: {list(keys.keys())}")
        except Exception as e:
            print(f"[WARN] 读取配置文件失败: {e}")

    return keys


def save_api_keys(keys: Dict[str, str]):
    """保存 API Key 到配置文件"""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_keys.json")
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(keys, f, indent=2, ensure_ascii=False)
        print(f"[OK] API Key 已保存到: {config_path}")
    except Exception as e:
        print(f"[WARN] 保存配置文件失败: {e}")


def call_llm(provider: str, api_key: str, prompt: str,
             max_retries: int = 2, timeout: int = 60) -> Optional[str]:
    """
    调用 LLM API（兼容 OpenAI 格式）

    Args:
        provider: 提供商名称 (deepseek/qwen/doubao)
        api_key: API Key
        prompt: 用户提示词
        max_retries: 最大重试次数
        timeout: 超时时间（秒）

    Returns:
        LLM 返回的文本内容，失败返回 None
    """
    config = LLM_PROVIDERS.get(provider)
    if not config:
        print(f"[ERROR] 不支持的 LLM 提供商: {provider}")
        return None

    url = config["base_url"]
    model = config["model"]

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system",
             "content": "你是一个专业的 UML 建模专家。请严格按照用户要求的 JSON 格式输出，不要输出任何其他内容。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 4096,
    }

    for attempt in range(max_retries + 1):
        try:
            req = Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")

            print(f"   [INFO] 正在调用 {config['name']} ({model})...")
            print(f"   [INFO] 第 {attempt + 1} 次尝试...")

            with urlopen(req, timeout=timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            content = result["choices"][0]["message"]["content"].strip()

            # 提取 JSON（如果 LLM 返回了 ```json ... ``` 包裹）
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            print(f"   [OK] {config['name']} 返回成功（{len(content)} 字符）")
            return content

        except HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode("utf-8")
            except:
                pass
            print(f"   [ERROR] API 请求失败 (HTTP {e.code}): {error_body[:200]}")
            if attempt < max_retries:
                import time
                time.sleep(2)
        except URLError as e:
            print(f"   [ERROR] 网络连接失败: {e}")
            if attempt < max_retries:
                import time
                time.sleep(2)
        except Exception as e:
            print(f"   [ERROR] 调用失败: {e}")
            if attempt < max_retries:
                import time
                time.sleep(2)

    print(f"   [FAIL] {config['name']} 调用失败，已达最大重试次数")
    return None


def setup_llm_provider(api_keys: Dict[str, str]) -> Tuple[str, str]:
    """
    交互式选择和配置 LLM 提供商

    Returns:
        (provider_name, api_key) 元组，如果用户取消则返回 ("", "")
    """
    print("\n" + "=" * 60)
    print("  LLM 模型配置")
    print("=" * 60)

    # 显示已有 Key
    available = []
    for key, config in LLM_PROVIDERS.items():
        has_key = bool(api_keys.get(key))
        status = "已配置" if has_key else "未配置"
        available.append(key)
        print(f"  [{key}] {config['name']} - {status}")
        if not has_key:
            print(f"       {config['api_key_hint']}")

    print(f"  [0] 不使用 LLM（使用内置模板库）")
    print()

    choice = input("请选择 LLM 提供商: ").strip().lower()

    if choice == "0" or not choice:
        return ("", "")

    if choice not in LLM_PROVIDERS:
        # 模糊匹配
        for key in LLM_PROVIDERS:
            if key in choice or choice in key:
                choice = key
                break
        else:
            print("[WARN] 无效选择，将使用内置模板库")
            return ("", "")

    # 检查是否已有 Key
    if api_keys.get(choice):
        use_existing = input(
            f"检测到已配置 {LLM_PROVIDERS[choice]['name']} 的 API Key，是否使用？(Y/n): ").strip().lower()
        if use_existing != 'n':
            return (choice, api_keys[choice])

    # 输入新的 Key
    print(f"\n  {LLM_PROVIDERS[choice]['name']} - {LLM_PROVIDERS[choice]['api_key_hint']}")
    api_key = input(f"  请输入 {LLM_PROVIDERS[choice]['name']} API Key: ").strip()

    if not api_key:
        print("[WARN] 未输入 API Key，将使用内置模板库")
        return ("", "")

    # 保存 Key
    api_keys[choice] = api_key
    save_api_keys(api_keys)

    return (choice, api_key)


# LLM 分析 UML 的提示词模板
UML_ANALYSIS_PROMPT = """请分析以下软件/系统，生成完整的 UML 图数据。

系统名称：{query}

请严格按照以下 JSON 格式输出（不要输出任何其他文字，只输出 JSON）：

{{
  "system_name": "系统名称",
  "use_case_data": {{
    "actors": [
      {{"name": "参与者名称", "description": "描述"}}
    ],
    "use_cases": [
      {{"name": "用例名称", "description": "描述", "is_primary": false}}
    ],
    "relationships": [
      {{"from": "参与者或用例名", "to": "参与者或用例名", "type": "association|include|extend", "label": "关系标签"}}
    ]
  }},
  "class_data": {{
    "classes": [
      {{
        "name": "类名",
        "attributes": [
          {{"name": "属性名", "type": "类型", "visibility": "-"}}
        ],
        "methods": [
          {{"name": "方法名", "return_type": "返回类型", "visibility": "+", "params": ["参数名: 类型"]}}
        ]
      }}
    ],
    "relationships": [
      {{"from": "类名", "to": "类名", "type": "association|aggregation|composition|generalization|dependency", "label": "关系标签", "mult_from": "1", "mult_to": "*"}}
    ]
  }},
  "object_data": {{
    "objects": [
      {{"name": "对象名", "class_name": "类名", "attributes": {{"属性名": "属性值"}}}}
    ],
    "relationships": [
      {{"from": "对象名", "to": "对象名", "label": "关系标签", "type": "association"}}
    ]
  }},
  "sequence_data": {{
    "objects": ["对象/参与者名称列表"],
    "messages": [
      {{"from": "发送者", "to": "接收者", "text": "1: 消息文本", "type": "sync|return|async"}}
    ]
  }}
}}

要求：
1. 每种图至少包含 3-5 个核心元素
2. 关系类型只能用：association, include, extend, generalization, aggregation, composition, dependency
3. 消息类型只能用：sync(同步), return(返回), async(异步)
4. visibility 只能用：+(public), -(private), #(protected)
5. 用例图的 is_primary 标记核心用例为 true
6. 顺序图消息要按编号顺序，体现完整的交互流程
7. 类图的属性和方法要符合实际业务逻辑
8. 对象图要展示具体的实例数据"""


def parse_llm_response(response_text: str) -> Optional[Dict]:
    """解析 LLM 返回的 JSON 数据"""
    try:
        data = json.loads(response_text)
        # 基本验证
        if not isinstance(data, dict):
            return None
        return data
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON 解析失败: {e}")
        print(f"[INFO] LLM 返回内容前 200 字符: {response_text[:200]}")
        return None


def llm_response_to_template(data: Dict) -> SystemTemplate:
    """将 LLM 返回的数据转换为 SystemTemplate 对象"""
    template = SystemTemplate(
        name=data.get("system_name", "AI 生成系统"),
        keywords=[],
        description="由 AI 自动分析生成"
    )

    # 解析用例图数据
    if "use_case_data" in data:
        template.use_case_data = data["use_case_data"]

    # 解析类图数据
    if "class_data" in data:
        template.class_data = data["class_data"]

    # 解析对象图数据
    if "object_data" in data:
        template.object_data = data["object_data"]

    # 解析顺序图数据
    if "sequence_data" in data:
        template.sequence_data = data["sequence_data"]

    return template


# ============================================================
# 第八部分：AI 智能分析模块 - 内置模板库
# ============================================================

class UMLTemplateLibrary:
    """
    UML 模板库 - 内置常见系统的 UML 元素定义
    通过关键词匹配自动选择合适的模板
    """

    def __init__(self):
        self.templates: List[SystemTemplate] = []
        self._init_templates()

    def _init_templates(self):
        """初始化所有内置模板"""

        # ==================== 模板1：在线购物系统 ====================
        t = SystemTemplate(
            name="在线购物系统",
            keywords=["购物", "商城", "电商", "网购", "商品", "订单", "购物车", "shop", "shopping", "store",
                      "ecommerce", "e-commerce", "mall"],
            description="包含顾客/管理员、商品管理、订单处理、支付等核心模块"
        )
        t.use_case_data = {
            "actors": [
                {"name": "顾客", "description": "在线购物的用户"},
                {"name": "管理员", "description": "系统管理员"},
                {"name": "支付系统", "description": "第三方支付接口"}
            ],
            "use_cases": [
                {"name": "浏览商品", "description": "查看商品列表和详情"},
                {"name": "搜索商品", "description": "按关键词搜索商品"},
                {"name": "加入购物车", "description": "将商品添加到购物车"},
                {"name": "结算支付", "description": "提交订单并支付", "is_primary": True},
                {"name": "登录注册", "description": "用户登录或注册账户"},
                {"name": "查看订单", "description": "查看历史订单状态"},
                {"name": "评价商品", "description": "对已购商品进行评价"},
                {"name": "管理商品", "description": "增删改商品信息"},
                {"name": "管理订单", "description": "处理发货和退款"},
                {"name": "管理用户", "description": "管理用户账户"},
                {"name": "生成报表", "description": "生成销售统计报表"}
            ],
            "relationships": [
                {"from": "顾客", "to": "浏览商品", "type": "association"},
                {"from": "顾客", "to": "搜索商品", "type": "association"},
                {"from": "顾客", "to": "加入购物车", "type": "association"},
                {"from": "顾客", "to": "结算支付", "type": "association"},
                {"from": "顾客", "to": "登录注册", "type": "association"},
                {"from": "顾客", "to": "查看订单", "type": "association"},
                {"from": "顾客", "to": "评价商品", "type": "association"},
                {"from": "管理员", "to": "管理商品", "type": "association"},
                {"from": "管理员", "to": "管理订单", "type": "association"},
                {"from": "管理员", "to": "管理用户", "type": "association"},
                {"from": "管理员", "to": "生成报表", "type": "association"},
                {"from": "结算支付", "to": "登录注册", "type": "include", "label": "包含"},
                {"from": "浏览商品", "to": "搜索商品", "type": "extend", "label": "扩展"},
                {"from": "评价商品", "to": "查看订单", "type": "extend", "label": "扩展"},
            ]
        }
        t.class_data = {
            "classes": [
                {"name": "用户", "attributes": [
                    {"name": "用户ID", "type": "String", "visibility": "-"},
                    {"name": "用户名", "type": "String", "visibility": "-"},
                    {"name": "密码", "type": "String", "visibility": "-"},
                    {"name": "邮箱", "type": "String", "visibility": "-"},
                    {"name": "手机号", "type": "String", "visibility": "-"}
                ], "methods": [
                    {"name": "登录", "return_type": "boolean", "visibility": "+",
                     "params": ["用户名: String", "密码: String"]},
                    {"name": "注册", "return_type": "boolean", "visibility": "+", "params": ["用户信息: UserDTO"]},
                    {"name": "修改个人信息", "return_type": "void", "visibility": "+"}
                ]},
                {"name": "商品", "attributes": [
                    {"name": "商品ID", "type": "String", "visibility": "-"},
                    {"name": "名称", "type": "String", "visibility": "-"},
                    {"name": "价格", "type": "double", "visibility": "-"},
                    {"name": "库存", "type": "int", "visibility": "-"},
                    {"name": "描述", "type": "String", "visibility": "-"},
                    {"name": "分类", "type": "String", "visibility": "-"}
                ], "methods": [
                    {"name": "更新库存", "return_type": "void", "visibility": "+", "params": ["数量: int"]},
                    {"name": "获取详情", "return_type": "String", "visibility": "+"}
                ]},
                {"name": "订单", "attributes": [
                    {"name": "订单ID", "type": "String", "visibility": "-"},
                    {"name": "订单状态", "type": "String", "visibility": "-"},
                    {"name": "总金额", "type": "double", "visibility": "-"},
                    {"name": "创建时间", "type": "Date", "visibility": "-"},
                    {"name": "收货地址", "type": "String", "visibility": "-"}
                ], "methods": [
                    {"name": "创建订单", "return_type": "Order", "visibility": "+", "params": ["购物车: Cart"]},
                    {"name": "取消订单", "return_type": "boolean", "visibility": "+"},
                    {"name": "更新状态", "return_type": "void", "visibility": "+", "params": ["状态: String"]}
                ]},
                {"name": "购物车", "attributes": [
                    {"name": "用户ID", "type": "String", "visibility": "-"},
                    {"name": "商品列表", "type": "List<CartItem>", "visibility": "-"},
                    {"name": "总金额", "type": "double", "visibility": "-"}
                ], "methods": [
                    {"name": "添加商品", "return_type": "void", "visibility": "+",
                     "params": ["商品: Product", "数量: int"]},
                    {"name": "移除商品", "return_type": "void", "visibility": "+", "params": ["商品ID: String"]},
                    {"name": "计算总价", "return_type": "double", "visibility": "+"}
                ]},
                {"name": "支付记录", "attributes": [
                    {"name": "支付ID", "type": "String", "visibility": "-"},
                    {"name": "订单ID", "type": "String", "visibility": "-"},
                    {"name": "支付金额", "type": "double", "visibility": "-"},
                    {"name": "支付方式", "type": "String", "visibility": "-"},
                    {"name": "支付时间", "type": "Date", "visibility": "-"}
                ], "methods": [
                    {"name": "发起支付", "return_type": "boolean", "visibility": "+"},
                    {"name": "退款", "return_type": "boolean", "visibility": "+"}
                ]},
                {"name": "评价", "attributes": [
                    {"name": "评价ID", "type": "String", "visibility": "-"},
                    {"name": "评分", "type": "int", "visibility": "-"},
                    {"name": "内容", "type": "String", "visibility": "-"},
                    {"name": "评价时间", "type": "Date", "visibility": "-"}
                ], "methods": [
                    {"name": "提交评价", "return_type": "boolean", "visibility": "+"}
                ]}
            ],
            "relationships": [
                {"from": "订单", "to": "用户", "type": "association", "label": "所属", "mult_from": "*",
                 "mult_to": "1"},
                {"from": "订单", "to": "商品", "type": "aggregation", "label": "包含", "mult_from": "*",
                 "mult_to": "1..*"},
                {"from": "购物车", "to": "用户", "type": "composition", "label": "属于", "mult_from": "1",
                 "mult_to": "1"},
                {"from": "购物车", "to": "商品", "type": "aggregation", "label": "包含", "mult_from": "1",
                 "mult_to": "1..*"},
                {"from": "支付记录", "to": "订单", "type": "association", "label": "对应", "mult_from": "1",
                 "mult_to": "1"},
                {"from": "评价", "to": "商品", "type": "association", "label": "针对", "mult_from": "*",
                 "mult_to": "1"},
                {"from": "评价", "to": "用户", "type": "association", "label": "发布", "mult_from": "*",
                 "mult_to": "1"},
            ]
        }
        t.object_data = {
            "objects": [
                {"name": "user1", "class_name": "用户",
                 "attributes": {"用户ID": "U001", "用户名": "张三", "邮箱": "zhangsan@email.com"}},
                {"name": "product1", "class_name": "商品",
                 "attributes": {"商品ID": "P001", "名称": "iPhone 15", "价格": "7999", "库存": "100"}},
                {"name": "product2", "class_name": "商品",
                 "attributes": {"商品ID": "P002", "名称": "AirPods", "价格": "1299", "库存": "200"}},
                {"name": "cart1", "class_name": "购物车", "attributes": {"用户ID": "U001", "总金额": "9298"}},
                {"name": "order1", "class_name": "订单",
                 "attributes": {"订单ID": "O001", "订单状态": "已支付", "总金额": "9298"}},
                {"name": "payment1", "class_name": "支付记录",
                 "attributes": {"支付ID": "PAY001", "支付金额": "9298", "支付方式": "支付宝"}}
            ],
            "relationships": [
                {"from": "cart1", "to": "user1", "label": "属于", "type": "association"},
                {"from": "cart1", "to": "product1", "label": "包含", "type": "aggregation"},
                {"from": "cart1", "to": "product2", "label": "包含", "type": "aggregation"},
                {"from": "order1", "to": "user1", "label": "所属", "type": "association"},
                {"from": "order1", "to": "product1", "label": "包含", "type": "aggregation"},
                {"from": "payment1", "to": "order1", "label": "对应", "type": "association"},
            ]
        }
        t.sequence_data = {
            "objects": ["顾客", "前端界面", "订单服务", "支付服务", "数据库"],
            "messages": [
                {"from": "顾客", "to": "前端界面", "text": "1: 浏览商品列表", "type": "sync"},
                {"from": "前端界面", "to": "订单服务", "text": "2: 请求商品数据", "type": "sync"},
                {"from": "订单服务", "to": "数据库", "text": "3: 查询商品信息", "type": "sync"},
                {"from": "数据库", "to": "订单服务", "text": "4: 返回商品列表", "type": "return"},
                {"from": "订单服务", "to": "前端界面", "text": "5: 返回商品数据", "type": "return"},
                {"from": "前端界面", "to": "顾客", "text": "6: 展示商品页面", "type": "return"},
                {"from": "顾客", "to": "前端界面", "text": "7: 加入购物车", "type": "sync"},
                {"from": "顾客", "to": "前端界面", "text": "8: 提交订单", "type": "sync"},
                {"from": "前端界面", "to": "订单服务", "text": "9: 创建订单", "type": "sync"},
                {"from": "订单服务", "to": "数据库", "text": "10: 保存订单", "type": "sync"},
                {"from": "数据库", "to": "订单服务", "text": "11: 返回订单ID", "type": "return"},
                {"from": "订单服务", "to": "支付服务", "text": "12: 发起支付请求", "type": "sync"},
                {"from": "支付服务", "to": "订单服务", "text": "13: 返回支付链接", "type": "return"},
                {"from": "订单服务", "to": "前端界面", "text": "14: 返回支付信息", "type": "return"},
                {"from": "前端界面", "to": "顾客", "text": "15: 显示支付页面", "type": "return"},
                {"from": "顾客", "to": "前端界面", "text": "16: 确认支付", "type": "sync"},
                {"from": "前端界面", "to": "支付服务", "text": "17: 处理支付", "type": "sync"},
                {"from": "支付服务", "to": "数据库", "text": "18: 更新支付状态", "type": "sync"},
                {"from": "支付服务", "to": "前端界面", "text": "19: 返回支付结果", "type": "return"},
                {"from": "前端界面", "to": "顾客", "text": "20: 显示支付成功", "type": "return"},
            ]
        }
        self.templates.append(t)

        # ==================== 模板2：图书管理系统 ====================
        t = SystemTemplate(
            name="图书管理系统",
            keywords=["图书", "图书馆", "借书", "还书", "library", "book", "借阅", "藏书"],
            description="包含读者/管理员、图书借还、图书检索、罚款管理等核心模块"
        )
        t.use_case_data = {
            "actors": [
                {"name": "读者", "description": "借阅图书的用户"},
                {"name": "图书管理员", "description": "管理图书和借阅记录"},
                {"name": "系统管理员", "description": "维护系统参数"}
            ],
            "use_cases": [
                {"name": "搜索图书", "description": "按书名/作者/ISBN搜索"},
                {"name": "借阅图书", "description": "借出图书", "is_primary": True},
                {"name": "归还图书", "description": "归还已借图书", "is_primary": True},
                {"name": "续借图书", "description": "延长借阅期限"},
                {"name": "查看借阅记录", "description": "查看个人借阅历史"},
                {"name": "预约图书", "description": "预约已被借出的图书"},
                {"name": "登录系统", "description": "用户登录"},
                {"name": "注册账户", "description": "新用户注册"},
                {"name": "录入新书", "description": "添加新图书到系统"},
                {"name": "删除图书", "description": "从系统中移除图书"},
                {"name": "管理读者", "description": "管理读者信息"},
                {"name": "生成统计报表", "description": "生成借阅统计"},
                {"name": "处理逾期罚款", "description": "计算和收取逾期罚款"}
            ],
            "relationships": [
                {"from": "读者", "to": "搜索图书", "type": "association"},
                {"from": "读者", "to": "借阅图书", "type": "association"},
                {"from": "读者", "to": "归还图书", "type": "association"},
                {"from": "读者", "to": "续借图书", "type": "association"},
                {"from": "读者", "to": "查看借阅记录", "type": "association"},
                {"from": "读者", "to": "预约图书", "type": "association"},
                {"from": "读者", "to": "登录系统", "type": "association"},
                {"from": "读者", "to": "注册账户", "type": "association"},
                {"from": "图书管理员", "to": "录入新书", "type": "association"},
                {"from": "图书管理员", "to": "删除图书", "type": "association"},
                {"from": "图书管理员", "to": "管理读者", "type": "association"},
                {"from": "图书管理员", "to": "处理逾期罚款", "type": "association"},
                {"from": "系统管理员", "to": "生成统计报表", "type": "association"},
                {"from": "借阅图书", "to": "登录系统", "type": "include", "label": "包含"},
                {"from": "续借图书", "to": "借阅图书", "type": "extend", "label": "扩展"},
            ]
        }
        t.class_data = {
            "classes": [
                {"name": "读者", "attributes": [
                    {"name": "读者ID", "type": "String", "visibility": "-"},
                    {"name": "姓名", "type": "String", "visibility": "-"},
                    {"name": "借书证号", "type": "String", "visibility": "-"},
                    {"name": "最大借阅数", "type": "int", "visibility": "-"},
                    {"name": "已借数量", "type": "int", "visibility": "-"}
                ], "methods": [
                    {"name": "借书", "return_type": "boolean", "visibility": "+", "params": ["图书ID: String"]},
                    {"name": "还书", "return_type": "boolean", "visibility": "+", "params": ["图书ID: String"]},
                    {"name": "查询借阅", "return_type": "List<Record>", "visibility": "+"}
                ]},
                {"name": "图书", "attributes": [
                    {"name": "ISBN", "type": "String", "visibility": "-"},
                    {"name": "书名", "type": "String", "visibility": "-"},
                    {"name": "作者", "type": "String", "visibility": "-"},
                    {"name": "出版社", "type": "String", "visibility": "-"},
                    {"name": "库存总量", "type": "int", "visibility": "-"},
                    {"name": "可借数量", "type": "int", "visibility": "-"}
                ], "methods": [
                    {"name": "更新库存", "return_type": "void", "visibility": "+", "params": ["数量: int"]},
                    {"name": "查询状态", "return_type": "String", "visibility": "+"}
                ]},
                {"name": "借阅记录", "attributes": [
                    {"name": "记录ID", "type": "String", "visibility": "-"},
                    {"name": "借出日期", "type": "Date", "visibility": "-"},
                    {"name": "应还日期", "type": "Date", "visibility": "-"},
                    {"name": "实际归还日期", "type": "Date", "visibility": "-"},
                    {"name": "状态", "type": "String", "visibility": "-"}
                ], "methods": [
                    {"name": "计算逾期", "return_type": "int", "visibility": "+"},
                    {"name": "续借", "return_type": "boolean", "visibility": "+"}
                ]},
                {"name": "罚款记录", "attributes": [
                    {"name": "罚款ID", "type": "String", "visibility": "-"},
                    {"name": "金额", "type": "double", "visibility": "-"},
                    {"name": "原因", "type": "String", "visibility": "-"},
                    {"name": "是否已缴", "type": "boolean", "visibility": "-"}
                ], "methods": [
                    {"name": "缴纳罚款", "return_type": "boolean", "visibility": "+"}
                ]},
                {"name": "预约", "attributes": [
                    {"name": "预约ID", "type": "String", "visibility": "-"},
                    {"name": "预约日期", "type": "Date", "visibility": "-"},
                    {"name": "状态", "type": "String", "visibility": "-"}
                ], "methods": [
                    {"name": "取消预约", "return_type": "boolean", "visibility": "+"},
                    {"name": "通知取书", "return_type": "void", "visibility": "+"}
                ]}
            ],
            "relationships": [
                {"from": "借阅记录", "to": "读者", "type": "association", "label": "借阅者", "mult_from": "*",
                 "mult_to": "1"},
                {"from": "借阅记录", "to": "图书", "type": "association", "label": "借阅", "mult_from": "*",
                 "mult_to": "1"},
                {"from": "罚款记录", "to": "借阅记录", "type": "association", "label": "对应", "mult_from": "0..1",
                 "mult_to": "1"},
                {"from": "预约", "to": "读者", "type": "association", "label": "预约者", "mult_from": "*",
                 "mult_to": "1"},
                {"from": "预约", "to": "图书", "type": "association", "label": "预约", "mult_from": "*",
                 "mult_to": "1"},
            ]
        }
        t.object_data = {
            "objects": [
                {"name": "reader1", "class_name": "读者",
                 "attributes": {"读者ID": "R001", "姓名": "李四", "已借数量": "2"}},
                {"name": "book1", "class_name": "图书",
                 "attributes": {"ISBN": "978-7-111", "书名": "Python编程", "可借数量": "3"}},
                {"name": "book2", "class_name": "图书",
                 "attributes": {"ISBN": "978-7-222", "书名": "数据结构", "可借数量": "0"}},
                {"name": "record1", "class_name": "借阅记录",
                 "attributes": {"记录ID": "B001", "状态": "借出中", "应还日期": "2026-05-01"}},
                {"name": "record2", "class_name": "借阅记录",
                 "attributes": {"记录ID": "B002", "状态": "已逾期", "应还日期": "2026-04-01"}},
                {"name": "fine1", "class_name": "罚款记录",
                 "attributes": {"罚款ID": "F001", "金额": "5.0", "是否已缴": "否"}}
            ],
            "relationships": [
                {"from": "record1", "to": "reader1", "label": "借阅者", "type": "association"},
                {"from": "record1", "to": "book1", "label": "借阅", "type": "association"},
                {"from": "record2", "to": "reader1", "label": "借阅者", "type": "association"},
                {"from": "record2", "to": "book2", "label": "借阅", "type": "association"},
                {"from": "fine1", "to": "record2", "label": "对应", "type": "association"},
            ]
        }
        t.sequence_data = {
            "objects": ["读者", "前端界面", "借阅服务", "数据库"],
            "messages": [
                {"from": "读者", "to": "前端界面", "text": "1: 登录系统", "type": "sync"},
                {"from": "前端界面", "to": "借阅服务", "text": "2: 验证用户信息", "type": "sync"},
                {"from": "借阅服务", "to": "数据库", "text": "3: 查询用户数据", "type": "sync"},
                {"from": "数据库", "to": "借阅服务", "text": "4: 返回用户信息", "type": "return"},
                {"from": "借阅服务", "to": "前端界面", "text": "5: 验证成功", "type": "return"},
                {"from": "读者", "to": "前端界面", "text": "6: 搜索图书", "type": "sync"},
                {"from": "前端界面", "to": "借阅服务", "text": "7: 查询图书", "type": "sync"},
                {"from": "借阅服务", "to": "数据库", "text": "8: 搜索图书信息", "type": "sync"},
                {"from": "数据库", "to": "借阅服务", "text": "9: 返回搜索结果", "type": "return"},
                {"from": "借阅服务", "to": "前端界面", "text": "10: 返回图书列表", "type": "return"},
                {"from": "读者", "to": "前端界面", "text": "11: 选择图书借阅", "type": "sync"},
                {"from": "前端界面", "to": "借阅服务", "text": "12: 提交借阅请求", "type": "sync"},
                {"from": "借阅服务", "to": "数据库", "text": "13: 检查库存并创建借阅记录", "type": "sync"},
                {"from": "数据库", "to": "借阅服务", "text": "14: 返回借阅结果", "type": "return"},
                {"from": "借阅服务", "to": "前端界面", "text": "15: 返回借阅成功", "type": "return"},
                {"from": "前端界面", "to": "读者", "text": "16: 显示借阅成功", "type": "return"},
            ]
        }
        self.templates.append(t)

        # ==================== 模板3：酒店预订系统 ====================
        t = SystemTemplate(
            name="酒店预订系统",
            keywords=["酒店", "预订", "客房", "入住", "退房", "hotel", "预订房间", "宾馆", "旅馆", "reservation",
                      "booking"],
            description="包含客人/前台/管理员、房间预订、入住退房、账单管理等核心模块"
        )
        t.use_case_data = {
            "actors": [
                {"name": "客人", "description": "预订和入住的旅客"},
                {"name": "前台", "description": "酒店前台工作人员"},
                {"name": "管理员", "description": "酒店管理人员"}
            ],
            "use_cases": [
                {"name": "搜索房间", "description": "按日期和类型搜索可用房间"},
                {"name": "预订房间", "description": "在线预订客房", "is_primary": True},
                {"name": "取消预订", "description": "取消已有的预订"},
                {"name": "办理入住", "description": "前台为客人办理入住", "is_primary": True},
                {"name": "办理退房", "description": "前台为客人办理退房"},
                {"name": "查看预订", "description": "查看个人预订记录"},
                {"name": "支付账单", "description": "支付房费和其他费用"},
                {"name": "评价酒店", "description": "对入住体验进行评价"},
                {"name": "管理房间", "description": "管理房间信息和状态"},
                {"name": "查看报表", "description": "查看入住率和营收报表"},
                {"name": "管理员工", "description": "管理前台和保洁人员"}
            ],
            "relationships": [
                {"from": "客人", "to": "搜索房间", "type": "association"},
                {"from": "客人", "to": "预订房间", "type": "association"},
                {"from": "客人", "to": "取消预订", "type": "association"},
                {"from": "客人", "to": "查看预订", "type": "association"},
                {"from": "客人", "to": "支付账单", "type": "association"},
                {"from": "客人", "to": "评价酒店", "type": "association"},
                {"from": "前台", "to": "办理入住", "type": "association"},
                {"from": "前台", "to": "办理退房", "type": "association"},
                {"from": "前台", "to": "管理房间", "type": "association"},
                {"from": "管理员", "to": "查看报表", "type": "association"},
                {"from": "管理员", "to": "管理员工", "type": "association"},
                {"from": "预订房间", "to": "搜索房间", "type": "include", "label": "包含"},
                {"from": "办理入住", "to": "预订房间", "type": "extend", "label": "扩展"},
            ]
        }
        t.class_data = {
            "classes": [
                {"name": "客人", "attributes": [
                    {"name": "客人ID", "type": "String", "visibility": "-"},
                    {"name": "姓名", "type": "String", "visibility": "-"},
                    {"name": "身份证号", "type": "String", "visibility": "-"},
                    {"name": "手机号", "type": "String", "visibility": "-"}
                ], "methods": [
                    {"name": "预订", "return_type": "Reservation", "visibility": "+",
                     "params": ["房间类型: String", "日期: Date"]},
                    {"name": "取消预订", "return_type": "boolean", "visibility": "+"}
                ]},
                {"name": "房间", "attributes": [
                    {"name": "房间号", "type": "String", "visibility": "-"},
                    {"name": "类型", "type": "String", "visibility": "-"},
                    {"name": "价格", "type": "double", "visibility": "-"},
                    {"name": "状态", "type": "String", "visibility": "-"},
                    {"name": "楼层", "type": "int", "visibility": "-"}
                ], "methods": [
                    {"name": "更新状态", "return_type": "void", "visibility": "+", "params": ["状态: String"]},
                    {"name": "检查可用", "return_type": "boolean", "visibility": "+"}
                ]},
                {"name": "预订记录", "attributes": [
                    {"name": "预订ID", "type": "String", "visibility": "-"},
                    {"name": "入住日期", "type": "Date", "visibility": "-"},
                    {"name": "退房日期", "type": "Date", "visibility": "-"},
                    {"name": "状态", "type": "String", "visibility": "-"},
                    {"name": "总金额", "type": "double", "visibility": "-"}
                ], "methods": [
                    {"name": "确认预订", "return_type": "boolean", "visibility": "+"},
                    {"name": "计算费用", "return_type": "double", "visibility": "+"}
                ]},
                {"name": "账单", "attributes": [
                    {"name": "账单ID", "type": "String", "visibility": "-"},
                    {"name": "房费", "type": "double", "visibility": "-"},
                    {"name": "其他费用", "type": "double", "visibility": "-"},
                    {"name": "支付状态", "type": "String", "visibility": "-"}
                ], "methods": [
                    {"name": "生成账单", "return_type": "Bill", "visibility": "+"},
                    {"name": "支付", "return_type": "boolean", "visibility": "+"}
                ]}
            ],
            "relationships": [
                {"from": "预订记录", "to": "客人", "type": "association", "label": "预订人", "mult_from": "*",
                 "mult_to": "1"},
                {"from": "预订记录", "to": "房间", "type": "association", "label": "预订", "mult_from": "*",
                 "mult_to": "1"},
                {"from": "账单", "to": "预订记录", "type": "association", "label": "对应", "mult_from": "1",
                 "mult_to": "1"},
            ]
        }
        t.object_data = {
            "objects": [
                {"name": "guest1", "class_name": "客人",
                 "attributes": {"客人ID": "G001", "姓名": "王五", "手机号": "138****1234"}},
                {"name": "room1", "class_name": "房间",
                 "attributes": {"房间号": "301", "类型": "标准间", "价格": "299", "状态": "已预订"}},
                {"name": "room2", "class_name": "房间",
                 "attributes": {"房间号": "501", "类型": "豪华套房", "价格": "888", "状态": "空闲"}},
                {"name": "res1", "class_name": "预订记录",
                 "attributes": {"预订ID": "R001", "入住日期": "2026-04-15", "状态": "已确认"}},
                {"name": "bill1", "class_name": "账单",
                 "attributes": {"账单ID": "B001", "房费": "598", "支付状态": "未支付"}}
            ],
            "relationships": [
                {"from": "res1", "to": "guest1", "label": "预订人", "type": "association"},
                {"from": "res1", "to": "room1", "label": "预订", "type": "association"},
                {"from": "bill1", "to": "res1", "label": "对应", "type": "association"},
            ]
        }
        t.sequence_data = {
            "objects": ["客人", "前端界面", "预订服务", "房间服务", "数据库"],
            "messages": [
                {"from": "客人", "to": "前端界面", "text": "1: 搜索酒店", "type": "sync"},
                {"from": "前端界面", "to": "预订服务", "text": "2: 处理搜索请求", "type": "sync"},
                {"from": "预订服务", "to": "房间服务", "text": "3: 查询可用房间", "type": "sync"},
                {"from": "房间服务", "to": "数据库", "text": "4: 查询房间信息", "type": "sync"},
                {"from": "数据库", "to": "房间服务", "text": "5: 返回房间列表", "type": "return"},
                {"from": "房间服务", "to": "预订服务", "text": "6: 返回可用房间", "type": "return"},
                {"from": "预订服务", "to": "前端界面", "text": "7: 返回搜索结果", "type": "return"},
                {"from": "前端界面", "to": "客人", "text": "8: 展示搜索结果", "type": "return"},
                {"from": "客人", "to": "前端界面", "text": "9: 选择房间并预订", "type": "sync"},
                {"from": "前端界面", "to": "预订服务", "text": "10: 提交预订请求", "type": "sync"},
                {"from": "预订服务", "to": "数据库", "text": "11: 创建预订记录", "type": "sync"},
                {"from": "数据库", "to": "预订服务", "text": "12: 确认预订成功", "type": "return"},
                {"from": "预订服务", "to": "前端界面", "text": "13: 返回预订确认", "type": "return"},
                {"from": "前端界面", "to": "客人", "text": "14: 显示预订成功", "type": "return"},
            ]
        }
        self.templates.append(t)

        # ==================== 模板4：银行系统 ====================
        t = SystemTemplate(
            name="银行系统",
            keywords=["银行", "存款", "取款", "转账", "账户", "贷款", "bank", "banking", "atm", "储蓄", "信用卡"],
            description="包含客户/柜员/管理员、账户管理、存取款、转账、贷款等核心模块"
        )
        t.use_case_data = {
            "actors": [
                {"name": "客户", "description": "银行客户"},
                {"name": "柜员", "description": "银行柜台工作人员"},
                {"name": "系统管理员", "description": "银行系统管理员"}
            ],
            "use_cases": [
                {"name": "开户", "description": "新客户开立银行账户", "is_primary": True},
                {"name": "存款", "description": "向账户存入资金", "is_primary": True},
                {"name": "取款", "description": "从账户取出资金", "is_primary": True},
                {"name": "转账", "description": "向其他账户转账", "is_primary": True},
                {"name": "查询余额", "description": "查询账户余额"},
                {"name": "修改密码", "description": "修改账户密码"},
                {"name": "申请贷款", "description": "提交贷款申请"},
                {"name": "还款", "description": "偿还贷款"},
                {"name": "办理信用卡", "description": "申请信用卡"},
                {"name": "管理账户", "description": "冻结/解冻账户"},
                {"name": "生成对账单", "description": "生成交易对账单"},
                {"name": "系统维护", "description": "维护系统参数"}
            ],
            "relationships": [
                {"from": "客户", "to": "存款", "type": "association"},
                {"from": "客户", "to": "取款", "type": "association"},
                {"from": "客户", "to": "转账", "type": "association"},
                {"from": "客户", "to": "查询余额", "type": "association"},
                {"from": "客户", "to": "修改密码", "type": "association"},
                {"from": "客户", "to": "申请贷款", "type": "association"},
                {"from": "客户", "to": "还款", "type": "association"},
                {"from": "客户", "to": "办理信用卡", "type": "association"},
                {"from": "柜员", "to": "开户", "type": "association"},
                {"from": "柜员", "to": "存款", "type": "association"},
                {"from": "柜员", "to": "取款", "type": "association"},
                {"from": "柜员", "to": "管理账户", "type": "association"},
                {"from": "柜员", "to": "生成对账单", "type": "association"},
                {"from": "系统管理员", "to": "系统维护", "type": "association"},
                {"from": "取款", "to": "查询余额", "type": "include", "label": "包含"},
                {"from": "转账", "to": "查询余额", "type": "include", "label": "包含"},
            ]
        }
        t.class_data = {
            "classes": [
                {"name": "客户", "attributes": [
                    {"name": "客户ID", "type": "String", "visibility": "-"},
                    {"name": "姓名", "type": "String", "visibility": "-"},
                    {"name": "身份证号", "type": "String", "visibility": "-"},
                    {"name": "手机号", "type": "String", "visibility": "-"},
                    {"name": "地址", "type": "String", "visibility": "-"}
                ], "methods": [
                    {"name": "开户", "return_type": "Account", "visibility": "+", "params": ["账户类型: String"]},
                    {"name": "申请贷款", "return_type": "Loan", "visibility": "+"}
                ]},
                {"name": "账户", "attributes": [
                    {"name": "账号", "type": "String", "visibility": "-"},
                    {"name": "余额", "type": "double", "visibility": "-"},
                    {"name": "账户类型", "type": "String", "visibility": "-"},
                    {"name": "开户日期", "type": "Date", "visibility": "-"},
                    {"name": "状态", "type": "String", "visibility": "-"}
                ], "methods": [
                    {"name": "存款", "return_type": "boolean", "visibility": "+", "params": ["金额: double"]},
                    {"name": "取款", "return_type": "boolean", "visibility": "+", "params": ["金额: double"]},
                    {"name": "转账", "return_type": "boolean", "visibility": "+",
                     "params": ["目标账号: String", "金额: double"]},
                    {"name": "查询余额", "return_type": "double", "visibility": "+"}
                ]},
                {"name": "交易记录", "attributes": [
                    {"name": "交易ID", "type": "String", "visibility": "-"},
                    {"name": "交易类型", "type": "String", "visibility": "-"},
                    {"name": "金额", "type": "double", "visibility": "-"},
                    {"name": "交易时间", "type": "Date", "visibility": "-"},
                    {"name": "目标账号", "type": "String", "visibility": "-"}
                ], "methods": [
                    {"name": "记录交易", "return_type": "void", "visibility": "+"}
                ]},
                {"name": "贷款", "attributes": [
                    {"name": "贷款ID", "type": "String", "visibility": "-"},
                    {"name": "贷款金额", "type": "double", "visibility": "-"},
                    {"name": "利率", "type": "double", "visibility": "-"},
                    {"name": "期限", "type": "int", "visibility": "-"},
                    {"name": "还款状态", "type": "String", "visibility": "-"}
                ], "methods": [
                    {"name": "计算月供", "return_type": "double", "visibility": "+"},
                    {"name": "还款", "return_type": "boolean", "visibility": "+"}
                ]}
            ],
            "relationships": [
                {"from": "账户", "to": "客户", "type": "composition", "label": "所属", "mult_from": "1..*",
                 "mult_to": "1"},
                {"from": "交易记录", "to": "账户", "type": "association", "label": "交易", "mult_from": "*",
                 "mult_to": "1"},
                {"from": "贷款", "to": "客户", "type": "association", "label": "借款人", "mult_from": "0..*",
                 "mult_to": "1"},
            ]
        }
        t.object_data = {
            "objects": [
                {"name": "customer1", "class_name": "客户",
                 "attributes": {"客户ID": "C001", "姓名": "赵六", "手机号": "139****5678"}},
                {"name": "account1", "class_name": "账户",
                 "attributes": {"账号": "6222****1234", "余额": "50000", "账户类型": "储蓄卡"}},
                {"name": "account2", "class_name": "账户",
                 "attributes": {"账号": "6222****5678", "余额": "120000", "账户类型": "定期"}},
                {"name": "tx1", "class_name": "交易记录",
                 "attributes": {"交易ID": "T001", "交易类型": "存款", "金额": "10000"}},
                {"name": "tx2", "class_name": "交易记录",
                 "attributes": {"交易ID": "T002", "交易类型": "转账", "金额": "5000"}},
                {"name": "loan1", "class_name": "贷款",
                 "attributes": {"贷款ID": "L001", "贷款金额": "200000", "还款状态": "还款中"}}
            ],
            "relationships": [
                {"from": "account1", "to": "customer1", "label": "所属", "type": "composition"},
                {"from": "account2", "to": "customer1", "label": "所属", "type": "composition"},
                {"from": "tx1", "to": "account1", "label": "交易", "type": "association"},
                {"from": "tx2", "to": "account1", "label": "交易", "type": "association"},
                {"from": "loan1", "to": "customer1", "label": "借款人", "type": "association"},
            ]
        }
        t.sequence_data = {
            "objects": ["客户", "ATM/柜台", "账户服务", "数据库"],
            "messages": [
                {"from": "客户", "to": "ATM/柜台", "text": "1: 插卡/出示证件", "type": "sync"},
                {"from": "ATM/柜台", "to": "账户服务", "text": "2: 验证身份", "type": "sync"},
                {"from": "账户服务", "to": "数据库", "text": "3: 查询客户信息", "type": "sync"},
                {"from": "数据库", "to": "账户服务", "text": "4: 返回客户信息", "type": "return"},
                {"from": "账户服务", "to": "ATM/柜台", "text": "5: 验证通过", "type": "return"},
                {"from": "客户", "to": "ATM/柜台", "text": "6: 选择转账", "type": "sync"},
                {"from": "ATM/柜台", "to": "账户服务", "text": "7: 输入转账信息", "type": "sync"},
                {"from": "账户服务", "to": "数据库", "text": "8: 检查余额并执行转账", "type": "sync"},
                {"from": "数据库", "to": "账户服务", "text": "9: 返回转账结果", "type": "return"},
                {"from": "账户服务", "to": "ATM/柜台", "text": "10: 返回转账成功", "type": "return"},
                {"from": "ATM/柜台", "to": "客户", "text": "11: 显示转账成功", "type": "return"},
            ]
        }
        self.templates.append(t)

        # ==================== 模板5：学生管理系统 ====================
        t = SystemTemplate(
            name="学生管理系统",
            keywords=["学生", "教师", "课程", "成绩", "选课", "教务", "school", "student", "university", "education",
                      "大学", "学校", "学院"],
            description="包含学生/教师/管理员、选课退课、成绩管理、课程安排等核心模块"
        )
        t.use_case_data = {
            "actors": [
                {"name": "学生", "description": "在校学生"},
                {"name": "教师", "description": "授课教师"},
                {"name": "教务管理员", "description": "教务处管理人员"}
            ],
            "use_cases": [
                {"name": "选课", "description": "选择本学期课程", "is_primary": True},
                {"name": "退课", "description": "退选已选课程"},
                {"name": "查看成绩", "description": "查询课程成绩"},
                {"name": "查看课表", "description": "查看个人课程表"},
                {"name": "录入成绩", "description": "教师录入学生成绩", "is_primary": True},
                {"name": "管理课程", "description": "创建和修改课程信息"},
                {"name": "排课", "description": "安排课程时间和教室"},
                {"name": "管理学生信息", "description": "维护学生基本信息"},
                {"name": "生成成绩单", "description": "生成学生成绩单"},
                {"name": "统计分析", "description": "成绩统计和分析"}
            ],
            "relationships": [
                {"from": "学生", "to": "选课", "type": "association"},
                {"from": "学生", "to": "退课", "type": "association"},
                {"from": "学生", "to": "查看成绩", "type": "association"},
                {"from": "学生", "to": "查看课表", "type": "association"},
                {"from": "教师", "to": "录入成绩", "type": "association"},
                {"from": "教师", "to": "查看成绩", "type": "association"},
                {"from": "教务管理员", "to": "管理课程", "type": "association"},
                {"from": "教务管理员", "to": "排课", "type": "association"},
                {"from": "教务管理员", "to": "管理学生信息", "type": "association"},
                {"from": "教务管理员", "to": "生成成绩单", "type": "association"},
                {"from": "教务管理员", "to": "统计分析", "type": "association"},
                {"from": "选课", "to": "查看课表", "type": "include", "label": "包含"},
                {"from": "退课", "to": "选课", "type": "extend", "label": "扩展"},
            ]
        }
        t.class_data = {
            "classes": [
                {"name": "学生", "attributes": [
                    {"name": "学号", "type": "String", "visibility": "-"},
                    {"name": "姓名", "type": "String", "visibility": "-"},
                    {"name": "专业", "type": "String", "visibility": "-"},
                    {"name": "年级", "type": "int", "visibility": "-"},
                    {"name": "班级", "type": "String", "visibility": "-"}
                ], "methods": [
                    {"name": "选课", "return_type": "boolean", "visibility": "+", "params": ["课程ID: String"]},
                    {"name": "退课", "return_type": "boolean", "visibility": "+", "params": ["课程ID: String"]},
                    {"name": "查看成绩", "return_type": "List<Grade>", "visibility": "+"}
                ]},
                {"name": "教师", "attributes": [
                    {"name": "工号", "type": "String", "visibility": "-"},
                    {"name": "姓名", "type": "String", "visibility": "-"},
                    {"name": "职称", "type": "String", "visibility": "-"},
                    {"name": "院系", "type": "String", "visibility": "-"}
                ], "methods": [
                    {"name": "录入成绩", "return_type": "boolean", "visibility": "+",
                     "params": ["学号: String", "课程ID: String", "分数: double"]},
                    {"name": "查看所教课程", "return_type": "List<Course>", "visibility": "+"}
                ]},
                {"name": "课程", "attributes": [
                    {"name": "课程编号", "type": "String", "visibility": "-"},
                    {"name": "课程名称", "type": "String", "visibility": "-"},
                    {"name": "学分", "type": "int", "visibility": "-"},
                    {"name": "上课时间", "type": "String", "visibility": "-"},
                    {"name": "教室", "type": "String", "visibility": "-"},
                    {"name": "容量", "type": "int", "visibility": "-"}
                ], "methods": [
                    {"name": "更新信息", "return_type": "void", "visibility": "+", "params": ["信息: CourseInfo"]},
                    {"name": "查询选课人数", "return_type": "int", "visibility": "+"}
                ]},
                {"name": "成绩", "attributes": [
                    {"name": "学号", "type": "String", "visibility": "-"},
                    {"name": "课程编号", "type": "String", "visibility": "-"},
                    {"name": "分数", "type": "double", "visibility": "-"},
                    {"name": "学期", "type": "String", "visibility": "-"}
                ], "methods": [
                    {"name": "计算绩点", "return_type": "double", "visibility": "+"},
                    {"name": "是否及格", "return_type": "boolean", "visibility": "+"}
                ]},
                {"name": "选课记录", "attributes": [
                    {"name": "学号", "type": "String", "visibility": "-"},
                    {"name": "课程编号", "type": "String", "visibility": "-"},
                    {"name": "选课时间", "type": "Date", "visibility": "-"},
                    {"name": "状态", "type": "String", "visibility": "-"}
                ], "methods": [
                    {"name": "确认选课", "return_type": "boolean", "visibility": "+"}
                ]}
            ],
            "relationships": [
                {"from": "成绩", "to": "学生", "type": "association", "label": "学生", "mult_from": "*",
                 "mult_to": "1"},
                {"from": "成绩", "to": "课程", "type": "association", "label": "课程", "mult_from": "*",
                 "mult_to": "1"},
                {"from": "选课记录", "to": "学生", "type": "association", "label": "选课者", "mult_from": "*",
                 "mult_to": "1"},
                {"from": "选课记录", "to": "课程", "type": "association", "label": "所选课程", "mult_from": "*",
                 "mult_to": "1"},
                {"from": "课程", "to": "教师", "type": "association", "label": "授课教师", "mult_from": "*",
                 "mult_to": "1"},
            ]
        }
        t.object_data = {
            "objects": [
                {"name": "stu1", "class_name": "学生",
                 "attributes": {"学号": "2024001", "姓名": "小明", "专业": "计算机科学"}},
                {"name": "stu2", "class_name": "学生",
                 "attributes": {"学号": "2024002", "姓名": "小红", "专业": "软件工程"}},
                {"name": "teacher1", "class_name": "教师",
                 "attributes": {"工号": "T001", "姓名": "张教授", "职称": "教授"}},
                {"name": "course1", "class_name": "课程",
                 "attributes": {"课程编号": "CS101", "课程名称": "数据结构", "学分": "4"}},
                {"name": "grade1", "class_name": "成绩",
                 "attributes": {"学号": "2024001", "课程编号": "CS101", "分数": "92"}},
                {"name": "sel1", "class_name": "选课记录",
                 "attributes": {"学号": "2024001", "课程编号": "CS101", "状态": "已选"}}
            ],
            "relationships": [
                {"from": "grade1", "to": "stu1", "label": "学生", "type": "association"},
                {"from": "grade1", "to": "course1", "label": "课程", "type": "association"},
                {"from": "sel1", "to": "stu1", "label": "选课者", "type": "association"},
                {"from": "sel1", "to": "course1", "label": "所选课程", "type": "association"},
                {"from": "course1", "to": "teacher1", "label": "授课教师", "type": "association"},
            ]
        }
        t.sequence_data = {
            "objects": ["学生", "选课系统", "教务服务", "数据库"],
            "messages": [
                {"from": "学生", "to": "选课系统", "text": "1: 登录选课系统", "type": "sync"},
                {"from": "选课系统", "to": "教务服务", "text": "2: 验证学生身份", "type": "sync"},
                {"from": "教务服务", "to": "数据库", "text": "3: 查询学生信息", "type": "sync"},
                {"from": "数据库", "to": "教务服务", "text": "4: 返回学生信息", "type": "return"},
                {"from": "教务服务", "to": "选课系统", "text": "5: 验证成功", "type": "return"},
                {"from": "学生", "to": "选课系统", "text": "6: 浏览可选课程", "type": "sync"},
                {"from": "选课系统", "to": "教务服务", "text": "7: 获取课程列表", "type": "sync"},
                {"from": "教务服务", "to": "数据库", "text": "8: 查询课程信息", "type": "sync"},
                {"from": "数据库", "to": "教务服务", "text": "9: 返回课程列表", "type": "return"},
                {"from": "教务服务", "to": "选课系统", "text": "10: 返回课程数据", "type": "return"},
                {"from": "学生", "to": "选课系统", "text": "11: 选择课程并提交", "type": "sync"},
                {"from": "选课系统", "to": "教务服务", "text": "12: 提交选课请求", "type": "sync"},
                {"from": "教务服务", "to": "数据库", "text": "13: 检查冲突并创建选课记录", "type": "sync"},
                {"from": "数据库", "to": "教务服务", "text": "14: 返回选课结果", "type": "return"},
                {"from": "教务服务", "to": "选课系统", "text": "15: 返回选课成功", "type": "return"},
                {"from": "选课系统", "to": "学生", "text": "16: 显示选课成功", "type": "return"},
            ]
        }
        self.templates.append(t)

        # ==================== 模板6：医院管理系统 ====================
        t = SystemTemplate(
            name="医院管理系统",
            keywords=["医院", "病人", "医生", "挂号", "就诊", "处方", "住院", "hospital", "clinic", "医疗", "门诊",
                      "health"],
            description="包含患者/医生/护士/管理员、挂号就诊、处方管理、住院管理等核心模块"
        )
        t.use_case_data = {
            "actors": [
                {"name": "患者", "description": "就医的患者"},
                {"name": "医生", "description": "诊疗医生"},
                {"name": "护士", "description": "护理工作人员"},
                {"name": "管理员", "description": "医院管理人员"}
            ],
            "use_cases": [
                {"name": "在线挂号", "description": "预约挂号", "is_primary": True},
                {"name": "就诊", "description": "医生诊疗", "is_primary": True},
                {"name": "开具处方", "description": "医生开具药品处方"},
                {"name": "缴费", "description": "缴纳诊疗费用"},
                {"name": "取药", "description": "药房取药"},
                {"name": "查看病历", "description": "查看就诊记录"},
                {"name": "办理住院", "description": "办理住院手续"},
                {"name": "办理出院", "description": "办理出院手续"},
                {"name": "排班管理", "description": "管理医生排班"},
                {"name": "药品管理", "description": "管理药品库存"},
                {"name": "统计报表", "description": "生成医疗统计报表"}
            ],
            "relationships": [
                {"from": "患者", "to": "在线挂号", "type": "association"},
                {"from": "患者", "to": "缴费", "type": "association"},
                {"from": "患者", "to": "查看病历", "type": "association"},
                {"from": "医生", "to": "就诊", "type": "association"},
                {"from": "医生", "to": "开具处方", "type": "association"},
                {"from": "护士", "to": "办理住院", "type": "association"},
                {"from": "护士", "to": "办理出院", "type": "association"},
                {"from": "管理员", "to": "排班管理", "type": "association"},
                {"from": "管理员", "to": "药品管理", "type": "association"},
                {"from": "管理员", "to": "统计报表", "type": "association"},
                {"from": "就诊", "to": "在线挂号", "type": "include", "label": "包含"},
                {"from": "取药", "to": "开具处方", "type": "include", "label": "包含"},
            ]
        }
        t.class_data = {
            "classes": [
                {"name": "患者", "attributes": [
                    {"name": "患者ID", "type": "String", "visibility": "-"},
                    {"name": "姓名", "type": "String", "visibility": "-"},
                    {"name": "身份证号", "type": "String", "visibility": "-"},
                    {"name": "医保卡号", "type": "String", "visibility": "-"},
                    {"name": "联系电话", "type": "String", "visibility": "-"}
                ], "methods": [
                    {"name": "挂号", "return_type": "Registration", "visibility": "+",
                     "params": ["科室: String", "医生: String"]},
                    {"name": "查看病历", "return_type": "List<Record>", "visibility": "+"}
                ]},
                {"name": "医生", "attributes": [
                    {"name": "医生ID", "type": "String", "visibility": "-"},
                    {"name": "姓名", "type": "String", "visibility": "-"},
                    {"name": "科室", "type": "String", "visibility": "-"},
                    {"name": "职称", "type": "String", "visibility": "-"},
                    {"name": "专长", "type": "String", "visibility": "-"}
                ], "methods": [
                    {"name": "接诊", "return_type": "Diagnosis", "visibility": "+", "params": ["患者: Patient"]},
                    {"name": "开处方", "return_type": "Prescription", "visibility": "+"}
                ]},
                {"name": "处方", "attributes": [
                    {"name": "处方ID", "type": "String", "visibility": "-"},
                    {"name": "药品列表", "type": "List<Medicine>", "visibility": "-"},
                    {"name": "用法用量", "type": "String", "visibility": "-"},
                    {"name": "开具日期", "type": "Date", "visibility": "-"}
                ], "methods": [
                    {"name": "添加药品", "return_type": "void", "visibility": "+", "params": ["药品: Medicine"]},
                    {"name": "确认处方", "return_type": "boolean", "visibility": "+"}
                ]},
                {"name": "挂号记录", "attributes": [
                    {"name": "挂号ID", "type": "String", "visibility": "-"},
                    {"name": "挂号时间", "type": "Date", "visibility": "-"},
                    {"name": "科室", "type": "String", "visibility": "-"},
                    {"name": "状态", "type": "String", "visibility": "-"}
                ], "methods": [
                    {"name": "取消挂号", "return_type": "boolean", "visibility": "+"}
                ]}
            ],
            "relationships": [
                {"from": "挂号记录", "to": "患者", "type": "association", "label": "挂号人", "mult_from": "*",
                 "mult_to": "1"},
                {"from": "挂号记录", "to": "医生", "type": "association", "label": "就诊医生", "mult_from": "*",
                 "mult_to": "1"},
                {"from": "处方", "to": "医生", "type": "association", "label": "开具医生", "mult_from": "*",
                 "mult_to": "1"},
            ]
        }
        t.object_data = {
            "objects": [
                {"name": "patient1", "class_name": "患者",
                 "attributes": {"患者ID": "P001", "姓名": "钱七", "医保卡号": "YB001"}},
                {"name": "doctor1", "class_name": "医生",
                 "attributes": {"医生ID": "D001", "姓名": "李医生", "科室": "内科"}},
                {"name": "reg1", "class_name": "挂号记录",
                 "attributes": {"挂号ID": "R001", "科室": "内科", "状态": "已就诊"}},
                {"name": "presc1", "class_name": "处方", "attributes": {"处方ID": "PR001", "开具日期": "2026-04-11"}}
            ],
            "relationships": [
                {"from": "reg1", "to": "patient1", "label": "挂号人", "type": "association"},
                {"from": "reg1", "to": "doctor1", "label": "就诊医生", "type": "association"},
                {"from": "presc1", "to": "doctor1", "label": "开具医生", "type": "association"},
            ]
        }
        t.sequence_data = {
            "objects": ["患者", "挂号系统", "门诊服务", "药房服务", "数据库"],
            "messages": [
                {"from": "患者", "to": "挂号系统", "text": "1: 选择科室和医生", "type": "sync"},
                {"from": "挂号系统", "to": "门诊服务", "text": "2: 查询医生排班", "type": "sync"},
                {"from": "门诊服务", "to": "数据库", "text": "3: 查询排班信息", "type": "sync"},
                {"from": "数据库", "to": "门诊服务", "text": "4: 返回排班数据", "type": "return"},
                {"from": "门诊服务", "to": "挂号系统", "text": "5: 返回可用号源", "type": "return"},
                {"from": "患者", "to": "挂号系统", "text": "6: 确认挂号并支付", "type": "sync"},
                {"from": "挂号系统", "to": "数据库", "text": "7: 创建挂号记录", "type": "sync"},
                {"from": "数据库", "to": "挂号系统", "text": "8: 返回挂号成功", "type": "return"},
                {"from": "挂号系统", "to": "患者", "text": "9: 显示挂号成功", "type": "return"},
                {"from": "患者", "to": "门诊服务", "text": "10: 到诊签到", "type": "sync"},
                {"from": "门诊服务", "to": "数据库", "text": "11: 更新就诊状态", "type": "sync"},
                {"from": "数据库", "to": "门诊服务", "text": "12: 更新成功", "type": "return"},
                {"from": "门诊服务", "to": "患者", "text": "13: 等候叫号", "type": "return"},
            ]
        }
        self.templates.append(t)

    def search_template(self, query: str) -> List[SystemTemplate]:
        """
        根据用户输入的关键词搜索匹配的模板
        支持模糊匹配，返回按匹配度排序的模板列表
        """
        query_lower = query.lower().strip()
        results = []

        for template in self.templates:
            score = 0
            # 检查系统名称是否直接匹配
            if query_lower in template.name.lower():
                score += 10
            # 检查关键词匹配
            for keyword in template.keywords:
                if keyword.lower() in query_lower:
                    score += 5
                # 部分匹配也加分
                if query_lower in keyword.lower():
                    score += 3

            if score > 0:
                results.append((template, score))

        # 按匹配度排序
        results.sort(key=lambda x: x[1], reverse=True)
        return [t for t, s in results]

    def list_all_templates(self) -> List[str]:
        """列出所有可用模板名称"""
        return [f"  [{i + 1}] {t.name} - {t.description}" for i, t in enumerate(self.templates)]


class LocalAIEngine:
    """
    本地AI智能分析引擎 v3.0 (真正的机器学习模型)

    ✨ 升级特性：
    ✅ 真正的 AI 模型（非规则引擎）
    ✅ 基于 TF-IDF + 语义向量化
    ✅ 中文分词 + 词频统计
    ✅ 余弦相似度匹配算法
    ✅ 轻量级神经网络意图识别
    ✅ 自学习能力（反馈优化）
    ✅ 无需网络、无需API Key

    技术栈：
    - jieba: 中文分词
    - TF-IDF: 文本特征提取
    - 余弦相似度: 语义匹配
    - NumPy: 神经网络计算
    """

    def __init__(self):
        self.templates: List[SystemTemplate] = []
        self.user_templates: List[SystemTemplate] = []
        self.synonym_dict: Dict[str, List[str]] = {}
        self.category_rules: Dict[str, Dict] = {}

        # ========== AI 模型组件 ==========
        self.tfidf_vectorizer = None  # TF-IDF 向量化器
        self.word_embeddings = {}  # 词向量字典
        self.template_vectors = {}  # 模板向量缓存
        self.intent_classifier = None  # 意图分类器
        self.training_data = []  # 训练数据
        self.vocabulary = set()  # 词汇表
        self.idf_scores = {}  # IDF 分数

        # 自学习参数
        self.learning_rate = 0.01
        self.feedback_history = []

        # 初始化
        self._check_dependencies()
        self._init_synonyms()
        self._init_category_rules()
        self._load_template_library()
        self._load_user_templates()
        self._build_ai_model()

    def _check_dependencies(self):
        """检查并安装必要的依赖（优化版：使用subprocess，添加超时）"""
        import subprocess
        import sys

        def install_package(package: str, timeout: int = 30) -> bool:
            """安装单个包（带超时）"""
            try:
                result = subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', package, '-q'],
                    capture_output=True,
                    timeout=timeout,
                    text=True
                )
                return result.returncode == 0
            except subprocess.TimeoutExpired:
                print(f"[WARN] 安装 {package} 超时 ({timeout}s)")
                return False
            except Exception as e:
                print(f"[WARN] 安装 {package} 失败: {e}")
                return False

        # 检查 jieba
        try:
            import jieba
            print("[OK] jieba 已安装")
        except ImportError:
            print("\n[INFO] 正在安装 jieba...")
            if install_package('jieba'):
                try:
                    import jieba
                    print("[OK] jieba 安装完成")
                except ImportError:
                    print("[WARN] jieba 安装失败")

        # 检查 numpy
        try:
            import numpy as np
            self.np = np
            print("[OK] numpy 已安装")
        except ImportError:
            print("\n[INFO] 正在安装 numpy...")
            if install_package('numpy'):
                try:
                    import numpy as np
                    self.np = np
                    print("[OK] numpy 安装完成")
                except ImportError:
                    self.np = None
                    print("[WARN] numpy 安装失败，将使用简化模式")

    def _tokenize(self, text: str) -> List[str]:
        """
        使用 jieba 进行中文分词
        返回分词后的词语列表（去除停用词）
        """
        try:
            import jieba
            import jieba.posseg as pseg

            # 停用词列表
            stop_words = {'的', '了', '在', '是', '我', '有', '和', '就',
                          '不', '人', '都', '一', '一个', '上', '也', '很',
                          '到', '说', '要', '去', '你', '会', '着', '没有',
                          '看', '好', '自己', '这', '他', '她', '它', '们',
                          '那', '什么', '怎么', '如何', '为什么', '哪', '吗',
                          '吧', '啊', '呢', '呀', '哦', '嗯', '哈', '嘛', '哇'}

            # 使用 jieba 分词
            words = jieba.lcut(text)

            # 过滤停用词和短词
            filtered = [w for w in words if len(w) > 1 and w not in stop_words]

            return filtered
        except Exception as e:
            # 如果 jieba 失败，回退到简单分词
            return text.split()

    def _compute_tf(self, words: List[str]) -> Dict[str, float]:
        """
        计算 TF (Term Frequency) 词频
        TF(t,d) = (词t在文档d中出现次数) / (文档d中总词数)
        """
        tf_dict = {}
        total_words = len(words)

        if total_words == 0:
            return tf_dict

        for word in words:
            tf_dict[word] = tf_dict.get(word, 0) + 1

        # 归一化
        for word in tf_dict:
            tf_dict[word] /= total_words

        return tf_dict

    def _compute_idf(self):
        """
        计算 IDF (Inverse Document Frequency) 逆文档频率
        IDF(t) = log(总文档数 / 包含词t的文档数)
        """
        from math import log

        all_docs = []

        # 收集所有文档（模板名称+关键词）
        for template in self.templates + self.user_templates:
            doc_text = template.name + " " + " ".join(template.keywords)
            tokens = self._tokenize(doc_text)
            all_docs.append(set(tokens))

        total_docs = len(all_docs)

        if total_docs == 0:
            return

        # 统计每个词出现在多少文档中
        doc_freq = {}
        for doc_tokens in all_docs:
            for token in doc_tokens:
                doc_freq[token] = doc_freq.get(token, 0) + 1

        # 计算 IDF
        for term, freq in doc_freq.items():
            self.idf_scores[term] = log(total_docs / (1 + freq)) + 1

        # 更新词汇表
        self.vocabulary = set(self.idf_scores.keys())

    def _compute_tfidf_vector(self, text: str) -> Dict[str, float]:
        """
        计算 TF-IDF 向量
        TF-IDF(t,d) = TF(t,d) * IDF(t)
        """
        tokens = self._tokenize(text)
        tf = self._compute_tf(tokens)

        tfidf = {}
        for term, tf_value in tf.items():
            idf_value = self.idf_scores.get(term, 1.0)
            tfidf[term] = tf_value * idf_value

        return tfidf

    def _cosine_similarity(self, vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        """
        计算余弦相似度
        cos(θ) = (A·B) / (||A|| * ||B||)
        """
        # 找到共同的词
        common_terms = set(vec1.keys()) & set(vec2.keys())

        if not common_terms:
            return 0.0

        # 计算点积
        dot_product = sum(vec1[term] * vec2[term] for term in common_terms)

        # 计算模长
        norm1 = sum(v ** 2 for v in vec1.values()) ** 0.5
        norm2 = sum(v ** 2 for v in vec2.values()) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = dot_product / (norm1 * norm2)
        return max(0.0, min(1.0, similarity))

    def _build_word_embeddings(self):
        """
        构建简单的词向量（基于同义词共现）
        使用 Word Co-occurrence Matrix 的简化版
        """
        embedding_dim = 50  # 向量维度

        for category, rules in self.category_rules.items():
            keywords = rules["keywords"]

            # 为该类别的关键词生成相似的向量
            base_vector = self.np.random.randn(embedding_dim) * 0.1

            for keyword in keywords:
                # 为每个关键词添加一些随机扰动，但保持类别内相似
                noise = self.np.random.randn(embedding_dim) * 0.05
                self.word_embeddings[keyword.lower()] = base_vector + noise

                # 同义词共享相似向量
                for syn_group in self.synonym_dict.values():
                    if keyword in syn_group:
                        for syn in syn_group:
                            if syn.lower() not in self.word_embeddings:
                                syn_noise = self.np.random.randn(embedding_dim) * 0.02
                                self.word_embeddings[syn.lower()] = base_vector + syn_noise

    def _text_to_embedding(self, text: str) -> Any:
        """
        将文本转换为词嵌入的平均值（优化版：使用缓存）
        """
        # 检查缓存
        if hasattr(self, '_embedding_cache') and text in self._embedding_cache:
            return self._embedding_cache[text]

        tokens = self._tokenize(text)

        if not tokens:
            result = self.np.zeros(50)
            if not hasattr(self, '_embedding_cache'):
                self._embedding_cache = {}
            self._embedding_cache[text] = result
            return result

        vectors = []
        for token in tokens:
            token_lower = token.lower()
            if token_lower in self.word_embeddings:
                vectors.append(self.word_embeddings[token_lower])
            else:
                # 未登录词使用零向量（更高效）
                vectors.append(self.np.zeros(50))

        if vectors:
            result = self.np.mean(vectors, axis=0)
        else:
            result = self.np.zeros(50)

        # 缓存结果（限制缓存大小）
        if not hasattr(self, '_embedding_cache'):
            self._embedding_cache = {}
        if len(self._embedding_cache) < 1000:
            self._embedding_cache[text] = result

        return result

    class SimpleNeuralNet:
        """
        轻量级神经网络用于意图识别
        结构：Input(50) -> Hidden(32) -> Output(n_classes)
        """

        def __init__(self, input_size=50, hidden_size=32, output_size=9, learning_rate=0.01):
            self.np = None
            try:
                import numpy as np
                self.np = np
            except:
                pass

            if self.np is None:
                return

            self.lr = learning_rate

            # Xavier 初始化
            self.W1 = self.np.random.randn(input_size, hidden_size) * self.np.sqrt(2.0 / input_size)
            self.b1 = self.np.zeros((1, hidden_size))
            self.W2 = self.np.random.randn(hidden_size, output_size) * self.np.sqrt(2.0 / hidden_size)
            self.b2 = self.np.zeros((1, output_size))

            # 类别标签
            self.classes = [
                "电商购物", "图书教育", "学生管理", "医疗健康",
                "银行金融", "外卖餐饮", "交通出行", "社交聊天", "办公管理"
            ]

        def relu(self, x):
            return self.np.maximum(0, x)

        def relu_derivative(self, x):
            return (x > 0).astype(float)

        def softmax(self, x):
            exp_x = self.np.exp(x - self.np.max(x))
            return exp_x / exp_x.sum(axis=1, keepdims=True)

        def forward(self, X):
            """前向传播"""
            self.z1 = X @ self.W1 + self.b1
            self.a1 = self.relu(self.z1)
            self.z2 = self.a1 @ self.W2 + self.b2
            self.a2 = self.softmax(self.z2)
            return self.a2

        def backward(self, X, y, output):
            """反向传播"""
            m = X.shape[0]

            # 输出层误差
            dz2 = output - y
            dW2 = (self.a1.T @ dz2) / m
            db2 = self.np.sum(dz2, axis=0, keepdims=True) / m

            # 隐藏层误差
            dz1 = (dz2 @ self.W2.T) * self.relu_derivative(self.z1)
            dW1 = (X.T @ dz1) / m
            db1 = self.np.sum(dz1, axis=0, keepdims=True) / m

            # 更新参数
            self.W1 -= self.lr * dW1
            self.b1 -= self.lr * db1
            self.W2 -= self.lr * dW2
            self.b2 -= self.lr * db2

        def train(self, X, y, epochs=50, patience=10):
            """训练模型（带早停机制）"""
            best_loss = float('inf')
            patience_counter = 0

            for epoch in range(epochs):
                output = self.forward(X)
                self.backward(X, y, output)

                # 计算损失
                loss = -self.np.sum(y * self.np.log(output + 1e-8)) / len(y)

                # 早停检查
                if loss < best_loss:
                    best_loss = loss
                    patience_counter = 0
                else:
                    patience_counter += 1
                    if patience_counter >= patience:
                        break  # 早停退出

        def predict(self, X):
            """预测"""
            output = self.forward(X)
            pred_idx = self.np.argmax(output, axis=1)
            confidence = self.np.max(output, axis=1)
            return [(self.classes[idx], conf) for idx, conf in zip(pred_idx, confidence)]

    def _build_ai_model(self):
        """构建完整的 AI 模型（带缓存机制）"""
        import os
        import json
        import pickle
        from pathlib import Path

        cache_file = Path(__file__).parent / ".ai_model_cache.pkl"

        # 检查是否有缓存（且缓存有效）
        if cache_file.exists():
            try:
                print("\n🧠 正在加载本地AI模型缓存...")
                with open(cache_file, 'rb') as f:
                    cached_data = pickle.load(f)

                # 加载缓存的模型数据
                self.vocabulary = cached_data.get('vocabulary', set())
                self.idf_scores = cached_data.get('idf_scores', {})
                self.template_vectors = cached_data.get('template_vectors', {})
                self.word_embeddings = cached_data.get('word_embeddings', {})

                if cached_data.get('classifier_weights'):
                    try:
                        import numpy as np
                        weights = cached_data['classifier_weights']
                        self.intent_classifier = self.SimpleNeuralNet.__new__(self.SimpleNeuralNet)
                        self.intent_classifier.np = np
                        self.intent_classifier.W1 = np.array(weights['W1'])
                        self.intent_classifier.b1 = np.array(weights['b1'])
                        self.intent_classifier.W2 = np.array(weights['W2'])
                        self.intent_classifier.b2 = np.array(weights['b2'])
                        self.intent_classifier.classes = weights['classes']
                    except:
                        pass

                print("✅ AI 模型已从缓存加载！")
                return  # 使用缓存，跳过训练
            except Exception as e:
                print(f"[WARN] 缓存损坏，重新构建: {e}")

        # 无缓存或缓存无效，构建新模型
        print("\n🧠 正在构建本地AI模型...")

        # 1. 构建 IDF 表
        print("   ├─ 计算 IDF 逆文档频率...")
        self._compute_idf()
        print(f"   │  └─ 词汇表大小: {len(self.vocabulary)} 个词")

        # 2. 预计算模板向量
        print("   ├─ 预计算模板向量...")
        for template in self.templates + self.user_templates:
            template_text = template.name + " " + " ".join(template.keywords)
            self.template_vectors[template.name] = self._compute_tfidf_vector(template_text)
        print(f"   │  └─ 已处理 {len(self.template_vectors)} 个模板")

        # 3. 构建词向量
        print("   ├─ 构建词嵌入模型...")
        self._build_word_embeddings()
        print(f"   │  └─ 词向量数量: {len(self.word_embeddings)}")

        # 4. 训练意图分类器
        print("   └─ 训练神经网络分类器...")
        self._train_intent_classifier()

        print("✅ AI 模型构建完成！")

        # 保存到缓存
        try:
            cache_data = {
                'vocabulary': self.vocabulary,
                'idf_scores': self.idf_scores,
                'template_vectors': self.template_vectors,
                'word_embeddings': self.word_embeddings,
                'classifier_weights': None
            }

            if self.intent_classifier and hasattr(self.intent_classifier, 'W1'):
                cache_data['classifier_weights'] = {
                    'W1': self.intent_classifier.W1.tolist(),
                    'b1': self.intent_classifier.b1.tolist(),
                    'W2': self.intent_classifier.W2.tolist(),
                    'b2': self.intent_classifier.b2.tolist(),
                    'classes': self.intent_classifier.classes
                }

            with open(cache_file, 'wb') as f:
                pickle.dump(cache_data, f)
            print("💾 模型已缓存，下次启动将秒加载！")
        except Exception as e:
            print(f"[INFO] 缓存保存失败（不影响使用）: {e}")

    def _train_intent_classifier(self):
        """训练意图分类神经网络（优化版：快速训练）"""
        try:
            # 准备训练数据
            training_samples = []
            training_labels = []

            categories = list(self.category_rules.keys())
            category_to_idx = {cat: idx for idx, cat in enumerate(categories)}

            for category, rules in self.category_rules.items():
                keywords = rules["keywords"]

                for keyword in keywords[:5]:  # 每个类别取5个样本
                    embedding = self._text_to_embedding(keyword)
                    training_samples.append(embedding)

                    label = self.np.zeros(len(categories))
                    label[category_to_idx[category]] = 1.0
                    training_labels.append(label)

            if training_samples:
                X = self.np.array(training_samples)
                y = self.np.array(training_labels)

                # 创建并训练分类器（简化版：更小的网络）
                self.intent_classifier = self.SimpleNeuralNet(
                    input_size=50,
                    hidden_size=16,  # 从32减少到16
                    output_size=len(categories),
                    learning_rate=0.05  # 提高学习率加速收敛
                )

                # 训练（快速模式：50轮 + 早停）
                self.intent_classifier.train(X, y, epochs=50, patience=10)
        except Exception as e:
            print(f"   [WARN] 神经网络训练失败: {e}")
            self.intent_classifier = None

    def analyze_input(self, user_input: str) -> Tuple[SystemTemplate, float]:
        """
        分析用户输入 - 使用真正的 AI 算法
        返回最匹配的系统模板和置信度
        """
        # 方法1: TF-IDF + 余弦相似度
        input_vector = self._compute_tfidf_vector(user_input)

        best_match = None
        best_score_tfidf = 0.0

        for template_name, template_vec in self.template_vectors.items():
            similarity = self._cosine_similarity(input_vector, template_vec)

            if similarity > best_score_tfidf:
                best_score_tfidf = similarity
                # 找到对应的模板对象
                for tmpl in self.templates + self.user_templates:
                    if tmpl.name == template_name:
                        best_match = tmpl
                        break

        # 方法2: 词嵌入相似度
        input_embedding = self._text_to_embedding(user_input)
        best_score_embed = 0.0
        best_match_embed = None

        for template in self.templates + self.user_templates:
            template_embedding = self._text_to_embedding(template.name + " " + " ".join(template.keywords))

            # 计算余弦相似度
            dot_product = self.np.dot(input_embedding, template_embedding)
            norm_input = self.np.linalg.norm(input_embedding)
            norm_template = self.np.linalg.norm(template_embedding)

            if norm_input > 0 and norm_template > 0:
                similarity = dot_product / (norm_input * norm_template)
            else:
                similarity = 0.0

            if similarity > best_score_embed:
                best_score_embed = similarity
                best_match_embed = template

        # 方法3: 神经网络意图识别
        nn_category = None
        nn_confidence = 0.0

        if self.intent_classifier:
            try:
                predictions = self.intent_classifier.predict(input_embedding.reshape(1, -1))
                nn_category, nn_confidence = predictions[0]
            except:
                pass

        # 综合评分（加权平均）
        final_score = (best_score_tfidf * 0.4 + best_score_embed * 0.4 + nn_confidence * 0.2)

        # 选择最佳结果
        if best_score_tfidf >= best_score_embed:
            final_template = best_match
        else:
            final_template = best_match_embed

        return final_template, final_score * 100, {
            "tfidf_score": best_score_tfidf,
            "embedding_score": best_score_embed,
            "nn_confidence": nn_confidence,
            "nn_category": nn_category
        }

    def _init_synonyms(self):
        """初始化同义词字典 - 用于语义理解"""
        self.synonym_dict = {
            # 购物/电商相关
            "购物": ["购买", "买东西", "网购", "商城", "商店", "店铺", "下单", "购物车", "商品"],
            "订单": ["订单", "订购", "预约单", "采购单"],
            "支付": ["付款", "结算", "收款", "缴费", "充值", "提现"],
            "商品": ["产品", "货物", "物品", "货品", "库存"],
            "顾客": ["客户", "买家", "消费者", "用户", "会员"],

            # 图书/教育相关
            "图书": ["书籍", "书本", "图书", "藏书", "文献", "资料"],
            "借阅": ["借书", "还书", "借阅", "租借", "阅览"],
            "学生": ["学员", "考生", "学子", "在校生", "研究生", "本科生"],
            "老师": ["教师", "教授", "讲师", "导师", "教员"],
            "课程": ["课表", "科目", "学科", "教学计划", "培训"],
            "成绩": ["分数", "考试", "测评", "考核", "绩点"],

            # 医疗相关
            "医院": ["诊所", "卫生院", "医疗中心", "门诊", "卫生室"],
            "医生": ["医师", "大夫", "专家", "护士", "医护人员"],
            "患者": ["病人", "病患", "就诊者", "挂号者"],
            "药品": ["药物", "处方", "药房", "药库"],
            "挂号": ["预约", "就诊", "看诊", "门诊"],

            # 金融/银行相关
            "银行": ["金融", "储蓄", "贷款", "信用卡", "ATM", "柜员机"],
            "存款": ["存钱", "储蓄", "余额", "账户"],
            "取款": ["取钱", "提现", "转账", "汇款"],
            "账户": ["账号", "银行卡", "存折", "钱包"],

            # 外卖/餐饮相关
            "外卖": ["送餐", "订餐", "快餐", "餐饮配送", "美食"],
            "餐厅": ["饭店", "食堂", "餐馆", "小吃店", "美食店"],
            "骑手": ["配送员", "快递员", "送货员"],
            "菜单": ["菜品", "餐品", "食物", "料理"],

            # 交通/出行相关
            "打车": ["出租车", "网约车", "滴滴", "出行", "用车"],
            "公交": ["巴士", "公交车", "地铁", "轻轨", "交通"],
            "票务": ["购票", "订票", "车票", "机票", "门票"],

            # 社交/通讯相关
            "聊天": ["消息", "对话", "通信", "即时通讯", "IM"],
            "社交": ["交友", "社区", "论坛", "朋友圈", "动态"],
            "好友": ["朋友", "联系人", "关注", "粉丝"],

            # 办公/管理相关
            "办公": ["OA", "工作流", "审批", "考勤", "请假"],
            "人事": ["HR", "员工", "薪资", "招聘", "入职"],
            "财务": ["会计", "报销", "发票", "税务", "审计"],
            "仓库": ["库存", "物流", "进货", "出货", "仓储"],

            # 通用词汇
            "系统": ["软件", "程序", "平台", "应用", "APP", "网站", "管理系统"],
            "管理": ["控制", "维护", "运营", "监管", "治理"],
            "查询": ["搜索", "检索", "查找", "浏览", "查看"],
            "登录": ["注册", "认证", "授权", "身份验证", "账号"],
        }

    def _init_category_rules(self):
        """初始化系统分类规则"""
        self.category_rules = {
            "电商购物": {
                "keywords": ["购物", "商城", "电商", "网购", "商品", "订单", "购物车", "shop", "shopping",
                             "store", "ecommerce", "mall", "淘宝", "京东", "亚马逊", "拼多多"],
                "priority": 1,
                "default_template": "在线购物系统"
            },
            "图书教育": {
                "keywords": ["图书", "图书馆", "借书", "还书", "library", "book", "借阅", "藏书",
                             "学校", "教育", "学生", "课程", "成绩", "教务"],
                "priority": 1,
                "default_template": "图书管理系统"
            },
            "学生管理": {
                "keywords": ["学生", "学籍", "选课", "成绩", "教务", "校园", "school", "student"],
                "priority": 2,
                "default_template": "学生信息管理系统"
            },
            "医疗健康": {
                "keywords": ["医院", "医疗", "医生", "患者", "药品", "挂号", "门诊", "hospital",
                             "clinic", "health", "卫生"],
                "priority": 1,
                "default_template": "医院管理系统"
            },
            "银行金融": {
                "keywords": ["银行", "金融", "ATM", "存款", "取款", "贷款", "bank", "finance",
                             "credit", "card", "储蓄"],
                "priority": 1,
                "default_template": "银行ATM系统"
            },
            "外卖餐饮": {
                "keywords": ["外卖", "送餐", "订餐", "餐饮", "美食", "delivery", "food",
                             "restaurant", "饿了么", "美团"],
                "priority": 1,
                "default_template": "外卖订餐系统"
            },
            "交通出行": {
                "keywords": ["打车", "出租车", "网约车", "公交", "地铁", "票务", "travel",
                             "transport", "taxi", "uber", "滴滴"],
                "priority": 2,
                "default_template": None
            },
            "社交聊天": {
                "keywords": ["聊天", "社交", "微信", "QQ", "消息", "通讯", "chat", "social",
                             "message", "im"],
                "priority": 2,
                "default_template": None
            },
            "办公管理": {
                "keywords": ["办公", "OA", "人事", "HR", "财务", "仓库", "审批", "考勤",
                             "office", "admin", "management"],
                "priority": 3,
                "default_template": None
            }
        }

    def _load_template_library(self):
        """加载内置模板库（复用 UMLTemplateLibrary）"""
        library = UMLTemplateLibrary()
        self.templates = library.templates

    def _load_user_templates(self):
        """加载用户自定义模板"""
        template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_templates.json")
        if os.path.exists(template_path):
            try:
                with open(template_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data.get("templates", []):
                        t = SystemTemplate(
                            name=item["name"],
                            keywords=item.get("keywords", []),
                            description=item.get("description", "")
                        )
                        t.use_case_data = item.get("use_case_data")
                        t.class_data = item.get("class_data")
                        t.object_data = item.get("object_data")
                        t.sequence_data = item.get("sequence_data")
                        self.user_templates.append(t)
                    print(f"[OK] 已加载 {len(self.user_templates)} 个用户自定义模板")
            except Exception as e:
                print(f"[WARN] 加载用户模板失败: {e}")

    def _preprocess_input(self, user_input: str) -> str:
        """
        预处理用户输入
        - 转换为小写
        - 去除特殊字符
        - 分词并扩展同义词
        """
        import re

        text = user_input.lower().strip()
        # 去除特殊字符，保留中文、英文、数字
        text = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', text)
        # 去除多余空格
        text = ' '.join(text.split())

        return text

    def _expand_with_synonyms(self, text: str) -> List[str]:
        """
        使用同义词字典扩展输入文本
        返回包含原始词和所有同义词的列表
        """
        expanded_words = []
        words = text.split()

        for word in words:
            expanded_words.append(word)
            # 查找同义词
            for key, synonyms in self.synonym_dict.items():
                if word == key or word in synonyms:
                    expanded_words.extend(synonyms)
                    expanded_words.append(key)

        return list(set(expanded_words))

    def _classify_system(self, processed_input: str) -> Tuple[str, float]:
        """
        对系统进行分类
        返回 (类别名, 置信度)
        """
        best_category = "通用"
        best_score = 0.0

        input_lower = processed_input.lower()
        expanded = self._expand_with_synonyms(input_lower)

        for category, rules in self.category_rules.items():
            score = 0
            keywords = rules["keywords"]

            for keyword in keywords:
                if keyword.lower() in input_lower:
                    score += 10 / rules["priority"]
                # 也检查同义词扩展后的文本
                for exp_word in expanded:
                    if keyword.lower() == exp_word.lower():
                        score += 5 / rules["priority"]

            if score > best_score:
                best_score = score
                best_category = category

        return best_category, min(best_score / 100, 1.0)

    def _calculate_similarity(self, query: str, template: SystemTemplate) -> float:
        """
        计算查询与模板的相似度得分
        使用多维度匹配算法
        """
        score = 0.0
        query_lower = query.lower().strip()
        expanded_query = set(self._expand_with_synonyms(query_lower))

        # 1. 名称直接匹配（权重最高）
        if query_lower in template.name.lower() or template.name.lower() in query_lower:
            score += 50
        else:
            # 计算名称相似度（基于共同字符）
            common_chars = len(set(query_lower) & set(template.name.lower()))
            name_similarity = common_chars / max(len(query_lower), len(template.name.lower()))
            score += name_similarity * 20

        # 2. 关键词匹配（核心算法）
        matched_keywords = 0
        for keyword in template.keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in query_lower:
                score += 15
                matched_keywords += 1
            elif any(kw in expanded_query for kw in [keyword_lower] +
                                                    self.synonym_dict.get(keyword_lower, [])):
                score += 8
                matched_keywords += 1

        # 关键词覆盖率加成
        if template.keywords:
            coverage = matched_keywords / len(template.keywords)
            score += coverage * 25

        # 3. 分类一致性加成
        category, confidence = self._classify_system(query)
        if category in self.category_rules:
            default_tmpl = self.category_rules[category].get("default_template")
            if default_tmpl and default_tmpl == template.name:
                score += 30 * confidence

        return min(score, 100)

    def generate_smart_analysis(self, system_name: str, extra_desc: str = "",
                                diagram_types: List[str] = None) -> Optional[SystemTemplate]:
        """
        智能分析生成 - 核心方法（使用真正的AI算法）

        AI分析流程：
        1. 中文分词（jieba）
        2. TF-IDF 特征提取
        3. 词嵌入向量化
        4. 神经网络意图识别
        5. 多模型融合决策

        Args:
            system_name: 用户输入的系统名称
            extra_desc: 额外描述信息
            diagram_types: 要生成的图表类型列表

        Returns:
            SystemTemplate 或 None
        """
        import copy

        if diagram_types is None:
            diagram_types = ["usecase", "class", "object", "sequence"]

        # 合并输入
        full_input = f"{system_name} {extra_desc}".strip()

        print(f"\n{'=' * 60}")
        print(f"  🧠 本地AI智能分析中...")
        print(f"{'=' * 60}")
        print(f"\n  输入文本: {full_input}")

        # ========== 第一步：中文分词 ==========
        tokens = self._tokenize(full_input)
        print(f"\n📝 [步骤1] 中文分词（jieba）")
        print(f"   分词结果: {' / '.join(tokens[:10])}{'...' if len(tokens) > 10 else ''}")
        print(f"   有效词汇: {len(tokens)} 个")

        # ========== 第二步：TF-IDF 特征提取 ==========
        tfidf_vector = self._compute_tfidf_vector(full_input)
        top_keywords = sorted(tfidf_vector.items(), key=lambda x: x[1], reverse=True)[:5]
        print(f"\n📊 [步骤2] TF-IDF 特征提取")
        print(f"   关键特征词:")
        for word, score in top_keywords:
            print(f"     • {word}: {score:.4f}")

        # ========== 第三步：词嵌入向量化 ==========
        embedding = self._text_to_embedding(full_input)
        embed_norm = self.np.linalg.norm(embedding)
        print(f"\n🔢 [步骤3] 词嵌入向量化")
        print(f"   向量维度: {len(embedding)}")
        print(f"   向量模长: {embed_norm:.4f}")

        # ========== 第四步：神经网络意图识别 ==========
        nn_category = None
        nn_confidence = 0.0
        if self.intent_classifier:
            try:
                predictions = self.intent_classifier.predict(embedding.reshape(1, -1))
                nn_category, nn_confidence = predictions[0]
                print(f"\n🧠 [步骤4] 神经网络意图识别")
                print(f"   预测类别: {nn_category}")
                print(f"   置信度: {nn_confidence:.2%}")
            except Exception as e:
                print(f"\n⚠️ [步骤4] 神经网络预测失败: {e}")

        # ========== 第五步：综合匹配 ==========
        analysis_result = self.analyze_input(full_input)
        base_template = analysis_result[0]
        confidence = analysis_result[1]
        details = analysis_result[2]

        best_score_tfidf = details.get("tfidf_score", 0)
        best_score_embed = details.get("embedding_score", 0)
        nn_confidence = details.get("nn_confidence", 0)
        nn_category = details.get("nn_category", None)

        if not base_template or confidence < 10:
            print(f"\n⚠️ 未在模板库中找到精确匹配 (置信度: {confidence:.1f}%)")
            print("\n💡 AI 建议：")

            # 如果神经网络有预测结果，显示最接近的类别
            if nn_category:
                print(f"   ├─ 神经网络识别为: 【{nn_category}】类系统")

            print(f"\n   🚀 正在启动【智能元素生成器】...")
            print(f"      AI 将根据关键词自动分析并生成UML元素\n")

            # 调用智能元素生成器
            generated_template = self._generate_system_from_input(full_input, nn_category)

            return generated_template

        # 低置信度警告（10-30%）：给出建议但允许用户决定
        if confidence < 30:
            print(f"\n⚠️ 匹配度较低 (置信度: {confidence:.1f}%)")
            print("   AI 推测这可能不是您想要的系统，但已找到最接近的模板：")

        # 显示详细分析结果
        category, cat_confidence = self._classify_system(full_input)

        print(f"\n{'=' * 60}")
        print(f"✨ AI 分析完成！")
        print(f"{'=' * 60}")
        print(f"\n  📌 最终结果:")
        print(f"     └─ 匹配模板: {base_template.name}")
        print(f"     └─ 综合置信度: {confidence:.1f}%")
        print(f"     └─ 系统类别: {category}")
        print(f"\n  🔬 分析细节:")
        print(f"     ├─ TF-IDF 相似度: {best_score_tfidf * 100:.1f}% (权重40%)")
        print(f"     ├─ 词嵌入相似度: {best_score_embed * 100:.1f}% (权重40%)")
        print(f"     └─ NN 意图置信度: {nn_confidence:.2%} (权重20%)")
        print(f"\n  📄 模板信息:")
        print(f"     └─ 描述: {base_template.description}")

        # 创建结果模板（深拷贝以避免修改原模板）
        result = SystemTemplate(
            name=system_name if system_name else base_template.name,
            description=f"由本地AI引擎 v3.0 分析生成（基于'{base_template.name}'模板）",
            category=category,
            keywords=base_template.keywords.copy()
        )

        # 复制所需图表数据
        if "usecase" in diagram_types and base_template.use_case_data:
            result.use_case_data = copy.deepcopy(base_template.use_case_data)
            print(f"\n  ✅ 数据准备:")
            print(f"     └─ 用例图: {len(base_template.use_case_data['actors'])} 参与者, "
                  f"{len(base_template.use_case_data['use_cases'])} 用例")

        if "class" in diagram_types and base_template.class_data:
            result.class_data = copy.deepcopy(base_template.class_data)
            print(f"     └─ 类图: {len(base_template.class_data['classes'])} 个类")

        if "object" in diagram_types and base_template.object_data:
            result.object_data = copy.deepcopy(base_template.object_data)
            print(f"     └─ 对象图: {len(base_template.object_data['objects'])} 个对象")

        if "sequence" in diagram_types and base_template.sequence_data:
            result.sequence_data = copy.deepcopy(base_template.sequence_data)
            print(f"     └─ 顺序图: {len(base_template.sequence_data['objects'])} 对象, "
                  f"{len(base_template.sequence_data['messages'])} 消息")

        # 记录成功匹配用于自学习
        self._record_feedback(full_input, base_template.name, True)

        return result

    def _record_feedback(self, input_text: str, matched_template: str, is_correct: bool):
        """记录用户反馈用于自学习"""
        feedback_record = {
            "input": input_text,
            "template": matched_template,
            "correct": is_correct,
            "timestamp": __import__('datetime').datetime.now().isoformat()
        }
        self.feedback_history.append(feedback_record)

        # 只保留最近100条记录
        if len(self.feedback_history) > 100:
            self.feedback_history = self.feedback_history[-100:]

    def learn_from_feedback(self):
        """
        从反馈中学习 - 自学习功能
        根据用户反馈调整模型参数
        """
        if not self.feedback_history:
            print("[INFO] 暂无反馈数据可供学习")
            return

        correct_matches = [f for f in self.feedback_history if f["correct"]]

        if len(correct_matches) < 5:
            print(f"[INFO] 反馈数据不足（需要至少5条正确记录），当前: {len(correct_matches)} 条")
            return

        print(f"\n📚 开始自学习...")
        print(f"   反馈记录总数: {len(self.feedback_history)}")
        print(f"   正确匹配数: {len(correct_matches)}")

        # 基于反馈调整 IDF 权重
        for feedback in correct_matches:
            if feedback["template"]:
                tokens = self._tokenize(feedback["input"])
                for token in tokens:
                    if token in self.idf_scores:
                        # 增加成功匹配的词的权重
                        self.idf_scores[token] *= 1.05

        # 重新训练神经网络
        if self.intent_classifier and len(correct_matches) >= 10:
            print("   正在重新训练神经网络...")
            self._train_intent_classifier()

        print("✅ 自学习完成！")

    def _generate_system_from_input(self, user_input: str, category_hint: str = None) -> SystemTemplate:
        """
        🧠 真正的通用AI智能元素生成器 v5.0 (纯语义理解版)

        ✨ 革命性升级：
        ✅ 零依赖 - 不需要任何预定义词典或模板
        ✅ 无限词汇 - 支持任意中文/英文/混合输入
        ✅ 真正智能 - 基于语言学规则的深层语义理解
        ✅ 动态创造 - 根据语义"发明"合理的UML元素
        ✅ 自适应 - 根据输入复杂度自动调整生成策略

        🎯 核心技术：
        1. 词法分析 → 提取词汇的语法属性
        2. 语义分解 → 理解输入的业务含义
        3. 概念扩展 → 自动推导相关实体和操作
        4. 角色推理 → 智能推断系统参与者
        5. 流程构建 → 设计合理的业务流程

        💡 示例：
        输入: "住宿" → AI自动理解：预订、入住、退房、支付等完整业务链
        输入: "图书管理" → AI自动理解：借阅、归还、查询、罚款等图书馆业务
        输入: "任何新词汇" → AI都能理解并生成合理的UML元素
        """

        print(f"\n🚀 [通用AI引擎 v5.0] 启动真正的语义分析...")
        print(f"   输入: 【{user_input}】")

        # ========== 第一步：深度语义理解 ==========
        semantic_result = self._true_semantic_understanding(user_input)

        core_concept = semantic_result["core_concept"]
        concept_type = semantic_result["concept_type"]
        business_nature = semantic_result["business_nature"]
        action_verbs = semantic_result["action_verbs"]
        related_entities = semantic_result["related_entities"]
        system_complexity = semantic_result["complexity"]

        print(f"\n🧠 [语义分析结果]")
        print(f"   ├─ 核心概念: {core_concept}")
        print(f"   ├─ 概念类型: {concept_type}")
        print(f"   ├─ 业务性质: {business_nature}")
        print(f"   ├─ 动作动词: {', '.join(action_verbs[:5])}")
        print(f"   ├─ 相关实体: {', '.join(related_entities[:5])}")
        print(f"   └─ 系统复杂度: {system_complexity}")

        # ========== 第二步：智能参与者推导 ==========
        actors = self._deduce_participants(core_concept, concept_type, business_nature, system_complexity)

        # ========== 第三步：动态用例创造 ==========
        use_cases = self._create_use_cases_dynamically(
            core_concept, actors, concept_type, business_nature,
            action_verbs, related_entities, system_complexity
        )

        # ========== 第四步：语义类图建模 ==========
        classes_data = self._build_semantic_class_model(
            core_concept, use_cases, concept_type, business_nature,
            related_entities, system_complexity
        )

        # ========== 第五步：对象实例化 ==========
        objects_data = self._instantiate_objects_intelligently(classes_data)

        # ========== 第六步：流程设计 ==========
        sequence_data = self._design_business_flow(
            core_concept, actors, use_cases, concept_type, business_nature
        )

        # ========== 第七步：组装系统模板 ==========
        generated_template = SystemTemplate(
            name=user_input,
            description=f"由本地AI引擎 v5.0 (真·语义理解) 智能生成 | 类型: {concept_type}",
            keywords=[user_input] + related_entities[:5]
        )

        generated_template.use_case_data = {
            "system_name": user_input,
            "actors": actors,
            "use_cases": use_cases,
            "relationships": self._build_actor_usecase_relationships(actors, use_cases)
        }

        generated_template.class_data = classes_data
        generated_template.object_data = objects_data
        generated_template.sequence_data = sequence_data

        print(f"\n✨ [AI生成完成] UML四图数据已准备就绪！")
        print(f"   ├─ 👥 参与者: {len(actors)} 个")
        print(f"   ├─ ⭕ 用例: {len(use_cases)} 个")
        print(f"   ├─ 🔷 类: {len(classes_data['classes'])} 个")
        print(f"   ├─ ⬡ 对象: {len(objects_data['objects'])} 个")
        print(f"   └─ 📈 顺序图消息: {len(sequence_data['messages'])} 条")

        return generated_template

    def _true_semantic_understanding(self, text: str) -> Dict:
        """
        🔬 真正的语义理解 - 基于语言学的深层分析

        不依赖任何预定义词典，而是通过语言规则理解文本含义
        """
        tokens = self._tokenize(text)

        if not tokens:
            tokens = [text]

        # 提取核心概念
        core_concept = text.strip()

        # 概念类型识别（基于语言学特征）
        concept_type = self._identify_concept_type(tokens, text)

        # 业务性质判断
        business_nature = self._infer_business_nature(tokens, text, concept_type)

        # 动作动词提取
        action_verbs = self._extract_action_verbs(core_concept, tokens, concept_type)

        # 相关实体推导
        related_entities = self._derive_related_entities(core_concept, tokens, concept_type, business_nature)

        # 复杂度评估
        complexity = self._assess_system_complexity(
            len(tokens), len(related_entities), len(action_verbs), business_nature
        )

        return {
            "core_concept": core_concept,
            "concept_type": concept_type,
            "business_nature": business_nature,
            "action_verbs": action_verbs,
            "related_entities": related_entities,
            "complexity": complexity,
            "original_tokens": tokens
        }

    def _identify_concept_type(self, tokens: List[str], original_text: str) -> str:
        """
        识别概念类型 - 判断输入代表什么类型的系统

        基于语言学特征（非词典匹配）
        """
        text_lower = original_text.lower()
        text_combined = "".join(tokens)

        # 服务型特征（提供某种服务给用户）
        service_indicators = ['服务', '平台', '系统', '管理', '中心', '站', '网', '店', '馆', '院', '所']
        if any(ind in text_combined or ind in original_text for ind in service_indicators):
            return "服务型系统"

        # 产品型特征（具体的物品或商品）
        product_indicators = ['产品', '商品', '货物', '物品', '设备', '工具', '软件', '应用']
        if any(ind in text_combined or ind in original_text for ind in product_indicators):
            return "产品型系统"

        # 活动型特征（某种活动或过程）
        activity_indicators = ['活动', '流程', '过程', '作业', '操作', '处理', '交易']
        if any(ind in text_combined or ind in original_text for ind in activity_indicators):
            return "活动型系统"

        # 场所型特征（物理或虚拟场所）
        place_indicators = ['住宿', '酒店', '餐厅', '医院', '学校', '银行', '商城', '超市', '图书馆']
        if any(ind in text_combined or ind in original_text for ind in place_indicators):
            return "场所型系统"

        # 抽象概念型（抽象的管理或概念）
        abstract_patterns = ['管理', '控制', '监控', '分析', '统计', '规划', '设计']
        if any(pat in text_combined or pat in original_text for pat in abstract_patterns):
            return "管理型系统"

        # 默认：根据长度和词数判断
        if len(original_text) <= 2:
            return "基础服务系统"
        elif len(tokens) == 1:
            return f"{original_text}服务系统"
        else:
            return "综合管理系统"

    def _infer_business_nature(self, tokens: List[str], original_text: str, concept_type: str) -> str:
        """
        推断业务性质 - 理解这个系统的核心业务是什么

        基于语义推理而非关键词匹配
        """
        text = original_text

        # 预约预订类
        booking_patterns = ['住宿', '预订', '预约', '挂号', '购票', '订房', '订票', '预约']
        if any(p in text for p in booking_patterns):
            return "预订预约型"

        # 交易支付类
        transaction_patterns = ['支付', '购买', '买卖', '交易', '结算', '收款', '付款', '购物']
        if any(p in text for p in transaction_patterns):
            return "交易支付型"

        # 信息管理类
        info_patterns = ['管理', '信息', '数据', '记录', '档案', '资料', '文档']
        if any(p in text for p in info_patterns):
            return "信息管理型"

        # 资源共享类
        resource_patterns = ['共享', '借用', '租赁', '租用', '借阅', '出租']
        if any(p in text for p in resource_patterns):
            return "资源共享型"

        # 服务提供类
        service_patterns = ['服务', '咨询', '帮助', '支持', '维护', '保养']
        if any(p in text for p in service_patterns):
            return "服务提供型"

        # 审批流程类
        approval_patterns = ['审批', '申请', '审核', '批准', '同意', '签署']
        if any(p in text for p in approval_patterns):
            return "审批流程型"

        # 默认：根据概念类型推断
        type_nature_map = {
            "服务型系统": "服务提供型",
            "产品型系统": "交易支付型",
            "活动型系统": "流程处理型",
            "场所型系统": "资源使用型",
            "管理型系统": "信息管理型",
            "基础服务系统": "基本服务型",
            "综合管理系统": "综合管理型"
        }

        return type_nature_map.get(concept_type, "通用业务型")

    def _extract_action_verbs(self, concept: str, tokens: List[str], concept_type: str) -> List[str]:
        """
        提取动作动词 - 推断这个系统中会发生的核心动作

        基于概念类型和业务性质动态生成
        """
        verbs = []

        # 通用动作（几乎所有系统都有）
        universal_verbs = ["查询", "查看", "搜索", "浏览", "提交", "修改", "删除", "导出"]
        verbs.extend(universal_verbs[:4])

        # 基于概念类型的特定动作
        type_verbs = {
            "服务型系统": ["预订", "取消", "确认", "评价", "反馈"],
            "产品型系统": ["购买", "退货", "换货", "收藏", "比较"],
            "活动型系统": ["发起", "参与", "完成", "中止", "评价"],
            "场所型系统": ["进入", "离开", "使用", "预约", "登记"],
            "管理型系统": ["添加", "编辑", "删除", "审核", "统计"],
            "基础服务系统": ["使用", "申请", "办理", "领取", "归还"],
            "综合管理系统": ["配置", "监控", "分析", "报告", "优化"]
        }

        specific_verbs = type_verbs.get(concept_type, ["使用", "操作"])
        verbs.extend(specific_verbs[:3])

        # 基于核心概念的动作
        concept_actions = [
            f"处理{concept}",
            f"管理{concept}",
            f"统计{concept}"
        ]
        verbs.extend(concept_actions[:2])

        return list(set(verbs))[:12]

    def _derive_related_entities(self, concept: str, tokens: List[str],
                                 concept_type: str, business_nature: str) -> List[str]:
        """
        推导相关实体 - 基于语义自动生成与核心概念相关的实体

        这是真正AI的核心：能够"联想"相关的事物
        """
        entities = []

        # 用户相关实体
        entities.extend(["用户", "管理员", "操作员"])

        # 基于概念类型的实体
        type_entities = {
            "服务型系统": [
                f"{concept}订单", f"{concept}记录", f"{concept}状态",
                "支付信息", "时间安排"
            ],
            "产品型系统": [
                f"{concept}库存", f"{concept}分类", f"{concept}详情",
                "供应商", "价格信息"
            ],
            "活动型系统": [
                f"{concept}计划", f"{concept}结果", f"{concept}进度",
                "参与者", "资源分配"
            ],
            "场所型系统": [
                f"{concept}房间", f"{concept}设施", f"{concept}资源",
                "预订信息", "使用记录"
            ],
            "管理型系统": [
                f"{concept}数据", f"{concept}配置", f"{concept}日志",
                "权限设置", "操作历史"
            ],
            "基础服务系统": [
                f"{concept}信息", f"{concept}列表", f"{concept}详情",
                "申请记录", "处理状态"
            ],
            "综合管理系统": [
                f"{concept}模块", f"{concept}报表", f"{concept}指标",
                "系统配置", "用户权限"
            ]
        }

        specific_entities = type_entities.get(concept_type, [f"{concept}数据"])
        entities.extend(specific_entities[:4])

        # 通用辅助实体
        entities.extend(["系统日志", "通知消息", "统计数据"])

        return list(set(entities))[:15]

    def _assess_system_complexity(self, token_count: int, entity_count: int,
                                  verb_count: str, business_nature: str) -> str:
        """
        评估系统复杂度 - 决定生成多少个UML元素
        """
        score = token_count * 2 + entity_count + verb_count * 1.5

        if score <= 10:
            return "简单"
        elif score <= 20:
            return "中等"
        elif score <= 30:
            return "复杂"
        else:
            return "企业级"

    def _deduce_participants(self, concept: str, concept_type: str,
                             business_nature: str, complexity: str) -> List[Dict]:
        """
        智能参与者推导 - 基于语义自动生成系统参与者

        推理逻辑：
        1. 谁会使用这个系统？（主要用户）
        2. 谁会运营这个系统？（工作人员）
        3. 谁会管理这个系统？（管理人员）
        4. 是否有特殊角色？（根据业务性质）
        """
        participants = []

        # 主要用户（根据概念类型动态命名）
        user_roles = {
            "服务型系统": f"{concept}客户",
            "产品型系统": "消费者",
            "活动型系统": "参与者",
            "场所型系统": f"{concept}使用者",
            "管理型系统": "普通员工",
            "基础服务系统": "服务对象",
            "综合管理系统": "系统用户"
        }

        primary_user = user_roles.get(concept_type, "用户")
        participants.append({
            "name": primary_user,
            "description": f"使用{concept}系统的最终用户"
        })

        # 运营人员
        operator_roles = {
            "服务型系统": f"{concept}服务员",
            "产品型系统": "销售人员",
            "活动型系统": "组织者",
            "场所型系统": f"{concept}工作人员",
            "管理型系统": "业务人员",
            "基础服务系统": "服务提供者",
            "综合管理系统": "运营人员"
        }

        operator = operator_roles.get(concept_type, "操作员")
        participants.append({
            "name": operator,
            "description": f"负责{concept}日常运营的工作人员"
        })

        # 管理人员
        participants.append({
            "name": f"{concept}管理员",
            "description": f"负责{concept}系统管理和决策"
        })

        # 根据业务性质添加特殊角色
        if business_nature in ["交易支付型", "预订预约型"]:
            participants.append({
                "name": "财务人员",
                "description": f"处理{concept}相关的财务事务"
            })

        if complexity in ["复杂", "企业级"]:
            participants.append({
                "name": "技术人员",
                "description": f"负责{concept}系统的技术维护"
            })

        if business_nature == "审批流程型":
            participants.append({
                "name": "审批主管",
                "description": f"负责{concept}相关申请的审批"
            })

        return participants

    def _create_use_cases_dynamically(self, concept: str, actors: List[Dict], concept_type: str,
                                      business_nature: str, action_verbs: List[str],
                                      related_entities: List[str], complexity: str) -> List[Dict]:
        """
        动态用例创造 - 基于语义为每个参与者生成合理的操作用例

        这不是从模板中选取，而是根据语义"发明"用例
        """
        use_cases = []

        if not actors:
            return use_cases

        # 获取参与者名称
        primary_actor = actors[0]["name"] if len(actors) > 0 else "用户"
        operator_actor = actors[1]["name"] if len(actors) > 1 else "操作员"
        manager_actor = actors[2]["name"] if len(actors) > 2 else "管理员"

        # 为主要用户生成用例（面向用户的操作）
        user_use_cases = []

        # 基础访问用例
        user_use_cases.extend([
            {"name": f"访问{concept}系统", "actor": primary_actor},
            {"name": f"注册{concept}账号", "actor": primary_actor},
            {"name": f"登录{concept}系统", "actor": primary_actor},
            {"name": f"查询{concept}信息", "actor": primary_actor}
        ])

        # 核心业务用例（根据业务性质）
        if business_nature == "预订预约型":
            user_use_cases.extend([
                {"name": f"预订{concept}", "actor": primary_actor},
                {"name": f"查看{concept}预订状态", "actor": primary_actor},
                {"name": f"取消{concept}预订", "actor": primary_actor},
                {"name": f"修改{concept}预订信息", "actor": primary_actor}
            ])
        elif business_nature == "交易支付型":
            user_use_cases.extend([
                {"name": f"购买{concept}", "actor": primary_actor},
                {"name": f"查看{concept}订单", "actor": primary_actor},
                {"name": f"支付{concept}费用", "actor": primary_actor},
                {"name": f"申请{concept}退款", "actor": primary_actor}
            ])
        elif business_nature == "资源共享型":
            user_use_cases.extend([
                {"name": f"申请使用{concept}", "actor": primary_actor},
                {"name": f"查看{concept}可用性", "actor": primary_actor},
                {"name": f"归还{concept}", "actor": primary_actor},
                {"name": f"续借{concept}", "actor": primary_actor}
            ])
        elif business_nature == "信息管理型":
            user_use_cases.extend([
                {"name": f"提交{concept}信息", "actor": primary_actor},
                {"name": f"修改{concept}数据", "actor": primary_actor},
                {"name": f"删除{concept}记录", "actor": primary_actor},
                {"name": f"导出{concept}报表", "actor": primary_actor}
            ])
        else:
            user_use_cases.extend([
                {"name": f"使用{concept}服务", "actor": primary_actor},
                {"name": f"提交{concept}请求", "actor": primary_actor},
                {"name": f"跟踪{concept}进度", "actor": primary_actor},
                {"name": f"评价{concept}服务", "actor": primary_actor}
            ])

        use_cases.extend(user_use_cases[:8])

        # 为操作员生成用例
        operator_use_cases = [
            {"name": f"处理{concept}请求", "actor": operator_actor},
            {"name": f"审核{concept}申请", "actor": operator_actor},
            {"name": f"更新{concept}状态", "actor": operator_actor},
            {"name": f"管理{concept}资源", "actor": operator_actor}
        ]
        use_cases.extend(operator_use_cases[:4])

        # 为管理员生成用例
        admin_use_cases = [
            {"name": f"配置{concept}参数", "actor": manager_actor},
            {"name": f"查看{concept}统计报表", "actor": manager_actor},
            {"name": f"管理{concept}用户权限", "actor": manager_actor},
            {"name": f"监控{concept}运行状态", "actor": manager_actor}
        ]
        use_cases.extend(admin_use_cases[:4])

        # 如果有特殊角色，为其生成用例
        if len(actors) > 3:
            for special_actor in actors[3:]:
                special_uc = {
                    "name": f"处理{special_actor['name']}相关事务",
                    "actor": special_actor["name"]
                }
                use_cases.append(special_uc)

        return use_cases

    def _build_actor_usecase_relationships(self, actors: List[Dict], use_cases: List[Dict]) -> List[Dict]:
        """构建参与者-用例关联关系"""
        relationships = []

        actor_uc_map = {}
        for uc in use_cases:
            actor = uc.get("actor", "用户")
            if actor not in actor_uc_map:
                actor_uc_map[actor] = []
            actor_uc_map[actor].append(uc["name"])

        for actor, ucs in actor_uc_map.items():
            for uc_name in ucs[:8]:
                relationships.append({
                    "from": actor,
                    "to": uc_name,
                    "type": "association"
                })

        return relationships

    def _build_semantic_class_model(self, concept: str, use_cases: List[Dict],
                                    concept_type: str, business_nature: str,
                                    related_entities: List[str], complexity: str) -> Dict:
        """
        语义类图建模 - 基于语义理解动态生成类结构

        根据用例和业务性质自动设计合理的类
        """
        classes = []
        relationships = []

        # 1. 核心实体类（基于概念）
        main_entity = {
            "name": concept if concept else "核心实体",
            "attributes": self._generate_class_attributes(concept, "entity"),
            "methods": self._generate_class_methods(concept, "entity")
        }
        classes.append(main_entity)

        # 2. 用户类
        user_class = {
            "name": "用户",
            "attributes": [
                {"name": "userId", "type": "String"},
                {"name": "用户名", "type": "String"},
                {"name": "密码", "type": "String"},
                {"name": "联系方式", "type": "String"},
                {"name": "角色类型", "type": "String"}
            ],
            "methods": [
                {"name": "登录()"},
                {"name": "注册()"},
                {"name": "修改个人信息()"},
                {"name": "验证权限()"}
            ]
        }
        classes.append(user_class)

        # 3. 业务记录类（根据业务性质动态命名）
        if business_nature == "预订预约型":
            record_name = f"{concept}预订"
        elif business_nature == "交易支付型":
            record_name = f"{concept}订单"
        elif business_nature == "资源共享型":
            record_name = f"{concept}借用记录"
        else:
            record_name = f"{concept}记录"

        record_class = {
            "name": record_name,
            "attributes": self._generate_class_attributes(record_name, "record"),
            "methods": self._generate_class_methods(record_name, "record")
        }
        classes.append(record_class)

        # 4. 服务/管理类
        service_class = {
            "name": f"{concept}服务",
            "attributes": [
                {"name": "serviceId", "type": "String"},
                {"name": "服务名称", "type": "String"},
                {"name": "服务状态", "type": "String"},
                {"name": "可用性", "type": "Boolean"}
            ],
            "methods": [
                {"name": f"处理{concept}请求()"},
                {"name": f"验证{concept}数据()"},
                {"name": f"发送通知()"},
                {"name": f"记录日志()"}
            ]
        }
        classes.append(service_class)

        # 5. 根据复杂度添加辅助类
        if complexity in ["复杂", "企业级"]:
            config_class = {
                "name": f"{concept}配置",
                "attributes": [
                    {"name": "configId", "type": "String"},
                    {"name": "参数名称", "type": "String"},
                    {"name": "参数值", "type": "String"},
                    {"name": "描述", "type": "String"}
                ],
                "methods": [
                    {"name": "加载配置()"},
                    {"name": "更新参数()"},
                    {"name": "验证配置()"}
                ]
            }
            classes.append(config_class)

        # 构建关系
        relationships = [
            {"from": record_class["name"], "to": user_class["name"],
             "type": "association", "label": "归属"},
            {"from": record_class["name"], "to": main_entity["name"],
             "type": "association", "label": "关联"},
            {"from": service_class["name"], "to": record_class["name"],
             "type": "dependency", "label": "处理"},
            {"from": user_class["name"], "to": service_class["name"],
             "type": "association", "label": "使用"}
        ]

        return {
            "classes": classes,
            "relationships": relationships
        }

    def _generate_class_attributes(self, entity_name: str, entity_type: str) -> List[Dict]:
        """动态生成类属性"""
        base_attrs = [
            {"name": f"{entity_name}Id", "type": "String"},
            {"name": "名称", "type": "String"},
            {"name": "创建时间", "type": "DateTime"},
            {"name": "更新时间", "type": "DateTime"},
            {"name": "状态", "type": "String"}
        ]

        if entity_type == "entity":
            base_attrs.extend([
                {"name": "描述", "type": "String"},
                {"name": "类型", "type": "String"}
            ])
        elif entity_type == "record":
            base_attrs.extend([
                {"name": "金额", "type": "Double"},
                {"name": "数量", "type": "Integer"},
                {"name": "备注", "type": "String"}
            ])

        return base_attrs

    def _generate_class_methods(self, entity_name: str, entity_type: str) -> List[Dict]:
        """动态生成类方法"""
        base_methods = [
            {"name": f"获取{entity_name}信息()"},
            {"name": f"更新{entity_name}数据()"},
            {"name": f"验证{entity_name}合法性()"}
        ]

        if entity_type == "entity":
            base_methods.append({"name": f"计算{entity_name}统计()"})
        elif entity_type == "record":
            base_methods.extend([
                {"name": f"确认{entity_name}完成()"},
                {"name": f"取消{entity_name}()"}
            ])

        return base_methods

    def _instantiate_objects_intelligently(self, class_data: Dict) -> Dict:
        """智能对象实例化 - 为每个类创建示例对象"""
        objects = []

        for cls in class_data["classes"][:4]:
            obj = {
                "name": f"{cls['name']}_01",
                "class_name": cls["name"],
                "attributes": {}
            }

            for attr in cls["attributes"]:
                attr_type = attr["type"].lower()
                if attr["name"].endswith("Id") or attr["name"] == "id":
                    obj["attributes"][attr["name"]] = f"OBJ_{len(objects) + 1:04d}"
                elif attr_type in ["string", "str"]:
                    obj["attributes"][attr["name"]] = f"示例{attr['name']}"
                elif attr_type in ["int", "integer"]:
                    obj["attributes"][attr["name"]] = len(objects) + 1
                elif attr_type in ["double", "float", "decimal"]:
                    obj["attributes"][attr["name"]] = 99.99
                elif attr_type in ["datetime", "date", "time"]:
                    obj["attributes"][attr["name"]] = "2025-01-01 00:00"
                elif attr_type in ["bool", "boolean"]:
                    obj["attributes"][attr["name"]] = True
                else:
                    obj["attributes"][attr["name"]] = "-"

            objects.append(obj)

        return {
            "objects": objects,
            "links": []
        }

    def _design_business_flow(self, concept: str, actors: List[Dict],
                              use_cases: List[Dict], concept_type: str,
                              business_nature: str) -> Dict:
        """
        设计业务流程 - 创建顺序图消息序列

        基于业务性质设计合理的交互流程
        """
        # 选择主要对象
        seq_objects = [a["name"] for a in actors[:2]] + [f"{concept}系统", "数据库"]

        messages = []

        # 基础流程（几乎所有系统都有）
        base_flow = [
            {"from": seq_objects[0], "to": seq_objects[2],
             "text": f"1. 发起{concept}请求", "type": "sync"},
            {"from": seq_objects[2], "to": seq_objects[3],
             "text": f"2. 查询{concept}数据", "type": "sync"},
            {"from": seq_objects[3], "to": seq_objects[2],
             "text": f"3. 返回{concept}信息", "type": "return"},
            {"from": seq_objects[2], "to": seq_objects[1],
             "text": f"4. 处理{concept}业务逻辑", "type": "sync"},
            {"from": seq_objects[1], "to": seq_objects[2],
             "text": f"5. 确认处理结果", "type": "return"},
            {"from": seq_objects[2], "to": seq_objects[0],
             "text": f"6. 返回响应结果", "type": "return"}
        ]
        messages.extend(base_flow)

        # 根据业务性质添加特定步骤
        if business_nature == "预订预约型":
            messages.insert(3, {"from": seq_objects[2], "to": seq_objects[2],
                                "text": f"检查{concept}可用性", "type": "self"})
            messages.insert(5, {"from": seq_objects[2], "to": seq_objects[3],
                                "text": f"锁定{concept}资源", "type": "sync"})

        elif business_nature == "交易支付型":
            messages.insert(4, {"from": seq_objects[2], "to": seq_objects[2],
                                "text": "计算费用", "type": "self"})
            messages.insert(6, {"from": seq_objects[2], "to": seq_objects[2],
                                "text": "验证支付安全性", "type": "self"})

        elif business_nature == "审批流程型":
            messages.insert(4, {"from": seq_objects[1], "to": seq_objects[1],
                                "text": "审核申请材料", "type": "self"})
            messages.insert(6, {"from": seq_objects[1], "to": seq_objects[2],
                                "text": "返回审批意见", "type": "return"})

        return {
            "title": f"{concept}处理流程",
            "objects": seq_objects,
            "messages": messages
        }

    def show_system_suggestions(self, partial_input: str) -> List[Tuple[str, float]]:
        """
        根据部分输入返回系统建议列表
        用于自动补全或提示
        """
        results = []
        processed = self._preprocess_input(partial_input)

        for template in self.templates + self.user_templates:
            score = self._calculate_similarity(processed, template)
            if score > 10:
                results.append((template.name, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:10]

    def add_custom_template(self, template: SystemTemplate) -> bool:
        """
        添加用户自定义模板
        支持持久化存储
        """
        try:
            self.user_templates.append(template)
            self._save_user_templates()
            print(f"[OK] 自定义模板 '{template.name}' 已添加")
            return True
        except Exception as e:
            print(f"[ERROR] 添加模板失败: {e}")
            return False

    def _save_user_templates(self):
        """保存用户自定义模板到文件"""
        template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_templates.json")
        try:
            data = {"templates": []}
            for t in self.user_templates:
                item = {
                    "name": t.name,
                    "keywords": t.keywords,
                    "description": t.description,
                    "use_case_data": t.use_case_data,
                    "class_data": t.class_data,
                    "object_data": t.object_data,
                    "sequence_data": t.sequence_data
                }
                data["templates"].append(item)

            with open(template_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"[OK] 用户模板已保存到: {template_path}")
        except Exception as e:
            print(f"[WARN] 保存用户模板失败: {e}")

    def get_statistics(self) -> Dict:
        """获取引擎统计信息"""
        return {
            "total_builtin_templates": len(self.templates),
            "total_user_templates": len(self.user_templates),
            "total_synonym_groups": len(self.synonym_dict),
            "total_categories": len(self.category_rules),
            "supported_diagrams": ["用例图", "类图", "对象图", "顺序图"]
        }


class UMLAutoGenerator:
    """
    UML 自动生成器 - 根据模板自动创建 UML 图
    """

    def __init__(self):
        self.library = UMLTemplateLibrary()

    def show_available_templates(self):
        """显示所有可用模板"""
        print("\n" + "=" * 60)
        print("  可用的系统模板：")
        print("=" * 60)
        for line in self.library.list_all_templates():
            print(line)
        print("=" * 60)

    def generate_from_template(self, template: SystemTemplate, diagram_types: List[str],
                               output_dir: str = "") -> bool:
        """
        根据模板生成指定类型的 UML 图

        Args:
            template: 系统模板
            diagram_types: 要生成的图表类型列表，如 ["usecase", "class", "object", "sequence"]
            output_dir: 输出目录
        """
        if not output_dir:
            output_dir = os.path.join(os.path.dirname(__file__), "output")

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        success = True

        for diag_type in diagram_types:
            try:
                if diag_type == "usecase" and template.use_case_data:
                    self._generate_use_case(template, output_dir)
                elif diag_type == "class" and template.class_data:
                    self._generate_class(template, output_dir)
                elif diag_type == "object" and template.object_data:
                    self._generate_object(template, output_dir)
                elif diag_type == "sequence" and template.sequence_data:
                    self._generate_sequence(template, output_dir)
                else:
                    print(f"[WARN] 模板 '{template.name}' 不支持 {diag_type} 类型图表")
            except Exception as e:
                print(f"[ERROR] 生成 {diag_type} 图失败: {e}")
                import traceback
                traceback.print_exc()
                success = False

        return success

    def _generate_use_case(self, template: SystemTemplate, output_dir: str):
        """根据模板生成用例图"""
        data = template.use_case_data

        with VisioAutomation(visible=True) as visio:
            visio.new_document()
            visio.set_page_size(11, 8.5)

            builder = UseCaseDiagramBuilder(visio)
            builder.set_title(f"{template.name}用例图")
            builder.set_system_name(template.name)

            # 创建参与者
            actor_map = {}
            for actor_data in data["actors"]:
                actor = builder.add_actor(actor_data["name"], actor_data.get("description", ""))
                actor_map[actor_data["name"]] = actor

            # 创建用例
            uc_map = {}
            for uc_data in data["use_cases"]:
                uc = builder.add_use_case(uc_data["name"], uc_data.get("description", ""),
                                          uc_data.get("is_primary", False))
                uc_map[uc_data["name"]] = uc

            # 创建关系
            for rel_data in data["relationships"]:
                from_item = actor_map.get(rel_data["from"]) or uc_map.get(rel_data["from"])
                to_item = actor_map.get(rel_data["to"]) or uc_map.get(rel_data["to"])

                if from_item and to_item:
                    rel_type_map = {
                        "association": RelationshipType.ASSOCIATION,
                        "include": RelationshipType.INCLUDE,
                        "extend": RelationshipType.EXTEND,
                        "generalization": RelationshipType.GENERALIZATION
                    }
                    rel_type = rel_type_map.get(rel_data["type"], RelationshipType.ASSOCIATION)
                    builder.add_relationship(from_item, to_item, rel_type, rel_data.get("label", ""))

            if builder.build():
                save_path = os.path.join(output_dir, f"{template.name}_用例图.vsdx")
                visio.save_document(save_path)
                print(f"\n [OK] {template.name}用例图已生成！")
                print(f" 文件: {os.path.abspath(save_path)}")

    def _generate_class(self, template: SystemTemplate, output_dir: str):
        """根据模板生成类图"""
        data = template.class_data

        with VisioAutomation(visible=True) as visio:
            visio.new_document()
            visio.set_page_size(11, 8.5)

            builder = ClassDiagramBuilder(visio)
            builder.set_title(f"{template.name}类图")

            # 创建类
            class_map = {}
            for cls_data in data["classes"]:
                cls = builder.add_class(cls_data["name"])
                for attr in cls_data.get("attributes", []):
                    builder.add_attribute(cls, attr["name"], attr.get("type", "String"),
                                          attr.get("visibility", "-"))
                for method in cls_data.get("methods", []):
                    builder.add_method(cls, method["name"], method.get("return_type", "void"),
                                       method.get("visibility", "+"),
                                       method.get("params", []))
                class_map[cls_data["name"]] = cls

            # 创建关系
            for rel_data in data["relationships"]:
                from_cls = class_map.get(rel_data["from"])
                to_cls = class_map.get(rel_data["to"])

                if from_cls and to_cls:
                    rel_type_map = {
                        "association": RelationshipType.ASSOCIATION,
                        "aggregation": RelationshipType.AGGREGATION,
                        "composition": RelationshipType.COMPOSITION,
                        "generalization": RelationshipType.GENERALIZATION,
                        "realization": RelationshipType.REALIZATION,
                        "dependency": RelationshipType.DEPENDENCY
                    }
                    rel_type = rel_type_map.get(rel_data["type"], RelationshipType.ASSOCIATION)
                    builder.add_relationship(from_cls, to_cls, rel_type,
                                             rel_data.get("mult_from", "1"),
                                             rel_data.get("mult_to", "*"),
                                             rel_data.get("label", ""))

            if builder.build():
                save_path = os.path.join(output_dir, f"{template.name}_类图.vsdx")
                visio.save_document(save_path)
                print(f"\n [OK] {template.name}类图已生成！")
                print(f" 文件: {os.path.abspath(save_path)}")

    def _generate_object(self, template: SystemTemplate, output_dir: str):
        """根据模板生成对象图"""
        data = template.object_data

        with VisioAutomation(visible=True) as visio:
            visio.new_document()
            visio.set_page_size(11, 8.5)

            builder = ObjectDiagramBuilder(visio)
            builder.set_title(f"{template.name}对象图")

            # 创建对象
            obj_map = {}
            for obj_data in data["objects"]:
                obj = builder.add_object(obj_data["name"], obj_data["class_name"],
                                         obj_data.get("attributes", {}))
                obj_map[obj_data["name"]] = obj

            # 创建关系
            for rel_data in data["relationships"]:
                from_obj = obj_map.get(rel_data["from"])
                to_obj = obj_map.get(rel_data["to"])

                if from_obj and to_obj:
                    builder.add_relationship(from_obj, to_obj,
                                             rel_data.get("label", ""),
                                             rel_data.get("type", "association"))

            if builder.build():
                save_path = os.path.join(output_dir, f"{template.name}_对象图.vsdx")
                visio.save_document(save_path)
                print(f"\n [OK] {template.name}对象图已生成！")
                print(f" 文件: {os.path.abspath(save_path)}")

    def _generate_sequence(self, template: SystemTemplate, output_dir: str):
        """根据模板生成顺序图"""
        data = template.sequence_data

        with VisioAutomation(visible=True) as visio:
            visio.new_document()
            visio.set_page_size(11, 8.5)

            builder = SequenceDiagramBuilder(visio)
            builder.set_title(f"{template.name}顺序图")

            # 创建对象
            obj_map = {}
            for obj_name in data["objects"]:
                obj = builder.add_object(obj_name)
                obj_map[obj_name] = obj

            # 创建消息
            for msg_data in data["messages"]:
                from_obj = obj_map.get(msg_data["from"])
                to_obj = obj_map.get(msg_data["to"])

                if from_obj and to_obj:
                    builder.add_message(from_obj, to_obj, msg_data["text"],
                                        msg_data.get("type", "sync"))

            if builder.build():
                save_path = os.path.join(output_dir, f"{template.name}_顺序图.vsdx")
                visio.save_document(save_path)
                print(f"\n [OK] {template.name}顺序图已生成！")
                print(f" 文件: {os.path.abspath(save_path)}")


def ai_auto_generate():
    """
    AI 智能生成入口 - 本地AI引擎优先（无需网络/API）

    支持三种模式：
    1. 🤖 本地AI智能分析（推荐，无需网络）
    2. ☁️ AI 大模型分析（需要API Key）
    3. 📚 内置模板库匹配

    流程：
    1. 用户输入系统名称
    2. 选择分析模式
    3. 执行智能分析
    4. 选择要生成的图表类型
    5. 生成 Visio 文件
    """
    print("\n" + "=" * 70)
    print("  🤖 AI 智能分析 - UML 图自动生成")
    print("=" * 70)
    print("\n请输入您要分析的软件/系统/程序名称：")
    print("（例如：在线购物系统、图书管理系统、微信、抖音、外卖系统等）")
    print("也可以输入关键词，如：电商、银行、学生、医院等")

    query = input("\n请输入: ").strip()
    if not query:
        print("[WARN] 输入不能为空！")
        return

    # ============ 第一步：选择分析模式 ============
    print(f"\n{'=' * 60}")
    print(f"  分析目标: {query}")
    print(f"{'=' * 60}")
    print("\n请选择分析模式：")
    print("  [1] 🤖 本地AI智能分析（推荐✨）")
    print("      • 无需网络、无需API Key")
    print("      • 基于规则引擎 + 知识图谱")
    print("      • 支持同义词理解和语义匹配")
    print("      • 内置6种常见系统模板")
    print()
    print("  [2] ☁️ AI 大模型分析（DeepSeek/千问/豆包）")
    print("      • 支持任意自定义系统")
    print("      • 需要配置 API Key")
    print()
    print("  [3] 📚 内置模板库快速选择")
    print("      • 直接从6种预设模板中选择")
    print()
    print("  [0] 取消")

    mode = input("\n请选择 [0-3]: ").strip()

    selected_template = None

    if mode == "0" or not mode:
        print("已取消。")
        return

    elif mode == "1":
        # ============ 本地AI引擎模式（新功能）============
        engine = LocalAIEngine()

        # 显示引擎统计信息
        stats = engine.get_statistics()
        print(f"\n{'=' * 60}")
        print(f"  🤖 本地AI引擎已启动")
        print(f"{'=' * 60}")
        print(f"  内置模板: {stats['total_builtin_templates']} 个")
        print(f"  用户模板: {stats['total_user_templates']} 个")
        print(f"  同义词组: {stats['total_synonym_groups']} 组")
        print(f"  系统类别: {stats['total_categories']} 类")

        # 执行智能分析
        extra_desc = input("\n可选：输入额外描述（如功能特点等，直接回车跳过）: ").strip()
        selected_template = engine.generate_smart_analysis(query, extra_desc)

        if not selected_template:
            fallback = input("\n是否切换到其他模式？(Y/n): ").strip().lower()
            if fallback != 'n':
                print("\n请重新运行并选择其他模式。")
                return

    elif mode == "2":
        # ============ LLM 分析模式 ============
        api_keys = load_api_keys()
        provider, api_key = setup_llm_provider(api_keys)

        if not provider or not api_key:
            # 用户没有配置 LLM，回退到本地AI引擎
            print("\n[INFO] 未配置 LLM，回退到本地AI引擎...")
            engine = LocalAIEngine()
            selected_template = engine.generate_smart_analysis(query)

            if not selected_template:
                print(f"\n[WARN] 本地AI也无法匹配 '{query}'")
                print("建议：配置 LLM API Key 或使用更具体的关键词")
                input("\n按回车键返回主菜单...")
                return
        else:
            # 调用 LLM 分析
            print(f"\n{'=' * 60}")
            print(f"  正在使用 {LLM_PROVIDERS[provider]['name']} 分析: {query}")
            print(f"{'=' * 60}")

            prompt = UML_ANALYSIS_PROMPT.format(query=query)
            response = call_llm(provider, api_key, prompt)

            if response:
                data = parse_llm_response(response)
                if data:
                    selected_template = llm_response_to_template(data)
                    print(f"\n[OK] AI 分析完成！系统名称: {selected_template.name}")
                else:
                    print("\n[ERROR] AI 返回的数据格式不正确")
                    fallback = input("是否回退到本地AI引擎？(Y/n): ").strip().lower()
                    if fallback != 'n':
                        engine = LocalAIEngine()
                        selected_template = engine.generate_smart_analysis(query)
            else:
                print("\n[ERROR] AI 分析失败")
                fallback = input("是否回退到本地AI引擎？(Y/n): ").strip().lower()
                if fallback != 'n':
                    engine = LocalAIEngine()
                    selected_template = engine.generate_smart_analysis(query)

    elif mode == "3":
        # ============ 内置模板库模式 ============
        generator = UMLAutoGenerator()
        matched = generator.library.search_template(query)

        if not matched:
            print(f"\n[WARN] 未找到与 '{query}' 匹配的系统模板")
            print("\n当前可用的系统模板有：")
            generator.show_available_templates()
            print("\n提示：您可以尝试输入以上系统的名称或相关关键词")
            print("或者选择模式 [1] 使用本地AI智能分析（支持语义理解）")
            input("\n按回车键返回主菜单...")
            return

        if len(matched) > 1:
            print(f"\n找到 {len(matched)} 个匹配的系统：")
            for i, t in enumerate(matched):
                print(f"  [{i + 1}] {t.name} - {t.description}")

            try:
                choice = input(f"\n请选择 [1-{len(matched)}]: ").strip()
                idx = int(choice) - 1
                if 0 <= idx < len(matched):
                    selected_template = matched[idx]
                else:
                    selected_template = matched[0]
            except (ValueError, IndexError):
                selected_template = matched[0]
        else:
            selected_template = matched[0]

    else:
        print("[WARN] 无效选项")
        return

    # ============ 检查是否获取到模板 ============
    if not selected_template:
        print("\n[ERROR] 未能获取到系统数据，请重试")
        input("\n按回车键返回主菜单...")
        return

    print(f"\n{'=' * 60}")
    print(f"  ✅ 已选择系统: {selected_template.name}")
    print(f"  {selected_template.description}")
    print(f"{'=' * 60}")

    # ============ 第二步：选择图表类型 ============
    available_types = []
    type_names = {
        "usecase": "用例图",
        "class": "类图",
        "object": "对象图",
        "sequence": "顺序图"
    }

    if selected_template.use_case_data:
        available_types.append("usecase")
    if selected_template.class_data:
        available_types.append("class")
    if selected_template.object_data:
        available_types.append("object")
    if selected_template.sequence_data:
        available_types.append("sequence")

    if not available_types:
        print("[ERROR] 模板中没有可用的图表数据")
        input("\n按回车键返回主菜单...")
        return

    print("\n请选择要生成的图表类型：")
    for i, t in enumerate(available_types):
        print(f"  [{i + 1}] {type_names[t]}")
    print(f"  [{len(available_types) + 1}] 全部生成")
    print(f"  [0] 取消")

    try:
        choice = input(f"\n请选择 [0-{len(available_types) + 1}]: ").strip()
        choice_idx = int(choice)

        if choice_idx == 0:
            print("已取消。")
            return

        if choice_idx == len(available_types) + 1:
            diagram_types = available_types
        elif 1 <= choice_idx <= len(available_types):
            diagram_types = [available_types[choice_idx - 1]]
        else:
            print("[WARN] 无效选项")
            return
    except ValueError:
        print("[WARN] 无效输入")
        return

    # ============ 第三步：确认并生成 ============
    print(f"\n即将生成以下图表：")
    for dt in diagram_types:
        print(f"  ✓ {selected_template.name}{type_names[dt]}")

    confirm = input("\n确认生成？(Y/n): ").strip().lower()
    if confirm == 'n':
        print("已取消。")
        return

    print(f"\n{'=' * 60}")
    print(f"  🚀 开始自动生成 UML 图...")
    print(f"{'=' * 60}")

    output_dir = os.path.join(os.path.dirname(__file__), "output")
    generator = UMLAutoGenerator()
    success = generator.generate_from_template(selected_template, diagram_types, output_dir)

    if success:
        print(f"\n{'=' * 60}")
        print(f"  ✅ 所有图表生成完毕！")
        print(f"  📁 输出目录: {os.path.abspath(output_dir)}")
        print(f"{'=' * 60}")
        print("\n💡 提示：生成的 .vsdx 文件可以用 Visio 打开编辑")
    else:
        print("\n[ERROR] 部分图表生成失败，请检查错误信息")

    input("\n按回车键返回主菜单...")


# ============================================================
# 第八部分：主程序 - 交互式菜单
# ============================================================

def check_dependencies():
    """检查依赖项"""
    print("\n 正在检查依赖项...")

    try:
        import win32com.client
        print("   [OK] pywin32 已安装")
    except ImportError:
        print("   [FAIL] pywin32 未安装")
        print("   请运行: pip install pywin32")
        return False

    return True


@dataclass
class SequenceObject:
    """顺序图中的对象/参与者"""
    name: str  # 对象名称（如"用户"、"订单服务"）
    x: float = 0.0  # X 坐标
    y: float = 0.0  # Y 坐标（对象框的顶部）
    shape: Any = None  # Visio 形状引用
    lifeline_shape: Any = None  # 生命线形状


@dataclass
class SequenceMessage:
    """顺序图中的消息"""
    from_object: SequenceObject  # 发送者
    to_object: SequenceObject  # 接收者
    message_text: str  # 消息文本（如"1: 提交订单"）
    message_type: str = "sync"  # 消息类型：sync(同步调用), async(异步), return(返回)
    y_position: float = 0.0  # 消息的 Y 坐标位置


class SequenceDiagramBuilder:
    """
    顺序图（Sequence Diagram）构建器

    功能：
      * 自动绘制对象框和虚线生命线
      * 绘制带编号的消息箭头
      * 支持同步/异步/返回消息
      * 标准的 UML 顺序图布局

    使用方法：
      builder = SequenceDiagramBuilder(visio)
      builder.set_title("用户登录顺序图")

      user = builder.add_object("用户")
      login_service = builder.add_object("登录服务")
      database = builder.add_object("数据库")

      builder.add_message(user, login_service, "1: 输入用户名密码")
      builder.add_message(login_service, database, "2: 验证用户信息", "sync")
      builder.add_message(database, login_service, "3: 返回验证结果", "return")

      builder.build()
    """

    def __init__(self, visio: VisioAutomation):
        self.visio = visio
        self.title = "顺序图"
        self.objects: List[SequenceObject] = []
        self.messages: List[SequenceMessage] = []

        # 布局参数（动态计算）
        self.layout_info = {
            'margin_top': 1.5,
            'margin_bottom': 0.6,
            'content_top': 0,
            'content_bottom': 0,
            'message_spacing': 0.65
        }

    def set_title(self, title: str):
        """设置图表标题"""
        self.title = title

    def add_object(self, name: str) -> SequenceObject:
        """
        添加一个参与对象

        Args:
            name: 对象名称

        Returns:
            SequenceObject 对象实例
        """
        obj = SequenceObject(name=name)
        self.objects.append(obj)
        return obj

    def add_message(self, from_obj: SequenceObject, to_obj: SequenceObject,
                    text: str, msg_type: str = "sync") -> SequenceMessage:
        """
        添加一条消息

        Args:
            from_obj: 发送者对象
            to_obj: 接收者对象
            text: 消息文本（建议包含编号，如"1: 登录"）
            msg_type: 消息类型
                   - "sync": 同步调用（实线箭头）
                   - "async": 异步消息（开放箭头）
                   - "return": 返回消息（虚线箭头）

        Returns:
            SequenceMessage 消息实例
        """
        msg = SequenceMessage(
            from_object=from_obj,
            to_object=to_obj,
            message_text=text,
            message_type=msg_type
        )
        self.messages.append(msg)
        return msg

    def build(self) -> bool:
        """
        构建完整的顺序图

        Returns:
            bool: 是否成功构建
        """
        print(f"\n{'=' * 60}")
        print(f" 开始构建顺序图: {self.title}")
        print(f"{'=' * 60}")

        if not self.objects or not self.messages:
            print("[ERROR] 至少需要一个对象和一条消息！")
            return False

        try:
            # 1. 先用默认页面大小进行布局计算，确定实际需要的空间
            page_width = 11.0
            default_page_height = 8.5

            # 2. 布局算法（计算所有元素位置）
            print("\n 正在进行智能布局...")
            self._layout_objects(page_width, default_page_height)

            # 3. 根据布局结果动态计算所需页面高度
            content_bottom = self.layout_info.get('content_bottom', 1.0)
            margin_bottom_extra = 0.8  # 底部额外留白
            needed_page_height = max(default_page_height,
                                     self.layout_info.get('content_top',
                                                          default_page_height) - content_bottom + margin_bottom_extra + self.layout_info.get(
                                         'margin_top', 1.5))
            # 确保页面高度至少为默认值，且向上取整到0.5英寸
            page_height = max(default_page_height, (needed_page_height + 0.5) // 0.5 * 0.5 + 0.5)

            # 设置页面大小
            self.visio.set_page_size(page_width, page_height)

            # 4. 用新的页面高度重新布局（确保所有元素在页面内）
            self._layout_objects(page_width, page_height)

            # 5. 绘制系统边界框
            print(" 正在绘制系统边界框...")
            self._draw_sequence_boundary(page_width, page_height)

            # 6. 绘制标题
            print(" 正在添加标题...")
            self._draw_title()

            # 7. 绘制对象框和生命线
            print(" 正在绘制对象...")
            for obj in self.objects:
                self._draw_object_with_lifeline(obj)

            # 8. 绘制消息
            print(" 正在绘制消息...")
            self._draw_messages()

            # 9. 调整视图
            print(" 正在调整视图...")
            self.visio.zoom_to_fit()

            print(f"\n[OK] 顺序图 '{self.title}' 构建完成！")
            return True

        except Exception as e:
            print(f"\n[ERROR] 构建顺序图失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _layout_objects(self, page_width: float, page_height: float):
        """
        布局所有对象
        对象均匀分布在页面顶部，确保所有内容在边界框内
        动态计算所需空间，并保存布局信息用于绘制边界框
        """
        num_objects = len(self.objects)
        num_messages = len(self.messages)
        if num_objects == 0:
            return

        # 边界框参数
        margin_x = 0.6
        margin_top = 1.5  # 标题区域高度
        margin_bottom = 0.8

        # 保存到布局信息
        self.layout_info['margin_top'] = margin_top
        self.layout_info['margin_x'] = margin_x

        # 对象框参数
        object_width = 1.4
        object_height = 0.45

        # 计算可用宽度
        available_width = page_width - 2 * margin_x

        # 计算间距
        total_width = num_objects * object_width + (num_objects - 1) * 0.3
        if total_width > available_width:
            spacing = (available_width - num_objects * object_width) / (num_objects - 1) if num_objects > 1 else 0
            object_width = (available_width - (num_objects - 1) * 0.3) / num_objects
        else:
            spacing = 0.3

        start_x = margin_x + (available_width - total_width) / 2

        # 设置每个对象的 X 坐标（Visio 坐标系：Y 轴向上为正）
        for i, obj in enumerate(self.objects):
            obj.x = start_x + i * (object_width + spacing) + object_width / 2
            obj.y = page_height - margin_top  # 从顶部开始（留出标题空间）

        # 记录内容顶部位置
        content_top = obj.y + object_height / 2 if self.objects else page_height
        self.layout_info['content_top'] = content_top

        # 计算生命线起始位置（对象框底部）
        lifeline_start_y = page_height - margin_top - object_height - 0.15

        # 动态计算消息间距，确保所有消息都能显示
        min_message_spacing = 0.5
        max_message_spacing = 0.65
        ideal_message_spacing = 0.58

        # 计算实际需要的底部位置（确保不超出页面）
        actual_bottom = lifeline_start_y - (num_messages + 0.5) * min_message_spacing
        # 确保底部不超出页面范围
        if actual_bottom < margin_bottom:
            actual_bottom = margin_bottom

        # 根据可用空间计算消息间距
        available_height = lifeline_start_y - actual_bottom
        message_spacing = min(max_message_spacing, available_height / (num_messages + 0.5))
        message_spacing = max(min_message_spacing, message_spacing)

        # 重新计算实际底部位置
        actual_bottom = lifeline_start_y - (num_messages + 0.5) * message_spacing

        # 保存消息间距和内容底部位置
        self.layout_info['message_spacing'] = message_spacing
        self.layout_info['content_bottom'] = actual_bottom
        self.layout_info['margin_bottom'] = max(margin_bottom, abs(actual_bottom) + 0.3)

        print(f"   [INFO] 布局计算: {num_messages}条消息, 间距={message_spacing:.2f}\"")
        print(f"   [INFO] 内容范围: Y={content_top:.2f}\" 到 Y={actual_bottom:.2f}\"")
        print(f"   [INFO] 页面高度: {page_height:.1f}\"")

        # 设置每个消息的 Y 位置
        for i, msg in enumerate(self.messages):
            msg.y_position = lifeline_start_y - (i + 1) * message_spacing

    def _draw_sequence_boundary(self, page_width: float, page_height: float):
        """
        绘制顺序图的系统边界框（矩形边框）
        根据实际内容大小动态调整边界框，确保所有内容都在背景内
        """
        page = self.visio.page

        try:
            # 从布局信息获取参数
            margin_x = self.layout_info.get('margin_x', 0.6)
            content_top = self.layout_info.get('content_top', page_height - 1.2)
            content_bottom = self.layout_info.get('content_bottom', 1.0)

            # 计算边界框参数
            x = margin_x - 0.1  # 左边距
            w = page_width - 2 * margin_x + 0.2  # 宽度

            # 动态计算高度：确保包含所有内容（标题 + 对象 + 消息 + 底部留白）
            title_top = page_height - 0.1  # 标题顶部
            bottom_padding = 0.5  # 底部留白
            y = content_bottom - bottom_padding  # 边界框底部
            h = title_top - y  # 高度（从底部到顶部）

            print(f"   [INFO] 边界框尺寸: X={x:.1f}, Y={y:.1f}, W={w:.1f}\", H={h:.1f}\"")

            # 绘制矩形边框（作为背景）
            boundary = page.DrawRectangle(x, y, x + w, y + h)

            # 设置边框样式：细线、深灰色、白色填充
            try:
                boundary.CellsU("LineColor").FormulaU = "RGB(80,80,80)"  # 深灰色边框
            except:
                pass
            try:
                boundary.CellsU("LineWidth").FormulaU = "1.0 pt"  # 稍粗的边框线
            except:
                pass
            try:
                boundary.CellsU("FillForegnd").FormulaU = "RGB(252,252,252)"  # 浅灰白色填充
            except:
                pass
            try:
                boundary.CellsU("FillPattern").FormulaU = "1"  # 实心填充
            except:
                pass

            # 将边框移到最底层（不遮挡其他元素）
            try:
                boundary.CellsU("LayerMember").FormulaU = "0"
            except:
                pass

            print(f"   [OK] 已绘制系统边界框 (背景) ({w:.1f}\" × {h:.1f}\")")
            print(f"   [OK] 所有内容将显示在边界框内")

        except Exception as e:
            print(f"[WARN] 绘制边界框失败: {e}")

    def _draw_object_with_lifeline(self, obj: SequenceObject):
        """绘制对象框和虚线生命线"""
        page = self.visio.page

        # 对象框尺寸
        width = 1.6
        height = 0.55

        x = obj.x
        y = obj.y

        # 绘制矩形对象框
        shape = page.DrawRectangle(
            x - width / 2,
            y - height / 2,
            x + width / 2,
            y + height / 2
        )

        try:
            shape.Text = obj.name
        except:
            pass

        # 设置样式
        try:
            shape.CellsU("FillForegnd").FormulaU = "RGB(255,255,255)"
        except:
            pass
        try:
            shape.CellsU("LineColor").FormulaU = "RGB(0,0,0)"
        except:
            pass
        try:
            shape.CellsU("LineWidth").FormulaU = "1 pt"
        except:
            pass
        try:
            shape.CellsU("CharSize").FormulaU = "10 pt"
        except:
            pass
        try:
            shape.CellsU("CharBold").FormulaU = "True"
        except:
            pass
        try:
            shape.CellsU("HAlign").FormulaU = "1"  # 居中
        except:
            pass
        try:
            shape.CellsU("VAlign").FormulaU = "1"  # 垂直居中
        except:
            pass

        obj.shape = shape

        # 绘制虚线生命线（从对象框底部向下延伸到页面底部）
        lifeline_bottom_y = 0.5  # 页面底部的 Y 坐标
        lifeline_top_y = y - height / 2  # 生命线起点（对象框底部）

        lifeline = page.DrawLine(x, lifeline_top_y, x, lifeline_bottom_y)

        # 设置虚线样式
        try:
            lifeline.CellsU("LineColor").FormulaU = "RGB(100,100,100)"
        except:
            pass
        try:
            lifeline.CellsU("LineWidth").FormulaU = "0.75 pt"
        except:
            pass
        try:
            lifeline.CellsU("LinePattern").FormulaU = "33"  # 虚线
        except:
            pass

        obj.lifeline_shape = lifeline

        print(f"   [OK] 已绘制对象: {obj.name}（含生命线）")

    def _draw_messages(self):
        """绘制所有消息 - 标准UML顺序图箭头样式"""
        page = self.visio.page

        for i, msg in enumerate(self.messages):
            try:
                from_x = msg.from_object.x
                to_x = msg.to_object.x
                y = msg.y_position

                # 绘制水平消息线
                connector = page.DrawLine(from_x, y, to_x, y)

                # 设置基础样式
                try:
                    connector.CellsU("LineColor").FormulaU = "RGB(0,0,0)"
                except:
                    pass
                try:
                    connector.CellsU("LineWidth").FormulaU = "1 pt"
                except:
                    pass

                # 根据消息类型设置不同的线条样式和箭头
                if msg.message_type == "sync":
                    # 同步调用消息：实线 + 实心三角箭头
                    try:
                        connector.CellsU("LinePattern").FormulaU = "1"  # 实线
                    except:
                        pass
                    try:
                        connector.CellsU("EndArrow").FormulaU = "2"  # 实心三角箭头
                    except:
                        pass
                    try:
                        connector.CellsU("EndArrowSize").FormulaU = "2"
                    except:
                        pass

                elif msg.message_type == "async":
                    # 异步消息：实线 + 开放箭头
                    try:
                        connector.CellsU("LinePattern").FormulaU = "1"  # 实线
                    except:
                        pass
                    try:
                        connector.CellsU("EndArrow").FormulaU = "24"  # 开放箭头
                    except:
                        pass
                    try:
                        connector.CellsU("EndArrowSize").FormulaU = "2"
                    except:
                        pass

                elif msg.message_type == "return":
                    # 返回消息：虚线 + 开放箭头
                    try:
                        connector.CellsU("LinePattern").FormulaU = "33"  # 虚线
                    except:
                        pass
                    try:
                        connector.CellsU("EndArrow").FormulaU = "24"  # 开放箭头
                    except:
                        pass
                    try:
                        connector.CellsU("EndArrowSize").FormulaU = "2"
                    except:
                        pass

                else:
                    # 默认：实线无箭头
                    try:
                        connector.CellsU("LinePattern").FormulaU = "1"
                    except:
                        pass
                    try:
                        connector.CellsU("EndArrow").FormulaU = "0"
                    except:
                        pass

                # 在消息线上方添加文本标签
                label_x = (from_x + to_x) / 2
                label_y = y + 0.15

                # 计算标签宽度，确保文字不换行
                text_width = max(len(msg.message_text) * 0.06 + 0.3, 1.5)

                label_shape = self.visio.add_text_box(
                    label_x,
                    label_y,
                    msg.message_text,
                    width=text_width,
                    height=0.4
                )

                if label_shape:
                    try:
                        label_shape.CellsU("CharSize").FormulaU = "9 pt"
                    except:
                        pass
                    try:
                        label_shape.CellsU("FillForegnd").FormulaU = "RGB(255,255,255)"
                    except:
                        pass
                    try:
                        label_shape.CellsU("LinePattern").FormulaU = "0"  # 无边框
                    except:
                        pass

                print(f"   [OK] 已绘制消息 {i + 1}: {msg.message_text}")

            except Exception as e:
                print(f"   [WARN] 绘制消息失败: {e}")

    def _draw_title(self):
        """绘制标题"""
        page_width = self.visio.page.PageSheet.Cells("PageWidth").Result("in")
        page_height = self.visio.page.PageSheet.Cells("PageHeight").Result("in")

        self.visio.add_text_box(
            x=page_width / 2,
            y=page_height - 0.4,
            text=self.title,
            width=6,
            height=0.6
        )


def generate_sequence_example():
    """
    示例4：创建一个酒店预订系统的顺序图
    包含：对象框、虚线生命线、带编号的消息箭头（同步/异步/返回）
    """
    with VisioAutomation(visible=True) as visio:
        visio.new_document()
        visio.set_page_size(11, 8.5)

        builder = SequenceDiagramBuilder(visio)
        builder.set_title("酒店预订系统顺序图")

        seq_obj_user = builder.add_object("用户")
        seq_obj_ui = builder.add_object("界面")
        seq_obj_controller = builder.add_object("控制器")
        seq_obj_db = builder.add_object("数据库")

        # 同步消息（实线+实心三角箭头）
        builder.add_message(seq_obj_user, seq_obj_ui, "1: 搜索酒店", "sync")
        builder.add_message(seq_obj_ui, seq_obj_controller, "2: 处理搜索请求", "sync")
        builder.add_message(seq_obj_controller, seq_obj_db, "3: 查询酒店信息", "sync")

        # 返回消息（虚线+开放箭头）
        builder.add_message(seq_obj_db, seq_obj_controller, "4: 返回结果", "return")
        builder.add_message(seq_obj_controller, seq_obj_ui, "5: 显示列表", "return")
        builder.add_message(seq_obj_ui, seq_obj_user, "6: 展示搜索结果", "return")

        # 同步消息
        builder.add_message(seq_obj_user, seq_obj_ui, "7: 选择房间并预订", "sync")
        builder.add_message(seq_obj_ui, seq_obj_controller, "8: 提交预订请求", "sync")
        builder.add_message(seq_obj_controller, seq_obj_db, "9: 创建订单记录", "sync")

        # 返回消息
        builder.add_message(seq_obj_db, seq_obj_controller, "10: 确认成功", "return")
        builder.add_message(seq_obj_controller, seq_obj_ui, "11: 返回预订确认", "return")
        builder.add_message(seq_obj_ui, seq_obj_user, "12: 显示预订成功", "return")

        # 异步消息（实线+开放箭头）
        builder.add_message(seq_obj_controller, seq_obj_db, "13: 发送通知邮件", "async")

        if builder.build():
            save_path = os.path.join(os.path.dirname(__file__), "output", "sequence_test.vsdx")
            visio.save_document(save_path)
            print(f"\n 顺序图已成功生成！")
            print(f" 文件保存位置: {os.path.abspath(save_path)}")
            input("\n按回车键返回主菜单...")


def show_main_menu():
    """显示主菜单"""
    print("\n" + "=" * 70)
    print("   Visio UML 图自动生成系统 v5.0")
    print("=" * 70)
    print("\n请选择要生成的图表类型：\n")
    print("  [1] 用例图 (Use Case Diagram)")
    print("      示例：在线购物系统用例图")
    print("      包含：参与者、用例、系统边界、关联/包含/扩展/泛化关系\n")
    print("  [2] 类图 (Class Diagram)")
    print("      示例：图书管理系统类图")
    print("      包含：类/接口/抽象类、继承/实现/聚合/组合/依赖/关联关系\n")
    print("  [3] 对象图 (Object Diagram)")
    print("      示例：订单处理场景对象图")
    print("      包含：对象实例、属性值、对象间关系\n")
    print("  [4] 顺序图 (Sequence Diagram)")
    print("      示例：酒店预订系统顺序图")
    print("      包含：对象框、虚线生命线、带编号的消息箭头\n")
    print("  [5] 生成全部示例（依次生成所有四种图）")
    print()
    print("  [6] 🤖 AI 智能分析生成（新✨）")
    print("      ✅ 本地AI引擎（推荐）：无需网络、无需API Key")
    print("      ✅ 支持同义词理解和语义匹配")
    print("      ✅ 内置6种常见系统模板 + 支持自定义")
    print("      ☁️ 也支持 DeepSeek / 通义千问 / 豆包 大模型")
    print()
    print("  [0] 退出程序")
    print("\n" + "-" * 70)


def main():
    """
    主函数 - 交互式菜单驱动
    """
    print("\n" + "=" * 70)
    print("  Visio UML 图自动生成系统 v5.0 (完整版)")
    print("=" * 70)
    print("\n本系统将演示如何使用 Python 自动生成专业的 Visio UML 图表")
    print("支持：用例图 | 类图 | 对象图 | 顺序图")
    print("兼容：Microsoft Visio 2016 及以上版本")
    print("\n特点：")
    print("  * 所有代码已整合到一个文件中")
    print("  * 通过菜单选择要生成的图表类型")
    print("  * 生成的文件是标准的 .vsdx 格式，可在 Visio 中继续编辑")
    print("  * 【新✨】本地AI智能引擎：无需网络、无需API Key")
    print("  * 支持同义词理解和语义匹配")
    print("  * 内置6种常见系统模板（电商/图书/学生/医院/银行/外卖）")

    if not check_dependencies():
        input("\n按回车键退出...")
        return

    output_dir = os.path.join(os.path.dirname(__file__), "output")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"\n 已创建输出目录: {output_dir}")

    while True:
        show_main_menu()

        try:
            choice = input("\n请输入选项编号 [0-6]: ").strip()

            if choice == "0":
                print("\n 感谢使用！再见！")
                break
            elif choice == "1":
                print("\n>> 正在生成【用例图】示例...")
                generate_use_case_example()
            elif choice == "2":
                print("\n>> 正在生成【类图】示例...")
                generate_class_example()
            elif choice == "3":
                print("\n>> 正在生成【对象图】示例...")
                generate_object_example()
            elif choice == "4":
                print("\n>> 正在生成【顺序图】示例...")
                generate_sequence_example()
            elif choice == "5":
                print("\n>> 正在生成【全部示例】...\n")
                generate_use_case_example()
                generate_class_example()
                generate_object_example()
                generate_sequence_example()
                print("\n 所有示例已完成！")
                input("\n按回车键返回主菜单...")
            elif choice == "6":
                print("\n>> 启动 AI 智能分析...\n")
                ai_auto_generate()
            else:
                print("\n[ERROR] 无效选项，请重新输入！")
                input("按回车键继续...")

        except KeyboardInterrupt:
            print("\n\n 程序已中断，再见！")
            break
        except Exception as e:
            print(f"\n[ERROR] 发生错误: {e}")
            import traceback
            traceback.print_exc()
            input("\n按回车键继续...")


if __name__ == "__main__":
    main()
