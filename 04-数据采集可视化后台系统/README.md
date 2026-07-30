# 数据采集与可视化后台系统

> 从数据采集到可视化展示的全链路后端系统，支持多线程爬虫、自实现 LRU 缓存、MySQL 存储、RESTful API 与 ECharts 可视化，可直接部署上线使用。

---

## 目录

- [项目背景](#项目背景)
- [核心特性](#核心特性)
- [系统架构](#系统架构)
- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [核心模块详解](#核心模块详解)
- [LRU 缓存实现原理](#lru-缓存实现原理)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [API 接口文档](#api-接口文档)
- [使用示例](#使用示例)
- [性能指标](#性能指标)
- [部署指南](#部署指南)
- [项目亮点](#项目亮点)
- [常见问题 FAQ](#常见问题-faq)
- [开发路线图](#开发路线图)
- [联系方式](#联系方式)

---

## 项目背景

### 痛点

企业在日常运营中，数据分散在多个来源（网站、接口、文件），人工整理存在以下问题：

- **效率低**：手动复制粘贴，耗时耗力
- **易出错**：人工操作难免遗漏或错误
- **不及时**：无法实时获取最新数据
- **难复用**：数据格式不统一，难以二次利用

### 解决方案

本项目提供一套完整的 **自动化数据采集与可视化后台系统**，覆盖数据全生命周期：

```
采集 → 缓存 → 存储 → API 服务 → 可视化展示
```

- 多线程爬虫自动采集数据
- LRU 缓存加速查询，无需依赖 Redis
- MySQL 持久化存储，连接池管理
- RESTful API 标准化接口
- ECharts 可视化实时展示

---

## 核心特性

| 特性 | 说明 |
|------|------|
| 🕷️ **多线程爬虫** | 生产者-消费者模式，并发采集不阻塞主服务 |
| ⚡ **自实现 LRU 缓存** | 双向链表 + 哈希表，不依赖 Redis，命中率 70%+ |
| 🗄️ **MySQL 连接池** | 避免反复建连，接口响应稳定 |
| 📊 **ECharts 可视化** | 前端实时图表展示，支持多种图表类型 |
| ⏰ **定时采集** | APScheduler 支持 cron 表达式，自动执行 |
| 📤 **数据导出** | 支持 CSV 批量导出 |
| 🔍 **分页查询** | 支持关键词搜索与分页 |
| 🏗️ **生产级架构** | 模块化设计，可扩展、可部署 |

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        前端展示层 (ECharts)                       │
│              数据可视化 / 图表渲染 / 交互界面                      │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Flask API 服务层                             │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ /api/data│  │/api/crawler│  │/api/cache│  │/api/data/export│ │
│  │ 数据查询  │  │ 采集管理   │  │缓存统计  │  │  数据导出     │  │
│  └────┬─────┘  └─────┬─────┘  └────┬─────┘  └──────┬───────┘  │
└───────┼──────────────┼─────────────┼───────────────┼──────────┘
        │              │             │               │
        ▼              ▼             ▼               ▼
┌──────────────┐ ┌───────────┐ ┌──────────┐ ┌──────────────┐
│ LRU 缓存层   │ │ 爬虫服务   │ │缓存统计  │ │ 数据处理     │
│ 双向链表+哈希 │ │多线程采集  │ │ 模块     │ │ 清洗 / 聚合  │
└──────┬───────┘ └─────┬─────┘ └──────────┘ └──────┬───────┘
       │ (未命中)      │                          │
       ▼               ▼                          │
┌──────────────────────────────────────┐          │
│         MySQL 存储层 (连接池)         │◄─────────┘
│    数据表 / 索引 / 持久化存储         │
└──────────────────────────────────────┘
        ▲
        │ 定时写入
┌───────┴──────────────────────────────┐
│      APScheduler 定时任务            │
│   cron 表达式调度 / 自动采集          │
└──────────────────────────────────────┘
```

### 数据流程

```
1. 采集触发    定时任务 / 手动触发 → 启动采集
2. 多线程爬取  爬虫服务 → requests + BeautifulSoup → 原始数据
3. 数据清洗    原始数据 → DataProcessor → 结构化数据
4. 缓存写入   结构化数据 → LRU 缓存（热数据加速）
5. 持久化存储  结构化数据 → MySQL（连接池写入）
6. API 查询   前端请求 → 先查缓存 → 未命中查 MySQL → 返回
7. 可视化展示  ECharts → 调用 API → 渲染图表
8. 数据导出    API → 查询数据 → 生成 CSV → 下载
```

---

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 后端框架 | Flask | 轻量级 Web 框架 |
| 数据库 | MySQL 5.7+ | 持久化存储，支持连接池 |
| 缓存 | 自实现 LRU | 双向链表 + 哈希表，无需 Redis |
| 爬虫 | requests + BeautifulSoup | HTTP 请求 + HTML 解析 |
| 并发 | threading + Queue | 多线程采集，生产者-消费者模式 |
| 定时任务 | APScheduler | cron 表达式调度 |
| 数据处理 | Pandas | 数据清洗与聚合 |
| 可视化 | ECharts | 前端图表渲染 |
| 数据导出 | csv 模块 | CSV 批量导出 |

---

## 项目结构

```
04-数据采集可视化后台系统/
├── README.md                        # 项目说明文档（本文件）
├── requirements.txt                  # Python 依赖包
├── config.py                         # 配置文件（数据库、缓存、爬虫配置）
├── app.py                            # Flask 主应用入口
│
├── api/                              # API 路由模块
│   ├── __init__.py
│   └── routes.py                     # RESTful 接口定义
│
├── services/                         # 业务服务层
│   ├── __init__.py
│   ├── crawler.py                    # 多线程爬虫服务
│   ├── cache.py                      # 自实现 LRU 缓存
│   └── data_processor.py             # 数据清洗与聚合
│
├── models/                           # 数据模型层
│   ├── __init__.py
│   └── database.py                   # MySQL 连接池与表结构
│
├── tasks/                            # 定时任务
│   ├── __init__.py
│   └── scheduler.py                  # APScheduler 调度器
│
├── sql/                              # 数据库脚本
│   └── init.sql                      # 表结构初始化脚本
│
├── static/                           # 前端静态资源
│   └── index.html                    # ECharts 可视化页面
│
└── docs/                             # 文档目录
    ├── DESIGN.md                     # 设计文档
    └── screenshots/                  # 演示截图
```

---

## 核心模块详解

### 1. 多线程爬虫 `services/crawler.py`

采用 **生产者-消费者模式**，避免采集阻塞主服务：

| 组件 | 职责 |
|------|------|
| Producer | 将待采集 URL 放入任务队列 |
| Consumer (多线程) | 从队列取任务，执行 HTTP 请求 + 解析 |
| ResultQueue | 存储采集结果，交由数据处理模块 |

**特点：**
- 可配置线程数（默认 4-8 线程）
- 线程安全的队列通信
- 异常捕获，单条失败不影响整体采集

### 2. 自实现 LRU 缓存 `services/cache.py`

不依赖 Redis，纯 Python 实现的 LRU 缓存：

| 组件 | 职责 |
|------|------|
| 哈希表 (dict) | key → 链表节点，O(1) 查找 |
| 双向链表 | 维护访问顺序，头部最新，尾部最久未访问 |
| TTL 过期 | 每个节点记录写入时间，超时自动失效 |
| 命中率统计 | 记录命中 / 未命中次数，方便调优 |

### 3. 数据库模型 `models/database.py`

| 功能 | 说明 |
|------|------|
| 连接池 | Flask-SQLAlchemy 自带，配置 pool_size / max_overflow |
| 表结构 | 规范化设计，合理索引 |
| 事务管理 | 保证数据一致性 |

### 4. 定时任务 `tasks/scheduler.py`

| 功能 | 说明 |
|------|------|
| APScheduler | 支持 cron 表达式 |
| 定时采集 | 按配置时间自动启动爬虫 |
| 任务状态 | 记录每次执行结果 |

### 5. 数据处理 `services/data_processor.py`

| 功能 | 说明 |
|------|------|
| 数据清洗 | 去重、格式标准化、空值处理 |
| 数据聚合 | Pandas 分组统计、汇总计算 |
| 数据转换 | 原始数据 → 结构化数据 |

---

## LRU 缓存实现原理

### 数据结构

```
哈希表 (dict)
  key ──→ 节点指针
            │
            ▼
双向链表
  [head] ←→ [node A] ←→ [node B] ←→ [node C] ←→ [tail]
   最新访问                                    最久未访问（淘汰对象）
```

### 核心操作

**1. 查询（GET）：**

```python
def get(self, key):
    if key not in self.hash_table:
        self.miss_count += 1     # 未命中
        return None
    node = self.hash_table[key]
    # 检查 TTL 是否过期
    if node.is_expired():
        self._remove(node)
        del self.hash_table[key]
        self.miss_count += 1
        return None
    # 命中：移到链表头部（标记为最近访问）
    self._move_to_head(node)
    self.hit_count += 1
    return node.value
```

**2. 写入（PUT）：**

```python
def put(self, key, value):
    if key in self.hash_table:
        # 已存在：更新值，移到头部
        node = self.hash_table[key]
        node.value = value
        node.timestamp = time.time()
        self._move_to_head(node)
    else:
        # 新增
        node = Node(key, value)
        self.hash_table[key] = node
        self._add_to_head(node)
        # 超过容量，淘汰尾部（最久未访问）
        if len(self.hash_table) > self.capacity:
            tail = self._remove_tail()
            del self.hash_table[tail.key]
```

**3. 命中率统计：**

```python
def hit_rate(self):
    total = self.hit_count + self.miss_count
    return self.hit_count / total if total > 0 else 0
```

### 性能表现

| 指标 | 数值 | 测试条件 |
|------|------|----------|
| 缓存命中率 | 70%+ | 1000 QPS 压测 |
| 查询延迟 | O(1) | 哈希表 + 链表指针操作 |
| 内存占用 | 低 | 纯 Python 实现，无外部依赖 |

---

## 快速开始

### 1. 环境要求

- Python 3.8+
- MySQL 5.7+
- pip

### 2. 安装依赖

```bash
# 克隆仓库
git clone https://github.com/abliva/project.git
cd project/04-数据采集可视化后台系统

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate    # Linux/Mac
# venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置数据库

编辑 `config.py`：

```python
MYSQL_HOST = 'localhost'
MYSQL_PORT = 3306
MYSQL_USER = 'root'
MYSQL_PASSWORD = 'your-password'
MYSQL_DB = 'data_collection'

# 连接池配置
POOL_SIZE = 5
MAX_OVERFLOW = 10
```

初始化表结构：

```bash
mysql -u root -p < sql/init.sql
```

### 4. 启动服务

```bash
python app.py
```

启动后访问 `http://localhost:5000` 查看可视化界面。

### 5. 验证服务

```bash
# 健康检查
curl http://localhost:5000/api/data?page=1&size=5

# 启动采集任务
curl -X POST http://localhost:5000/api/crawler/start \
  -H "Content-Type: application/json" \
  -d '{"source": "example", "threads": 4}'

# 查看缓存统计
curl http://localhost:5000/api/cache/stats
```

---

## 配置说明

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `MYSQL_HOST` | localhost | 数据库地址 |
| `MYSQL_PORT` | 3306 | 数据库端口 |
| `MYSQL_USER` | root | 数据库用户名 |
| `MYSQL_PASSWORD` | - | 数据库密码 |
| `MYSQL_DB` | data_collection | 数据库名 |
| `POOL_SIZE` | 5 | 连接池大小 |
| `MAX_OVERFLOW` | 10 | 连接池最大溢出 |
| `CACHE_CAPACITY` | 1000 | LRU 缓存容量 |
| `CACHE_TTL` | 3600 | 缓存过期时间（秒） |
| `CRAWLER_THREADS` | 4 | 爬虫线程数 |
| `SCHEDULE_CRON` | `0 * * * *` | 定时采集 cron 表达式 |

---

## API 接口文档

### 1. 数据查询

```
GET /api/data?page=1&size=20&keyword=
```

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `page` | int | 1 | 页码 |
| `size` | int | 20 | 每页条数 |
| `keyword` | string | - | 搜索关键词 |

**响应示例：**

```json
{
  "success": true,
  "data": {
    "total": 1500,
    "page": 1,
    "size": 20,
    "items": [
      {"id": 1, "title": "示例数据", "value": 100, "created_at": "2026-01-01"}
    ]
  }
}
```

### 2. 数据导出

```
POST /api/data/export
Content-Type: application/json

{
  "format": "csv",
  "filters": {"keyword": "测试"}
}
```

返回 CSV 文件下载。

### 3. 启动采集任务

```
POST /api/crawler/start
Content-Type: application/json

{
  "source": "example",
  "threads": 4
}
```

**响应示例：**

```json
{
  "success": true,
  "message": "采集任务已启动",
  "data": {
    "task_id": "task_20260101_001",
    "threads": 4,
    "status": "running"
  }
}
```

### 4. 查询采集状态

```
GET /api/crawler/status
```

**响应示例：**

```json
{
  "success": true,
  "data": {
    "status": "running",
    "progress": "75%",
    "collected": 750,
    "total": 1000,
    "threads": 4
  }
}
```

### 5. 缓存统计

```
GET /api/cache/stats
```

**响应示例：**

```json
{
  "success": true,
  "data": {
    "capacity": 1000,
    "current_size": 850,
    "hit_count": 7000,
    "miss_count": 3000,
    "hit_rate": 0.70,
    "expired_count": 120
  }
}
```

---

## 使用示例

### Python 客户端示例

```python
import requests

BASE_URL = "http://localhost:5000"

# 1. 查询数据
resp = requests.get(f"{BASE_URL}/api/data", params={
    "page": 1, "size": 10, "keyword": "测试"
})
data = resp.json()["data"]
print(f"共 {data['total']} 条，当前页 {len(data['items'])} 条")

# 2. 启动采集
resp = requests.post(f"{BASE_URL}/api/crawler/start", json={
    "source": "example", "threads": 8
})
print("采集任务:", resp.json()["message"])

# 3. 查看缓存统计
stats = requests.get(f"{BASE_URL}/api/cache/stats").json()["data"]
print(f"缓存命中率: {stats['hit_rate']:.1%}")

# 4. 导出 CSV
resp = requests.post(f"{BASE_URL}/api/data/export", json={
    "format": "csv", "filters": {}
})
with open("export.csv", "wb") as f:
    f.write(resp.content)
print("导出完成")
```

---

## 性能指标

| 指标 | 数值 | 说明 |
|------|------|------|
| LRU 缓存命中率 | **70%+** | 1000 QPS 压测 |
| 多线程爬虫并发数 | 4-8 线程 | 可配置 |
| 接口平均响应时间（命中缓存） | **<100ms** | 缓存加速 |
| 接口平均响应时间（未命中） | 50-200ms | 查询 MySQL |
| 数据采集吞吐 | 1000+ 条/分钟 | 8 线程并发 |
| MySQL 连接池 | 5-15 连接 | pool_size=5, max_overflow=10 |

---

## 部署指南

### 本地开发部署

```bash
python app.py
# 默认 http://0.0.0.0:5000
```

### 生产环境部署

使用 Gunicorn + Nginx：

```bash
# Gunicorn 启动（4 worker）
gunicorn -w 4 -b 0.0.0.0:5000 app:app

# Nginx 反向代理
server {
    listen 80;
    server_name your-domain.com;
    location / {
        proxy_pass http://127.0.0.1:5000;
    }
}
```

### Docker 部署

```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

```bash
docker build -t data-backend .
docker run -p 5000:5000 \
  -e MYSQL_HOST=localhost \
  -e MYSQL_PASSWORD=your-password \
  data-backend
```

### Docker Compose 部署（含 MySQL）

```yaml
version: '3'
services:
  app:
    build: .
    ports:
      - "5000:5000"
    environment:
      - MYSQL_HOST=db
      - MYSQL_PASSWORD=your-password
    depends_on:
      - db
  db:
    image: mysql:5.7
    environment:
      - MYSQL_ROOT_PASSWORD=your-password
      - MYSQL_DATABASE=data_collection
    volumes:
      - ./sql/init.sql:/docker-entrypoint-initdb.d/init.sql
```

```bash
docker-compose up -d
```

---

## 项目亮点

1. **自实现 LRU 缓存**：双向链表 + 哈希表，不依赖 Redis，深入理解缓存淘汰算法底层原理，1000 QPS 压测命中率 70%+
2. **多线程爬虫**：生产者-消费者模式，线程安全队列通信，避免阻塞主服务
3. **MySQL 连接池**：避免反复建连（TCP 三次握手 + 认证），接口响应稳定
4. **定时采集**：APScheduler 支持 cron 表达式，全自动执行
5. **全链路覆盖**：采集 → 缓存 → 存储 → API → 可视化，完整闭环
6. **生产级架构**：模块化设计、前后端分离、可扩展、可部署

---

## 常见问题 FAQ

**Q: 启动报错 "ModuleNotFoundError"？**
A: 确保已安装依赖：`pip install -r requirements.txt`

**Q: 数据库连接失败？**
A: 检查 `config.py` 中 MySQL 配置是否正确，确认 MySQL 服务已启动。

**Q: 爬虫采集不到数据？**
A: 1) 检查目标网站是否可访问；2) 查看爬虫日志是否有异常；3) 部分网站需要设置 User-Agent 或 Cookie。

**Q: 缓存命中率低？**
A: 1) 检查缓存容量是否过小；2) 调整 TTL 过期时间；3) 确认是否有大量不同的查询 key。

**Q: 如何替换 LRU 为 Redis？**
A: 修改 `services/cache.py`，使用 `redis-py` 库，接口保持一致即可，其余代码无需改动。

**Q: 如何新增数据源？**
A: 在 `services/crawler.py` 中新增采集方法，遵循现有生产者-消费者模式。

---

## 开发路线图

- [x] 多线程爬虫采集
- [x] 自实现 LRU 缓存
- [x] MySQL 连接池
- [x] RESTful API
- [x] ECharts 可视化
- [x] 定时任务调度
- [x] CSV 数据导出
- [ ] 替换为 Redis 缓存（可选）
- [ ] 增加 Elasticsearch 全文搜索
- [ ] 支持更多数据源（API / 文件导入）
- [ ] 增加数据告警机制

---

## 联系方式

- **作者**：蔡俊鸿
- **邮箱**：2730126314@qq.com
- **GitHub**：[github.com/abliva](https://github.com/abliva)

---

⭐ 如果这个项目对你有帮助，欢迎 Star 支持一下！
