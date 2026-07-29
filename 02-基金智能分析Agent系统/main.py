# -*- coding: utf-8 -*-
"""
基金智能分析决策 Agent 系统 - 主程序入口

提供CLI交互界面，用户可输入基金代码，系统自动执行完整的
"数据获取 → 舆情分析 → 决策建议"流程并输出专业报告。

使用方法：
    python main.py                    # 交互模式
    python main.py --code 110011      # 直接分析指定基金
    python main.py --batch            # 批量分析示例基金
    python main.py --help             # 查看帮助信息
"""

import sys
import os
import argparse
import json
from datetime import datetime

# 添加项目根目录到系统路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入Agent核心模块
from agent.core import FundAnalysisAgent, AnalysisReport
from config import SAMPLE_FUND_CODES


def print_banner():
    """打印程序启动横幅"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║        🤖   基金智能分析决策 Agent 系统   🤖                ║
║                                                              ║
║     技术栈：Python + AkShare + RAG + 情感分析               ║
║     功能：智能基金分析 | 舆情监控 | 投资决策建议              ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)
    print(f"\n⏰ 当前时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 66)


def print_menu():
    """打印主菜单"""
    menu = """
┌─────────────────────────────────────┐
│           请选择操作模式              │
├─────────────────────────────────────┤
│  1. 单只基金分析（输入代码）          │
│  2. 批量分析示例基金                 │
│  3. 查看示例基金列表                 │
│  4. 系统状态检查                     │
│  0. 退出系统                         │
└─────────────────────────────────────┘
"""
    print(menu)


def analyze_single_fund(agent: FundAnalysisAgent, fund_code: str):
    """
    分析单只基金并输出报告
    
    Args:
        agent: Agent实例
        fund_code: 基金代码
    """
    print(f"\n{'━'*66}")
    print(f"📊 开始分析基金: {fund_code}")
    print(f"{'━'*66}\n")
    
    try:
        # 执行完整分析流程
        report = agent.analyze_fund(fund_code, include_news=True)
        
        # 输出Markdown格式报告
        print("\n\n" + "█"*70)
        print("📋 完整分析报告")
        print("█"*70 + "\n")
        
        markdown_report = report.to_markdown()
        print(markdown_report)
        
        # 询问是否保存报告
        save_choice = input("\n💾 是否将报告保存到文件？(y/n): ").strip().lower()
        if save_choice == 'y':
            save_report(report)
        
        return report
        
    except ValueError as ve:
        print(f"\n❌ 输入错误: {ve}")
        print("请确保输入正确的6位基金代码")
    except Exception as e:
        print(f"\n❌ 分析过程出错: {str(e)}")
        print("请检查网络连接或稍后重试")
    
    return None


def batch_analysis(agent: FundAnalysisAgent, fund_codes: list = None):
    """
    批量分析多只基金
    
    Args:
        agent: Agent实例
        fund_codes: 基金代码列表（默认使用配置中的示例）
    """
    if not fund_codes:
        fund_codes = SAMPLE_FUND_CODES
    
    print(f"\n{'━'*66}")
    print(f"📦 开始批量分析 {len(fund_codes)} 只基金")
    print(f"{'━'*66}\n")
    
    results = agent.batch_analyze(fund_codes)
    
    # 输出汇总结果
    print("\n\n" + "█"*70)
    print("📊 批量分析汇总报告")
    print("█"*70 + "\n")
    
    print("| 基金代码 | 基金名称 | 建议 | 得分 | 风险等级 |")
    print("|----------|----------|------|------|----------|")
    
    for code, report in results.items():
        if report and report.decision_result:
            dr = report.decision_result
            emoji = "🟢" if dr.action == "BUY" else ("🔴" if dr.action == "SELL" else "🟡")
            print(
                f"| {code} | {report.fund_name[:10]}... | "
                f"{emoji}{dr.recommendation} | {dr.total_score:.1f}/100 | {dr.risk_level} |"
            )
    
    # 询问是否详细查看某只基金的报告
    view_detail = input("\n🔍 是否查看某只基金的详细报告？(输入基金代码或按回车跳过): ").strip()
    if view_detail in results:
        print(results[view_detail].to_markdown())
    
    return results


def save_report(report: AnalysisReport, output_dir: str = "output"):
    """
    保存分析报告到文件
    
    Args:
        report: 分析报告对象
        output_dir: 输出目录
    """
    try:
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"{report.fund_code}_{timestamp}"
        
        # 保存Markdown版本
        md_path = os.path.join(output_dir, f"{base_filename}.md")
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(report.to_markdown())
        print(f"✅ Markdown报告已保存: {md_path}")
        
        # 保存JSON版本
        json_path = os.path.join(output_dir, f"{base_filename}.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            f.write(report.to_json())
        print(f"✅ JSON数据已保存: {json_path}")
        
    except Exception as e:
        print(f"❌ 保存失败: {str(e)}")


def show_sample_funds():
    """显示示例基金列表"""
    print("\n" + "━"*50)
    print("📝 示例基金列表")
    print("━"*50 + "\n")
    
    fund_descriptions = {
        "110011": "易方达中小盘混合",
        "000001": "华夏成长混合",
        "161725": "招商中证白酒指数",
        "005827": "易方达蓝筹精选混合",
        "000961": "天弘沪深300ETF联接",
    }
    
    print("| 代码 | 基金名称 |")
    print("|------|----------|")
    for code, name in fund_descriptions.items():
        print(f"| {code} | {name} |")
    
    print("\n💡 提示: 可以直接输入上述代码进行快速测试")


def check_system_status(agent: FundAnalysisAgent):
    """检查系统状态"""
    print("\n" + "━"*50)
    print("🔧 系统状态检查")
    print("━"*50 + "\n")
    
    status = agent.get_agent_status()
    
    print(f"Agent类型: {status['agent_type']}")
    print(f"\n已加载模块:")
    for module in status['modules_loaded']:
        print(f"  ✅ {module}")
    
    print(f"\nLLM模式: {'启用' if status['llm_enabled'] else '规则引擎'}")
    print(f"历史任务数: {status['tasks_executed']}")
    print(f"成功率: {status['success_rate']:.1f}%")
    
    # 测试数据获取能力
    print("\n📡 数据源连通性测试:")
    test_code = SAMPLE_FUND_CODES[0]
    print(f"  正在测试获取基金 {test_code} 的基本信息...")
    
    try:
        from agent.tools.data_fetcher import FundDataFetcher
        fetcher = FundDataFetcher()
        info = fetcher.get_fund_info(test_code)
        print(f"  ✅ AkShare数据源正常 (基金: {info.get('fund_name', 'N/A')})")
    except Exception as e:
        print(f"  ❌ AkShare数据源异常: {str(e)}")
    
    print("\n✅ 系统状态检查完成")


def interactive_mode():
    """交互式运行模式"""
    print_banner()
    
    # 初始化Agent
    print("\n🔄 正在初始化AI分析引擎...")
    agent = FundAnalysisAgent(use_llm=False)  # 默认使用规则引擎
    print("✅ 初始化完成！\n")
    
    while True:
        print_menu()
        
        choice = input("请输入选项编号: ").strip()
        
        if choice == '1':
            # 单只基金分析
            print("\n请输入要分析的基金代码（6位数字）")
            print("提示: 输入 'list' 查看示例基金列表")
            
            fund_input = input("基金代码: ").strip()
            
            if fund_input.lower() == 'list':
                show_sample_funds()
                continue
            
            if fund_input and len(fund_input) == 6 and fund_input.isdigit():
                analyze_single_fund(agent, fund_input)
            else:
                print("❌ 无效的基金代码，请重新输入")
        
        elif choice == '2':
            # 批量分析
            batch_analysis(agent)
        
        elif choice == '3':
            # 显示示例基金
            show_sample_funds()
        
        elif choice == '4':
            # 系统状态
            check_system_status(agent)
        
        elif choice == '0':
            # 退出
            print("\n感谢使用基金智能分析决策 Agent 系统！")
            print("投资有风险，入市需谨慎。祝您投资顺利！\n")
            break
        
        else:
            print("❌ 无效选项，请重新选择")
        
        # 暂停一下让用户看清输出
        input("\n按回车键继续...")


def single_command_mode(fund_code: str):
    """单命令行模式：直接分析指定基金"""
    print_banner()
    
    print(f"🎯 目标基金: {fund_code}\n")
    
    agent = FundAnalysisAgent(use_llm=False)
    analyze_single_fund(agent, fund_code)


def batch_command_mode():
    """批量分析命令行模式"""
    print_banner()
    
    agent = FundAnalysisAgent(use_llm=False)
    batch_analysis(agent)


def main():
    """主函数 - 解析命令行参数并启动相应模式"""
    parser = argparse.ArgumentParser(
        description="基金智能分析决策 Agent 系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python main.py                    # 启动交互模式
  python main.py --code 110011      # 分析基金110011
  python main.py --batch            # 批量分析示例基金
  python main.py --llm              # 使用LLM增强模式（需要API Key）
        """
    )
    
    parser.add_argument(
        '--code', '-c',
        type=str,
        help='指定要分析的基金代码（6位数字）'
    )
    
    parser.add_argument(
        '--batch', '-b',
        action='store_true',
        help='批量分析示例基金'
    )
    
    parser.add_argument(
        '--llm',
        action='store_true',
        help='启用LLM高级情感分析（需设置OPENAI_API_KEY环境变量）'
    )
    
    parser.add_argument(
        '--api-key',
        type=str,
        help='LLM API密钥（可选，也可通过环境变量OPENAI_API_KEY设置）'
    )
    
    args = parser.parse_args()
    
    # 根据参数选择运行模式
    if args.code:
        # 单基金直接分析模式
        single_command_mode(args.code)
    elif args.batch:
        # 批量分析模式
        batch_command_mode()
    else:
        # 默认进入交互模式
        interactive_mode()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断操作")
        print("感谢使用，再见！")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 程序运行出错: {str(e)}")
        sys.exit(1)
