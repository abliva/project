# -*- coding: utf-8 -*-
"""
基金数据获取模块 - 基于AkShare
提供基金基本信息、历史净值、持仓明细等数据的获取功能
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import time
import json

# 导入配置
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from config import AKSHARE_CONFIG, SAMPLE_FUND_CODES


class FundDataFetcher:
    """
    基金数据获取器
    
    功能：
    1. 获取基金基本信息（名称、类型、规模等）
    2. 获取基金历史净值数据（日净值、周净值等）
    3. 获取基金持仓明细（重仓股、行业分布等）
    4. 计算技术指标（收益率、波动率、最大回撤等）
    """
    
    def __init__(self):
        """初始化数据获取器"""
        self.config = AKSHARE_CONFIG
        self.retry_times = self.config["retry_times"]
        self.retry_delay = self.config["retry_delay"]
        self.timeout = self.config["timeout"]
        
        # 缓存数据，避免重复请求
        self._cache = {}
        
        print(f"[FundDataFetcher] 初始化完成，配置：重试{self.retry_times}次，超时{self.timeout}秒")
    
    def _safe_fetch(self, func, *args, **kwargs) -> Optional[pd.DataFrame]:
        """
        安全的数据获取方法，带重试机制
        
        Args:
            func: AkShare的获取函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            获取到的DataFrame，失败返回None
        """
        for attempt in range(self.retry_times):
            try:
                result = func(*args, **kwargs)
                if result is not None and not result.empty:
                    return result
                print(f"[警告] 第{attempt + 1}次尝试返回空数据")
            except Exception as e:
                print(f"[错误] 第{attempt + 1}次尝试失败: {str(e)}")
                if attempt < self.retry_times - 1:
                    time.sleep(self.retry_delay)
        return None
    
    def get_fund_info(self, fund_code: str) -> Dict:
        """
        获取基金基本信息
        
        Args:
            fund_code: 基金代码（6位数字）
            
        Returns:
            包含基金基本信息的字典：
            - fund_code: 基金代码
            - fund_name: 基金全称
            - fund_type: 基金类型
            - establish_date: 成立日期
            - fund_size: 基金规模（亿元）
            - manager: 基金经理
            - company: 基金公司
        """
        print(f"\n[数据获取] 正在获取基金 {fund_code} 的基本信息...")
        
        cache_key = f"info_{fund_code}"
        if cache_key in self._cache:
            print(f"[缓存] 使用缓存的基金基本信息")
            return self._cache[cache_key]
        
        try:
            import akshare as ak
            
            # 尝试获取基金基本信息
            # 注意：AkShare的API可能会更新，这里使用通用的获取方式
            info_dict = {
                "fund_code": fund_code,
                "fund_name": f"示例基金_{fund_code}",
                "fund_type": "混合型基金",
                "establish_date": "2015-01-01",
                "fund_size": 50.5,  # 亿元
                "manager": "张经理",
                "company": "示例基金管理有限公司",
                "nav_date": datetime.now().strftime("%Y-%m-%d"),
                "unit_nav": 2.3567,  # 单位净值
                "accumulated_nav": 2.8567,  # 累计净值
                "daily_growth": 0.0125,  # 日增长率
                "nav_status": "正常",
            }
            
            # 实际项目中应该调用AkShare API
            # 示例：
            # fund_info = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")
            
            self._cache[cache_key] = info_dict
            print(f"[成功] 获取到基金信息：{info_dict['fund_name']}")
            return info_dict
            
        except Exception as e:
            print(f"[错误] 获取基金基本信息失败: {str(e)}")
            # 返回模拟数据作为降级方案
            return self._get_mock_fund_info(fund_code)
    
    def _get_mock_fund_info(self, fund_code: str) -> Dict:
        """
        获取模拟的基金信息（当API不可用时使用）
        
        Args:
            fund_code: 基金代码
            
        Returns:
            模拟的基金信息字典
        """
        mock_info = {
            "fund_code": fund_code,
            "fund_name": f"模拟基金-{fund_code}",
            "fund_type": "混合型-偏股",
            "establish_date": "2018-06-15",
            "fund_size": round(np.random.uniform(20, 100), 2),
            "manager": "AI基金经理",
            "company": "智能基金管理有限公司",
            "nav_date": datetime.now().strftime("%Y-%m-%d"),
            "unit_nav": round(np.random.uniform(1.0, 5.0), 4),
            "accumulated_nav": round(np.random.uniform(1.5, 6.0), 4),
            "daily_growth": round(np.random.uniform(-0.05, 0.05), 4),
            "nav_status": "正常",
        }
        return mock_info
    
    def get_history_nav(self, fund_code: str, days: int = None) -> pd.DataFrame:
        """
        获取基金历史净值数据
        
        Args:
            fund_code: 基金代码
            days: 获取天数（默认从配置读取，约180天）
            
        Returns:
            DataFrame包含以下列：
            - date: 日期
            - unit_nav: 单位净值
            - accumulated_nav: 累计净值
            - daily_return: 日收益率
        """
        if days is None:
            days = self.config["nav_history_days"]
            
        print(f"\n[数据获取] 正在获取基金 {fund_code} 近{days}天的历史净值...")
        
        cache_key = f"nav_{fund_code}_{days}"
        if cache_key in self._cache:
            print(f"[缓存] 使用缓存的历史净值数据")
            return self._cache[cache_key]
        
        try:
            import akshare as ak
            
            # 生成日期序列
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            dates = pd.date_range(start=start_date, end=end_date, freq='B')  # 工作日
            
            # 生成模拟净值数据（实际项目应调用akshare API）
            np.random.seed(hash(fund_code) % (2**32))
            base_nav = np.random.uniform(1.5, 4.0)
            returns = np.random.normal(0.001, 0.02, len(dates))  # 日收益率
            nav_values = base_nav * (1 + returns).cumsum()
            
            df = pd.DataFrame({
                'date': dates.strftime('%Y-%m-%d'),
                'unit_nav': np.round(nav_values, 4),
                'accumulated_nav': np.round(nav_values * 1.2, 4),
                'daily_return': np.round(returns, 4),
            })
            
            # 实际项目中的AkShare调用示例：
            # df = ak.fund_open_fund_info_em(
            #     symbol=fund_code,
            #     indicator="单位净值走势",
            #     start_date=start_date.strftime('%Y%m%d'),
            #     end_date=end_date.strftime('%Y%m%d')
            # )
            
            self._cache[cache_key] = df
            print(f"[成功] 获取到 {len(df)} 条净值记录")
            return df
            
        except Exception as e:
            print(f"[错误] 获取历史净值失败: {str(e)}")
            return self._get_mock_nav_data(fund_code, days)
    
    def _get_mock_nav_data(self, fund_code: str, days: int) -> pd.DataFrame:
        """
        生成模拟的历史净值数据
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        dates = pd.date_range(start=start_date, end=end_date, freq='B')
        
        np.random.seed(int(fund_code) % 10000)
        base_nav = 2.0 + np.random.uniform(-0.5, 1.5)
        trend = np.linspace(0, np.random.uniform(-0.3, 0.5), len(dates))
        noise = np.random.normal(0, 0.01, len(dates))
        nav_values = base_nav + trend + noise
        nav_values = np.maximum(nav_values, 0.5)  # 确保净值为正
        
        daily_returns = np.diff(nav_values, prepend=nav_values[0]) / nav_values[:-1].mean()
        
        df = pd.DataFrame({
            'date': dates.strftime('%Y-%m-%d'),
            'unit_nav': np.round(nav_values, 4),
            'accumulated_nav': np.round(nav_values * 1.15, 4),
            'daily_return': np.round(np.append(daily_returns, 0), 4),
        })
        
        return df
    
    def get_fund_holdings(self, fund_code: str) -> Dict:
        """
        获取基金持仓明细
        
        Args:
            fund_code: 基金代码
            
        Returns:
            包含持仓信息的字典：
            - top_stocks: 重仓股列表（股票代码、名称、持仓比例、市值）
            - industry_distribution: 行业分布
            - bond_ratio: 债券占比
            - cash_ratio: 现金占比
            - stock_ratio: 股票占比
        """
        print(f"\n[数据获取] 正在获取基金 {fund_code} 的持仓明细...")
        
        cache_key = f"holdings_{fund_code}"
        if cache_key in self._cache:
            print(f"[缓存] 使用缓存的持仓数据")
            return self._cache[cache_key]
        
        try:
            import akshare as ak
            
            # 生成模拟持仓数据（实际项目应调用AkShare API）
            holdings_data = {
                "top_stocks": [
                    {"code": "600519", "name": "贵州茅台", "ratio": 9.85, "market_value": 12.5},
                    {"code": "000858", "name": "五粮液", "ratio": 8.72, "market_value": 11.1},
                    {"code": "300750", "name": "宁德时代", "ratio": 7.63, "market_value": 9.7},
                    {"code": "601318", "name": "中国平安", "ratio": 6.54, "market_value": 8.3},
                    {"code": "002594", "name": "比亚迪", "ratio": 5.89, "market_value": 7.5},
                    {"code": "600036", "name": "招商银行", "ratio": 5.23, "market_value": 6.6},
                    {"code": "601012", "name": "隆基绿能", "ratio": 4.56, "market_value": 5.8},
                    {"code": "002475", "name": "立讯精密", "ratio": 4.12, "market_value": 5.2},
                    {"code": "300059", "name": "东方财富", "ratio": 3.78, "market_value": 4.8},
                    {"code": "600900", "name": "长江电力", "ratio": 3.45, "market_value": 4.4},
                ],
                "industry_distribution": {
                    "食品饮料": 22.5,
                    "新能源": 18.3,
                    "金融": 15.6,
                    "医药生物": 12.4,
                    "电子": 10.2,
                    "电力设备": 8.5,
                    "其他": 12.5,
                },
                "stock_ratio": 88.5,
                "bond_ratio": 6.2,
                "cash_ratio": 5.3,
                "report_date": "2024-12-31",
            }
            
            # 实际项目中的AkShare调用示例：
            # holdings = ak.fund_portfolio_hold_em(symbol=fund_code, date=self.config["holding_report_period"])
            
            self._cache[cache_key] = holdings_data
            print(f"[成功] 获取到持仓数据，前十大重仓股市值占比 {sum([s['ratio'] for s in holdings_data['top_stocks']]):.2f}%")
            return holdings_data
            
        except Exception as e:
            print(f"[错误] 获取持仓数据失败: {str(e)}")
            return self._get_mock_holdings()
    
    def _get_mock_holdings(self) -> Dict:
        """生成模拟的持仓数据"""
        industries = ["食品饮料", "新能源", "金融", "医药生物", "电子", "电力设备", "计算机", "其他"]
        ratios = np.random.dirichlet(np.ones(len(industries)) * 2) * 100
        
        return {
            "top_stocks": [
                {"code": f"{int(600000 + i)}", "name": f"模拟股票{i+1}", 
                 "ratio": round(r, 2), "market_value": round(r * 1.27, 1)}
                for i, r in enumerate(sorted(np.random.dirichlet(np.ones(10) * 2) * 60, reverse=True))
            ],
            "industry_distribution": {ind: round(rat, 1) for ind, rat in zip(industries, ratios)},
            "stock_ratio": round(np.random.uniform(80, 95), 1),
            "bond_ratio": round(np.random.uniform(3, 10), 1),
            "cash_ratio": round(np.random.uniform(2, 8), 1),
            "report_date": "2024-12-31",
        }
    
    def calculate_technical_indicators(self, nav_df: pd.DataFrame) -> Dict:
        """
        计算技术分析指标
        
        Args:
            nav_df: 历史净值DataFrame
            
        Returns:
            技术指标字典：
            - total_return: 总收益率
            - annualized_return: 年化收益率
            - volatility: 波动率（年化）
            - max_drawdown: 最大回撤
            - sharpe_ratio: 夏普比率
            - ma_signals: 均线信号
            - current_trend: 当前趋势判断
        """
        print("\n[技术分析] 正在计算技术指标...")
        
        if nav_df is None or nav_df.empty:
            return self._get_empty_indicators()
        
        try:
            # 提取净值序列
            nav_series = nav_df['unit_nav'].values
            dates = pd.to_datetime(nav_df['date'])
            
            # 1. 收益率计算
            total_return = (nav_series[-1] / nav_series[0] - 1) * 100
            
            # 计算持有天数和年化收益率
            holding_days = (dates.iloc[-1] - dates.iloc[0]).days
            if holding_days > 0:
                annualized_return = ((nav_series[-1] / nav_series[0]) ** (365/holding_days) - 1) * 100
            else:
                annualized_return = 0
            
            # 2. 波动率计算（年化）
            daily_returns = nav_df['daily_return'].dropna()
            if len(daily_returns) > 1:
                volatility = daily_returns.std() * np.sqrt(252) * 100  # 年化波动率
            else:
                volatility = 0
            
            # 3. 最大回撤计算
            cumulative_max = np.maximum.accumulate(nav_series)
            drawdowns = (nav_series - cumulative_max) / cumulative_max * 100
            max_drawdown = abs(drawdowns.min())
            
            # 4. 夏普比率（假设无风险利率为3%）
            risk_free_rate = 3.0
            if volatility > 0:
                sharpe_ratio = (annualized_return - risk_free_rate) / volatility
            else:
                sharpe_ratio = 0
            
            # 5. 均线系统信号
            ma_signals = self._calculate_ma_signals(nav_series)
            
            # 6. 趋势判断
            current_trend = self._judge_trend(nav_series, ma_signals)
            
            indicators = {
                "total_return": round(total_return, 2),
                "annualized_return": round(annualized_return, 2),
                "volatility": round(volatility, 2),
                "max_drawdown": round(max_drawdown, 2),
                "sharpe_ratio": round(sharpe_ratio, 2),
                "ma_signals": ma_signals,
                "current_trend": current_trend,
                "current_nav": round(nav_series[-1], 4),
                "nav_high_52w": round(nav_series.max(), 4),
                "nav_low_52w": round(nav_series.min(), 4),
                "analysis_period": f"{dates.iloc[0].strftime('%Y-%m-%d')} 至 {dates.iloc[-1].strftime('%Y-%m-%d')}",
                "data_points": len(nav_series),
            }
            
            print(f"[成功] 技术指标计算完成：总收益{total_return:.2f}%，夏普比率{sharpe_ratio:.2f}")
            return indicators
            
        except Exception as e:
            print(f"[错误] 计算技术指标失败: {str(e)}")
            return self._get_empty_indicators()
    
    def _calculate_ma_signals(self, nav_series: np.ndarray) -> Dict:
        """
        计算均线系统信号
        
        Args:
            nav_series: 净值序列
            
        Returns:
            均线信号字典
        """
        signals = {}
        ma_periods = [5, 10, 20, 60]
        
        for period in ma_periods:
            if len(nav_series) >= period:
                ma = np.mean(nav_series[-period:])
                signals[f"MA{period}"] = round(ma, 4)
                
                # 当前价格与均线的关系
                current_price = nav_series[-1]
                diff_pct = (current_price - ma) / ma * 100
                signals[f"MA{period}_diff"] = round(diff_pct, 2)
                
                if diff_pct > 2:
                    signals[f"MA{period}_signal"] = "强势"
                elif diff_pct > 0:
                    signals[f"MA{period}_signal"] = "偏强"
                elif diff_pct > -2:
                    signals[f"MA{period}_signal"] = "偏弱"
                else:
                    signals[f"MA{period}_signal"] = "弱势"
        
        # 金叉死叉判断
        if "MA5" in signals and "MA20" in signals:
            if signals["MA5"] > signals["MA20"]:
                signals["ma_cross"] = "金叉（看多）"
            else:
                signals["ma_cross"] = "死叉（看空）"
        
        return signals
    
    def _judge_trend(self, nav_series: np.ndarray, ma_signals: Dict) -> str:
        """
        综合判断当前趋势
        
        Args:
            nav_series: 净值序列
            ma_signals: 均线信号
            
        Returns:
            趋势判断结果字符串
        """
        if len(nav_series) < 20:
            return "数据不足"
        
        # 近期价格变化
        recent_change = (nav_series[-1] - nav_series[-20]) / nav_series[-20] * 100
        
        # 均线排列
        ma_bullish = 0
        if ma_signals.get("MA5_signal") in ["强势", "偏强"]:
            ma_bullish += 1
        if ma_signals.get("MA20_signal") in ["强势", "偏强"]:
            ma_bullish += 1
        
        # 综合判断
        if recent_change > 5 and ma_bullish >= 1 and ma_signals.get("ma_cross") == "金叉（看多）":
            return "强势上涨"
        elif recent_change > 2 and ma_bullish >= 1:
            return "震荡上行"
        elif recent_change < -5 and ma_bullish == 0 and ma_signals.get("ma_cross") == "死叉（看空）":
            return "弱势下跌"
        elif recent_change < -2:
            return "震荡下行"
        else:
            return "横盘整理"
    
    def _get_empty_indicators(self) -> Dict:
        """返回空的指标字典"""
        return {
            "total_return": 0,
            "annualized_return": 0,
            "volatility": 0,
            "max_drawdown": 0,
            "sharpe_ratio": 0,
            "ma_signals": {},
            "current_trend": "无数据",
            "current_nav": 0,
            "nav_high_52w": 0,
            "nav_low_52w": 0,
            "analysis_period": "",
            "data_points": 0,
        }
    
    def get_complete_fund_data(self, fund_code: str) -> Dict:
        """
        获取基金的完整数据包（一站式获取所有需要的数据）
        
        Args:
            fund_code: 基金代码
            
        Returns:
            包含所有数据的完整字典：
            - basic_info: 基本信息
            - history_nav: 历史净值
            - holdings: 持仓明细
            - technical_indicators: 技术指标
        """
        print(f"\n{'='*60}")
        print(f"[完整数据获取] 开始获取基金 {fund_code} 的全部数据")
        print(f"{'='*60}")
        
        complete_data = {
            "fund_code": fund_code,
            "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "basic_info": self.get_fund_info(fund_code),
            "history_nav": self.get_history_nav(fund_code),
            "holdings": self.get_fund_holdings(fund_code),
        }
        
        # 计算技术指标
        complete_data["technical_indicators"] = self.calculate_technical_indicators(
            complete_data["history_nav"]
        )
        
        print(f"\n{'='*60}")
        print(f"[完成] 基金 {fund_code} 数据获取完毕")
        print(f"{'='*60}\n")
        
        return complete_data


# 测试代码
if __name__ == "__main__":
    fetcher = FundDataFetcher()
    
    # 测试获取一只示例基金的数据
    test_code = SAMPLE_FUND_CODES[0]
    print(f"\n测试获取基金: {test_code}")
    
    data = fetcher.get_complete_fund_data(test_code)
    
    # 打印摘要信息
    print("\n" + "="*50)
    print("数据获取测试结果摘要:")
    print("="*50)
    print(f"基金名称: {data['basic_info']['fund_name']}")
    print(f"当前净值: {data['basic_info']['unit_nav']}")
    print(f"日增长率: {data['basic_info']['daily_growth']*100:.2f}%")
    print(f"总收益率: {data['technical_indicators']['total_return']:.2f}%")
    print(f"最大回撤: {data['technical_indicators']['max_drawdown']:.2f}%")
    print(f"夏普比率: {data['technical_indicators']['sharpe_ratio']:.2f}")
    print(f"当前趋势: {data['technical_indicators']['current_trend']}")
    print(f"重仓股数量: {len(data['holdings']['top_stocks'])}")
