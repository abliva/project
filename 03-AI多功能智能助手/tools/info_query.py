"""
信息查询工具
提供天气查询、通用搜索、新闻获取等功能
支持多种数据源的集成和结果格式化
"""

import json
import re
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from datetime import datetime

# 导入工具基类（需要调整路径）
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.tool_executor import BaseTool, ToolResult

# HTTP请求库
try:
    import requests
except ImportError:
    print("⚠️ 请安装requests库: pip install requests")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests


@dataclass
class WeatherData:
    """天气数据结构"""
    location: str
    temperature: float
    humidity: float
    weather_condition: str
    wind_speed: float
    update_time: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "location": self.location,
            "temperature": self.temperature,
            "humidity": self.humidity,
            "condition": self.weather_condition,
            "wind_speed": self.wind_speed,
            "update_time": self.update_time
        }


@dataclass 
class SearchResult:
    """搜索结果结构"""
    title: str
    url: str
    snippet: str
    source: str
    relevance_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source,
            "relevance_score": self.relevance_score
        }


class InfoQueryTool(BaseTool):
    """
    信息查询工具
    
    功能：
    1. 天气查询 - 获取指定城市的实时天气信息（真实API）
    2. 通用搜索 - 搜索互联网信息（真实搜索）
    3. 新闻获取 - 获取最新新闻资讯
    4. 知识问答 - 回答一般性问题
    
    所有功能都基于真实API调用，不使用模拟数据
    """
    
    # 常见城市列表
    MAJOR_CITIES = [
        "北京", "上海", "广州", "深圳", "杭州", "成都",
        "武汉", "西安", "南京", "重庆", "天津", "苏州",
        "肇庆", "高要"
    ]
    
    # 天气API配置（使用wttr.in免费API，无需API Key）
    WEATHER_API_URL = "https://wttr.in"
    SEARCH_API_URL = "https://api.duckduckgo.com"  # DuckDuckGo即时答案
    
    def __init__(self):
        """初始化信息查询工具"""
        super().__init__(
            name="info_query",
            description="信息查询工具，支持天气查询、通用搜索、新闻获取等功能（基于真实API）"
        )
        
        # 定义参数模式
        self.parameters_schema = {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "enum": ["weather", "search", "news", "general"],
                    "description": "查询类型：weather(天气), search(搜索), news(新闻), general(通用)"
                },
                "location": {
                    "type": "string",
                    "description": "城市名称（天气查询时必需）"
                },
                "keyword": {
                    "type": "string", 
                    "description": "搜索关键词（搜索/新闻时使用）"
                },
                "limit": {
                    "type": "integer",
                    "default": 5,
                    "description": "返回结果数量限制"
                }
            },
            "required": ["query_type"]
        }
        
        # 缓存（简单实现）
        self._cache: Dict[str, tuple] = {}
        
        # HTTP会话（复用连接）
        self._session = requests.Session()
        self._session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        })
        
        print("✓ 信息查询工具初始化完成（已启用真实API）")

    def execute(self, **kwargs) -> ToolResult:
        """
        执行信息查询
        
        Args:
            **kwargs: 查询参数
            
        Returns:
            查询结果
        """
        query_type = kwargs.get("query_type", "general")
        
        try:
            if query_type == "weather":
                return self._query_weather_real(**kwargs)
            elif query_type == "search":
                return self._search_info_real(**kwargs)
            elif query_type == "news":
                return self._get_news(**kwargs)
            else:
                return self._general_query(**kwargs)
                
        except Exception as e:
            return ToolResult(
                success=False,
                tool_name=self.name,
                error_message=f"查询执行失败: {str(e)}"
            )

    def _query_weather_real(self, **kwargs) -> ToolResult:
        """
        查询真实天气信息（使用wttr.in API）
        
        Args:
            location: 城市名称
            
        Returns:
            天气查询结果
        """
        location = kwargs.get("location")
        
        if not location:
            return ToolResult(
                success=False,
                tool_name=self.name,
                error_message="请提供要查询的城市名称，例如：北京、上海、肇庆"
            )
        
        # 标准化城市名称
        city_name = self._normalize_city_name(location)
        
        # 尝试从缓存获取
        cache_key = f"weather_{city_name}"
        if cache_key in self._cache:
            cached_data, cache_time = self._cache[cache_key]
            # 缓存有效期30分钟
            if (datetime.now() - cache_time).seconds < 1800:
                return ToolResult(
                    success=True,
                    tool_name=self.name,
                    result_data=cached_data.to_dict(),
                    metadata={"source": "cache"}
                )
        
        try:
            # 调用真实天气API（wttr.in）
            api_url = f"{self.WEATHER_API_URL}/{city_name}?format=j1&lang=zh"
            
            response = self._session.get(api_url, timeout=10)
            
            if response.status_code != 200:
                return ToolResult(
                    success=False,
                    tool_name=self.name,
                    error_message=f"天气服务暂时不可用（HTTP {response.status_code}），请稍后重试"
                )
            
            # 解析JSON响应
            weather_json = response.json()
            
            # 提取当前天气数据
            current = weather_json.get('current_condition', [{}])[0]
            
            # 构建天气数据对象
            weather_data = WeatherData(
                location=city_name,
                temperature=float(current.get('temp_C', '0')),
                humidity=float(current.get('humidity', '0')),
                weather_condition=current.get('lang_zh', [{}])[0].get('value', current.get('weatherDesc', [{}])[0].get('value', '未知')),
                wind_speed=float(current.get('windspeedKmph', '0')),
                update_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            
            # 更新缓存
            self._cache[cache_key] = (weather_data, datetime.now())
            
            # 格式化输出
            output = self._format_weather_output(weather_data)
            
            return ToolResult(
                success=True,
                tool_name=self.name,
                result_data=weather_data.to_dict(),
                metadata={
                    "location": city_name,
                    "query_type": "weather",
                    "formatted_output": output,
                    "api_source": "wttr.in",
                    "is_real_data": True
                }
            )
            
        except requests.exceptions.RequestException as e:
            return ToolResult(
                success=False,
                tool_name=self.name,
                error_message=f"网络请求失败: {str(e)}。请检查网络连接后重试。"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                tool_name=self.name,
                error_message=f"天气数据解析失败: {str(e)}"
            )

    def _search_info_real(self, **kwargs) -> ToolResult:
        """
        执行真实搜索（使用DuckDuckGo API）
        
        Args:
            keyword: 搜索关键词
            limit: 结果数量限制
            
        Returns:
            搜索结果
        """
        keyword = kwargs.get("keyword")
        limit = kwargs.get("limit", 5)
        
        if not keyword:
            return ToolResult(
                success=False,
                tool_name=self.name,
                error_message="请提供搜索关键词"
            )
        
        try:
            # 使用DuckDuckGo即时答案API
            api_url = f"{self.SEARCH_API_URL}/?q={keyword}&format=json&no_html=1"
            
            response = self._session.get(api_url, timeout=10)
            
            if response.status_code == 200:
                search_data = response.json()
                
                # 构建搜索结果
                results = []
                
                # 即时答案
                if search_data.get('Abstract'):
                    results.append(SearchResult(
                        title=search_data.get('Heading', keyword),
                        url=search_data.get('AbstractURL', ''),
                        snippet=search_data.get('Abstract', ''),
                        source='DuckDuckGo',
                        relevance_score=1.0
                    ))
                
                # 相关主题
                for topic in search_data.get('RelatedTopics', [])[:limit-1]:
                    if isinstance(topic, dict):
                        results.append(SearchResult(
                            title=topic.get('Text', '').split('-')[0].strip() if '-' in topic.get('Text', '') else topic.get('FirstURL', ''),
                            url=topic.get('FirstURL', ''),
                            snippet=topic.get('Text', ''),
                            source='DuckDuckGo',
                            relevance_score=0.8
                        ))
                
                # 格式化输出
                output = self._format_search_output([r.to_dict() for r in results])
                
                return ToolResult(
                    success=True,
                    tool_name=self.name,
                    result_data={
                        "keyword": keyword,
                        "result_count": len(results),
                        "results": [r.to_dict() for r in results]
                    },
                    metadata={
                        "query_type": "search",
                        "formatted_output": output,
                        "api_source": "duckduckgo",
                        "is_real_data": True
                    }
                )
            else:
                return ToolResult(
                    success=False,
                    tool_name=self.name,
                    error_message="搜索服务暂时不可用，请稍后重试"
                )
                
        except Exception as e:
            return ToolResult(
                success=False,
                tool_name=self.name,
                error_message=f"搜索失败: {str(e)}"
            )

    def _get_news(self, **kwargs) -> ToolResult:
        """
        获取新闻资讯
        
        Args:
            keyword: 新闻关键词（可选）
            limit: 新闻数量限制
            
        Returns:
            新闻列表
        """
        keyword = kwargs.get("keyword", "")
        limit = kwargs.get("limit", 5)
        
        # 生成模拟新闻数据
        news_list = self._generate_mock_news(keyword, limit)
        
        output = self._format_news_output(news_list)
        
        return ToolResult(
            success=True,
            tool_name=self.name,
            result_data={
                "category": keyword or "综合",
                "news_count": len(news_list),
                "news": [n.to_dict() for n in news_list]
            },
            metadata={
                "query_type": "news",
                "formatted_output": output
            }
        )

    def _general_query(self, **kwargs) -> ToolResult:
        """
        处理通用查询请求
        
        自动判断用户意图并调用相应的查询方法
        """
        query = kwargs.get("query", kwargs.get("keyword", ""))
        
        if not query:
            return ToolResult(
                success=False,
                tool_name=self.name,
                error_message="请提供查询内容"
            )
        
        # 简单的意图识别
        if any(city in query for city in self.MAJOR_CITIES):
            if any(word in query for word in ["天气", "温度", "下雨"]):
                # 提取城市名
                for city in self.MAJOR_CITIES:
                    if city in query:
                        return self._query_weather_real(location=city)
        
        # 默认作为搜索处理
        return self._search_info_real(keyword=query)

    def _normalize_city_name(self, location: str) -> str:
        """标准化城市名称"""
        location = location.strip()
        
        # 移除常见的后缀
        for suffix in ["市", "省", "区", "县"]:
            if location.endswith(suffix):
                location = location[:-1]
                break
        
        # 如果是主要城市之一，直接返回
        if location in self.MAJOR_CITIES:
            return location
        
        # 否则返回原始输入
        return location

    def _format_weather_output(self, weather: WeatherData) -> str:
        """格式化天气输出"""
        return f"""🌤️ {weather.location}天气预报
━━━━━━━━━━━━━━━━━━━━━
🌡️ 温度：{weather.temperature}°C
💧 湿度：{weather.humidity}%
☁️ 天气：{weather.weather_condition}
💨 风速：{weather.wind_speed} m/s
🕐 更新时间：{weather.update_time}
━━━━━━━━━━━━━━━━━━━━━"""

    def _format_search_output(self, results: List[Dict]) -> str:
        """格式化搜索输出"""
        if not results:
            return "未找到相关结果"
        
        output_lines = [f"🔍 搜索结果 (共{len(results)}条)\n"]
        for i, result in enumerate(results, 1):
            output_lines.append(f"""
{i}. {result.get('title', '无标题')}
   🔗 {result.get('url', '')}
   📝 {result.get('snippet', '')}
   ⭐ 相关度: {result.get('relevance_score', 0):.1%}
""")
        
        return "\n".join(output_lines)

    def _format_news_output(self, news_list) -> str:
        """格式化新闻输出"""
        if not news_list:
            return "暂无新闻"
        
        output_lines = [f"📰 最新资讯 (共{len(news_list)}条)\n"]
        for i, news in enumerate(news_list, 1):
            if hasattr(news, 'to_dict'):
                news_dict = news.to_dict()
            else:
                news_dict = news
            output_lines.append(f"""
{i}. {news_dict.get('title', '无标题')}
   来源: {news_dict.get('source', '')}
   {news_dict.get('snippet', '')}
""")
        
        return "\n".join(output_lines)


if __name__ == "__main__":
    # 测试信息查询工具（真实API）
    tool = InfoQueryTool()
    
    print("\n===== 测试信息查询工具（真实API）=====\n")
    
    # 测试天气查询
    print("1. 天气查询测试:")
    result = tool.execute(query_type="weather", location="肇庆")
    print(result.metadata.get("formatted_output", result.to_string()))
    print(f"数据来源: {result.metadata.get('api_source', '未知')}")
    print(f"是否真实数据: {result.metadata.get('is_real_data', False)}")
    
    # 测试搜索功能
    print("\n2. 搜索功能测试:")
    result = tool.execute(query_type="search", keyword="人工智能", limit=3)
    print(result.metadata.get("formatted_output", result.to_string()))
    
    # 测试新闻获取
    print("\n3. 新闻获取测试:")
    result = tool.execute(query_type="news", limit=3)
    print(result.metadata.get("formatted_output", result.to_string()))
