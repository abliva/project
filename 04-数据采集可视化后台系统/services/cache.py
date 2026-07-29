# -*- coding: utf-8 -*-
"""
LRU本地缓存模块 + TTL过期策略 + 命中率统计
功能：
1. 基于双向链表+哈希表的LRU Cache实现
2. 支持TTL（Time To Live）过期时间设置
3. 缓存容量限制，超出时自动淘汰最久未使用的缓存项
4. 命中率统计与性能监控
5. 线程安全设计（支持多线程环境）
6. 支持批量操作和条件查询
"""

import time
import threading
import logging
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

# 配置日志
logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """缓存条目数据类"""
    key: Any  # 缓存键
    value: Any  # 缓存值
    created_at: float  # 创建时间戳
    expires_at: float  # 过期时间戳（0表示永不过期）
    access_count: int = 0  # 访问次数（用于统计热度）
    size: int = 1  # 占用空间大小（可用于更精细的容量控制）


class LRUCache:
    """
    LRU（Least Recently Used）最近最少使用缓存实现
    
    特性：
    - O(1) 时间复杂度的get/set操作
    - 自动淘汰最久未访问的缓存项
    - 支持TTL过期机制
    - 内置命中率统计
    - 线程安全（使用互斥锁）
    
    使用示例：
    >>> cache = LRUCache(maxsize=100, default_ttl=300)
    >>> cache.set('key1', 'value1', ttl=60)
    >>> value = cache.get('key1')
    >>> stats = cache.get_stats()  # 查看命中率等统计信息
    """
    
    def __init__(self, maxsize: int = 1000, default_ttl: int = 300):
        """
        初始化LRU缓存
        
        参数:
            maxsize: 缓存最大容量（最多存储多少个缓存项）
            default_ttl: 默认TTL过期时间（秒），0表示永不过期
        """
        # 基础配置
        self.maxsize = maxsize  # 最大容量
        self.default_ttl = default_ttl  # 默认TTL（秒）
        
        # 核心数据结构：OrderedDict维护插入顺序（用于LRU淘汰策略）
        # Python 3.7+ 的dict本身有序，但OrderedDict提供了move_to_end()方法
        self.cache: OrderedDict[Any, CacheEntry] = OrderedDict()
        
        # 线程锁，保证多线程环境下操作的原子性
        self._lock = threading.RLock()
        
        # ===== 命中率统计相关 =====
        self.hits = 0  # 命中次数
        self.misses = 0  # 未命中次数
        self.evictions = 0  # 淘汰次数
        self.expirations = 0  # 过期清理次数
        
        # 当前实际存储的缓存项数量
        self.current_size = 0
        
        logger.info(f"✅ LRU缓存初始化完成 | 最大容量: {maxsize} | 默认TTL: {default_ttl}s")
    
    def _is_expired(self, entry: CacheEntry) -> bool:
        """
        检查缓存条目是否已过期
        
        参数:
            entry: 缓存条目对象
            
        返回:
            bool: True表示已过期，False表示未过期
        """
        if entry.expires_at == 0:
            return False  # expires_at为0表示永不过期
        return time.time() > entry.expires_at
    
    def _evict_if_needed(self):
        """
        当缓存超过最大容量时，淘汰最久未使用的缓存项（LRU策略）
        应该在持有锁的情况下调用此方法
        """
        while len(self.cache) > self.maxsize:
            # OrderedDict的第一个元素就是最久未访问的（LRU尾部）
            oldest_key, oldest_entry = self.cache.popitem(last=False)
            self.evictions += 1
            self.current_size -= 1
            logger.debug(f"🗑️ 淘汰缓存项 | Key: {oldest_key} | 原因: 达到容量上限")
    
    def _cleanup_expired(self) -> int:
        """
        清理所有已过期的缓存项
        
        返回:
            int: 清理掉的过期缓存项数量
        """
        current_time = time.time()
        expired_keys = []
        
        # 收集所有已过期的key
        for key, entry in self.cache.items():
            if entry.expires_at > 0 and current_time > entry.expires_at:
                expired_keys.append(key)
        
        # 删除过期的缓存项
        for key in expired_keys:
            del self.cache[key]
            self.current_size -= 1
            self.expirations += 1
        
        if expired_keys:
            logger.info(f"🧹 清理过期缓存 | 清理数量: {len(expired_keys)} | 当前容量: {self.current_size}/{self.maxsize}")
        
        return len(expired_keys)
    
    def get(self, key: Any, default: Any = None) -> Any:
        """
        获取缓存值
        
        参数:
            key: 缓存键
            default: 未命中时的默认返回值
            
        返回:
            Any: 缓存的值，如果不存在或已过期则返回default
        """
        with self._lock:
            # 检查缓存是否存在
            if key not in self.cache:
                self.misses += 1
                logger.debug(f"💔 缓存未命中 | Key: {key}")
                return default
            
            entry = self.cache[key]
            
            # 检查是否过期
            if self._is_expired(entry):
                # 删除过期项
                del self.cache[key]
                self.current_size -= 1
                self.misses += 1
                self.expirations += 1
                logger.debug(f"⏰ 缓存已过期 | Key: {key}")
                return default
            
            # 命中！移动到OrderedDict末尾（标记为最近使用）
            self.cache.move_to_end(key)
            
            # 更新统计信息
            self.hits += 1
            entry.access_count += 1
            
            logger.debug(f"✅ 缓存命中 | Key: {key} | 访问次数: {entry.access_count}")
            
            return entry.value
    
    def set(self, key: Any, value: Any, ttl: int = None) -> bool:
        """
        设置缓存值
        
        参数:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），如果为None则使用默认TTL，0表示永不过期
            
        返回:
            bool: 设置是否成功
        """
        with self._lock:
            current_time = time.time()
            
            # 如果key已存在，先删除旧值
            if key in self.cache:
                del self.cache[key]
                self.current_size -= 1
                logger.debug(f"🔄 更新已有缓存 | Key: {key}")
            
            # 计算过期时间
            if ttl is None:
                ttl = self.default_ttl
            
            expires_at = 0 if ttl == 0 else (current_time + ttl)
            
            # 创建新的缓存条目
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=current_time,
                expires_at=expires_at,
                access_count=0,
                size=1
            )
            
            # 添加到缓存（OrderedDict末尾表示最新访问）
            self.cache[key] = entry
            self.current_size += 1
            
            # 检查是否需要淘汰旧缓存
            self._evict_if_needed()
            
            logger.debug(f"💾 设置缓存 | Key: {key} | TTL: {ttl}s | 当前容量: {self.current_size}/{self.maxsize}")
            
            return True
    
    def delete(self, key: Any) -> bool:
        """
        删除指定缓存项
        
        参数:
            key: 要删除的缓存键
            
        返回:
            bool: 是否成功删除（如果key不存在则返回False）
        """
        with self._lock:
            if key in self.cache:
                del self.cache[key]
                self.current_size -= 1
                logger.debug(f"🗑️ 删除缓存 | Key: {key}")
                return True
            return False
    
    def exists(self, key: Any) -> bool:
        """
        检查缓存是否存在且未过期（不会更新访问顺序）
        
        参数:
            key: 缓存键
            
        返回:
            bool: 缓存是否存在且有效
        """
        with self._lock:
            if key not in self.cache:
                return False
            
            entry = self.cache[key]
            if self._is_expired(entry):
                # 过期了就删除
                del self.cache[key]
                self.current_size -= 1
                self.expirations += 1
                return False
            
            return True
    
    def clear(self):
        """
        清空所有缓存
        """
        with self._lock:
            cleared_count = len(self.cache)
            self.cache.clear()
            self.current_size = 0
            logger.info(f"🧹 清空全部缓存 | 清理数量: {cleared_count}")
    
    def cleanup(self) -> int:
        """
        手动触发过期缓存清理（通常由定时任务或外部调度调用）
        
        返回:
            int: 清理掉的过期缓存项数量
        """
        with self._lock:
            return self._cleanup_expired()
    
    def keys(self) -> List[Any]:
        """
        获取所有有效的缓存键列表
        
        返回:
            list: 缓存键列表
        """
        with self._lock:
            # 先清理过期项
            self._cleanup_expired()
            return list(self.cache.keys())
    
    def values(self) -> List[Any]:
        """
        获取所有有效的缓存值列表
        
        返回:
            list: 缓存值列表
        """
        with self._lock:
            self._cleanup_expired()
            return [entry.value for entry in self.cache.values()]
    
    def items(self) -> List[Tuple[Any, Any]]:
        """
        获取所有有效的缓存键值对列表
        
        返回:
            list: (key, value) 元组列表
        """
        with self._lock:
            self._cleanup_expired()
            return [(key, entry.value) for key, entry in self.cache.items()]
    
    def get_size(self) -> int:
        """
        获取当前缓存的实际项目数量（不包括过期项）
        
        返回:
            int: 当前缓存项数量
        """
        with self._lock:
            self._cleanup_expired()
            return self.current_size
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息和命中率数据
        
        返回:
            dict: 统计信息字典，包含以下字段：
                  - hits: 命中次数
                  - misses: 未命中次数
                  - hit_rate: 命中率（百分比）
                  - evictions: 淘汰次数
                  - expirations: 过期清理次数
                  - current_size: 当前缓存项数
                  - maxsize: 最大容量
                  - usage_rate: 容量使用率（百分比）
        """
        with self._lock:
            total_requests = self.hits + self.misses
            hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
            usage_rate = (self.current_size / self.maxsize * 100) if self.maxsize > 0 else 0
            
            return {
                'hits': self.hits,
                'misses': self.misses,
                'total_requests': total_requests,
                'hit_rate': round(hit_rate, 2),
                'evictions': self.evictions,
                'expirations': self.expirations,
                'current_size': self.current_size,
                'maxsize': self.maxsize,
                'usage_rate': round(usage_rate, 2),
                'timestamp': time.time()
            }
    
    def reset_stats(self):
        """
        重置统计数据（不影响缓存数据本身）
        """
        with self._lock:
            self.hits = 0
            self.misses = 0
            self.evictions = 0
            self.expirations = 0
            logger.info("📊 缓存统计数据已重置")
    
    def get_hot_keys(self, top_n: int = 10) -> List[Tuple[Any, int]]:
        """
        获取访问频率最高的缓存键（热门Key）
        
        参数:
            top_n: 返回前N个热门Key
            
        返回:
            list: [(key, access_count)] 元组列表，按访问次数降序排列
        """
        with self._lock:
            # 按访问次数排序
            sorted_items = sorted(
                self.cache.items(),
                key=lambda x: x[1].access_count,
                reverse=True
            )
            
            # 返回前top_n个
            return [(key, entry.access_count) for key, entry in sorted_items[:top_n]]
    
    def set_many(self, data: Dict[Any, Any], ttl: int = None) -> int:
        """
        批量设置缓存
        
        参数:
            data: {key: value} 字典
            ttl: 统一的TTL过期时间
            
        返回:
            int: 成功设置的缓存项数量
        """
        count = 0
        for key, value in data.items():
            if self.set(key, value, ttl):
                count += 1
        logger.info(f"📦 批量设置缓存 | 数量: {count}")
        return count
    
    def get_many(self, keys: List[Any]) -> Dict[Any, Any]:
        """
        批量获取缓存
        
        参数:
            keys: 缓存键列表
            
        返回:
            dict: {key: value} 字典（只包含命中且未过期的项）
        """
        result = {}
        for key in keys:
            value = self.get(key)
            if value is not None:
                result[key] = value
        return result
    
    def __len__(self) -> int:
        """返回当前缓存项数量"""
        return self.get_size()
    
    def __contains__(self, key: Any) -> bool:
        """支持 'in' 操作符"""
        return self.exists(key)
    
    def __repr__(self) -> str:
        """对象的字符串表示"""
        stats = self.get_stats()
        return (f"<LRUCache size={stats['current_size']}/{stats['maxsize']} "
                f"hit_rate={stats['hit_rate']}%>")


# ==================== 全局缓存实例（单例模式）====================
# 在应用启动时初始化的全局缓存实例
_global_cache: Optional[LRUCache] = None
_cache_lock = threading.Lock()


def get_cache(maxsize: int = 1000, default_ttl: int = 300) -> LRUCache:
    """
    获取全局缓存实例（单例模式）
    保证整个应用共享同一个缓存实例
    
    参数:
        maxsize: 缓存最大容量
        default_ttl: 默认TTL过期时间（秒）
        
    返回:
        LRUCache: 全局缓存实例
    """
    global _global_cache
    
    if _global_cache is None:
        with _cache_lock:
            # 双重检查锁定（Double-Checked Locking）
            if _global_cache is None:
                _global_cache = LRUCache(maxsize=maxsize, default_ttl=default_ttl)
                logger.info("🌐 全局缓存实例已创建")
    
    return _global_cache


def init_cache(config=None):
    """
    初始化全局缓存（在应用启动时调用）
    
    参数:
        config: 缓存配置字典，包含maxsize、default_ttl等参数
    """
    global _global_cache
    
    if config is None:
        from config import CacheConfig
        config = CacheConfig.__dict__
    
    maxsize = config.get('CACHE_MAX_SIZE', 1000)
    default_ttl = config.get('CACHE_DEFAULT_TTL', 300)
    
    _global_cache = LRUCache(maxsize=maxsize, default_ttl=default_ttl)
    logger.info(f"✅ 全局缓存初始化完成 | 容量: {maxsize} | TTL: {default_ttl}s")


# ==================== 使用示例 ====================
if __name__ == '__main__':
    print("=" * 60)
    print("🧪 LRU缓存测试")
    print("=" * 60)
    
    # 创建缓存实例（容量5，默认TTL 10秒）
    cache = LRUCache(maxsize=5, default_ttl=10)
    
    # 1. 基本set/get操作
    print("\n1️⃣ 基本操作测试:")
    cache.set('user:1', {'name': '张三', 'age': 25})
    cache.set('user:2', {'name': '李四', 'age': 30})
    cache.set('config:app', {'debug': True, 'version': '1.0'})
    
    user1 = cache.get('user:1')
    print(f"获取 user:1 = {user1}")
    
    nonexistent = cache.get('user:999', default='默认值')
    print(f"获取不存在的 key = {nonexistent}")
    
    # 2. 测试LRU淘汰策略
    print("\n2️⃣ LRU淘汰测试（容量只有5）:")
    for i in range(6):
        cache.set(f'item:{i}', f'value_{i}')
        print(f"  设置 item:{i}, 当前容量: {cache.get_size()}")
    
    # item:0应该已经被淘汰了
    item0 = cache.get('item:0')
    print(f"  item:0 是否还存在? {item0 is not None}")
    
    # 3. 测试TTL过期
    print("\n3️⃣ TTL过期测试（设置2秒过期）:")
    cache.set('temp:data', '临时数据', ttl=2)
    print(f"  立即获取: {cache.get('temp:data')}")
    
    import time
    print("  ⏳ 等待3秒...")
    time.sleep(3)
    
    after_expire = cache.get('temp:data')
    print(f"  3秒后获取: {after_expire} (应该为None)")
    
    # 4. 命中率统计
    print("\n4️⃣ 命中率统计:")
    # 连续多次访问同一个key
    for _ in range(10):
        cache.get('user:1')
    
    # 多次访问不存在的key
    for _ in range(5):
        cache.get('nonexistent:key')
    
    stats = cache.get_stats()
    print(f"  📊 统计信息:")
    print(f"     命中次数: {stats['hits']}")
    print(f"     未命中次数: {stats['misses']}")
    print(f"     命中率: {stats['hit_rate']}%")
    print(f"     淘汰次数: {stats['evictions']}")
    print(f"     过期清理: {stats['expirations']}")
    print(f"     当前容量: {stats['current_size']}/{stats['maxsize']}")
    print(f"     使用率: {stats['usage_rate']}%")
    
    # 5. 热门Key分析
    print("\n5️⃣ 热门Key Top 5:")
    hot_keys = cache.get_hot_keys(top_n=5)
    for key, access_count in hot_keys:
        print(f"     {key}: {access_count}次访问")
    
    # 6. 批量操作
    print("\n6️⃣ 批量操作测试:")
    batch_data = {
        'batch:1': '数据A',
        'batch:2': '数据B',
        'batch:3': '数据C'
    }
    cache.set_many(batch_data, ttl=60)
    
    batch_result = cache.get_many(['batch:1', 'batch:2', 'batch:3', 'batch:99'])
    print(f"  批量获取结果: {list(batch_result.keys())}")
    
    # 7. 清理与清空
    print("\n7️⃣ 清理测试:")
    cache.set('will_expire', '即将过期', ttl=1)
    time.sleep(2)
    
    cleaned = cache.cleanup()
    print(f"  手动清理过期项: {cleaned}个")
    
    print(f"\n  最终缓存对象: {cache}")
    
    print("\n" + "=" * 60)
    print("✅ 所有测试完成!")
    print("=" * 60)
