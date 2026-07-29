# -*- coding: utf-8 -*-
"""
多因子决策引擎
综合技术面、舆情面、基本面等多维度因子，输出投资建议

核心功能：
1. 多因子评分体系（技术面35% + 舆情面35% + 基本面20% + 市场环境10%）
2. 风险调整与仓位建议
3. 买入/持有/卖出信号生成
4. 建议价格区间计算
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

# 导入配置
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import DECISION_CONFIG


@dataclass
class FactorScore:
    """单因子得分"""
    name: str                           # 因子名称
    score: float                        # 得分 (0-100)
    weight: float                       # 权重
    weighted_score: float = 0           # 加权得分
    details: Dict = field(default_factory=dict)  # 详细信息
    
    def __post_init__(self):
        self.weighted_score = self.score * self.weight


@dataclass
class DecisionResult:
    """
    决策结果数据类
    
    包含完整的投资建议和风险提示
    """
    # 基本信息
    fund_code: str                      # 基金代码
    fund_name: str                      # 基金名称
    analysis_time: str                  # 分析时间
    
    # 综合评分
    total_score: float                  # 综合得分 (0-100)
    confidence_level: float             # 置信度 (0-1)
    
    # 各因子得分
    technical_score: FactorScore        # 技术面因子
    sentiment_score: FactorScore        # 舆情面因子
    fundamental_score: FactorScore      # 基本面因子
    market_score: FactorScore           # 市场环境因子
    
    # 投资建议
    recommendation: str                 # 建议：强烈买入/买入/持有/减持/卖出
    action: str                         # 操作：BUY/HOLD/SELL
    position_suggestion: float          # 建议仓位比例 (0-1)
    target_price_range: Tuple[float, float]  # 目标净值区间
    stop_loss_price: float              # 止损价位
    take_profit_price: float            # 止盈价位
    
    # 风险评估
    risk_level: str                     # 风险等级：低/中/高/极高
    risk_factors: List[str]             # 主要风险因素
    volatility_adjustment: float        # 波动率调整系数
    
    # 详细分析
    key_findings: List[str]             # 关键发现
    reasoning: str                      # 决策推理过程
    summary: str                       # 一句话总结
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "fund_code": self.fund_code,
            "fund_name": self.fund_name,
            "analysis_time": self.analysis_time,
            "total_score": round(self.total_score, 2),
            "confidence_level": round(self.confidence_level, 2),
            "technical_score": {
                "name": self.technical_score.name,
                "score": self.technical_score.score,
                "weight": self.technical_score.weight,
                "weighted_score": round(self.technical_score.weighted_score, 2),
                "details": self.technical_score.details,
            },
            "sentiment_score": {
                "name": self.sentiment_score.name,
                "score": self.sentiment_score.score,
                "weight": self.sentiment_score.weight,
                "weighted_score": round(self.sentiment_score.weighted_score, 2),
                "details": self.sentiment_score.details,
            },
            "fundamental_score": {
                "name": self.fundamental_score.name,
                "score": self.fundamental_score.score,
                "weight": self.fundamental_score.weight,
                "weighted_score": round(self.fundamental_score.weighted_score, 2),
                "details": self.fundamental_score.details,
            },
            "market_score": {
                "name": self.market_score.name,
                "score": self.market_score.score,
                "weight": self.market_score.weight,
                "weighted_score": round(self.market_score.weighted_score, 2),
                "details": self.market_score.details,
            },
            "recommendation": self.recommendation,
            "action": self.action,
            "position_suggestion": self.position_suggestion,
            "target_price_range": self.target_price_range,
            "stop_loss_price": self.stop_loss_price,
            "take_profit_price": self.take_profit_price,
            "risk_level": self.risk_level,
            "risk_factors": self.risk_factors,
            "volatility_adjustment": self.volatility_adjustment,
            "key_findings": self.key_findings,
            "reasoning": self.reasoning,
            "summary": self.summary,
        }


class DecisionEngine:
    """
    多因子决策引擎
    
    整合多个维度的分析结果，通过加权模型输出最终的投资决策建议。
    
    因子权重配置：
    - 技术面因子 (35%)：基于净值走势的技术指标
    - 舆情面因子 (35%)：基于新闻情感分析的舆情指数
    - 基本面因子 (20%)：基金基本面数据（规模、持仓等）
    - 市场环境 (10%)：整体市场环境评估
    """
    
    def __init__(self):
        """初始化决策引擎"""
        self.config = DECISION_CONFIG
        self.factor_weights = self.config["factor_weights"]
        
        # 决策阈值
        self.buy_threshold = self.config["buy_threshold"]
        self.hold_threshold = self.config["hold_threshold"]
        self.sell_threshold = self.config["sell_threshold"]
        
        # 风控参数
        self.max_position = self.config["max_position_ratio"]
        self.min_confidence = self.config["min_confidence"]
        self.volatility_penalty = self.config["volatility_penalty"]
        
        print(f"[DecisionEngine] 决策引擎初始化完成")
        print(f"  因子权重：技术{self.factor_weights['technical']*100}% | "
              f"舆情{self.factor_weights['sentiment']*100}% | "
              f"基本{self.factor_weights['fundamental']*100}% | "
              f"市场{self.factor_weights['market']*100}%")
    
    def make_decision(self, fund_data: Dict, sentiment_data: Dict) -> DecisionResult:
        """
        执行完整的多因子决策流程
        
        Args:
            fund_data: 基金完整数据（来自DataFetcher）
            sentiment_data: 舆情情感数据（来自SentimentAnalyzer）
            
        Returns:
            完整的决策结果对象
        """
        print("\n" + "="*70)
        print("[DecisionEngine] 开始执行多因子决策分析...")
        print("="*70)
        
        # 1. 计算各因子得分
        technical = self._calculate_technical_factor(fund_data)
        sentiment = self._calculate_sentiment_factor(sentiment_data)
        fundamental = self._calculate_fundamental_factor(fund_data)
        market = self._calculate_market_factor(fund_data, sentiment_data)
        
        # 2. 加权综合得分
        total_score = (
            technical.weighted_score +
            sentiment.weighted_score +
            fundamental.weighted_score +
            market.weighted_score
        )
        
        print(f"\n[得分汇总]")
        print(f"  技术面: {technical.score:.1f}分 (×{technical.weight}) = {technical.weighted_score:.2f}")
        print(f"  舆情面: {sentiment.score:.1f}分 (×{sentiment.weight}) = {sentiment.weighted_score:.2f}")
        print(f"  基本面: {fundamental.score:.1f}分 (×{fundamental.weight}) = {fundamental.weighted_score:.2f}")
        print(f"  市场面: {market.score:.1f}分 (×{market.weight}) = {market.weighted_score:.2f}")
        print(f"  {'-'*50}")
        print(f"  综合得分: {total_score:.2f}")
        
        # 3. 波动率调整
        volatility_adj = self._adjust_for_volatility(total_score, fund_data)
        adjusted_score = total_score * volatility_adj
        
        print(f"\n[风险调整]")
        print(f"  波动率调整系数: {volatility_adj:.3f}")
        print(f"  调整后综合得分: {adjusted_score:.2f}")
        
        # 4. 生成投资建议
        recommendation, action = self._generate_recommendation(adjusted_score)
        
        # 5. 计算目标价位
        target_range, stop_loss, take_profit = self._calculate_price_targets(
            fund_data, adjusted_score, volatility_adj
        )
        
        # 6. 评估风险等级
        risk_level, risk_factors = self._assess_risk(fund_data, sentiment_data, adjusted_score)
        
        # 7. 置信度计算
        confidence = self._calculate_confidence(technical, sentiment, fundamental, market)
        
        # 8. 仓位建议
        position = self._suggest_position(adjusted_score, confidence, risk_level)
        
        # 9. 生成关键发现和推理
        key_findings = self._generate_key_findings(
            technical, sentiment, fundamental, market, fund_data, sentiment_data
        )
        reasoning = self._build_reasoning(technical, sentiment, fundamental, market, adjusted_score)
        summary = self._generate_summary(recommendation, adjusted_score, fund_data)
        
        # 构建最终结果
        result = DecisionResult(
            fund_code=fund_data.get("fund_code", ""),
            fund_name=fund_data.get("basic_info", {}).get("fund_name", "未知"),
            analysis_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            total_score=round(adjusted_score, 2),
            confidence_level=confidence,
            technical_score=technical,
            sentiment_score=sentiment,
            fundamental_score=fundamental,
            market_score=market,
            recommendation=recommendation,
            action=action,
            position_suggestion=position,
            target_price_range=target_range,
            stop_loss_price=stop_loss,
            take_profit_price=take_profit,
            risk_level=risk_level,
            risk_factors=risk_factors,
            volatility_adjustment=volatility_adj,
            key_findings=key_findings,
            reasoning=reasoning,
            summary=summary,
        )
        
        print("\n" + "="*70)
        print(f"[决策完成] {result.fund_name} ({result.fund_code})")
        print(f"  建议: {result.recommendation}")
        print(f"  综合得分: {result.total_score}/100")
        print(f"  风险等级: {result.risk_level}")
        print(f"  建议仓位: {result.position_suggestion*100:.1f}%")
        print("="*70 + "\n")
        
        return result
    
    def _calculate_technical_factor(self, fund_data: Dict) -> FactorScore:
        """
        计算技术面因子得分 (0-100)
        
        评估维度：
        - 收益率表现（30%）
        - 风险调整后收益（25%）
        - 趋势强度（25%）
        - 均线系统信号（20%）
        """
        indicators = fund_data.get("technical_indicators", {})
        weight = self.factor_weights["technical"]
        
        details = {}
        sub_scores = []
        
        # 1. 收益率得分 (0-30分)
        total_return = indicators.get("total_return", 0)
        annualized_return = indicators.get("annualized_return", 0)
        
        if annualized_return >= 20:
            return_score = 30
        elif annualized_return >= 10:
            return_score = 25
        elif annualized_return >= 5:
            return_score = 20
        elif annualized_return >= 0:
            return_score = 15
        elif annualized_return >= -5:
            return_score = 10
        else:
            return_score = 5
        
        sub_scores.append(return_score)
        details["收益率得分"] = f"{return_score}/30 (年化收益:{annualized_return:.2f}%)"
        
        # 2. 夏普比率得分 (0-25分)
        sharpe = indicators.get("sharpe_ratio", 0)
        if sharpe >= 2:
            sharpe_score = 25
        elif sharpe >= 1.5:
            sharpe_score = 22
        elif sharpe >= 1:
            sharpe_score = 18
        elif sharpe >= 0.5:
            sharpe_score = 14
        elif sharpe >= 0:
            sharpe_score = 10
        else:
            sharpe_score = 5
        
        sub_scores.append(sharpe_score)
        details["夏普比率得分"] = f"{sharpe_score}/25 (Sharpe:{sharpe:.2f})"
        
        # 3. 趋势强度得分 (0-25分)
        trend = indicators.get("current_trend", "")
        trend_scores = {
            "强势上涨": 25,
            "震荡上行": 20,
            "横盘整理": 15,
            "震荡下行": 10,
            "弱势下跌": 5,
            "无数据": 12,
            "数据不足": 12,
        }
        trend_score = trend_scores.get(trend, 12)
        sub_scores.append(trend_score)
        details["趋势得分"] = f"{trend_score}/25 ({trend})"
        
        # 4. 均线系统得分 (0-20分)
        ma_signals = indicators.get("ma_signals", {})
        ma_cross = ma_signals.get("ma_cross", "")
        ma_bullish_count = sum(
            1 for k in ["MA5_signal", "MA20_signal"] 
            if ma_signals.get(k) in ["强势", "偏强"]
        )
        
        if "金叉" in ma_cross and ma_bullish_count >= 2:
            ma_score = 20
        elif "金叉" in ma_cross or ma_bullish_count >= 1:
            ma_score = 16
        elif ma_bullish_count == 0 and "死叉" not in ma_cross:
            ma_score = 13
        else:
            ma_score = 8
        
        sub_scores.append(ma_score)
        details["均线系统得分"] = f"{ma_score}/20 ({ma_cross})"
        
        # 总分
        total_technical_score = sum(sub_scores)
        
        return FactorScore(
            name="技术面",
            score=float(total_technical_score),
            weight=weight,
            details=details,
        )
    
    def _calculate_sentiment_factor(self, sentiment_data: Dict) -> FactorScore:
        """
        计算舆情面因子得分 (0-100)
        
        评估维度：
        - 情感得分转化（40%）
        - 利好消息占比（30%）
        - 趋势变化方向（30%）
        """
        weight = self.factor_weights["sentiment"]
        details = {}
        sub_scores = []
        
        # 1. 情感得分转化 (0-40分)
        overall_score = sentiment_data.get("overall_score", 0)
        
        # 将情感得分(-5到5)映射到0-40分
        if overall_score >= 3:
            sentiment_base = 40
        elif overall_score >= 1.5:
            sentiment_base = 34
        elif overall_score >= 0.5:
            sentiment_base = 28
        elif overall_score > -0.5:
            sentiment_base = 22
        elif overall_score > -1.5:
            sentiment_base = 16
        elif overall_score > -3:
            sentiment_base = 10
        else:
            sentiment_base = 4
        
        sub_scores.append(sentiment_base)
        details["情感得分"] = f"{sentiment_base}/40 (原始分:{overall_score:+.2f})"
        
        # 2. 利好消息占比 (0-30分)
        positive_ratio = sentiment_data.get("positive_ratio", 50)
        positive_score = min(positive_ratio / 100 * 30, 30)
        sub_scores.append(positive_score)
        details["利好消息占比"] = f"{positive_score:.1f}/30 ({positive_ratio:.1f}%)"
        
        # 3. 趋势变化 (0-30分)
        latest_trend = sentiment_data.get("latest_trend", "平稳")
        trend_map = {
            "转好": 28,
            "平稳": 22,
            "转差": 12,
            "数据不足": 18,
            "未知": 18,
        }
        trend_score = trend_map.get(latest_trend, 18)
        sub_scores.append(trend_score)
        details["舆情趋势"] = f"{trend_score}/30 ({latest_trend})"
        
        total_sentiment_score = sum(sub_scores)
        
        return FactorScore(
            name="舆情面",
            score=float(total_sentiment_score),
            weight=weight,
            details=details,
        )
    
    def _calculate_fundamental_factor(self, fund_data: Dict) -> FactorScore:
        """
        计算基本面因子得分 (0-100)
        
        评估维度：
        - 基金规模与流动性（30%）
        - 持仓结构合理性（35%）
        - 历史业绩稳定性（35%）
        """
        weight = self.factor_weights["fundamental"]
        basic_info = fund_data.get("basic_info", {})
        holdings = fund_data.get("holdings", {})
        indicators = fund_data.get("technical_indicators", {})
        
        details = {}
        sub_scores = []
        
        # 1. 基金规模得分 (0-30分)
        fund_size = basic_info.get("fund_size", 50)
        if 20 <= fund_size <= 80:  # 中等规模最佳
            size_score = 28
        elif 10 <= fund_size < 20 or 80 < fund_size <= 150:
            size_score = 24
        elif fund_size < 10 or fund_size > 150:
            size_score = 18
        else:
            size_score = 22
        
        sub_scores.append(size_score)
        details["规模评分"] = f"{size_score}/30 (规模:{fund_size}亿)"
        
        # 2. 持仓结构得分 (0-35分)
        stock_ratio = holdings.get("stock_ratio", 85)
        cash_ratio = holdings.get("cash_ratio", 5)
        top10_concentration = sum([s.get("ratio", 0) for s in holdings.get("top_stocks", [])])
        
        # 检查集中度（前十大持仓占比40-60%较为合理）
        if 40 <= top10_concentration <= 60:
            concentration_score = 15
        elif 30 <= top10_concentration < 40 or 60 < top10_concentration <= 70:
            concentration_score = 12
        else:
            concentration_score = 8
        
        # 现金比例适中加分
        cash_score = 10 if 3 <= cash_ratio <= 10 else 6
        
        holding_score = concentration_score + cash_score + 10  # 基础分
        sub_scores.append(holding_score)
        details["持仓结构"] = f"{holding_score}/35 (股票:{stock_ratio}% | 现金:{cash_ratio}% | 集中度:{top10_concentration:.1f}%)"
        
        # 3. 业绩稳定性得分 (0-35分)
        max_drawdown = indicators.get("max_drawdown", 15)
        volatility = indicators.get("volatility", 15)
        
        # 最大回撤越小越好
        if max_drawdown <= 10:
            dd_score = 18
        elif max_drawdown <= 20:
            dd_score = 14
        elif max_drawdown <= 30:
            dd_score = 10
        else:
            dd_score = 6
        
        # 波动率适中较好
        if 10 <= volatility <= 20:
            vol_score = 17
        elif volatility < 10 or volatility <= 25:
            vol_score = 14
        else:
            vol_score = 10
        
        stability_score = dd_score + vol_score
        sub_scores.append(stability_score)
        details["稳定性评分"] = f"{stability_score}/35 (最大回撤:{max_drawdown:.2f}% | 波动率:{volatility:.2f}%)"
        
        total_fundamental_score = sum(sub_scores)
        
        return FactorScore(
            name="基本面",
            score=float(total_fundamental_score),
            weight=weight,
            details=details,
        )
    
    def _calculate_market_factor(self, fund_data: Dict, sentiment_data: Dict) -> FactorScore:
        """
        计算市场环境因子得分 (0-100)
        
        评估维度：
        - 大盘整体情绪（40%）
        - 行业景气度（30%）
        - 政策环境（30%）
        """
        weight = self.factor_weights["market"]
        details = {}
        sub_scores = []
        
        # 这里使用简化的市场环境评估
        # 实际项目中可接入更多市场数据源
        
        # 1. 大盘情绪 (0-40分)
        overall_sentiment = sentiment_data.get("overall_score", 0)
        if overall_sentiment >= 2:
            market_sentiment = 36
        elif overall_sentiment >= 1:
            market_sentiment = 30
        elif overall_sentiment >= 0:
            market_sentiment = 24
        elif overall_sentiment >= -1:
            market_sentiment = 18
        else:
            market_sentiment = 12
        
        sub_scores.append(market_sentiment)
        details["大盘情绪"] = f"{market_sentiment}/40"
        
        # 2. 行业景气度 (0-30分) - 基于持仓行业分布简化判断
        holdings = fund_data.get("holdings", {})
        industry_dist = holdings.get("industry_distribution", {})
        
        # 假设新能源、医药等为当前热门行业
        hot_industries = ["新能源", "医药生物", "半导体", "人工智能"]
        industry_score = 0
        for ind, ratio in industry_dist.items():
            if any(hot in ind for hot in hot_industries):
                industry_score += ratio * 0.3
        
        industry_score = min(industry_score * 10, 30)
        sub_scores.append(industry_score)
        details["行业景气度"] = f"{industry_score:.1f}/30"
        
        # 3. 政策环境 (0-30分) - 简化为中性偏积极
        policy_score = 22  # 默认中等偏上
        sub_scores.append(policy_score)
        details["政策环境"] = f"{policy_score}/30 (当前假设为中性偏积极)"
        
        total_market_score = sum(sub_scores)
        
        return FactorScore(
            name="市场环境",
            score=float(total_market_score),
            weight=weight,
            details=details,
        )
    
    def _adjust_for_volatility(self, score: float, fund_data: Dict) -> float:
        """
        根据波动率调整得分
        
        高波动基金的得分会被适当降低以反映风险
        """
        indicators = fund_data.get("technical_indicators", {})
        volatility = indicators.get("volatility", 15)
        
        # 波动率越高，惩罚越大
        if volatility > 30:
            adjustment = 1 - self.volatility_penalty * 1.5
        elif volatility > 20:
            adjustment = 1 - self.volatility_penalty
        elif volatility > 15:
            adjustment = 1 - self.volatility_penalty * 0.5
        else:
            adjustment = 1.0
        
        return max(adjustment, 0.7)  # 最低不低于0.7
    
    def _generate_recommendation(self, score: float) -> Tuple[str, str]:
        """
        根据综合得分生成投资建议
        
        Returns:
            (建议文字, 操作代码)
        """
        if score >= 75:
            return ("强烈买入", "BUY")
        elif score >= self.buy_threshold:
            return ("买入", "BUY")
        elif score >= self.hold_threshold:
            return ("持有", "HOLD")
        elif score >= self.sell_threshold:
            return ("减持", "SELL")
        else:
            return ("卖出", "SELL")
    
    def _calculate_price_targets(self, fund_data: Dict, score: float, 
                                  volatility_adj: float) -> Tuple[Tuple[float, float], float, float]:
        """
        计算目标价位、止损位和止盈位
        """
        current_nav = fund_data.get("basic_info", {}).get("unit_nav", 2.0)
        indicators = fund_data.get("technical_indicators", {})
        volatility = indicators.get("volatility", 15)
        
        # 根据得分确定预期涨跌幅
        if score >= 70:
            expected_return = np.random.uniform(0.08, 0.15)  # 8%-15%
        elif score >= 55:
            expected_return = np.random.uniform(0.03, 0.08)   # 3%-8%
        elif score >= 45:
            expected_return = np.random.uniform(-0.02, 0.03)  # -2%~3%
        elif score >= 35:
            expected_return = np.random.uniform(-0.08, -0.02) # -8%~-2%
        else:
            expected_return = np.random.uniform(-0.15, -0.08) # -15%~-8%
        
        # 目标价位区间（考虑波动率）
        price_volatility = volatility / 100
        target_high = current_nav * (1 + expected_return + price_volatility * 0.5)
        target_low = current_nav * (1 + expected_return - price_volatility * 0.5)
        
        # 止损位（通常在下方5%-10%）
        stop_loss = current_nav * (1 - abs(expected_return) * 0.6 - 0.05)
        
        # 止盈位
        take_profit = current_nav * (1 + abs(expected_return) * 1.5 + 0.03)
        
        return (
            (round(target_low, 4), round(target_high, 4)),
            round(stop_loss, 4),
            round(take_profit, 4),
        )
    
    def _assess_risk(self, fund_data: Dict, sentiment_data: Dict, 
                     score: float) -> Tuple[str, List[str]]:
        """
        评估风险等级并识别主要风险因素
        """
        risk_factors = []
        risk_score = 0
        
        indicators = fund_data.get("technical_indicators", {})
        holdings = fund_data.get("holdings", {})
        
        # 1. 最大回撤风险
        max_dd = indicators.get("max_drawdown", 0)
        if max_dd > 25:
            risk_factors.append(f"历史最大回撤较大({max_dd:.1f}%)")
            risk_score += 2
        elif max_dd > 15:
            risk_factors.append(f"存在一定回撤风险({max_dd:.1f}%)")
            risk_score += 1
        
        # 2. 波动率风险
        volatility = indicators.get("volatility", 0)
        if volatility > 25:
            risk_factors.append(f"高波动性({volatility:.1f}%)")
            risk_score += 2
        elif volatility > 18:
            risk_factors.append(f"波动偏高({volatility:.1f}%)")
            risk_score += 1
        
        # 3. 集中度风险
        top10_ratio = sum([s.get("ratio", 0) for s in holdings.get("top_stocks", [])])
        if top10_ratio > 65:
            risk_factors.append(f"重仓股集中度过高({top10_ratio:.1f}%)")
            risk_score += 1
        
        # 4. 舆情风险
        neg_ratio = sentiment_data.get("negative_ratio", 0)
        if neg_ratio > 40:
            risk_factors.append(f"负面舆情占比较高({neg_ratio:.1f}%)")
            risk_score += 2
        elif neg_ratio > 25:
            risk_factors.append(f"存在一定负面舆论({neg_ratio:.1f}%)")
            risk_score += 1
        
        # 5. 规模风险
        fund_size = fund_data.get("basic_info", {}).get("fund_size", 50)
        if fund_size < 5:
            risk_factors.append("基金规模过小，存在清盘风险")
            risk_score += 2
        elif fund_size > 200:
            risk_factors.append("基金规模过大，调仓灵活性受限")
            risk_score += 1
        
        # 确定风险等级
        if risk_score >= 6:
            risk_level = "极高"
        elif risk_score >= 4:
            risk_level = "高"
        elif risk_score >= 2:
            risk_level = "中"
        else:
            risk_level = "低"
        
        if not risk_factors:
            risk_factors.append("暂未识别到显著风险因素")
        
        return (risk_level, risk_factors)
    
    def _calculate_confidence(self, technical: FactorScore, sentiment: FactorScore,
                               fundamental: FactorScore, market: FactorScore) -> float:
        """
        计算决策置信度
        
        基于各因子得分的一致性和数据质量
        """
        scores = [technical.score, sentiment.score, fundamental.score, market.score]
        
        # 计算得分离散度（标准差）
        mean_score = np.mean(scores)
        std_dev = np.std(scores)
        
        # 一致性越高，置信度越高
        consistency = 1 - min(std_dev / 30, 1)  # 归一化
        
        # 数据完整性检查（这里简化处理）
        data_quality = 0.9  # 假设数据质量较高
        
        confidence = consistency * 0.6 + data_quality * 0.4
        return round(max(min(confidence, 1.0), self.min_confidence), 2)
    
    def _suggest_position(self, score: float, confidence: float, 
                          risk_level: str) -> float:
        """
        建议仓位比例
        """
        base_position = 0.5  # 基准仓位50%
        
        # 根据得分调整
        if score >= 70:
            score_adj = 0.3
        elif score >= 55:
            score_adj = 0.15
        elif score >= 45:
            score_adj = 0
        elif score >= 35:
            score_adj = -0.15
        else:
            score_adj = -0.3
        
        # 根据置信度调整
        conf_adj = (confidence - 0.5) * 0.2
        
        # 根据风险等级调整
        risk_adj = {"低": 0.05, "中": 0, "高": -0.1, "极高": -0.2}.get(risk_level, 0)
        
        position = base_position + score_adj + conf_adj + risk_adj
        position = max(0, min(position, self.max_position))  # 限制范围
        
        return round(position, 2)
    
    def _generate_key_findings(self, technical: FactorScore, sentiment: FactorScore,
                                fundamental: FactorScore, market: FactorScore,
                                fund_data: Dict, sentiment_data: Dict) -> List[str]:
        """生成关键发现列表"""
        findings = []
        
        # 技术面关键点
        tech_details = technical.details
        if "趋势得分" in tech_details:
            findings.append(f"技术面显示{'上涨' if technical.score > 60 else '下跌或震荡'}趋势")
        
        # 舆情面关键点
        sent_label = sentiment_data.get("overall_label", "中性")
        findings.append(f"舆情整体倾向为'{sent_label}'")
        
        # 基本面关键点
        fund_size = fund_data.get("basic_info", {}).get("fund_size", 0)
        if fund_size > 100:
            findings.append(f"属于大规模基金({fund_size}亿)，运作相对稳健")
        elif fund_size < 20:
            findings.append(f"中小规模基金({fund_size}亿)，灵活性较强")
        
        # 综合判断
        if technical.score > 65 and sentiment.score > 65:
            findings.append("技术与舆情双重支撑，具备较好的投资价值")
        elif technical.score < 40 and sentiment.score < 40:
            findings.append("技术与舆情均不理想，建议谨慎对待")
        
        return findings[:5]  # 返回最多5条关键发现
    
    def _build_reasoning(self, technical: FactorScore, sentiment: FactorScore,
                          fundamental: FactorScore, market: FactorScore,
                          final_score: float) -> str:
        """构建决策推理说明"""
        parts = []
        
        # 各因子表现
        factor_descriptions = [
            (technical, "技术面"),
            (sentiment, "舆情面"),
            (fundamental, "基本面"),
            (market, "市场环境"),
        ]
        
        for factor, name in factor_descriptions:
            if factor.score >= 70:
                desc = f"{name}表现优秀({factor.score}分)"
            elif factor.score >= 55:
                desc = f"{name}表现良好({factor.score}分)"
            elif factor.score >= 40:
                desc = f"{name}表现一般({factor.score}分)"
            else:
                desc = f"{name}表现较弱({factor.score}分)"
            parts.append(desc)
        
        reasoning = "；".join(parts)
        reasoning += f"。综合得分{final_score:.2f}分，"
        
        # 最终结论
        if final_score >= 65:
            reasoning += "整体偏向乐观。"
        elif final_score >= 45:
            reasoning += "多空力量相对均衡。"
        else:
            reasoning += "整体偏向悲观。"
        
        return reasoning
    
    def _generate_summary(self, recommendation: str, score: float, 
                          fund_data: Dict) -> str:
        """生成一句话总结"""
        fund_name = fund_data.get("basic_info", {}).get("fund_name", "该基金")
        current_nav = fund_data.get("basic_info", {}).get("unit_nav", 0)
        
        summary = f"基于多因子分析，{fund_name}(当前净值{current_nav:.4f})综合评分为{score:.1f}分，"
        
        if "买入" in recommendation:
            summary += "建议关注买入机会，但需注意控制风险。"
        elif "持有" in recommendation:
            summary += "建议继续持有观察，等待更明确的信号。"
        elif "减持" in recommendation or "卖出" in recommendation:
            summary += "建议适当减仓或回避，规避潜在风险。"
        else:
            summary += "请结合自身情况审慎决策。"
        
        return summary


# 测试代码
if __name__ == "__main__":
    from tools.data_fetcher import FundDataFetcher
    from tools.news_crawler import NewsCrawler, SentimentAnalyzer
    
    # 初始化各模块
    fetcher = FundDataFetcher()
    crawler = NewsCrawler()
    analyzer = SentimentAnalyzer()
    engine = DecisionEngine()
    
    # 测试代码
    test_code = "110011"
    
    # 获取数据
    fund_data = fetcher.get_complete_fund_data(test_code)
    news_list = crawler.fetch_fund_news(test_code, fund_data['basic_info']['fund_name'])
    analyzed_news = analyzer.analyze_news_batch(news_list)
    sentiment_data = analyzer.calculate_overall_sentiment(analyzed_news)
    
    # 执行决策
    decision = engine.make_decision(fund_data, sentiment_data)
    
    # 输出结果
    print("\n" + "="*70)
    print("决策结果详情:")
    print("="*70)
    print(decision.to_dict())
