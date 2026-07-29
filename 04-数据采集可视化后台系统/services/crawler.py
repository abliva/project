# -*- coding: utf-8 -*-
"""
通用爬虫框架 - 定向爬虫模块（多渠道数据抓取）
功能：
1. 支持多数据源配置（网页API、数据库、文件等）
2. 请求头管理与随机User-Agent
3. 反爬策略（请求间隔、代理池、Cookie管理）
4. 多线程并发采集
5. 请求重试机制与异常处理
6. 数据采集日志记录
"""

import time
import random
import threading
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

# 配置日志记录器
logger = logging.getLogger(__name__)


@dataclass
class CrawlResult:
    """爬虫结果数据类"""
    success: bool  # 是否成功
    url: str  # 请求的URL
    data: Optional[Any] = None  # 获取到的数据（可以是文本、JSON、字典等）
    status_code: Optional[int] = None  # HTTP状态码
    error_message: Optional[str] = None  # 错误信息
    crawl_time: Optional[float] = None  # 爬取耗时（秒）
    headers: Optional[Dict] = None  # 响应头


class DataCrawler:
    """
    通用数据采集器
    
    提供完整的网页/API数据抓取功能，支持：
    - 单URL采集和批量URL采集
    - 自定义请求头、Cookie、代理
    - 自动重试和错误处理
    - 多线程并发加速
    - 反爬虫策略应对
    """
    
    def __init__(self, config=None):
        """
        初始化爬虫实例
        
        参数:
            config: 爬虫配置字典，包含timeout、retries等参数
                   如果为None，使用默认配置
        """
        # 加载配置（从config.py导入或使用默认值）
        self.config = config or {}
        
        # 基础配置
        self.timeout = self.config.get('CRAWLER_REQUEST_TIMEOUT', 30)
        self.max_retries = self.config.get('CRAWLER_MAX_RETRIES', 3)
        self.retry_delay = self.config.get('CRAWLER_RETRY_DELAY', 1.0)
        
        # 并发配置
        self.thread_pool_size = self.config.get('CRAWLER_THREAD_POOL_SIZE', 5)
        self.concurrent_requests = self.config.get('CRAWLER_CONCURRENT_REQUESTS', 10)
        
        # User-Agent列表（模拟不同浏览器）
        self.user_agents = self.config.get('CRAWLER_USER_AGENTS', [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        ])
        
        # 请求延迟范围（秒）- 避免被封禁
        self.delay_min = self.config.get('CRAWLER_REQUEST_DELAY_MIN', 0.5)
        self.delay_max = self.config.get('CRAWLER_REQUEST_DELAY_MAX', 2.0)
        
        # 代理配置
        self.proxy_enabled = self.config.get('CRAWLER_PROXY_ENABLED', False)
        self.proxy_list = self.config.get('CRAWLER_PROXY_LIST', [])
        self._current_proxy_index = 0
        
        # Cookie存储
        self.cookies = {}
        self.session_cookies = {}
        
        # 创建线程锁，保证线程安全
        self._lock = threading.Lock()
        
        # 统计信息
        self.stats = {
            'total_requests': 0,
            'success_count': 0,
            'failed_count': 0,
            'total_time': 0.0
        }
        
        # 初始化requests Session（带连接池和重试机制）
        self.session = self._create_session()
        
        logger.info(f"✅ 爬虫初始化完成 | 超时:{self.timeout}s | 重试:{self.max_retries}次 | 线程数:{self.thread_pool_size}")
    
    def _create_session(self):
        """
        创建带有连接池和自动重试机制的requests Session
        
        返回:
            Session: 配置好的requests会话对象
        """
        session = requests.Session()
        
        # 配置自动重试策略
        retry_strategy = Retry(
            total=self.max_retries,  # 总重试次数
            backoff_factor=self.retry_delay,  # 重试间隔递增因子
            status_forcelist=[429, 500, 502, 503, 504],  # 需要重试的HTTP状态码
            allowed_methods=["HEAD", "GET", "OPTIONS"]  # 允许重试的HTTP方法
        )
        
        # 挂载到HTTP和HTTPS适配器
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,  # 连接池大小
            pool_maxsize=self.thread_pool_size  # 最大连接数
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _get_random_user_agent(self) -> str:
        """
        随机获取一个User-Agent字符串
        
        返回:
            str: User-Agent字符串
        """
        return random.choice(self.user_agents)
    
    def _get_random_proxy(self) -> Optional[Dict[str, str]]:
        """
        从代理列表中轮询获取一个代理
        
        返回:
            dict: 代理配置 {'http': 'url', 'https': 'url'}
                  如果未启用代理或列表为空则返回None
        """
        if not self.proxy_enabled or not self.proxy_list:
            return None
        
        with self._lock:
            proxy_url = self.proxy_list[self._current_proxy_index]
            self._current_proxy_index = (self._current_proxy_index + 1) % len(self.proxy_list)
        
        return {
            'http': proxy_url,
            'https': proxy_url
        }
    
    def _get_headers(self, custom_headers: Dict = None) -> Dict:
        """
        构建请求头，合并默认头和自定义头
        
        参数:
            custom_headers: 用户自定义的请求头
            
        返回:
            dict: 合并后的完整请求头
        """
        headers = {
            'User-Agent': self._get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
        }
        
        if custom_headers:
            headers.update(custom_headers)
        
        return headers
    
    def _delay_request(self):
        """
        在请求之间添加随机延迟，避免被目标网站封禁
        实现反爬虫策略中的频率控制
        """
        delay = random.uniform(self.delay_min, self.delay_max)
        time.sleep(delay)
    
    def _make_request(self, url: str, method: str = 'GET', 
                      params: Dict = None, data: Dict = None,
                      json_data: Dict = None, 
                      custom_headers: Dict = None,
                      cookies: Dict = None,
                      timeout: int = None,
                      allow_redirects: bool = True) -> CrawlResult:
        """
        执行单次HTTP请求（核心方法）
        
        参数:
            url: 请求的目标URL
            method: HTTP方法 GET/POST/PUT/DELETE
            params: URL查询参数
            data: POST表单数据
            json_data: POST JSON数据
            custom_headers: 自定义请求头
            cookies: Cookie字典
            timeout: 超时时间（覆盖默认值）
            allow_redirects: 是否允许重定向
            
        返回:
            CrawlResult: 包含请求结果的封装对象
        """
        start_time = time.time()
        
        try:
            # 构建请求参数
            headers = self._get_headers(custom_headers)
            proxy = self._get_random_proxy()
            req_timeout = timeout or self.timeout
            
            # 合并Cookie
            merged_cookies = {**self.cookies}
            if cookies:
                merged_cookies.update(cookies)
            
            logger.debug(f"🔍 开始请求: {method} {url}")
            
            # 发送HTTP请求
            response = self.session.request(
                method=method.upper(),
                url=url,
                params=params,
                data=data,
                json=json_data,
                headers=headers,
                cookies=merged_cookies,
                proxies=proxy,
                timeout=req_timeout,
                allow_redirects=allow_redirects
            )
            
            # 计算耗时
            elapsed_time = time.time() - start_time
            
            # 更新统计信息
            with self._lock:
                self.stats['total_requests'] += 1
                self.stats['total_time'] += elapsed_time
                if response.status_code == 200:
                    self.stats['success_count'] += 1
                else:
                    self.stats['failed_count'] += 1
            
            # 保存服务器返回的Set-Cookie
            if response.cookies:
                self.session_cookies.update(response.cookies.get_dict())
            
            logger.info(f"✅ 请求成功 | URL: {url} | 状态码: {response.status_code} | 耗时: {elapsed_time:.2f}s")
            
            # 尝试解析JSON响应，否则返回文本
            try:
                result_data = response.json()
            except ValueError:
                result_data = response.text
            
            return CrawlResult(
                success=True,
                url=url,
                data=result_data,
                status_code=response.status_code,
                crawl_time=elapsed_time,
                headers=dict(response.headers)
            )
            
        except requests.exceptions.Timeout as e:
            error_msg = f"请求超时: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return CrawlResult(success=False, url=url, error_message=error_msg, crawl_time=time.time()-start_time)
            
        except requests.exceptions.ConnectionError as e:
            error_msg = f"连接错误: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return CrawlResult(success=False, url=url, error_message=error_msg, crawl_time=time.time()-start_time)
            
        except requests.exceptions.RequestException as e:
            error_msg = f"请求异常: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return CrawlResult(success=False, url=url, error_message=error_msg, crawl_time=time.time()-start_time)
            
        except Exception as e:
            error_msg = f"未知错误: {str(e)}"
            logger.error(f"❌ {error_msg}", exc_info=True)
            return CrawlResult(success=False, url=url, error_message=error_msg, crawl_time=time.time()-start_time)
    
    def crawl_single(self, url: str, **kwargs) -> CrawlResult:
        """
        爬取单个URL（公开接口）
        
        参数:
            url: 目标URL
            **kwargs: 其他请求参数（传递给_make_request）
            
        返回:
            CrawlResult: 爬取结果
        """
        # 添加请求延迟（反爬策略）
        self._delay_request()
        
        # 执行请求
        result = self._make_request(url, **kwargs)
        
        return result
    
    def crawl_batch(self, urls: List[str], **kwargs) -> List[CrawlResult]:
        """
        批量爬取多个URL（使用线程池并发执行）
        
        参数:
            urls: URL列表
            **kwargs: 请求参数（传递给每个请求）
            
        返回:
            list[CrawlResult]: 所有URL的爬取结果列表
        """
        results = []
        
        logger.info(f"🚀 开始批量爬取 | URL数量: {len(urls)} | 并发数: {self.thread_pool_size}")
        
        # 使用线程池并发执行
        with ThreadPoolExecutor(max_workers=self.thread_pool_size) as executor:
            # 提交所有任务
            future_to_url = {
                executor.submit(self.crawl_single, url, **kwargs): url 
                for url in urls
            }
            
            # 收集结果
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"❌ 批量任务异常 | URL: {url} | 错误: {str(e)}")
                    results.append(CrawlResult(success=False, url=url, error_message=str(e)))
        
        # 统计成功率
        success_count = sum(1 for r in results if r.success)
        total_time = sum(r.crawl_time for r in results if r.crawl_time)
        
        logger.info(f"✅ 批量爬取完成 | 成功: {success_count}/{len(results)} | 总耗时: {total_time:.2f}s")
        
        return results
    
    def parse_html(self, html_content: str, parser: str = 'lxml') -> BeautifulSoup:
        """
        解析HTML内容，返回BeautifulSoup对象
        
        参数:
            html_content: HTML字符串内容
            parser: 解析器类型（lxml/html.parser/html5lib）
            
        返回:
            BeautifulSoup: 解析后的对象，可用于CSS选择器/XPath提取数据
        """
        try:
            soup = BeautifulSoup(html_content, parser)
            logger.debug("✅ HTML解析成功")
            return soup
        except Exception as e:
            logger.error(f"❌ HTML解析失败: {str(e)}")
            raise
    
    def extract_by_css(self, soup: BeautifulSoup, css_selector: str, 
                       attribute: str = None) -> List[str]:
        """
        使用CSS选择器提取数据
        
        参数:
            soup: BeautifulSoup对象
            css_selector: CSS选择器表达式
            attribute: 要提取的属性名，如果为None则提取文本内容
            
        返回:
            list: 提取的数据列表
        """
        elements = soup.select(css_selector)
        results = []
        
        for elem in elements:
            if attribute:
                value = elem.get(attribute)
            else:
                value = elem.get_text(strip=True)
            
            if value:
                results.append(value)
        
        logger.debug(f"📊 CSS选择器提取 | 选择器: {css_selector} | 结果数: {len(results)}")
        return results
    
    def set_cookie(self, name: str, value: str):
        """
        设置Cookie（用于需要登录态的网站）
        
        参数:
            name: Cookie名称
            value: Cookie值
        """
        self.cookies[name] = value
        logger.debug(f"🍪 设置Cookie: {name}")
    
    def clear_cookies(self):
        """清除所有Cookie"""
        self.cookies.clear()
        self.session_cookies.clear()
        logger.info("🧹 已清除所有Cookie")
    
    def get_stats(self) -> Dict:
        """
        获取爬虫运行统计信息
        
        返回:
            dict: 统计信息字典，包括请求数、成功率、平均耗时等
        """
        total = self.stats['total_requests']
        success = self.stats['success_count']
        
        stats_dict = {
            **self.stats,
            'success_rate': (success / total * 100) if total > 0 else 0,
            'avg_time': (self.stats['total_time'] / total) if total > 0 else 0,
            'active_proxies': len(self.proxy_list) if self.proxy_enabled else 0,
            'session_created_at': datetime.now().isoformat()
        }
        
        return stats_dict
    
    def close(self):
        """
        关闭爬虫，释放资源
        应在程序退出时调用
        """
        if self.session:
            self.session.close()
            logger.info("🔒 爬虫Session已关闭")
    
    def __enter__(self):
        """支持上下文管理器协议"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文时自动关闭"""
        self.close()
        return False


# ==================== 使用示例 ====================
if __name__ == '__main__':
    # 示例：基本使用方式
    from config import CrawlerConfig
    
    # 创建爬虫实例
    crawler = DataCrawler(config=CrawlerConfig.__dict__)
    
    # 单个URL爬取
    result = crawler.crawl_single('https://httpbin.org/get')
    print(f"状态: {result.success}, 数据: {result.data}")
    
    # 批量URL爬取
    urls = [
        'https://httpbin.org/get',
        'https://httpbin.org/ip',
        'https://httpbin.org/headers'
    ]
    results = crawler.crawl_batch(urls)
    for r in results:
        print(f"URL: {r.url}, 成功: {r.success}")
    
    # 查看统计信息
    stats = crawler.get_stats()
    print(f"统计: {stats}")
    
    # 关闭爬虫
    crawler.close()
