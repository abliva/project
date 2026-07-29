# -*- coding: utf-8 -*-
"""
Agent 核心模块 - 任务规划与工具调度

实现"数据获取 → 舆情分析 → 决策建议"的完整决策链编排
作为系统的中央协调器，负责任务分解、工具调用、结果整合
"""

import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

# 导入子模块
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from agent.tools.data_fetcher import FundDataFetcher
from agent.tools.news_crawler import NewsCrawler, SentimentAnalyzer
from agent.tools.sentiment import LLMAnalyzer
from agent.decision import DecisionEngine, DecisionResult


@dataclass
class TaskStatus:
    """任务状态跟踪"""
    task_name: str
    status: str = "pending"  # pending/running/completed/failed
    start_time: float = None  # 改为存储时间戳
    end_time: float = None   # 改为存储时间戳
    duration: float = 0.0
    result: Any = None
    error: str = None
    
    def get_start_time_str(self) -> str:
        """获取格式化的开始时间字符串"""
        if self.start_time:
            return datetime.fromtimestamp(self.start_time).strftime("%H:%M:%S")
        return ""
    
    def get_end_time_str(self) -> str:
        """获取格式化的结束时间字符串"""
        if self.end_time:
            return datetime.fromtimestamp(self.end_time).strftime("%H:%M:%S")
        return ""


@dataclass
class AnalysisReport:
    """
    完整分析报告
    
    整合所有分析结果，生成结构化的投资建议报告
    """
    # 元信息
    report_id: str                           # 报告ID
    generate_time: str                        # 生成时间
    fund_code: str                            # 基金代码
    fund_name: str                            # 基金名称
    
    # 分析结果
    decision_result: DecisionResult = None     # 决策结果
    technical_analysis: Dict = None           # 技术面详细分析
    sentiment_analysis: Dict = None           # 舆情面详细分析
    fundamental_analysis: Dict = None         # 基本面详细分析
    news_summary: List[Dict] = None           # 新闻摘要列表
    
    # 执行统计
    execution_time: float = 0.0               # 总执行时间（秒）
    tasks_completed: int = 0                  # 已完成任务数
    tasks_total: int = 0                      # 总任务数
    data_sources: List[str] = None            # 使用的数据源
    
    def to_markdown(self) -> str:
        """生成Markdown格式的报告"""
        lines = []
        
        # 报告头
        lines.append(f"# 基金智能分析报告")
        lines.append(f"\n**报告编号**: {self.report_id}")
        lines.append(f"**生成时间**: {self.generate_time}")
        lines.append(f"**分析标的**: {self.fund_name} ({self.fund_code})")
        lines.append(f"**执行耗时**: {self.execution_time:.2f}秒")
        lines.append("\n---\n")
        
        if self.decision_result:
            dr = self.decision_result
            
            # 投资建议摘要
            lines.append("## 📊 投资建议摘要\n")
            lines.append(f"| 项目 | 内容 |")
            lines.append("|------|------|")
            lines.append(f"| **综合评分** | **{dr.total_score}/100** |")
            lines.append(f"| **投资建议** | **{dr.recommendation}** |")
            lines.append(f"| **操作方向** | {dr.action} |")
            lines.append(f"| **建议仓位** | {dr.position_suggestion*100:.1f}% |")
            lines.append(f"| **风险等级** | {dr.risk_level} |")
            lines.append(f"| **置信度** | {dr.confidence_level*100:.1f}% |")
            lines.append("")
            
            # 目标价位
            lines.append("### 💰 价位参考")
            lines.append(f"- **目标区间**: {dr.target_price_range[0]:.4f} - {dr.target_price_range[1]:.4f}")
            lines.append(f"- **止损价位**: {dr.stop_loss_price:.4f}")
            lines.append(f"- **止盈价位**: {dr.take_profit_price:.4f}")
            lines.append("")
            
            # 一句话总结
            lines.append(f"> **{dr.summary}**\n")
            
            # 多因子得分详情
            lines.append("## 📈 多因子分析详情\n")
            lines.append("| 因子维度 | 得分 | 权重 | 加权分 | 关键指标 |")
            lines.append("|----------|------|------|--------|----------|")
            
            for factor_score in [dr.technical_score, dr.sentiment_score, 
                                  dr.fundamental_score, dr.market_score]:
                details_str = "；".join([f"{k}:{v}" for k, v in list(factor_score.details.items())[:2]])
                lines.append(
                    f"| {factor_score.name} | {factor_score.score:.1f} | "
                    f"{factor_score.weight*100:.0%} | {factor_score.weighted_score:.2f} | "
                    f"{details_str[:40]}... |"
                )
            lines.append("")
            
            # 风险提示
            lines.append("## ⚠️ 风险提示\n")
            lines.append(f"**风险等级**: {dr.risk_level}\n")
            lines.append("**主要风险因素**:")
            for risk in dr.risk_factors:
                lines.append(f"- {risk}")
            lines.append("")
            
            # 关键发现
            lines.append("## 🔍 关键发现\n")
            for i, finding in enumerate(dr.key_findings, 1):
                lines.append(f"{i}. {finding}")
            lines.append("")
            
            # 决策推理
            lines.append("## 🧠 决策推理\n")
            lines.append(dr.reasoning)
            lines.append("")
        
        # 新闻摘要（如果有）
        if self.news_summary and len(self.news_summary) > 0:
            lines.append("## 📰 相关新闻摘要\n")
            for i, news in enumerate(self.news_summary[:8], 1):  # 显示前8条
                sentiment_emoji = {
                    "强烈利好": "🟢🟢",
                    "利好": "🟢",
                    "中性": "⚪",
                    "利空": "🔴",
                    "强烈利空": "🔴🔴",
                }.get(news.get('sentiment', '中性'), '⚪')
                
                lines.append(f"{i}. {sentiment_emoji} [{news.get('source', '')}] {news.get('title', '')}")
                lines.append(f"   情感: {news.get('sentiment', 'N/A')} | 时间: {news.get('time', 'N/A')}")
            lines.append("")
        
        # 免责声明
        lines.append("---\n")
        lines.append("> **免责声明**: 本报告由AI系统自动生成，仅供参考，不构成任何投资建议。")
        lines.append("> 投资有风险，入市需谨慎。请根据自身情况独立判断并决策。\n")
        
        return "\n".join(lines)
    
    def to_json(self) -> str:
        """导出为JSON格式"""
        output = {
            "report_id": self.report_id,
            "generate_time": self.generate_time,
            "fund_code": self.fund_code,
            "fund_name": self.fund_name,
            "execution_time": self.execution_time,
            "decision_result": self.decision_result.to_dict() if self.decision_result else None,
            "news_count": len(self.news_summary) if self.news_summary else 0,
        }
        return json.dumps(output, ensure_ascii=False, indent=2)


class FundAnalysisAgent:
    """
    基金智能分析Agent - 核心类
    
    职责：
    1. 接收用户输入的基金代码
    2. 编排和调度各功能模块执行分析流程
    3. 整合多源数据和分析结果
    4. 生成结构化的投资建议报告
    
    工作流程：
    用户输入基金代码
        ↓
    [阶段1] 数据获取层
        ├── 获取基金基本信息
        ├── 获取历史净值数据
        └── 获取持仓明细
        ↓
    [阶段2] 信息处理层
        ├── 计算技术指标
        ├── 抓取相关新闻
        └── 进行情感分析
        ↓
    [阶段3] 决策输出层
        ├── 多因子评分
        ├── 风险评估
        └── 生成投资建议
        ↓
    输出完整分析报告
    """
    
    def __init__(self, use_llm: bool = False, api_key: str = None):
        """
        初始化Agent
        
        Args:
            use_llm: 是否使用LLM进行高级情感分析
            api_key: LLM API密钥
        """
        print("="*70)
        print("🤖 基金智能分析决策 Agent 系统")
        print("="*70)
        print("[初始化] 正在加载各功能模块...")
        
        # 初始化各个工具模块
        self.data_fetcher = FundDataFetcher()
        self.news_crawler = NewsCrawler()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.llm_analyzer = LLMAnalyzer(api_key=api_key) if use_llm else LLMAnalyzer()
        self.decision_engine = DecisionEngine()
        
        # 配置
        self.use_llm = use_llm
        self.task_history: List[TaskStatus] = []
        
        print("[初始化] 所有模块加载完成 ✓")
        print(f"[配置] LLM模式: {'启用' if use_llm else '规则引擎'}")
    
    def analyze_fund(self, fund_code: str, include_news: bool = True) -> AnalysisReport:
        """
        执行完整的基金分析流程（主入口）
        
        Args:
            fund_code: 基金代码（6位数字）
            include_news: 是否包含新闻情感分析（默认True）
            
        Returns:
            完整的分析报告对象
        """
        # 验证基金代码
        if not self._validate_fund_code(fund_code):
            raise ValueError(f"无效的基金代码: {fund_code}")
        
        # 初始化报告
        report_id = f"RPT_{fund_code}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        report = AnalysisReport(
            report_id=report_id,
            generate_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            fund_code=fund_code,
            fund_name="",
            data_sources=[],
        )
        
        overall_start = time.time()
        
        try:
            # ==================== 阶段1：数据获取 ====================
            print("\n" + "▶"*35)
            print("【阶段1】数据获取")
            print("▶"*35)
            
            # 任务1：获取基金完整数据
            fund_data_task = TaskStatus(task_name="基金数据获取")
            fund_data_task.status = "running"
            fund_data_task.start_time = time.time()  # 使用时间戳

            fund_data = self.data_fetcher.get_complete_fund_data(fund_code)

            fund_data_task.status = "completed"
            fund_data_task.end_time = time.time()  # 使用时间戳
            fund_data_task.duration = fund_data_task.end_time - fund_data_task.start_time if fund_data_task.start_time else 0.0
            fund_data_task.result = "成功"
            self.task_history.append(fund_data_task)
            
            # 更新报告基本信息
            report.fund_name = fund_data.get("basic_info", {}).get("fund_name", "")
            report.technical_analysis = fund_data.get("technical_indicators", {})
            report.fundamental_analysis = {
                "holdings": fund_data.get("holdings", {}),
                "basic_info": fund_data.get("basic_info", {}),
            }
            report.data_sources.append("AkShare")
            
            # ==================== 阶段2：信息处理 ====================
            print("\n" + "▶"*35)
            print("【阶段2】信息处理与分析")
            print("▶"*35)
            
            sentiment_data = None
            analyzed_news = []
            
            if include_news:
                # 任务2：新闻抓取（增加异常保护，确保不影响整体流程）
                news_task = TaskStatus(task_name="新闻抓取")
                news_task.status = "running"
                news_task.start_time = time.time()  # 使用时间戳

                try:
                    news_list = self.news_crawler.fetch_fund_news(
                        fund_code,
                        fund_data['basic_info']['fund_name']
                    )

                    # 同时抓取市场新闻
                    market_news = self.news_crawler.fetch_market_news()
                    all_news = news_list + market_news

                    news_task.status = "completed"
                    news_task.end_time = time.time()  # 使用时间戳
                    news_task.duration = news_task.end_time - news_task.start_time if news_task.start_time else 0.0
                    news_task.result = f"获取{len(all_news)}条新闻"
                    self.task_history.append(news_task)

                    # 任务3：情感分析
                    sentiment_task = TaskStatus(task_name="情感分析")
                    sentiment_task.status = "running"
                    sentiment_task.start_time = time.time()  # 使用时间戳

                    # 使用基础情感分析器进行批量分析
                    analyzed_news = self.sentiment_analyzer.analyze_news_batch(all_news)

                    # 如果启用LLM，对重要新闻进行深度分析
                    if self.use_llm and analyzed_news:
                        important_news = [n for n in analyzed_news
                                         if abs(n.sentiment_score) > 1.5][:3]
                        for news in important_news:
                            llm_result = self.llm_analyzer.analyze_sentiment(
                                news.title + " " + news.content
                            )
                            # 用LLM结果增强基础分析
                            news.sentiment_label = llm_result.label
                            news.sentiment_score = llm_result.score

                    # 计算整体舆情指数
                    sentiment_data = self.sentiment_analyzer.calculate_overall_sentiment(analyzed_news)

                    sentiment_task.status = "completed"
                    sentiment_task.end_time = time.time()  # 使用时间戳
                    sentiment_task.duration = sentiment_task.end_time - sentiment_task.start_time if sentiment_task.start_time else 0.0
                    sentiment_task.result = f"整体情感: {sentiment_data.get('overall_label', 'N/A')}"
                    self.task_history.append(sentiment_task)

                    # 准备新闻摘要
                    report.news_summary = [
                        {
                            "title": n.title,
                            "source": n.source,
                            "time": n.publish_time,
                            "sentiment": n.sentiment_label,
                            "score": n.sentiment_score,
                        }
                        for n in analyzed_news[:10]
                    ]

                    report.sentiment_analysis = sentiment_data
                    report.data_sources.append("新闻爬虫")

                except Exception as news_error:
                    # 新闻抓取/情感分析失败时，使用默认值继续执行
                    print(f"\n⚠️ [警告] 新闻抓取或情感分析出现异常: {str(news_error)}")
                    print("   将跳过新闻分析，继续执行决策流程...")

                    news_task.status = "failed"
                    news_task.end_time = time.time()  # 使用时间戳
                    news_task.duration = news_task.end_time - news_task.start_time if news_task.start_time else 0.0
                    news_task.error = str(news_error)
                    news_task.result = "新闻抓取失败，已跳过"
                    self.task_history.append(news_task)

                    # 设置默认的舆情数据
                    sentiment_data = {
                        "overall_score": 0,
                        "overall_label": "中性",
                        "positive_ratio": 50,
                        "negative_ratio": 20,
                        "neutral_ratio": 30,
                        "latest_trend": "平稳",
                    }
                    analyzed_news = []
            
            # ==================== 阶段3：决策输出 ====================
            print("\n" + "▶"*35)
            print("【阶段3】多因子决策")
            print("▶"*35)
            
            # 任务4：执行决策
            decision_task = TaskStatus(task_name="决策引擎")
            decision_task.status = "running"
            decision_task.start_time = time.time()  # 使用时间戳
            
            # 如果没有舆情数据，使用中性默认值
            if not sentiment_data:
                sentiment_data = {
                    "overall_score": 0,
                    "overall_label": "中性",
                    "positive_ratio": 50,
                    "negative_ratio": 20,
                    "neutral_ratio": 30,
                    "latest_trend": "平稳",
                }
            
            # 执行决策
            decision_result = self.decision_engine.make_decision(fund_data, sentiment_data)
            
            decision_task.status = "completed"
            decision_task.end_time = time.time()  # 使用时间戳
            decision_task.duration = decision_task.end_time - decision_task.start_time if decision_task.start_time else 0.0
            decision_task.result = f"建议: {decision_result.recommendation}"
            self.task_history.append(decision_task)
            
            # 更新报告
            report.decision_result = decision_result
            report.data_sources.append("决策引擎")
            
        except Exception as e:
            print(f"\n❌ [错误] 分析过程出现异常: {str(e)}")
            import traceback
            print(f"\n[详细错误信息]")
            traceback.print_exc()
            # 创建错误状态的任务记录
            error_task = TaskStatus(
                task_name="异常捕获",
                status="failed",
                error=str(e),
            )
            self.task_history.append(error_task)
            raise
        
        finally:
            # 计算总耗时
            total_time = time.time() - overall_start
            report.execution_time = round(total_time, 2)
            report.tasks_completed = sum(1 for t in self.task_history if t.status == "completed")
            report.tasks_total = len(self.task_history)
            
            # 打印执行摘要
            self._print_execution_summary(report)
        
        return report
    
    def _validate_fund_code(self, fund_code: str) -> bool:
        """
        验证基金代码格式
        
        Args:
            fund_code: 待验证的基金代码
            
        Returns:
            是否有效
        """
        if not fund_code:
            return False
        
        # 基金代码应为6位数字
        if len(fund_code) != 6 or not fund_code.isdigit():
            return False
        
        return True
    
    def _print_execution_summary(self, report: AnalysisReport):
        """打印执行摘要"""
        print("\n" + "="*70)
        print("📋 执行摘要")
        print("="*70)
        print(f"报告ID: {report.report_id}")
        print(f"分析标的: {report.fund_name} ({report.fund_code})")
        print(f"总耗时: {report.execution_time:.2f}秒")
        print(f"完成任务: {report.tasks_completed}/{report.tasks_total}")
        print(f"数据来源: {', '.join(report.data_sources)}")
        
        print("\n任务明细:")
        for task in self.task_history:
            status_icon = {"completed": "✅", "running": "⏳", "failed": "❌", "pending": "⏸️"}
            icon = status_icon.get(task.status, "❓")
            duration_str = f"{task.duration:.2f}s" if task.duration > 0 else "-"
            print(f"  {icon} {task.task_name}: {task.result or task.error or '-'} ({duration_str})")
        
        if report.decision_result:
            print(f"\n最终建议: {report.decision_result.recommendation}")
            print(f"综合评分: {report.decision_result.total_score}/100")
        
        print("="*70 + "\n")
    
    def batch_analyze(self, fund_codes: List[str]) -> Dict[str, AnalysisReport]:
        """
        批量分析多个基金
        
        Args:
            fund_codes: 基金代码列表
            
        Returns:
            字典：{基金代码: 分析报告}
        """
        results = {}
        total = len(fund_codes)
        
        print(f"\n{'='*70}")
        print(f"📦 开始批量分析 {total} 只基金")
        print(f"{'='*70}\n")
        
        for i, code in enumerate(fund_codes, 1):
            print(f"\n[{i}/{total}] 正在分析基金: {code}")
            
            try:
                report = self.analyze_fund(code)
                results[code] = report
            except Exception as e:
                print(f"[警告] 基金 {code} 分析失败: {str(e)}")
                continue
        
        # 打印批量分析汇总
        print(f"\n{'='*70}")
        print(f"批量分析完成！成功: {len(results)}/{total}")
        print(f"{'='*70}")
        
        return results
    
    def get_agent_status(self) -> Dict:
        """
        获取Agent运行状态信息
        
        Returns:
            状态字典
        """
        return {
            "agent_type": "FundAnalysisAgent",
            "modules_loaded": [
                "FundDataFetcher",
                "NewsCrawler", 
                "SentimentAnalyzer",
                "LLMAnalyzer",
                "DecisionEngine",
            ],
            "llm_enabled": self.use_llm,
            "tasks_executed": len(self.task_history),
            "success_rate": (
                sum(1 for t in self.task_history if t.status == "completed") / 
                max(len(self.task_history), 1) * 100
            ),
            "last_activity": self.task_history[-1].end_time if self.task_history else None,
        }


# 测试代码
if __name__ == "__main__":
    # 创建Agent实例
    agent = FundAnalysisAgent(use_llm=False)
    
    # 测试单只基金分析
    test_fund = "110011"
    
    print(f"\n开始测试分析基金: {test_fund}")
    
    try:
        report = agent.analyze_fund(test_fund)
        
        # 输出Markdown报告
        print("\n" + "#"*70)
        print("# 生成的分析报告")
        print("#"*70)
        print(report.to_markdown())
        
        # 保存为JSON
        print("\n# JSON格式输出:")
        print(report.to_json())
        
    except Exception as e:
        print(f"测试失败: {e}")
