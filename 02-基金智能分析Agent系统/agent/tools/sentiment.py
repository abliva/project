# -*- coding: utf-8 -*-
"""
情感分析模块 - 基于LLM的高级情感分析
支持使用大语言模型进行更精准的情感判断和分析
"""

import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# 导入配置
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from config import SENTIMENT_CONFIG


@dataclass
class SentimentResult:
    """情感分析结果数据类"""
    label: str                           # 情感标签（利好/利空/中性）
    score: float                         # 情感得分 (-5 到 5)
    confidence: float                    # 置信度 (0 到 1)
    key_factors: List[str]               # 关键影响因素
    reasoning: str                       # 分析推理过程
    suggestion: str                      # 相关建议


class LLMAnalyzer:
    """
    基于LLM的情感分析器
    
    功能：
    1. 使用大语言模型分析文本情感
    2. 提供结构化的情感分析结果
    3. 支持上下文理解的情感判断
    4. 可选集成OpenAI或其他LLM服务
    """
    
    def __init__(self, api_key: str = None, model: str = None):
        """
        初始化LLM分析器
        
        Args:
            api_key: API密钥（可选，不提供则使用规则引擎）
            model: 模型名称
        """
        self.api_key = api_key
        self.model = model or "sensenova-6.7-flash-lite"
        self.use_llm = bool(api_key)  # 是否使用真实LLM

        # 加载配置
        self.config = SENTIMENT_CONFIG

        # LLM API配置（从全局配置读取）
        import sys, os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        from config import LLM_CONFIG
        self.llm_config = LLM_CONFIG
        
        if self.use_llm:
            print(f"[LLMAnalyzer] 初始化完成，使用模型: {self.model}")
        else:
            print("[LLMAnalyzer] 初始化完成，使用增强规则引擎模式")
    
    def analyze_sentiment(self, text: str, context: str = None) -> SentimentResult:
        """
        分析文本情感（主入口）
        
        Args:
            text: 待分析的文本
            context: 上下文信息（如相关市场环境）
            
        Returns:
            SentimentResult对象
        """
        if self.use_llm:
            return self._llm_analyze(text, context)
        else:
            return self._rule_based_analyze(text, context)
    
    def _llm_analyze(self, text: str, context: str = None) -> SentimentResult:
        """
        使用LLM进行情感分析
        
        Args:
            text: 待分析文本
            context: 上下文
            
        Returns:
            情感分析结果
        """
        try:
            import openai

            # 使用SenseNova（商汤）API配置
            llm_api_key = self.api_key or self.llm_config.get("api_key", "")
            llm_base_url = self.llm_config.get("base_url", "https://token.sensenova.cn/v1")
            llm_model = self.model or self.llm_config.get("model", "sensenova-6.7-flash-lite")

            client = openai.OpenAI(
                api_key=llm_api_key,
                base_url=llm_base_url,
                timeout=self.llm_config.get("timeout", 60)
            )
            
            # 构建提示词
            prompt = self._build_llm_prompt(text, context)
            
            response = client.chat.completions.create(
                model=llm_model,
                messages=[
                    {"role": "system", "content": "你是一个专业的金融情感分析专家。请分析给定文本的情感倾向，并以JSON格式输出结果。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # 降低随机性以获得稳定结果
                response_format={"type": "json_object"}
            )
            
            # 解析响应
            result_json = json.loads(response.choices[0].message.content)
            
            return SentimentResult(
                label=result_json.get("label", "中性"),
                score=float(result_json.get("score", 0)),
                confidence=float(result_json.get("confidence", 0.7)),
                key_factors=result_json.get("key_factors", []),
                reasoning=result_json.get("reasoning", ""),
                suggestion=result_json.get("suggestion", ""),
            )
            
        except Exception as e:
            print(f"[错误] LLM分析失败: {str(e)}，回退到规则引擎")
            return self._rule_based_analyze(text, context)
    
    def _rule_based_analyze(self, text: str, context: str = None) -> SentimentResult:
        """
        基于规则的增强情感分析（当LLM不可用时的备选方案）
        
        结合了：
        1. 关键词匹配
        2. 规则推理
        3. 上下文感知
        4. 否定词处理
        5. 程度副词加权
        """
        # 导入基础情感分析器
        from .news_crawler import SentimentAnalyzer
        base_analyzer = SentimentAnalyzer()
        
        # 获取基础得分和标签
        base_score, base_label, base_conf = base_analyzer.analyze_text(text)
        
        # 增强分析：否定词检测和处理
        enhanced_score = self._handle_negation(text, base_score)
        
        # 程度副词加权
        enhanced_score = self._apply_intensity_modifiers(text, enhanced_score)
        
        # 上下文修正
        if context:
            _, context_label, _ = base_analyzer.analyze_text(context)
            if context_label in ["利空", "强烈利空"]:
                enhanced_score *= 0.9  # 在利空环境下适当调低得分
            elif context_label in ["利好", "强烈利好"]:
                enhanced_score *= 1.1  # 在利好环境下适当调高得分
        
        # 最终分类
        final_label, final_conf = self._classify_with_reasoning(enhanced_score, text)
        
        # 提取关键因素
        key_factors = self._extract_key_factors(text)
        
        # 生成建议
        suggestion = self._generate_suggestion(final_label, enhanced_score)
        
        return SentimentResult(
            label=final_label,
            score=round(enhanced_score, 2),
            confidence=final_conf,
            key_factors=key_factors,
            reasoning=self._build_reasoning(base_score, enhanced_score, text),
            suggestion=suggestion,
        )
    
    def _handle_negation(self, text: str, original_score: float) -> float:
        """
        处理否定词，反转情感极性
        
        Args:
            text: 输入文本
            original_score: 原始得分
            
        Returns:
            处理后的得分
        """
        negation_words = ["不", "没", "无", "非", "未", "别", "莫", "勿", "不是", "没有", "并非"]
        
        for neg_word in negation_words:
            if neg_word in text:
                # 找到否定词后面的情感词并反转
                # 简化实现：如果整个句子有否定词，反转得分
                return -original_score * 0.8  # 反转并稍微减弱
        
        return original_score
    
    def _apply_intensity_modifiers(self, text: str, score: float) -> float:
        """
        应用程度副词修饰
        
        Args:
            text: 输入文本
            score: 当前得分
            
        Returns:
            修饰后的得分
        """
        intensifiers = {
            "非常": 1.5,
            "特别": 1.4,
            "极其": 1.6,
            "十分": 1.3,
            "相当": 1.2,
            "比较": 1.1,
            "稍微": 0.8,
            "有点": 0.7,
            "略": 0.7,
            "稍微": 0.8,
        }
        
        modifier = 1.0
        for word, factor in intensifiers.items():
            if word in text:
                modifier = max(modifier, factor)
                break  # 只取第一个匹配的程度副词
        
        return score * modifier
    
    def _classify_with_reasoning(self, score: float, text: str) -> Tuple[str, float]:
        """
        带推理的分类
        
        Args:
            score: 情感得分
            text: 原始文本（用于辅助判断）
            
        Returns:
            (标签, 置信度)
        """
        thresholds = [
            (3.0, "强烈利好"),
            (1.5, "利好"),
            (-0.5, "中性"),
            (-1.5, "利空"),
            (-float("inf"), "强烈利空"),
        ]
        
        for threshold, label in thresholds:
            if score >= threshold:
                # 置信度基于得分绝对值
                confidence = min(abs(score) / 4, 1.0)
                return (label, round(confidence, 2))
        
        return ("中性", 0.5)
    
    def _extract_key_factors(self, text: str) -> List[str]:
        """
        提取关键影响因素
        
        Args:
            text: 输入文本
            
        Returns:
            关键因素列表
        """
        factors = []
        
        # 金融领域关键因素关键词
        factor_patterns = {
            "业绩表现": ["业绩", "营收", "利润", "收益", "盈利"],
            "市场情绪": ["情绪", "信心", "预期", "乐观", "悲观"],
            "资金流向": ["资金", "流入", "流出", "申购", "赎回"],
            "政策因素": ["政策", "监管", "法规", "调控", "利好政策"],
            "行业动态": ["行业", "板块", "产业链", "景气度"],
            "公司经营": ["管理层", "战略", "重组", "并购", "转型"],
            "外部环境": ["国际", "贸易", "汇率", "地缘政治", "宏观"],
        }
        
        for category, keywords in factor_patterns.items():
            for keyword in keywords:
                if keyword in text:
                    factors.append(category)
                    break
        
        return factors[:3]  # 返回最多3个主要因素
    
    def _generate_suggestion(self, label: str, score: float) -> str:
        """
        根据情感分析结果生成投资建议
        
        Args:
            label: 情感标签
            score: 情感得分
            
        Returns:
            建议文字
        """
        suggestions = {
            "强烈利好": "当前市场情绪极度乐观，可考虑适度参与但需警惕追高风险",
            "利好": "消息面偏向积极，可作为买入参考之一，结合其他指标综合判断",
            "中性": "消息面无明显方向，建议观望或维持现有仓位",
            "利空": "存在一定负面因素，建议谨慎操作或适当减仓",
            "强烈利空": "市场情绪极度悲观，建议暂时回避或做好风险控制",
        }
        
        base_suggestion = suggestions.get(label, "无法确定")
        
        # 根据得分微调建议
        if abs(score) > 3:
            base_suggestion += "（信号较强）"
        
        return base_suggestion
    
    def _build_reasoning(self, base_score: float, final_score: float, text: str) -> str:
        """
        构建分析推理说明
        
        Args:
            base_score: 基础得分
            final_score: 最终得分
            text: 分析文本
            
        Returns:
            推理说明文字
        """
        reasoning_parts = []
        
        # 说明基础情感
        if base_score > 0:
            reasoning_parts.append(f"文本中检测到较多正向表达（基础得分：{base_score:+.2f}）")
        elif base_score < 0:
            reasoning_parts.append(f"文本中检测到较多负向表达（基础得分：{base_score:+.2f}）")
        else:
            reasoning_parts.append("未检测到明显的情感倾向表达")
        
        # 说明修饰情况
        if abs(final_score - base_score) > 0.1:
            if final_score > base_score:
                reasoning_parts.append("经过否定词和程度副词处理后，情感强度有所增强")
            else:
                reasoning_parts.append("经过否定词处理后，情感极性发生反转或减弱")
        
        return "；".join(reasoning_parts)
    
    def _build_llm_prompt(self, text: str, context: str = None) -> str:
        """
        构建LLM分析的提示词
        
        Args:
            text: 待分析文本
            context: 上下文
            
        Returns:
            格式化的提示词
        """
        prompt = f"""请分析以下金融相关文本的情感倾向：

{text}

{"上下文信息：" + context if context else ""}

请以JSON格式返回分析结果，包含以下字段：
- label: 情感标签（"强烈利好"/"利好"/"中性"/"利空"/"强烈利空"）
- score: 情感得分（-5到5之间的数值，正值表示利好，负值表示利空）
- confidence: 置信度（0到1之间）
- key_factors: 影响情感的主要因素列表
- reasoning: 简要的分析推理过程
- suggestion: 基于此情感的投资建议

只返回JSON，不要其他内容。"""

        return prompt
    
    def batch_analyze(self, texts: List[str], contexts: List[str] = None) -> List[SentimentResult]:
        """
        批量分析多个文本
        
        Args:
            texts: 待分析的文本列表
            contexts: 对应的上下文列表（可选）
            
        Returns:
            情感分析结果列表
        """
        results = []
        
        for i, text in enumerate(texts):
            context = contexts[i] if contexts and i < len(contexts) else None
            result = self.analyze_sentiment(text, context)
            results.append(result)
            
            # 显示进度
            if (i + 1) % 10 == 0 or i + 1 == len(texts):
                print(f"  [进度] 已分析 {i+1}/{len(texts)} 条文本")
        
        return results


# 便捷函数
def quick_analyze(text: str) -> Dict:
    """
    快速分析文本情感的便捷函数
    
    Args:
        text: 待分析文本
        
    Returns:
        字典格式的分析结果
    """
    analyzer = LLMAnalyzer()  # 使用规则引擎模式
    result = analyzer.analyze_sentiment(text)
    
    return {
        "label": result.label,
        "score": result.score,
        "confidence": result.confidence,
        "key_factors": result.key_factors,
        "suggestion": result.suggestion,
    }


# 测试代码
if __name__ == "__main__":
    # 测试文本
    test_texts = [
        "今日A股三大指数集体上涨，创业板指涨超2%，北向资金净流入超百亿，市场情绪高涨",
        "受外围市场暴跌影响，两市低开低走，超4000股下跌，投资者恐慌情绪蔓延",
        "某基金公布季度报告，持仓结构小幅调整，整体运作平稳",
        "央行宣布降准0.5个百分点，释放长期资金约1万亿，利好资本市场",
        "该基金重仓股暴雷，连续三个跌停，净值出现大幅回撤",
    ]
    
    print("="*70)
    print("LLM情感分析测试")
    print("="*70)
    
    analyzer = LLMAnalyzer()  # 使用规则引擎模式
    
    for i, text in enumerate(test_texts, 1):
        print(f"\n{'-'*70}")
        print(f"测试文本 {i}:")
        print(f"内容: {text[:50]}...")
        
        result = analyzer.analyze_sentiment(text)
        
        print(f"\n分析结果:")
        print(f"  情感标签: {result.label}")
        print(f"  情感得分: {result.score:+.2f}")
        print(f"  置信度:   {result.confidence:.2%}")
        print(f"  关键因素: {', '.join(result.key_factors) if result.key_factors else '无'}")
        print(f"  推理过程: {result.reasoning}")
        print(f"  建议:     {result.suggestion}")
