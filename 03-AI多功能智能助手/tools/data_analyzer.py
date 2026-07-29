"""
数据分析工具
提供CSV/JSON等数据文件的读取、分析和可视化功能
支持数据统计、趋势分析和报告生成
"""

import json
import os
import re
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime

# 尝试导入pandas，如果不可用则使用基础方法
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    print("⚠ pandas未安装，将使用基础数据分析功能")

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.tool_executor import BaseTool, ToolResult


@dataclass
class DataAnalysisRequest:
    """数据分析请求"""
    file_path: str                    # 数据文件路径
    analysis_type: str = "overview"   # 分析类型：overview, statistical, trend, custom
    target_columns: List[str] = field(default_factory=list)  # 目标列（可选）
    filters: Dict[str, Any] = field(default_factory=dict)     # 过滤条件
    output_format: str = "summary"    # 输出格式：summary, detailed, json
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "analysis_type": self.analysis_type,
            "target_columns": self.target_columns,
            "filters": self.filters,
            "output_format": self.output_format
        }


@dataclass 
class AnalysisResult:
    """分析结果"""
    success: bool
    analysis_type: str
    summary: str                      # 文字摘要
    statistics: Dict[str, Any] = field(default_factory=dict)  # 统计数据
    insights: List[str] = field(default_factory=list)         # 发现和洞察
    visualizations: List[str] = field(default_factory=list)   # 可视化建议
    raw_data: Any = None              # 原始数据引用
    error_message: str = ""
    processing_time: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "analysis_type": self.analysis_type,
            "summary": self.summary,
            "statistics": self.statistics,
            "insights_count": len(self.insights),
            "insights": self.insights[:5],  # 限制输出数量
            "visualizations": self.visualizations,
            "error_message": self.error_message,
            "processing_time": round(self.processing_time, 3)
        }


class DataAnalyzerTool(BaseTool):
    """
    数据分析工具
    
    功能：
    1. 数据读取 - 支持CSV、JSON、Excel等格式
    2. 概览分析 - 基本统计信息、数据质量检查
    3. 统计分析 - 描述性统计、分布分析
    4. 趋势分析 - 时间序列分析、变化趋势
    5. 自定义查询 - 灵活的数据筛选和聚合
    
    注意：完整功能需要安装pandas库
    """
    
    SUPPORTED_FORMATS = ['.csv', '.json', '.xlsx', '.xls', '.tsv']
    
    # 分析类型定义
    ANALYSIS_TYPES = {
        "overview": {
            "name": "概览分析",
            "description": "数据基本信息、结构预览、质量评估"
        },
        "statistical": {
            "name": "统计分析",
            "description": "描述性统计、分布特征、相关性"
        },
        "trend": {
            "name": "趋势分析",
            "description": "时间序列、变化趋势、预测"
        },
        "comparison": {
            "name": "对比分析",
            "description": "分组比较、差异分析"
        },
        "custom": {
            "name": "自定义分析",
            "description": "用户指定的自定义分析任务"
        }
    }

    def __init__(self):
        """初始化数据分析工具"""
        super().__init__(
            name="data_analyzer",
            description="数据分析工具，支持CSV/JSON文件读取、统计分析和趋势洞察"
        )
        
        # 参数模式
        self.parameters_schema = {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "要分析的数据文件路径"
                },
                "analysis_type": {
                    "type": "string",
                    "enum": list(self.ANALYSIS_TYPES.keys()),
                    "default": "overview",
                    "description": "分析类型"
                },
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要分析的列名列表"
                },
                "filters": {
                    "type": "object",
                    "description": "数据过滤条件，如 {'column': 'value'}"
                },
                "output_format": {
                    "type": "string",
                    "enum": ["summary", "detailed", "json"],
                    "default": "summary",
                    "description": "输出详细程度"
                }
            },
            "required": ["file_path"]
        }
        
        # 分析历史记录
        self.analysis_history: List[AnalysisResult] = []
        
        print(f"✓ 数据分析工具初始化完成 | Pandas支持: {'✓' if HAS_PANDAS else '✗ (使用基础模式)'}")

    def execute(self, **kwargs) -> ToolResult:
        """
        执行数据分析
        
        Args:
            **kwargs: 分析参数
            
        Returns:
            分析结果
        """
        import time
        start_time = time.time()
        
        try:
            # 构建请求对象
            request = DataAnalysisRequest(
                file_path=kwargs.get("file_path", ""),
                analysis_type=kwargs.get("analysis_type", "overview"),
                target_columns=kwargs.get("columns", []),
                filters=kwargs.get("filters", {}),
                output_format=kwargs.get("output_format", "summary")
            )
            
            # 验证文件存在性和格式
            validation_result = self._validate_file(request.file_path)
            if not validation_result[0]:
                result = AnalysisResult(
                    success=False,
                    analysis_type=request.analysis_type,
                    error_message=validation_result[1],
                    processing_time=time.time() - start_time
                )
                return ToolResult(success=False, tool_name=self.name, error_message=result.error_message)
            
            # 根据是否有pandas选择分析方法
            if HAS_PANDAS:
                analysis_result = self._analyze_with_pandas(request)
            else:
                analysis_result = self._analyze_basic(request)
            
            analysis_result.processing_time = time.time() - start_time
            
            # 记录到历史
            self.analysis_history.append(analysis_result)
            
            # 格式化输出
            formatted_output = self._format_analysis_output(analysis_result, request.output_format)
            
            return ToolResult(
                success=analysis_result.success,
                tool_name=self.name,
                result_data=analysis_result.to_dict(),
                metadata={
                    "formatted_output": formatted_output,
                    "file_analyzed": request.file_path,
                    "processing_time": analysis_result.processing_time
                }
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                tool_name=self.name,
                error_message=f"数据分析失败: {str(e)}"
            )

    def _validate_file(self, file_path: str) -> tuple[bool, str]:
        """验证文件是否有效"""
        if not file_path:
            return False, "请提供数据文件路径"
        
        if not os.path.exists(file_path):
            return False, f"文件不存在: {file_path}"
        
        # 检查文件扩展名
        _, ext = os.path.splitext(file_path)
        if ext.lower() not in self.SUPPORTED_FORMATS:
            return False, f"不支持的文件格式: {ext}。支持的格式: {', '.join(self.SUPPORTED_FORMATS)}"
        
        # 检查文件大小（限制为50MB）
        file_size = os.path.getsize(file_path)
        if file_size > 50 * 1024 * 1024:
            return False, f"文件过大 ({file_size / 1024 / 1024:.1f}MB)，请使用小于50MB的文件"
        
        return True, ""

    def _analyze_with_pandas(self, request: DataAnalysisRequest) -> AnalysisResult:
        """使用pandas进行完整数据分析"""
        import numpy as np
        
        try:
            # 读取数据
            df = self._read_data_with_pandas(request.file_path)
            
            if df.empty:
                return AnalysisResult(
                    success=False,
                    analysis_type=request.analysis_type,
                    error_message="数据文件为空或无法解析"
                )
            
            # 应用过滤条件
            if request.filters:
                df = self._apply_filters(df, request.filters)
            
            # 选择目标列
            if request.target_columns:
                available_cols = [c for c in request.target_columns if c in df.columns]
                if available_cols:
                    df = df[available_cols]
            
            # 根据分析类型执行相应分析
            analyzer_map = {
                "overview": self._pandas_overview,
                "statistical": self._pandas_statistical,
                "trend": self._pandas_trend,
                "comparison": self._pandas_comparison,
                "custom": self._pandas_custom
            }
            
            analyzer_func = analyzer_map.get(request.analysis_type, self._pandas_overview)
            result = analyzer_func(df, request)
            result.raw_data = df.head(10).to_dict('records')  # 保存前10行作为参考
            
            return result
            
        except Exception as e:
            return AnalysisResult(
                success=False,
                analysis_type=request.analysis_type,
                error_message=f"分析过程出错: {str(e)}"
            )

    def _read_data_with_pandas(self, file_path: str):
        """使用pandas读取数据文件"""
        _, ext = os.path.splitext(file_path)
        
        read_funcs = {
            '.csv': lambda f: pd.read_csv(f, encoding='utf-8'),
            '.tsv': lambda f: pd.read_csv(f, sep='\t', encoding='utf-8'),
            '.json': lambda f: pd.read_json(f, encoding='utf-8'),
            '.xlsx': lambda f: pd.read_excel(f),
            '.xls': lambda f: pd.read_excel(f)
        }
        
        read_func = read_funcs.get(ext.lower())
        if not read_func:
            raise ValueError(f"不支持的文件格式: {ext}")
        
        return read_func(file_path)

    def _apply_filters(self, df, filters: Dict[str, Any]):
        """应用数据过滤"""
        for column, value in filters.items():
            if column in df.columns:
                if isinstance(value, list):
                    df = df[df[column].isin(value)]
                elif isinstance(value, dict):
                    # 支持范围查询等复杂条件
                    if 'min' in value:
                        df = df[df[column] >= value['min']]
                    if 'max' in value:
                        df = df[df[column] <= value['max']]
                else:
                    df = df[df[column] == value]
        return df

    def _pandas_overview(self, df, request: DataAnalysisRequest) -> AnalysisResult:
        """概览分析"""
        summary_parts = []
        insights = []
        
        # 基本信息
        summary_parts.append(f"📊 数据概览报告\n{'='*40}\n")
        summary_parts.append(f"📁 文件: {os.path.basename(request.file_path)}")
        summary_parts.append(f"📏 数据维度: {df.shape[0]} 行 × {df.shape[1]} 列")
        summary_parts.append(f"💾 内存占用: {df.memory_usage(deep=True).sum() / 1024:.1f} KB")
        
        # 列信息
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
        
        summary_parts.append(f"\n📋 列类型分布:")
        summary_parts.append(f"   • 数值型: {len(numeric_cols)} 列")
        summary_parts.append(f"   • 分类型: {len(categorical_cols)} 列")
        
        # 缺失值分析
        missing_info = df.isnull().sum()
        missing_cols = missing_info[missing_info > 0]
        
        if len(missing_cols) > 0:
            missing_pct = (missing_cols / len(df) * 100).round(2)
            summary_parts.append(f"\n⚠️ 缺失值情况 ({len(missing_cols)} 列有缺失):")
            for col in missing_cols.head(5):
                summary_parts.append(f"   • {col}: {missing_cols[col]} ({missing_pct[col]:.1f}%)")
            insights.append(f"发现{len(missing_cols)}列存在缺失值，建议进行数据清洗")
        else:
            summary_parts.append("\n✅ 数据完整性良好，无缺失值")
        
        # 数值列基本统计
        if numeric_cols:
            summary_parts.append(f"\n📈 数值型变量统计 (前5个):")
            stats_df = df[numeric_cols[:5]].describe()
            for col in stats_df.columns[:5]:
                col_stats = stats_df[col]
                summary_parts.append(f"\n   【{col}】")
                summary_parts.append(f"      均值: {col_stats['mean']:.2f}")
                summary_parts.append(f"      标准差: {col_stats['std']:.2f}")
                summary_parts.append(f"      范围: [{col_stats['min']:.2f}, {col_stats['max']:.2f}]")
                
                # 异常检测（简化版）
                q1, q3 = col_stats['25%'], col_stats['75%']
                iqr = q3 - q1
                outliers_count = ((df[col] < (q1 - 1.5 * iqr)) | (df[col] > (q3 + 1.5 * iqr))).sum()
                if outliers_count > 0:
                    insights.append(f"{col}可能存在{outliers_count}个异常值")
        
        # 分类型列信息
        if categorical_cols:
            summary_parts.append(f"\n📝 分类型变量示例 (前3个):")
            for col in categorical_cols[:3]:
                unique_count = df[col].nunique()
                top_value = df[col].mode().iloc[0] if len(df[col].mode()) > 0 else "N/A"
                summary_parts.append(f"   • {col}: {unique_count}个唯一值, 最常见: '{top_value}'")
        
        # 生成洞察
        insights.insert(0, f"数据集包含{len(df)}条记录，整体规模{'适中' if len(df) < 10000 else '较大'}")
        if len(numeric_cols) >= 3:
            insights.append("数值型变量较多，适合进行相关性和回归分析")
        
        summary_text = "\n".join(summary_parts)
        
        return AnalysisResult(
            success=True,
            analysis_type="overview",
            summary=summary_text,
            statistics={
                "shape": list(df.shape),
                "numeric_columns": numeric_cols,
                "categorical_columns": categorical_cols,
                "missing_values": int(missing_info.sum()),
                "memory_usage_mb": round(df.memory_usage(deep=True).sum() / 1024 / 1024, 3)
            },
            insights=insights,
            visualizations=["数据分布直方图", "缺失值热力图", "相关性矩阵"]
        )

    def _pandas_statistical(self, df, request: DataAnalysisRequest) -> AnalysisResult:
        """统计分析"""
        import numpy as np
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        
        if not numeric_cols:
            return AnalysisResult(
                success=True,
                analysis_type="statistical",
                summary="⚠️ 数据集中没有数值型变量，无法进行统计分析",
                insights=["建议先对数据进行转换或编码"],
                statistics={"numeric_columns_available": False}
            )
        
        summary_parts = [f"📊 统计分析报告\n{'='*40}\n"]
        insights = []
        
        # 描述性统计
        desc_stats = df[numeric_cols].describe()
        summary_parts.append("📈 描述性统计:\n")
        
        for col in numeric_cols[:8]:  # 最多显示8列
            s = desc_stats[col]
            cv = s['std'] / s['mean'] if s['mean'] != 0 else 0  # 变异系数
            skewness = df[col].skew()  # 偏度
            
            summary_parts.append(f"\n【{col}】")
            summary_parts.append(f"  集中趋势: 均值={s['mean']:.2f}, 中位数={s['50%']:.2f}")
            summary_parts.append(f"  离散程度: 标准差={s['std']:.2f}, 变异系数={cv:.2f}")
            summary_parts.append(f"  分布形态: 偏度={skewness:.2f}", end="")
            if abs(skewness) > 1:
                summary_parts[-1] += " (偏态明显)"
            summary_parts.append(f"  极值范围: [{s['min']:.2f}, {s['max']:.2f}]")
            
            # 分布判断
            if cv < 0.1:
                insights.append(f"{col}变异系数低({cv:.2f})，数据相对集中稳定")
            elif cv > 1:
                insights.append(f"{col}变异系数高({cv:.2f})，离散程度大")
            
            if abs(skewness) > 1:
                direction = "右偏" if skewness > 0 else "左偏"
                insights.append(f"{col}呈{direction}分布，可能存在极端值")
        
        # 相关性分析（如果有多于1个数值列）
        if len(numeric_cols) >= 2:
            corr_matrix = df[numeric_cols].corr()
            strong_corrs = []
            
            # 找出强相关关系（|r| > 0.7）
            for i in range(len(corr_matrix.columns)):
                for j in range(i+1, len(corr_matrix.columns)):
                    corr_val = corr_matrix.iloc[i, j]
                    if abs(corr_val) > 0.7:
                        strong_corrs.append((
                            corr_matrix.columns[i],
                            corr_matrix.columns[j],
                            corr_val
                        ))
            
            if strong_corrs:
                summary_parts.append(f"\n\n🔗 强相关变量对 (|r| > 0.7):")
                for c1, c2, r in strong_corrs[:5]:
                    relation = "正相关" if r > 0 else "负相关"
                    summary_parts.append(f"  • {c1} ↔ {c2}: r={r:.3f} ({relation})")
                insights.append(f"发现{len(strong_corrs)}组强相关变量，注意多重共线性问题")
        
        summary_text = "\n".join(summary_parts)
        
        return AnalysisResult(
            success=True,
            analysis_type="statistical",
            summary=summary_text,
            statistics={
                "variables_analyzed": len(numeric_cols),
                "strong_correlations": len(strong_corrs) if 'strong_corrs' in dir() else 0
            },
            insights=insights,
            visualizations=[
                "箱线图（各变量分布）",
                "散点图矩阵（变量关系）",
                "相关系数热力图"
            ]
        )

    def _pandas_trend(self, df, request: DataAnalysisRequest) -> AnalysisResult:
        """趋势分析"""
        import numpy as np
        
        summary_parts = [f"📈 趋势分析报告\n{'='*40}\n"]
        insights = []
        
        # 尝试识别时间列
        date_columns = []
        for col in df.columns:
            if any(keyword in col.lower() for keyword in ['date', 'time', '日期', '时间']):
                date_columns.append(col)
        
        # 如果没有明确的时间列，尝试自动检测
        if not date_columns:
            for col in df.select_dtypes(include=['object']).columns:
                try:
                    pd.to_datetime(df[col].head())
                    date_columns.append(col)
                    break
                except:
                    continue
        
        if not date_columns:
            return AnalysisResult(
                success=True,
                analysis_type="trend",
                summary="⚠️ 未找到时间序列数据，无法进行趋势分析。\n提示：确保数据中包含日期/时间类型的列。",
                insights=["建议检查数据是否包含时间戳列", "可考虑添加时间维度后再分析"],
                statistics={"has_time_series": False}
            )
        
        time_col = date_columns[0]
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()[:3]  # 最多分析3个指标
        
        summary_parts.append(f"🕐 使用时间列: {time_col}")
        summary_parts.append(f"📊 分析指标: {', '.join(numeric_cols)}\n")
        
        # 转换时间为datetime并排序
        try:
            df_sorted = df.copy()
            df_sorted[time_col] = pd.to_datetime(df_sorted[time_col])
            df_sorted = df_sorted.sort_values(time_col)
            
            for metric in numeric_cols:
                if metric in df_sorted.columns and df_sorted[metric].notna().any():
                    series_data = df_sorted[[time_col, metric]].dropna()
                    
                    if len(series_data) < 2:
                        continue
                    
                    # 计算简单趋势
                    values = series_data[metric].values
                    first_val = values[0]
                    last_val = values[-1]
                    change_pct = ((last_val - first_val) / first_val * 100) if first_val != 0 else 0
                    
                    # 简单线性趋势斜率
                    x = range(len(values))
                    slope = np.polyfit(x, values, 1)[0]
                    
                    trend_direction = "上升 📈" if slope > 0 else ("下降 📉" if slope < 0 else "平稳 ➡️")
                    
                    summary_parts.append(f"\n【{metric}】趋势分析:")
                    summary_parts.append(f"  趋势方向: {trend_direction}")
                    summary_parts.append(f"  变化幅度: {change_pct:+.2f}%")
                    summary_parts.append(f"  起始值: {first_val:.2f} → 结束值: {last_val:.2f}")
                    
                    # 趋势强度判断
                    if abs(change_pct) > 50:
                        strength = "剧烈"
                        insights.append(f"{metric}呈现{strength}{trend_direction.split()[0]}趋势，变化幅度达{abs(change_pct):.1f}%")
                    elif abs(change_pct) > 20:
                        strength = "明显"
                        insights.append(f"{metric}呈{strength}{trend_direction.split()[0]}趋势")
                    else:
                        strength = "轻微"
                        insights.append(f"{metric}变化较为平稳，{trend_direction.split()[0]}幅度较小")
                    
                    # 波动性
                    volatility = np.std(np.diff(values))
                    avg_value = np.mean(values)
                    cv_volatility = volatility / avg_value if avg_value != 0 else 0
                    
                    if cv_volatility > 0.3:
                        summary_parts.append(f"  ⚠️ 波动性较高 (CV={cv_volatility:.2f})")
                        insights.append(f"{metric}波动较大，需关注异常点")
            
            summary_parts.append(f"\n💡 建议:")
            summary_parts.append("  • 可进一步进行季节性分解和周期分析")
            summary_parts.append("  • 建议结合业务背景解读趋势原因")
            
        except Exception as e:
            summary_parts.append(f"\n⚠️ 趋势计算过程中出现警告: {str(e)[:50]}")
        
        summary_text = "\n".join(summary_parts)
        
        return AnalysisResult(
            success=True,
            analysis_type="trend",
            summary=summary_text,
            statistics={
                "time_column": time_col,
                "metrics_analyzed": len(numeric_cols),
                "data_points": len(df)
            },
            insights=insights,
            visualizations=[
                "时间序列折线图",
                "移动平均线",
                "趋势分解图"
            ]
        )

    def _pandas_comparison(self, df, request: DataAnalysisRequest) -> AnalysisResult:
        """对比分析"""
        summary_parts = ["📊 对比分析报告\n" + "="*40 + "\n"]
        
        # 寻找可用于分组的分类变量
        cat_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()[:2]
        num_cols = df.select_dtypes(include=['number']).columns.tolist()[:3]
        
        if not cat_cols or not num_cols:
            return AnalysisResult(
                success=True,
                analysis_type="comparison",
                summary="⚠️ 缺少分类变量或数值变量，无法进行分组对比分析",
                insights=["确保数据中同时包含分类型和数值型列"],
                statistics={}
            )
        
        group_col = cat_cols[0]
        summary_parts.append(f"📂 按 [{group_col}] 进行分组对比\n")
        
        try:
            grouped = df.groupby(group_col)[num_cols].agg(['mean', 'count'])
            
            for metric in num_cols:
                if metric in grouped.columns.get_level_values(0):
                    summary_parts.append(f"\n【{metric}】各组对比:")
                    
                    group_means = grouped[(metric, 'mean')].dropna()
                    group_counts = grouped[(metric, 'count')]
                    
                    overall_mean = df[metric].mean()
                    
                    for group_name in group_means.index[:8]:  # 最多显示8组
                        group_mean = group_means[group_name]
                        count = group_counts[group_name]
                        diff_pct = ((group_mean - overall_mean) / overall_mean * 100) if overall_mean != 0 else 0
                        
                        indicator = "▲" if diff_pct > 0 else ("▼" if diff_pct < 0 else "─")
                        summary_parts.append(
                            f"  {indicator} {group_name}: {group_mean:.2f} "
                            f"(vs 总体 {overall_mean:.2f}, {diff_pct:+.1f}%, n={int(count)})"
                        )
            
            summary_parts.append("\n💡 对比洞察:")
            summary_parts.append("  • 各组间差异可帮助识别关键影响因素")
            summary_parts.append("  • 建议进行显著性检验验证差异统计意义")
            
        except Exception as e:
            summary_parts.append(f"⚠️ 分组计算时出现问题: {str(e)[:80]}")
        
        return AnalysisResult(
            success=True,
            analysis_type="comparison",
            summary="\n".join(summary_parts),
            insights=[f"按{group_col}分组后可观察到明显的组间差异"],
            statistics={"grouping_column": group_col},
            visualizations=["分组箱线图", "均值条形图", "堆叠柱状图"]
        )

    def _pandas_custom(self, df, request: DataAnalysisRequest) -> AnalysisResult:
        """自定义分析（基于用户需求）"""
        return AnalysisResult(
            success=True,
            analysis_type="custom",
            summary=f"✅ 已加载数据集，准备进行自定义分析\n"
                   f"可用操作:\n"
                   f"  • 指定具体列进行深入分析\n"
                   f"  • 设置过滤条件筛选子集\n"
                   f"  • 定义自定义聚合函数\n\n"
                   f"当前数据: {df.shape[0]}行 × {df.shape[1]}列\n"
                   f"列名: {', '.join(df.columns[:10])}",
            insights=["请提供更具体的分析需求以便生成定制化报告"],
            statistics={"shape": list(df.shape), "columns": list(df.columns)},
            visualizations=[]
        )

    def _analyze_basic(self, request: DataAnalysisRequest) -> AnalysisResult:
        """基础模式分析（无pandas时）"""
        try:
            _, ext = os.path.splitext(request.file_path)
            
            with open(request.file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.strip().split('\n')
            
            summary = f"""📊 基础数据分析报告（无Pandas模式）
{'='*40}

📁 文件: {os.path.basename(request.file_path)}
📐 格式: {ext}
📏 大小: {os.path.getsize(request.file_path) / 1024:.1f} KB
📝 行数: {len(lines)}

⚠️ 当前运行在基础模式（未安装pandas）
建议安装pandas以获得完整的分析功能：
  pip install pandas

📋 数据预览（前20行）:
{chr(10).join(lines[:20])}

💡 可用操作:
• 安装pandas后重新分析以获得完整功能
• 当前仅提供基础的文本查看能力
"""
            
            return AnalysisResult(
                success=True,
                analysis_type=request.analysis_type,
                summary=summary,
                statistics={
                    "mode": "basic",
                    "lines": len(lines),
                    "file_size_kb": round(os.path.getsize(request.file_path) / 1024, 2)
                },
                insights=["建议安装pandas库以启用高级分析功能"],
                visualizations=[]
            )
            
        except Exception as e:
            return AnalysisResult(
                success=False,
                analysis_type=request.analysis_type,
                error_message=f"基础分析失败: {str(e)}"
            )

    def _format_analysis_output(self, result: AnalysisResult, output_format: str) -> str:
        """格式化分析结果输出"""
        if output_format == "json":
            return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
        else:
            output = result.summary
            if result.insights:
                output += "\n\n💡 关键洞察:\n"
                for i, insight in enumerate(result.insights, 1):
                    output += f"  {i}. {insight}\n"
            return output

    def get_supported_formats(self) -> List[str]:
        """获取支持的文件格式"""
        return self.SUPPORTED_FORMATS.copy()

    def get_analysis_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取分析历史"""
        return [r.to_dict() for r in self.analysis_history[-limit:]]


if __name__ == "__main__":
    # 测试数据分析工具
    tool = DataAnalyzerTool()
    
    print("\n===== 测试数据分析工具 =====\n")
    
    # 创建测试数据文件
    test_data = """name,age,score,date,city
张三,25,85.5,2024-01-15,北京
李四,30,92.0,2024-02-20,上海
王五,28,78.3,2024-03-10,广州
赵六,35,88.7,2024-04-05,深圳
钱七,22,95.2,2024-05-18,杭州
孙八,29,82.1,2024-06-22,成都
周九,31,90.6,2024-07-30,武汉
吴十,27,76.8,2024-08-14,南京"""
    
    test_file = "test_data.csv"
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(test_data)
    
    # 测试各种分析类型
    test_cases = [
        {"file_path": test_file, "analysis_type": "overview"},
        {"file_path": test_file, "analysis_type": "statistical"},
        {"file_path": test_file, "analysis_type": "trend"},
        {"file_path": test_file, "analysis_type": "comparison"}
    ]
    
    for params in test_cases:
        print(f"\n测试 {params['analysis_type']} 分析:")
        result = tool.execute(**params)
        if result.success:
            print(f"✓ 分析完成 | 耗时: {result.metadata.get('processing_time', 0):.3f}s")
            # 显示部分输出
            formatted = result.metadata.get('formatted_output', '')
            print(formatted[:500] + "..." if len(formatted) > 500 else formatted)
        else:
            print(f"✗ 分析失败: {result.error_message}")
    
    # 清理测试文件
    if os.path.exists(test_file):
        os.remove(test_file)
        print("\n✓ 测试文件已清理")
