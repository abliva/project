# 数据采集与可视化后台系统

支持采集→缓存→存储→API→可视化全链路的后台系统，自实现 LRU 缓存，集成定时采集与 ECharts 可视化。

## 解决什么问题

数据采集系统常见痛点：接口响应慢（无缓存）、数据库连接频繁创建销毁（无连接池）、数据无法直观查看（无可视化）。本项目通过 LRU 缓存、连接池、可视化看板解决这些问题。

## 技术栈

- **Web框架**：Flask
- **数据库**：MySQL（生产）/ SQLite（开发）
- **缓存**：自实现 LRU（双向链表 + 哈希表）
- **爬虫**：多线程爬虫
- **定时任务**：APScheduler
- **可视化**：ECharts

## 核心模块

```
api/routes.py         # RESTful API（分页查询、CSV导出）
services/
├── crawler.py        # 多线程爬虫
├── cache.py          # LRU 缓存（TTL + 命中率统计）
├── data_processor.py # 数据清洗
└── database.py       # MySQL 连接池
tasks/scheduler.py    # APScheduler 定时采集
static/index.html     # ECharts 可视化看板
```

## 快速开始

```bash
pip install -r requirements.txt

# 配置 MySQL 连接（编辑 config.py）
# 或使用 SQLite（开发模式）

python app.py
# 访问 http://localhost:5001
```

## 核心特性

1. **LRU 缓存**：双向链表 + 哈希表实现，O(1) 读写，支持 TTL 过期与命中率统计
2. **连接池**：复用数据库连接，避免频繁创建销毁
3. **多线程爬虫**：并发采集，提升效率
4. **定时采集**：APScheduler 定时执行采集任务
5. **可视化看板**：ECharts 展示数据趋势

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/data` | GET | 分页查询数据 |
| `/api/data/export` | GET | CSV 批量导出 |
| `/api/collect` | POST | 手动触发采集 |
| `/api/stats` | GET | 缓存命中率统计 |
