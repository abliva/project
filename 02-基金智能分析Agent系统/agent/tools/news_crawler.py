# -*- coding: utf-8 -*-
"""
新闻抓取与情感分析模块
负责获取与基金相关的新闻资讯并进行情感倾向分析
"""

import re
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# 导入配置
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from config import SYSTEM_CONFIG


@dataclass
class NewsItem:
    """新闻条目数据类"""
    title: str                          # 新闻标题
    content: str                        # 新闻内容摘要
    source: str                         # 来源
    publish_time: str                   # 发布时间
    url: str                            # 链接
    sentiment_score: float = 0.0        # 情感得分
    sentiment_label: str = "中性"       # 情感标签
    keywords: List[str] = None          # 提取的关键词
    
    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []


class NewsCrawler:
    """
    新闻爬虫类
    
    功能：
    1. 根据基金代码或关键词搜索相关新闻
    2. 从多个财经网站抓取新闻数据
    3. 对新闻进行预处理和清洗
    4. 支持时间范围筛选
    """
    
    def __init__(self):
        """初始化新闻爬虫"""
        self.config = SYSTEM_CONFIG
        self.news_count = self.config["news_fetch_count"]
        self.time_range_days = self.config["news_time_range_days"]
        
        # 支持的新闻源（实际项目中可扩展）
        self.news_sources = [
            "东方财富网",
            "新浪财经",
            "同花顺",
            "雪球网",
            "金融界",
            "证券时报",
        ]
        
        print(f"[NewsCrawler] 初始化完成，将获取最近{self.time_range_days}天的新闻")
    
    def fetch_fund_news(self, fund_code: str, fund_name: str = None) -> List[NewsItem]:
        """
        获取指定基金的相关新闻
        
        Args:
            fund_code: 基金代码
            fund_name: 基金名称（可选，用于优化搜索）
            
        Returns:
            新闻列表
        """
        print(f"\n[新闻抓取] 正在搜索基金 {fund_code} 的相关新闻...")
        
        # 构建搜索关键词
        search_keywords = [fund_code]
        if fund_name:
            # 取基金名称的前几个字作为关键词
            keywords_from_name = fund_name.replace("基金", "").split()[0:2]
            search_keywords.extend(keywords_from_name)
        
        all_news = []
        
        # 从各个来源获取新闻（这里使用模拟数据）
        for keyword in search_keywords[:2]:  # 限制关键词数量避免过多请求
            news_for_keyword = self._search_news_by_keyword(keyword)
            all_news.extend(news_for_keyword)
            
            # 避免请求过快
            time.sleep(random.uniform(0.3, 0.8))
        
        # 去重（基于标题相似度）
        unique_news = self._deduplicate_news(all_news)
        
        # 按时间排序
        unique_news.sort(key=lambda x: x.publish_time, reverse=True)
        
        # 限制返回数量
        final_news = unique_news[:self.news_count]
        
        print(f"[成功] 共获取到 {len(final_news)} 条相关新闻")
        return final_news
    
    def _search_news_by_keyword(self, keyword: str) -> List[NewsItem]:
        """
        根据关键词搜索新闻（模拟实现）
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            新闻列表
        """
        # 在实际项目中，这里应该调用真实的新闻API或爬虫
        # 例如：requests.get("https://search-api.example.com?q=" + keyword)
        
        # 生成模拟新闻数据
        news_templates = self._generate_news_templates(keyword)
        
        news_list = []
        num_news = random.randint(5, 12)  # 每个关键词生成5-12条新闻
        
        for i in range(num_news):
            template = random.choice(news_templates)
            
            # 生成发布时间（最近的几天内）
            hours_ago = random.randint(0, self.time_range_days * 24)
            pub_time = datetime.now() - timedelta(hours=hours_ago)
            
            news_item = NewsItem(
                title=template["title"],
                content=template["content"],
                source=random.choice(self.news_sources),
                publish_time=pub_time.strftime("%Y-%m-%d %H:%M"),
                url=f"https://example.com/news/{keyword}/{i}",
            )
            news_list.append(news_item)
        
        return news_list
    
    def _generate_news_templates(self, keyword: str) -> List[Dict]:
        """
        生成新闻模板库（根据关键词定制）
        
        Args:
            keyword: 基金相关关键词
            
        Returns:
            新闻模板列表
        """
        templates = [
            # 利好消息
            {
                "title": f"{keyword}净值创新高，机构看好后市表现",
                "content": f"受市场利好因素推动，{keyword}今日净值上涨明显，创下近期新高。多位分析师表示，该基金持仓结构合理，未来有望继续获得超额收益。",
                "sentiment_bias": "positive"
            },
            {
                "title": f"资金大幅流入{keyword}，规模持续增长",
                "content": f"最新数据显示，{keyword}近期获得大量资金净流入，基金规模稳步提升。投资者对该基金的投资策略和业绩表现给予了高度认可。",
                "sentiment_bias": "positive"
            },
            {
                "title": f"{keyword}重仓股表现亮眼，带动净值上涨",
                "content": f"{keyword}的重仓股近期表现强劲，多只个股涨幅显著，直接推动了基金净值的上涨。基金经理表示将继续坚持价值投资理念。",
                "sentiment_bias": "positive"
            },
            {
                "title": f"季报显示{keyword}持仓调整成效显著",
                "content": f"最新披露的季度报告显示，{keyword}进行了积极的仓位调整，成功规避了部分市场风险，同时把握住了结构性机会，整体运作稳健。",
                "sentiment_bias": "positive"
            },
            {
                "title": f"分析师上调{keyword}评级至'强烈推荐'",
                "content": f"多家券商研究机构发布报告，上调{keyword}的投资评级。研究报告指出，该基金在风险控制能力、选股能力和业绩持续性方面均表现优异。",
                "sentiment_bias": "positive"
            },
            
            # 利空消息
            {
                "title": f"{keyword}遭遇大额赎回，短期承压明显",
                "content": f"受市场情绪影响，{keyword}近期面临一定的赎回压力。基金经理表示将审慎应对，保持投资组合的稳定性，等待市场企稳。",
                "sentiment_bias": "negative"
            },
            {
                "title": f"{keyword}净值连续回调，投资者需注意风险",
                "content": f"受到市场整体下跌影响，{keyword}净值出现连续回调。分析师建议投资者关注基金持仓结构变化，理性评估风险承受能力。",
                "sentiment_bias": "negative"
            },
            {
                "title": f"重仓板块走弱拖累{keyword}表现",
                "content": f"{keyword}重点配置的行业板块近期表现不佳，对基金净值形成一定压力。不过，长期来看，这些板块仍具备较好的投资价值。",
                "sentiment_bias": "negative"
            },
            {
                "title": f"市场波动加剧，{keyword}暂避锋芒降低仓位",
                "content": f"面对复杂的市场环境，{keyword}选择适当降低权益仓位以控制风险。这一操作虽然可能影响短期收益，但有助于保护持有人利益。",
                "sentiment_bias": "negative"
            },
            
            # 中性消息
            {
                "title": f"{keyword}发布最新运作报告",
                "content": f"{keyword}今日发布了最新的基金运作报告，详细披露了近期的投资策略、持仓变动和市场展望等信息，供投资者参考。",
                "sentiment_bias": "neutral"
            },
            {
                "title": f"{keyword}基金经理接受采访谈投资理念",
                "content": f"{keyword}的基金经理近日接受了媒体专访，深入阐述了其投资理念和未来的布局方向。他表示将继续专注于寻找具有长期成长性的优质标的。",
                "sentiment_bias": "neutral"
            },
            {
                "title": f"{keyword}分红公告：每份派发X元",
                "content": f"{keyword}发布公告，决定向持有人进行收益分配。此次分红体现了基金良好的盈利能力和对投资者的回报意愿。",
                "sentiment_bias": "neutral"
            },
        ]
        
        return templates
    
    def _deduplicate_news(self, news_list: List[NewsItem]) -> List[NewsItem]:
        """
        新闻去重（基于标题相似度）
        
        Args:
            news_list: 原始新闻列表
            
        Returns:
            去重后的新闻列表
        """
        seen_titles = set()
        unique_news = []
        
        for news in news_list:
            # 简单的去重逻辑：标题完全相同则去重
            title_key = news.title.strip().lower()
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_news.append(news)
        
        return unique_news
    
    def fetch_market_news(self) -> List[NewsItem]:
        """
        获取市场整体新闻（宏观经济、政策面等）
        
        Returns:
            市场新闻列表
        """
        print("\n[新闻抓取] 正在获取市场宏观新闻...")
        
        market_keywords = [
            "A股市场",
            "货币政策",
            "经济数据",
            "证监会",
            "央行",
            "美联储",
        ]
        
        all_market_news = []
        for keyword in market_keywords[:3]:  # 限制数量
            news = self._search_news_by_keyword(keyword)
            all_market_news.extend(news)
        
        # 去重并限制数量
        unique_news = self._deduplicate_news(all_market_news)[:10]
        
        print(f"[成功] 获取到 {len(unique_news)} 条市场新闻")
        return unique_news


class SentimentAnalyzer:
    """
    情感分析器
    
    功能：
    1. 基于关键词规则的情感分析
    2. 支持利好/利空/中性三分类
    3. 计算情感得分和置信度
    4. 支持批量处理
    """
    
    def __init__(self):
        """初始化情感分析器"""
        from config import SENTIMENT_CONFIG
        
        self.config = SENTIMENT_CONFIG
        self.positive_keywords = self.config["positive_keywords"]
        self.negative_keywords = self.config["negative_keywords"]
        
        # 阈值设置
        self.strong_positive_threshold = self.config["strong_positive_threshold"]
        self.positive_threshold = self.config["positive_threshold"]
        self.neutral_range = self.config["neutral_range"]
        self.negative_threshold = self.config["negative_threshold"]
        self.strong_negative_threshold = self.config["strong_negative_threshold"]
        
        print("[SentimentAnalyzer] 情感分析器初始化完成")
    
    def analyze_text(self, text: str) -> Tuple[float, str, float]:
        """
        分析单段文本的情感倾向
        
        Args:
            text: 待分析的文本
            
        Returns:
            元组：(情感得分, 情感标签, 置信度)
            - 得分范围：负数表示利空，正数表示利好
            - 标签：强烈利好/利好/中性/利空/强烈利空
            - 置信度：0-1之间
        """
        if not text or not text.strip():
            return (0.0, "中性", 0.0)
        
        score = 0.0
        matched_keywords = []
        
        # 扫描正面关键词
        for keyword, weight in self.positive_keywords.items():
            count = text.count(keyword)
            if count > 0:
                score += weight * count
                matched_keywords.append((keyword, weight, count))
        
        # 扫描负面关键词
        for keyword, weight in self.negative_keywords.items():
            count = text.count(keyword)
            if count > 0:
                score += weight * count  # weight本身是负数
                matched_keywords.append((keyword, weight, count))
        
        # 归一化得分（考虑文本长度）
        text_length = len(text)
        normalized_score = score / max(text_length / 100, 1)
        
        # 确定情感标签
        label, confidence = self._classify_sentiment(normalized_score)
        
        return (round(normalized_score, 3), label, round(confidence, 3))
    
    def _classify_sentiment(self, score: float) -> Tuple[str, float]:
        """
        根据得分分类情感标签
        
        Args:
            score: 情感得分
            
        Returns:
            (标签, 置信度)
        """
        abs_score = abs(score)
        
        if score >= self.strong_positive_threshold:
            return ("强烈利好", min(abs_score / 5, 1.0))
        elif score >= self.positive_threshold:
            return ("利好", min(abs_score / 3, 1.0))
        elif score >= self.neutral_range[0] and score <= self.neutral_range[1]:
            return ("中性", 0.5)
        elif score >= self.strong_negative_threshold:
            return ("强烈利空", min(abs_score / 5, 1.0))
        else:
            return ("利空", min(abs_score / 3, 1.0))
    
    def analyze_news_batch(self, news_list: List[NewsItem]) -> List[NewsItem]:
        """
        批量分析新闻情感
        
        Args:
            news_list: 新闻列表
            
        Returns:
            已标注情感的新闻列表
        """
        print(f"\n[情感分析] 开始批量分析 {len(news_list)} 条新闻的情感倾向...")
        
        analyzed_news = []
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        
        for i, news in enumerate(news_list, 1):
            # 分析标题和内容的综合情感
            title_score, title_label, title_conf = self.analyze_text(news.title)
            content_score, content_label, content_conf = self.analyze_text(news.content)
            
            # 综合得分（标题权重更高）
            combined_score = title_score * 0.6 + content_score * 0.4
            combined_label, combined_conf = self._classify_sentiment(combined_score)
            
            # 更新新闻对象
            news.sentiment_score = combined_score
            news.sentiment_label = combined_label
            news.keywords = self._extract_keywords(news.title + " " + news.content)
            
            analyzed_news.append(news)
            
            # 统计
            if "利好" in combined_label:
                positive_count += 1
            elif "利空" in combined_label:
                negative_count += 1
            else:
                neutral_count += 1
            
            if i % 5 == 0 or i == len(news_list):
                print(f"  已分析: {i}/{len(news_list)}")
        
        print(f"[完成] 情感分析统计：利好{positive_count}条 | 中性{neutral_count}条 | 利空{negative_count}条")
        
        return analyzed_news
    
    def _extract_keywords(self, text: str, top_n: int = 5) -> List[str]:
        """
        从文本中提取关键词
        
        Args:
            text: 输入文本
            top_n: 返回前N个关键词
            
        Returns:
            关键词列表
        """
        all_keywords = []
        
        # 从预定义的情感词表中提取匹配的关键词
        for keyword in list(self.positive_keywords.keys()) + list(self.negative_keywords.keys()):
            if keyword in text:
                all_keywords.append(keyword)
        
        # 返回出现频率最高的关键词（简单实现）
        # 这里可以集成jieba分词等更复杂的算法
        return list(set(all_keywords))[:top_n]
    
    def calculate_overall_sentiment(self, analyzed_news: List[NewsItem]) -> Dict:
        """
        计算整体舆情情感指数
        
        Args:
            analyzed_news: 已分析过的新闻列表
            
        Returns:
            整体情感统计字典：
            - overall_score: 综合情感得分
            - overall_label: 综合情感标签
            - distribution: 情感分布比例
            - positive_ratio: 利好占比
            - negative_ratio: 利空占比
            - neutral_ratio: 中性占比
            - avg_confidence: 平均置信度
            - news_count: 新闻总数
            - latest_trend: 最近趋势
        """
        if not analyzed_news:
            return {
                "overall_score": 0.0,
                "overall_label": "无数据",
                "distribution": {},
                "positive_ratio": 0,
                "negative_ratio": 0,
                "neutral_ratio": 100,
                "avg_confidence": 0.0,
                "news_count": 0,
                "latest_trend": "未知",
            }
        
        print("\n[舆情分析] 正在计算整体情感指数...")
        
        # 统计各类别数量
        sentiment_counts = {
            "强烈利好": 0,
            "利好": 0,
            "中性": 0,
            "利空": 0,
            "强烈利空": 0,
        }
        
        total_score = 0.0
        total_confidence = 0.0
        
        for news in analyzed_news:
            sentiment_counts[news.sentiment_label] = sentiment_counts.get(news.sentiment_label, 0) + 1
            total_score += news.sentiment_score
            total_confidence += 0.7  # 默认置信度（实际可使用analyze_text返回的置信度）
        
        total = len(analyzed_news)
        
        # 计算各项指标
        overall_score = round(total_score / total, 3)
        overall_label, _ = self._classify_sentiment(overall_score)
        
        positive_count = sentiment_counts["强烈利好"] + sentiment_counts["利好"]
        negative_count = sentiment_counts["利空"] + sentiment_counts["强烈利空"]
        neutral_count = sentiment_counts["中性"]
        
        positive_ratio = round(positive_count / total * 100, 1)
        negative_ratio = round(negative_count / total * 100, 1)
        neutral_ratio = round(neutral_count / total * 100, 1)
        
        avg_confidence = round(total_confidence / total, 3)
        
        # 判断最近趋势（比较前后半段新闻的情感差异）
        half_point = total // 2
        if half_point > 0:
            earlier_avg = sum(n.sentiment_score for n in analyzed_news[:half_point]) / half_point
            later_avg = sum(n.sentiment_score for n in analyzed_news[half_point:]) / (total - half_point)
            trend_diff = later_avg - earlier_avg
            
            if trend_diff > 0.5:
                latest_trend = "转好"
            elif trend_diff < -0.5:
                latest_trend = "转差"
            else:
                latest_trend = "平稳"
        else:
            latest_trend = "数据不足"
        
        result = {
            "overall_score": overall_score,
            "overall_label": overall_label,
            "distribution": sentiment_counts,
            "positive_ratio": positive_ratio,
            "negative_ratio": negative_ratio,
            "neutral_ratio": neutral_ratio,
            "avg_confidence": avg_confidence,
            "news_count": total,
            "latest_trend": latest_trend,
            "score_interpretation": self._interpret_score(overall_score),
        }
        
        print(f"[完成] 整体情感得分: {overall_score} ({overall_label})")
        print(f"  分布：利好{positive_ratio}% | 中性{neutral_ratio}% | 利空{negative_ratio}%")
        print(f"  趋势：{latest_trend}")
        
        return result
    
    def _interpret_score(self, score: float) -> str:
        """
        解读情感得分的含义
        
        Args:
            score: 情感得分
            
        Returns:
            文字解读
        """
        if score >= 3:
            return "市场情绪极度乐观，但需警惕过热风险"
        elif score >= 1.5:
            return "市场情绪偏向乐观，多数消息面利好"
        elif score >= 0.5:
            return "市场情绪略微偏多，利好消息略占优势"
        elif score > -0.5:
            return "市场情绪相对中性，多空力量均衡"
        elif score > -1.5:
            return "市场情绪略显悲观，利空消息有所增加"
        elif score > -3:
            return "市场情绪较为悲观，空头占据主导"
        else:
            return "市场情绪极度悲观，可能存在超跌反弹机会"


# 测试代码
if __name__ == "__main__":
    # 测试新闻抓取
    crawler = NewsCrawler()
    news_list = crawler.fetch_fund_news("110011", "易方达中小盘混合")
    
    print(f"\n获取到 {len(news_list)} 条新闻")
    for i, news in enumerate(news_list[:5], 1):
        print(f"\n{i}. [{news.source}] {news.title}")
        print(f"   时间: {news.publish_time}")
    
    # 测试情感分析
    analyzer = SentimentAnalyzer()
    analyzed_news = analyzer.analyze_news_batch(news_list)
    
    # 显示部分分析结果
    print("\n" + "="*60)
    print("情感分析结果样例:")
    print("="*60)
    for news in analyzed_news[:3]:
        print(f"\n标题: {news.title}")
        print(f"情感: {news.sentiment_label} (得分: {news.sentiment_score})")
        print(f"关键词: {news.keywords}")
    
    # 计算整体情感
    overall = analyzer.calculate_overall_sentiment(analyzed_news)
    print(f"\n整体情感指数: {overall['overall_score']} ({overall['overall_label']})")
    print(f"解读: {overall['score_interpretation']}")
