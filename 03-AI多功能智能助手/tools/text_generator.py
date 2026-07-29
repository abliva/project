"""
文案生成工具
提供营销文案、邮件、总结、报告等多种文本生成能力
支持多种风格和场景的智能文案创作
"""

import re
import json
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.tool_executor import BaseTool, ToolResult


@dataclass
class GenerationRequest:
    """生成请求数据结构"""
    content_type: str           # 文案类型
    topic: str                  # 主题/话题
    style: str = "professional"  # 风格：professional, casual, creative, formal
    tone: str = "neutral"       # 语气：neutral, friendly, persuasive, authoritative
    length: str = "medium"      # 长度：short, medium, long
    target_audience: str = ""   # 目标受众
    keywords: List[str] = field(default_factory=list)  # 关键词列表
    additional_requirements: str = ""  # 额外要求
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "content_type": self.content_type,
            "topic": self.topic,
            "style": self.style,
            "tone": self.tone,
            "length": self.length,
            "target_audience": self.target_audience,
            "keywords": self.keywords,
            "additional_requirements": self.additional_requirements
        }


@dataclass 
class GeneratedContent:
    """生成内容数据结构"""
    title: str
    content: str
    content_type: str
    word_count: int
    generation_time: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "content": self.content,
            "content_type": self.content_type,
            "word_count": self.word_count,
            "generation_time": self.generation_time,
            **self.metadata
        }


class TextGeneratorTool(BaseTool):
    """
    文案生成工具
    
    支持的文案类型：
    1. 营销文案 - 产品推广、广告语、宣传文案
    2. 邮件 - 商务邮件、邀请函、通知邮件
    3. 总结 - 文章总结、会议纪要、要点提炼
    4. 报告 - 工作报告、分析报告、调研报告
    5. 社交媒体 - 微博、朋友圈、小红书等平台内容
    6. 创意写作 - 故事、诗歌、创意短文
    """
    
    # 支持的内容类型
    CONTENT_TYPES = {
        "marketing": {
            "name": "营销文案",
            "description": "产品推广、广告语、品牌宣传等商业文案",
            "templates": ["产品介绍", "促销活动", "品牌故事", "广告标语"]
        },
        "email": {
            "name": "邮件",
            "description": "各类商务和正式邮件",
            "templates": ["商务邮件", "邀请函", "感谢信", "通知邮件", "求职信"]
        },
        "summary": {
            "name": "总结",
            "description": "文章、会议、文档等内容总结",
            "templates": ["文章摘要", "会议纪要", "读书笔记", "要点提炼"]
        },
        "report": {
            "name": "报告",
            "description": "各类工作报告和分析报告",
            "templates": ["工作汇报", "项目报告", "分析报告", "调研报告"]
        },
        "social_media": {
            "name": "社交媒体",
            "description": "适合社交平台发布的内容",
            "templates": ["微博动态", "朋友圈文案", "小红书笔记", "公众号推文"]
        },
        "creative": {
            "name": "创意写作",
            "description": "创意类文学内容",
            "templates": ["短篇故事", "现代诗", "散文随笔", "创意文案"]
        }
    }
    
    # 写作风格定义
    STYLES = {
        "professional": {"name": "专业正式", "characteristics": ["严谨", "规范", "权威"]},
        "casual": {"name": "轻松随意", "characteristics": ["亲切", "自然", "口语化"]},
        "creative": {"name": "创意新颖", "characteristics": ["独特", "有趣", "富有想象力"]},
        "formal": {"name": "庄重典雅", "characteristics": ["典雅", "得体", "传统"]}
    }

    def __init__(self):
        """初始化文案生成工具"""
        super().__init__(
            name="text_generator",
            description="智能文案生成工具，支持营销文案、邮件、总结、报告等多种类型"
        )
        
        # 定义参数模式
        self.parameters_schema = {
            "type": "object",
            "properties": {
                "content_type": {
                    "type": "string",
                    "enum": list(self.CONTENT_TYPES.keys()),
                    "description": f"文案类型: {', '.join(self.CONTENT_TYPES.keys())}"
                },
                "topic": {
                    "type": "string",
                    "description": "文案主题或核心内容"
                },
                "style": {
                    "type": "string",
                    "enum": list(self.STYLES.keys()),
                    "default": "professional",
                    "description": "写作风格"
                },
                "tone": {
                    "type": "string",
                    "enum": ["neutral", "friendly", "persuasive", "authoritative"],
                    "default": "neutral",
                    "description": "语气倾向"
                },
                "length": {
                    "type": "string",
                    "enum": ["short", "medium", "long"],
                    "default": "medium",
                    "description": "内容长度"
                },
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "需要包含的关键词列表"
                },
                "context": {
                    "type": "string",
                    "description": "背景信息或参考内容（用于总结等）"
                }
            },
            "required": ["content_type", "topic"]
        }
        
        # 统计信息
        self.generation_stats = {
            "total_generations": 0,
            "by_type": {},
            "by_style": {}
        }
        
        print("✓ 文案生成工具初始化完成")

    def execute(self, **kwargs) -> ToolResult:
        """
        执行文案生成
        
        Args:
            **kwargs: 生成参数
            
        Returns:
            生成的文案内容
        """
        try:
            # 构建请求对象
            request = self._build_request(**kwargs)
            
            # 根据类型调用相应的生成方法
            generator_map = {
                "marketing": self._generate_marketing,
                "email": self._generate_email,
                "summary": self._generate_summary,
                "report": self._generate_report,
                "social_media": self._generate_social_media,
                "creative": self._generate_creative
            }
            
            generator_func = generator_map.get(request.content_type)
            if not generator_func:
                return ToolResult(
                    success=False,
                    tool_name=self.name,
                    error_message=f"不支持的文案类型: {request.content_type}"
                )
            
            # 生成内容
            generated = generator_func(request)
            
            # 更新统计
            self._update_stats(request)
            
            return ToolResult(
                success=True,
                tool_name=self.name,
                result_data=generated.to_dict(),
                metadata={
                    "request": request.to_dict(),
                    "generation_info": {
                        "word_count": generated.word_count,
                        "style_used": request.style,
                        "tone_used": request.tone
                    }
                }
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                tool_name=self.name,
                error_message=f"文案生成失败: {str(e)}"
            )

    def _build_request(self, **kwargs) -> GenerationRequest:
        """构建生成请求对象"""
        return GenerationRequest(
            content_type=kwargs.get("content_type"),
            topic=kwargs.get("topic", ""),
            style=kwargs.get("style", "professional"),
            tone=kwargs.get("tone", "neutral"),
            length=kwargs.get("length", "medium"),
            keywords=kwargs.get("keywords", []),
            additional_requirements=kwargs.get("context", "")
        )

    def _generate_marketing(self, request: GenerationRequest) -> GeneratedContent:
        """生成营销文案"""
        
        # 根据长度确定字数范围
        length_config = {
            "short": (50, 150),
            "medium": (200, 500),
            "long": (500, 1000)
        }
        min_words, max_words = length_config.get(request.length, (200, 500))
        
        # 生成标题
        titles = [
            f"🌟 {request.topic} - 您的最佳选择！",
            f"✨ 发现{request.topic}的无限可能",
            f"🚀 {request.topic}，引领新时代潮流"
        ]
        import random
        title = random.choice(titles)
        
        # 生成正文内容模板
        content_templates = {
            "short": f"""【{request.topic}】
{self._get_style_intro(request.style)}

✨ 核心优势：
• 专业品质，值得信赖
• 创新理念，引领行业
• 客户至上，服务贴心

📞 立即行动，开启美好体验！""",
            
            "medium": f"""{title}

{self._get_style_intro(request.style)}

💡 为什么选择{request.topic}？

1️⃣ 卓越品质
我们始终坚持以最高标准打造{request.topic}，确保每一处细节都精益求精。

2️⃣ 创新驱动
采用前沿技术和创新思维，让{request.topic}与众不同。

3️⃣ 用户至上
以用户需求为核心，提供个性化的解决方案。

🎯 适用场景：
{' • '.join(self.CONTENT_TYPES['marketing']['templates'][:3])}

{self._get_call_to_action(request.tone)}

---
*本内容由AI助手生成，仅供参考*""",
            
            "long": f"""{title}

═════════════════════════════════
📖 品牌故事
═════════════════════════════════

{self._get_detailed_intro(request)}

═════════════════════════════════
✨ 产品亮点
═════════════════════════════════

🔹 技术创新
采用业界领先的技术方案，确保{request.topic}在性能和体验上的卓越表现。

🔹 品质保证
严格的质量控制体系，从源头到终端全程把关。

🔹 服务保障
专业的服务团队，7×24小时响应您的需求。

═════════════════════════════════
🎯 成功案例
═════════════════════════════════

众多客户的选择已经证明了{request.topic}的价值。他们通过使用我们的产品/服务，实现了业务增长和效率提升。

═════════════════════════════════
{self._get_call_to_action(request.tone)}
═════════════════════════════════

联系我们获取更多信息，让我们一起创造价值！

---
*AI生成内容 | {datetime.now().strftime('%Y-%m-%d')}*"""
        }
        
        content = content_templates.get(request.length, content_templates["medium"])
        
        # 插入关键词
        if request.keywords:
            keyword_text = "\n🏷️ 关键词：" + " | ".join(request.keywords[:5])
            content += keyword_text
        
        word_count = len(content.replace(" ", ""))
        
        return GeneratedContent(
            title=title,
            content=content,
            content_type="marketing",
            word_count=word_count,
            generation_time=datetime.now().isoformat(),
            metadata={"style": request.style, "tone": request.tone}
        )

    def _generate_email(self, request: GenerationRequest) -> GeneratedContent:
        """生成邮件内容"""
        
        subject = f"关于{request.topic}" if len(request.topic) < 20 else f"{request.topic[:20]}..."
        
        email_templates = {
            "professional": f"""主题：{subject}

尊敬的收件人：

您好！

{self._get_email_body(request)}

如有任何疑问或需要进一步沟通，欢迎随时联系我。

祝好！

[您的姓名]
[联系方式]
{datetime.now().strftime('%Y年%m月%d日')}""",
            
            "casual": f"""Hi there!

Hope this email finds you well! 👋

{self._get_casual_email_body(request)}

Let me know your thoughts when you have a moment!

Best regards,
[Your Name]""",
            
            "creative": f"""✨ Subject: {subject} ✨

Dear Friend,

{self._get_creative_email_body(request)}

Looking forward to hearing from you!

Cheers & Creativity 🎨
[Your Name]"""
        }
        
        content = email_templates.get(request.style, email_templates["professional"])
        
        return GeneratedContent(
            title=subject,
            content=content,
            content_type="email",
            word_count=len(content),
            generation_time=datetime.now().isoformat()
        )

    def _generate_summary(self, request: GenerationRequest) -> GeneratedContent:
        """生成总结内容"""
        
        context = request.additional_requirements or request.topic
        
        summary_template = f"""📝 内容摘要
━━━━━━━━━━━━━━━━━━━━━

📌 主题：{request.topic}
⏰ 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}

━━━━━━━━━━━━━━━━━━━━━
📋 要点总结
━━━━━━━━━━━━━━━━━━━━━

{self._extract_key_points(context)}

━━━━━━━━━━━━━━━━━━━━━
💡 核心观点
━━━━━━━━━━━━━━━━━━━━━

{self._get_main_ideas(context)}

━━━━━━━━━━━━━━━━━━━━━
📊 总结评价
━━━━━━━━━━━━━━━━━━━━━

本文主要围绕{request.topic}展开论述，涵盖了相关的重要内容和观点。整体而言，内容结构清晰，论点明确，具有一定的参考价值。

⚠️ *注：此为AI自动生成的摘要，建议结合原文阅读*
"""
        
        return GeneratedContent(
            title=f"{request.topic} - 内容摘要",
            content=summary_template,
            content_type="summary",
            word_count=len(summary_template),
            generation_time=datetime.now().isoformat()
        )

    def _generate_report(self, request: GenerationRequest) -> GeneratedContent:
        """生成报告内容"""
        
        report_content = f"""📊 {request.topic}报告
{'='*40}

📅 报告日期：{datetime.now().strftime('%Y年%m月%d日')}
👤 撰写人：AI助手
📝 报告类型：{self.CONTENT_TYPES['report']['name']}

{'='*40}

一、背景与目的
────────────
本报告旨在对{request.topic}进行全面分析和阐述。通过对相关数据的收集整理和深入分析，为决策提供参考依据。

二、主要内容
────────────
{self._generate_report_sections(request)}

三、分析与发现
────────────
基于上述内容分析，我们发现：

1. 主要趋势：{request.topic}呈现出积极的发展态势
2. 关键因素：多个方面共同作用推动了发展
3. 存在挑战：仍需关注和解决一些问题

四、结论与建议
────────────
综合以上分析，提出以下建议：

✅ 建议1：持续关注{request.topic}的发展动态
✅ 建议2：加强相关方面的投入和支持  
✅ 建议3：建立完善的跟踪评估机制

五、附录
────────────
- 数据来源说明
- 相关参考资料
- 方法论概述

{'='*40}
*本报告由AI辅助生成，仅供参考*
"""
        
        return GeneratedContent(
            title=f"{request.topic} - 分析报告",
            content=report_content,
            content_type="report",
            word_count=len(report_content),
            generation_time=datetime.now().isoformat()
        )

    def _generate_social_media(self, request: GenerationRequest) -> GeneratedContent:
        """生成社交媒体内容"""
        
        import random
        
        platform_templates = {
            "微博": f"""【{request.topic}】

{self._get_social_content(request, 'weibo')}

#{request.topic.replace(' ', '')}# {' '.join(['#' + kw + '#' for kw in request.keywords[:3]]) if request.keywords else ''}

📍 分享你的看法吧~ 👇""",
            
            "朋友圈": f"""{self._get_social_content(request, 'moments')}

✨ {request.topic} ✨

{''.join([f'🏷️ {kw}\n' for kw in request.keywords[:3]]) if request.keywords else ''}""",

            "小红书": f"""📝 {request.topic}｜必看攻略✨

{self._get_social_content(request, 'xiaohongshu')}

{'\n'.join([f'🔸 {kw}' for kw in request.keywords[:5]]) if request.keywords else ''}

💬 你们觉得呢？评论区见~

#分享 #日常 #{request.topic[:10]}"""
        }
        
        # 选择一个平台模板
        platform = random.choice(list(platform_templates.keys()))
        content = platform_templates[platform]
        
        emoji_sets = ["✨", "🌟", "💫", "🔥", "💡", "🎯"]
        selected_emojis = random.sample(emoji_sets, min(3, len(emoji_sets)))
        
        return GeneratedContent(
            title=f"[{platform}] {request.topic}",
            content=content,
            content_type="social_media",
            word_count=len(content),
            generation_time=datetime.now().isoformat(),
            metadata={"platform": platform, "emojis": selected_emojis}
        )

    def _generate_creative(self, request: GenerationRequest) -> GeneratedContent:
        """生成创意写作内容"""
        
        import random
        
        creative_types = [
            ("微型小说", self._generate_short_story),
            ("现代诗", self._generate_poem),
            ("散文随笔", self._generate_essay),
            ("创意文案", self._generate_creative_copy)
        ]
        
        # 随机选择一种创意形式
        choice = random.choice(creative_types)
        content_type_name, generator_func = choice
        
        content = generator_func(request)
        
        return GeneratedContent(
            title=f"《{request.topic}》- {content_type_name}",
            content=content,
            content_type="creative",
            word_count=len(content),
            generation_time=datetime.now().isoformat(),
            metadata={"creative_type": content_type_name}
        )

    # 辅助方法：各种风格的引导语
    def _get_style_intro(self, style: str) -> str:
        intros = {
            "professional": "在当今竞争激烈的市场环境中，选择合适的产品和服务至关重要。",
            "casual": "嘿！今天想和大家聊聊一个超棒的东西～",
            "creative": "想象一下，如果有一个完美的解决方案...",
            "formal": "谨以此文向您郑重推介..."
        }
        return intros.get(style, intros["professional"])

    def _get_call_to_action(self, tone: str) -> str:
        actions = {
            "neutral": "📞 立即联系我们了解更多详情",
            "friendly": "🤗 别犹豫了，快来体验吧！",
            "persuasive": "🔥 限时优惠，错过再等一年！",
            "authoritative": "✅ 行业首选，值得信赖"
        }
        return actions.get(tone, actions["neutral"])

    def _get_email_body(self, request: GenerationRequest) -> str:
        return f"""关于{request.topic}一事，我想与您进行沟通和交流。
经过仔细考虑和分析，我认为这是一个值得关注的话题。
希望能得到您的反馈和建议。"""

    def _get_casual_email_body(self, request: GenerationRequest) -> str:
        return f"""I wanted to reach out about {request.topic}. It's been on my mind lately and I thought you might be interested in discussing it!
Thoughts?"""

    def _get_creative_email_body(self, request: GenerationRequest) -> str:
        return f"""Something exciting is happening with {request.topic} and I couldn't wait to share it with you!
It's amazing how creativity can transform ordinary topics into something extraordinary..."""

    def _extract_key_points(self, text: str) -> str:
        """提取关键点（简化版）"""
        lines = text.split('\n')
        points = []
        for i, line in enumerate(lines[:8], 1):
            if line.strip():
                points.append(f"{i}. {line.strip()[:80]}...")
        return '\n'.join(points) if points else "• 核心内容一\n• 核心内容二\n• 核心内容三"

    def _get_main_ideas(self, text: str) -> str:
        """获取主要观点（简化版）"""
        return f"""• 观点一：{text[:30]}相关的重要内容
• 观点二：需要重点关注的关键要素
• 观点三：未来发展的可能方向"""

    def _generate_report_sections(self, request: GenerationRequest) -> str:
        """生成报告章节内容"""
        sections = [
            f"1. {request.topic}的现状分析\n   当前情况和发展态势",
            f"2. 数据统计与趋势\n   基于数据的客观呈现",
            f"3. 问题识别与分析\n   发现的主要问题和挑战",
            f"4. 解决方案探讨\n   可能的解决思路和方法"
        ]
        return '\n\n'.join(sections)

    def _get_social_content(self, request: GenerationRequest, platform: str) -> str:
        """获取社交媒体内容"""
        contents = {
            "weibo": f"今天想跟大家聊聊{request.topic}，真的太有感触了！{request.topic}不仅...（更多精彩内容）",
            "moments": f"今天遇到了一件关于{request.topic}的事情，让我有了新的感悟。生活就是这样，总在不经意间给我们惊喜✨",
            "xiaohongshu": f"姐妹们！今天要给大家安利{request.topic}！真的绝绝子～\n\n亲测有效，强烈推荐给大家！"
        }
        return contents.get(platform, contents["weibo"])

    def _generate_short_story(self, request: GenerationRequest) -> str:
        """生成微型小说"""
        return f"""《{request.topic}》

在那个平凡的日子里，{request.topic}悄然走进了我们的生活。

起初，没有人注意到它的存在。直到有一天...

它像一颗种子，在时间的土壤里悄悄发芽。每一个清晨，它都在阳光下舒展；每一个夜晚，它都在月光下沉淀。

渐渐地，人们开始谈论它，思考它，甚至依赖它。

这就是{request.topic}的力量——平凡中蕴含着不凡，简单里藏着深意。

或许，最珍贵的事物，往往就藏在我们身边。

【完】"""

    def _generate_poem(self, request: GenerationRequest) -> str:
        """生成现代诗"""
        return f"""《致{request.topic}》

你是清晨的第一缕阳光，
照亮了沉睡的梦想；
你是夜空中的那颗星，
指引着前行的方向。

{request.topic}啊，
你不仅仅是文字的组合，
更是心灵的回响。

在时光的长河里，
你静静地流淌，
带着温暖，带着希望，
流向远方，永不遗忘。

——AI作于{datetime.now().strftime('%Y年%m月')}"""

    def _generate_essay(self, request: GenerationRequest) -> str:
        """生成散文随笔"""
        return f"""关于{request.topic}的随想

有时候，生活会给我们很多意想不到的礼物。而{request.topic}，就是其中之一。

记得第一次接触{request.topic}时，内心涌起的是一种莫名的感动。那种感觉，就像是在茫茫人海中遇到了知己，又像是在漫长的旅途中找到了方向。

{request.topic}教会了我们什么？或许是坚持的意义，或许是选择的智慧，又或许，仅仅是让我们学会了珍惜当下。

在这个快节奏的时代，能够静下心来感受{request.topic}的美好，本身就是一种奢侈。但正是这种奢侈，让我们的生活变得更加丰富和有意义。

愿我们都能在{request.topic}中找到属于自己的那份感动和力量。

【随笔】"""

    def _generate_creative_copy(self, request: GenerationRequest) -> str:
        """生成创意文案"""
        return f"""✨ {request.topic} ✨

当世界还在沉睡时，{request.topic}已经开始书写传奇。

这不是普通的{request.topic}，
这是经过千锤百炼的艺术品，
是灵感与匠心的完美融合。

每一个细节，都诉说着专注的故事；
每一次体验，都创造着难忘的记忆。

{request.topic}——
不只是{request.topic}，
更是一种态度，一种生活方式。

#创新无界 #匠心独运 #{request.topic}"""

    def _update_stats(self, request: GenerationRequest):
        """更新生成统计"""
        self.generation_stats["total_generations"] += 1
        
        # 按类型统计
        if request.content_type not in self.generation_stats["by_type"]:
            self.generation_stats["by_type"][request.content_type] = 0
        self.generation_stats["by_type"][request.content_type] += 1
        
        # 按风格统计
        if request.style not in self.generation_stats["by_style"]:
            self.generation_stats["by_style"][request.style] = 0
        self.generation_stats["by_style"][request.style] += 1

    def get_supported_types(self) -> Dict[str, Any]:
        """获取支持的所有内容类型"""
        return self.CONTENT_TYPES

    def get_statistics(self) -> Dict[str, Any]:
        """获取生成统计信息"""
        return self.generation_stats


if __name__ == "__main__":
    # 测试文案生成工具
    tool = TextGeneratorTool()
    
    print("\n===== 测试文案生成工具 =====\n")
    
    test_cases = [
        {
            "content_type": "marketing",
            "topic": "智能家居系统",
            "style": "professional",
            "length": "medium"
        },
        {
            "content_type": "email",
            "topic": "项目合作洽谈",
            "style": "formal"
        },
        {
            "content_type": "social_media",
            "topic": "健康生活方式",
            "keywords": ["运动", "饮食", "作息"]
        },
        {
            "content_type": "summary",
            "topic": "人工智能发展趋势",
            "context": "人工智能正在快速发展，在各个领域都有广泛应用..."
        }
    ]
    
    for i, params in enumerate(test_cases, 1):
        print(f"\n{i}. 测试 {params['content_type']} 类型:")
        result = tool.execute(**params)
        if result.success:
            print(f"   ✓ 生成成功 | 字数: {result.result_data['word_count']}")
            print(f"   标题: {result.result_data['title']}")
            # 只显示部分内容预览
            preview = result.result_data['content'][:200]
            print(f"   预览: {preview}...")
        else:
            print(f"   ✗ 生成失败: {result.error_message}")
    
    # 显示统计
    stats = tool.get_statistics()
    print(f"\n📊 生成统计:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))
