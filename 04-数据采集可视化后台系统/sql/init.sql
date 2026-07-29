-- =====================================================
-- 通用数据采集与可视化后台系统 - 数据库初始化脚本
-- 数据库: MySQL 5.7+ / MySQL 8.0+
-- 字符集: utf8mb4 (支持完整Unicode，包括emoji)
-- 创建时间: 2024-01
-- 说明: 此脚本用于初始化系统所需的全部数据表和基础数据
-- =====================================================

-- 设置字符集（确保支持中文和特殊字符）
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- 如果数据库不存在则创建
CREATE DATABASE IF NOT EXISTS `data_collector` 
    DEFAULT CHARACTER SET utf8mb4 
    COLLATE utf8mb4_unicode_ci;

USE `data_collector`;

-- =====================================================
-- 表1: datasource (采集源表)
-- 用途: 存储所有数据源的配置信息（网页API、数据库、文件等）
-- =====================================================

DROP TABLE IF EXISTS `datasource`;

CREATE TABLE `datasource` (
    `id` INT(11) NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `name` VARCHAR(100) NOT NULL COMMENT '数据源名称（唯一）',
    `source_type` VARCHAR(50) NOT NULL COMMENT '数据源类型: web_api/database/file/other',
    `url` TEXT COMMENT '数据源URL或连接地址',
    `description` TEXT COMMENT '数据源描述说明',
    
    -- 配置信息（JSON格式，灵活存储各种配置参数）
    `config` JSON COMMENT '数据源配置参数(JSON): 请求头、认证信息、字段映射等',
    
    -- 采集规则配置
    `crawl_rule` JSON COMMENT '爬取规则: CSS选择器、XPath、API参数等',
    `data_mapping` JSON COMMENT '字段映射关系: 源字段->目标字段',
    
    -- 状态管理
    `is_active` TINYINT(1) DEFAULT 1 COMMENT '是否启用: 1-启用, 0-禁用',
    `priority` INT(11) DEFAULT 0 COMMENT '优先级(数字越大优先级越高)',
    
    -- 统计信息（冗余存储，方便快速查询）
    `total_crawls` INT(11) DEFAULT 0 COMMENT '总采集次数',
    `last_crawl_time` DATETIME COMMENT '最后采集时间',
    `last_crawl_status` VARCHAR(20) COMMENT '最后采集状态: success/failed/pending',
    `error_message` TEXT COMMENT '错误信息',
    
    -- 时间戳
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_datasource_name` (`name`),
    INDEX `idx_datasource_type` (`source_type`),
    INDEX `idx_datasource_active` (`is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='采集源表-存储所有数据源的配置信息';

-- =====================================================
-- 表2: crawlrecord (采集记录表)
-- 用途: 记录每次数据采集的详细信息，用于追踪历史和统计分析
-- =====================================================

DROP TABLE IF EXISTS `crawlrecord`;

CREATE TABLE `crawlrecord` (
    `id` INT(11) NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    
    -- 关联数据源
    `datasource_id` INT(11) NOT NULL COMMENT '关联的数据源ID',
    `datasource_name` VARCHAR(100) COMMENT '数据源名称(冗余存储,方便查询)',
    
    -- 采集任务信息
    `task_id` VARCHAR(100) COMMENT '任务ID(关联定时任务)',
    `task_name` VARCHAR(100) COMMENT '任务名称',
    
    -- 采集结果统计
    `status` VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '任务状态: running/success/failed/cancelled',
    `total_count` INT(11) DEFAULT 0 COMMENT '采集到的总数据条数',
    `success_count` INT(11) DEFAULT 0 COMMENT '成功处理的数据条数',
    `failed_count` INT(11) DEFAULT 0 COMMENT '失败的数据条数',
    `duplicate_count` INT(11) DEFAULT 0 COMMENT '重复数据条数',
    
    -- 数据详情（JSON格式存储实际采集的数据）
    `raw_data` JSON COMMENT '原始采集数据(JSON数组)',
    `processed_data` JSON COMMENT '清洗后的数据(JSON数组)',
    
    -- 执行信息
    `start_time` DATETIME COMMENT '开始时间',
    `end_time` DATETIME COMMENT '结束时间',
    `duration` FLOAT COMMENT '执行耗时(秒)',
    
    -- 错误信息
    `error_code` VARCHAR(20) COMMENT '错误代码',
    `error_message` TEXT COMMENT '错误详细描述',
    `error_traceback` TEXT COMMENT '异常堆栈信息',
    
    -- 其他信息
    `remark` TEXT COMMENT '备注信息',
    
    -- 时间戳
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    
    PRIMARY KEY (`id`),
    INDEX `idx_crawlrecord_datasource` (`datasource_id`),
    INDEX `idx_crawlrecord_status` (`status`),
    INDEX `idx_crawlrecord_created` (`created_at`),
    INDEX `idx_crawlrecord_task` (`task_id`),
    CONSTRAINT `fk_crawlrecord_datasource` 
        FOREIGN KEY (`datasource_id`) REFERENCES `datasource`(`id`) 
        ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='采集记录表-记录每次数据采集的详细信息';

-- =====================================================
-- 表3: statistics (统计数据表)
-- 用途: 存储聚合后的统计数据，用于前端图表展示
-- 支持按时间维度(hourly/daily/weekly/monthly)的聚合统计
-- =====================================================

DROP TABLE IF EXISTS `statistics`;

CREATE TABLE `statistics` (
    `id` INT(11) NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    
    -- 统计维度
    `stat_type` VARCHAR(50) NOT NULL COMMENT '统计类型: crawl_count/data_volume/success_rate/error_distribution',
    `stat_dimension` VARCHAR(50) NOT NULL COMMENT '统计维度: hourly/daily/weekly/monthly/datasource/category',
    
    -- 时间维度
    `stat_date` DATE NOT NULL COMMENT '统计日期',
    `stat_hour` INT(11) COMMENT '统计小时(仅hourly维度使用)',
    
    -- 关联信息
    `datasource_id` INT(11) COMMENT '数据源ID(可选,为空表示全局统计)',
    `category` VARCHAR(100) COMMENT '分类标签(可选)',
    
    -- 统计指标值（JSON格式，支持多指标）
    `metrics` JSON NOT NULL COMMENT '统计指标(JSON): {"count": 100, "success_rate": 95.5}',
    
    -- 额外信息
    `extra_data` JSON COMMENT '额外数据或明细',
    
    -- 时间戳
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_statistics_unique` (`stat_type`, `stat_dimension`, `stat_date`, `stat_hour`, `datasource_id`),
    INDEX `idx_statistics_type_dim` (`stat_type`, `stat_dimension`),
    INDEX `idx_statistics_date` (`stat_date`),
    INDEX `idx_statistics_datasource` (`datasource_id`),
    CONSTRAINT `fk_statistics_datasource` 
        FOREIGN KEY (`datasource_id`) REFERENCES `datasource`(`id`) 
        ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='统计数据表-存储聚合后的统计数据用于图表展示';

-- =====================================================
-- 初始化示例数据（便于测试和演示）
-- =====================================================

-- 插入示例数据源
INSERT INTO `datasource` (`name`, `source_type`, `url`, `description`, `is_active`, `priority`) VALUES
('电商商品API', 'web_api', 'https://api.example.com/products', '电商平台商品数据接口', 1, 10),
('新闻资讯爬虫', 'web_api', 'https://news.example.com/', '新闻网站内容采集', 1, 8),
('社交媒体监控', 'file', '/data/social_media.json', '社交媒体数据分析', 1, 6),
('金融行情接口', 'web_api', 'https://finance-api.example.com/market', '股票/基金实时行情', 1, 9),
('天气数据服务', 'web_api', 'https://weather-api.example.com/v1', '全国城市天气预报', 0, 5);

-- 插入示例采集记录（模拟最近几天的数据）
INSERT INTO `crawlrecord` (`datasource_id`, `datasource_name`, `task_name`, `status`, `total_count`, `success_count`, `failed_count`, `duration`, `start_time`, `end_time`, `created_at`) VALUES
(1, '电商商品API', '定时采集任务', 'success', 1500, 1485, 12, 45.3, DATE_SUB(NOW(), INTERVAL 2 HOUR), DATE_SUB(NOW(), INTERVAL 2 HOUR) + INTERVAL 45 SECOND, DATE_SUB(NOW(), INTERVAL 2 HOUR)),
(2, '新闻资讯爬虫', '定时采集任务', 'success', 320, 318, 2, 28.6, DATE_SUB(NOW(), INTERVAL 3 HOUR), DATE_SUB(NOW(), INTERVAL 3 HOUR) + INTERVAL 29 SECOND, DATE_SUB(NOW(), INTERVAL 3 HOUR)),
(4, '金融行情接口', '定时采集任务', 'success', 8500, 8500, 0, 12.1, DATE_SUB(NOW(), INTERVAL 1 HOUR), DATE_SUB(NOW(), INTERVAL 1 HOUR) + INTERVAL 12 SECOND, DATE_SUB(NOW(), INTERVAL 1 HOUR)),
(1, '电商商品API', '定时采集任务', 'success', 1520, 1510, 8, 46.8, DATE_SUB(NOW(), INTERVAL 1 DAY), DATE_SUB(NOW(), INTERVAL 1 DAY) + INTERVAL 47 SECOND, DATE_SUB(NOW(), INTERVAL 1 DAY)),
(2, '新闻资讯爬虫', '定时采集任务', 'failed', 0, 0, 0, 5.2, DATE_SUB(NOW(), INTERVAL 1 DAY), DATE_SUB(NOW(), INTERVAL 1 DAY) + INTERVAL 5 SECOND, DATE_SUB(NOW(), INTERVAL 1 DAY)),
(3, '社交媒体监控', '手动触发', 'success', 4500, 4489, 11, 89.3, DATE_SUB(NOW(), INTERVAL 1 DAY) + INTERVAL 2 HOUR, DATE_SUB(NOW(), INTERVAL 1 DAY) + INTERVAL 2 HOUR + INTERVAL 89 SECOND, DATE_SUB(NOW(), INTERVAL 1 DAY) + INTERVAL 2 HOUR),
(4, '金融行情接口', '定时采集任务', 'success', 8620, 8620, 0, 11.5, DATE_SUB(NOW(), INTERVAL 1 DAY) + INTERVAL 3 HOUR, DATE_SUB(NOW(), INTERVAL 1 DAY) + INTERVAL 3 HOUR + INTERVAL 12 SECOND, DATE_SUB(NOW(), INTERVAL 1 DAY) + INTERVAL 3 HOUR),
(1, '电商商品API', '定时采集任务', 'success', 1495, 1490, 5, 44.2, DATE_SUB(NOW(), INTERVAL 2 DAY), DATE_SUB(NOW(), INTERVAL 2 DAY) + INTERVAL 44 SECOND, DATE_SUB(NOW(), INTERVAL 2 DAY)),
(2, '新闻资讯爬虫', '定时采集任务', 'success', 335, 332, 3, 27.8, DATE_SUB(NOW(), INTERVAL 2 DAY), DATE_SUB(NOW(), INTERVAL 2 DAY) + INTERVAL 28 SECOND, DATE_SUB(NOW(), INTERVAL 2 DAY)),
(4, '金融行情接口', '定时采集任务', 'success', 8480, 8475, 5, 13.2, DATE_SUB(NOW(), INTERVAL 2 DAY), DATE_SUB(NOW(), INTERVAL 2 DAY) + INTERVAL 13 SECOND, DATE_SUB(NOW(), INTERVAL 2 DAY));

-- 插入示例统计数据
INSERT INTO `statistics` (`stat_type`, `stat_dimension`, `stat_date`, `metrics`) VALUES
('crawl_summary', 'daily', CURDATE() - INTERVAL 1 DAY, '{"total_count": 4, "success_count": 3, "failed_count": 1, "success_rate": 75.0}'),
('crawl_summary', 'daily', CURDATE() - INTERVAL 2 DAY, '{"total_count": 3, "success_count": 3, "failed_count": 0, "success_rate": 100.0}'),
('crawl_summary', 'daily', CURDATE() - INTERVAL 3 DAY, '{"total_count": 5, "success_count": 4, "failed_count": 1, "success_rate": 80.0}'),
('data_volume', 'daily', CURDATE() - INTERVAL 1 DAY, '{"total_records": 15445, "avg_per_task": 3861}'),
('data_volume', 'daily', CURDATE() - INTERVAL 2 DAY, '{"total_records": 10307, "avg_per_task": 3436}');

-- 恢复外键检查
SET FOREIGN_KEY_CHECKS = 1;

-- =====================================================
-- 初始化完成提示
-- =====================================================
SELECT '✅ 数据库初始化完成！' AS message;
SELECT CONCAT('已创建 ', COUNT(*), ' 张数据表') AS table_count FROM information_schema.tables WHERE table_schema = 'data_collector' AND table_type = 'BASE TABLE';
SELECT CONCAT('已插入 ', (SELECT COUNT(*) FROM datasource), ' 条数据源') AS datasource_count;
SELECT CONCAT('已插入 ', (SELECT COUNT(*) FROM crawlrecord), ' 条采集记录') AS record_count;
