# -*- coding: utf-8 -*-
"""
RESTful API路由模块
提供完整的RESTful接口：
1. 数据查询/筛选/分页接口
2. 数据导出（CSV格式）接口
3. 定时任务CRUD（创建/读取/更新/删除）接口
4. 统计数据查询接口
5. 健康检查接口
6. 缓存管理接口

所有接口返回统一格式的JSON响应
"""

import io
import csv
import logging
from datetime import datetime, timedelta
from functools import wraps
from flask import Blueprint, request, jsonify, Response, send_file
from sqlalchemy import and_, or_, desc, func, case

# 导入模型和工具
from models.database import db, DataSource, CrawlRecord, Statistics
from services.cache import get_cache
from services.data_processor import DataProcessor

# 配置日志
logger = logging.getLogger(__name__)


def create_api_blueprint():
    """
    创建API蓝图实例
    
    返回:
        Blueprint: Flask蓝图对象，包含所有API路由
    """
    api_bp = Blueprint('api', __name__, url_prefix='/api/v1')
    
    # ==================== 辅助函数 ====================
    
    def success_response(data=None, message='操作成功', code=200):
        """
        生成统一的成功响应格式
        
        参数:
            data: 响应数据
            message: 提示消息
            code: HTTP状态码
            
        返回:
            tuple: (JSON响应, 状态码)
        """
        response = {
            'success': True,
            'code': code,
            'message': message,
            'data': data,
            'timestamp': datetime.now().isoformat()
        }
        return jsonify(response), code
    
    def error_response(message='操作失败', code=400, errors=None):
        """
        生成统一的错误响应格式
        
        参数:
            message: 错误消息
            code: HTTP状态码
            errors: 详细错误列表
            
        返回:
            tuple: (JSON响应, 状态码)
        """
        response = {
            'success': False,
            'code': code,
            'message': message,
            'errors': errors,
            'timestamp': datetime.now().isoformat()
        }
        return jsonify(response), code
    
    def paginate_query(query, page=1, per_page=20):
        """
        对SQLAlchemy查询进行分页处理
        
        参数:
            query: SQLAlchemy查询对象
            page: 页码（从1开始）
            per_page: 每页数量
            
        返回:
            dict: 分页结果字典，包含items、total、pages等信息
        """
        # 限制每页最大数量
        per_page = min(per_page, 100)
        
        # 执行分页查询
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return {
            'items': [item.to_dict() for item in pagination.items],
            'total': pagination.total,
            'page': pagination.page,
            'pages': pagination.pages,
            'per_page': pagination.per_page,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    
    # ==================== 健康检查接口 ====================
    
    @api_bp.route('/health', methods=['GET'])
    def health_check():
        """
        健康检查接口 - 用于监控服务是否正常运行
        
        方法: GET
        
        返回:
            JSON: 服务状态信息，包括服务名、版本、状态、时间戳等
        """
        try:
            # 测试数据库连接
            db.session.execute(db.text('SELECT 1'))
            db_status = 'healthy'
        except Exception as e:
            logger.error(f"数据库健康检查失败: {str(e)}")
            db_status = f'unhealthy - {str(e)}'
        
        health_data = {
            'service': '数据采集与可视化后台系统',
            'version': '1.0.0',
            'status': 'running',
            'database': db_status,
            'timestamp': datetime.now().isoformat(),
            'uptime': 'active'
        }
        
        return success_response(data=health_data, message='服务运行正常')
    
    # ==================== 数据源管理接口 ====================
    
    @api_bp.route('/datasources', methods=['GET'])
    def list_datasources():
        """
        获取数据源列表（支持筛选、搜索、排序、分页）
        
        方法: GET
        
        查询参数:
            - page: 页码（默认1）
            - per_page: 每页数量（默认20，最大100）
            - source_type: 按类型筛选（web_api/database/file）
            - is_active: 是否启用（true/false）
            - keyword: 关键词搜索（匹配名称或描述）
            - sort_by: 排序字段（created_at/priority/name）
            - order: 排序方向（asc/desc）
            
        返回:
            JSON: 分页的数据源列表
        """
        try:
            # 获取查询参数
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            source_type = request.args.get('source_type')
            is_active = request.args.get('is_active')
            keyword = request.args.get('keyword', '')
            sort_by = request.args.get('sort_by', 'created_at')
            order = request.args.get('order', 'desc')
            
            # 构建基础查询
            query = DataSource.query
            
            # 应用筛选条件
            if source_type:
                query = query.filter(DataSource.source_type == source_type)
            
            if is_active is not None:
                active_bool = is_active.lower() == 'true'
                query = query.filter(DataSource.is_active == active_bool)
            
            if keyword:
                search_filter = or_(
                    DataSource.name.like(f'%{keyword}%'),
                    DataSource.description.like(f'%{keyword}%')
                )
                query = query.filter(search_filter)
            
            # 应用排序
            sort_column = getattr(DataSource, sort_by, DataSource.created_at)
            if order == 'asc':
                query = query.order_by(sort_column.asc())
            else:
                query = query.order_by(sort_column.desc())
            
            # 分页查询
            result = paginate_query(query, page, per_page)
            
            return success_response(data=result, message='获取数据源列表成功')
            
        except Exception as e:
            logger.error(f"获取数据源列表失败: {str(e)}")
            return error_response(message=f'服务器内部错误: {str(e)}', code=500)
    
    @api_bp.route('/datasources/<int:id>', methods=['GET'])
    def get_datasource(id):
        """
        获取单个数据源的详细信息
        
        方法: GET
        
        路径参数:
            id: 数据源ID
            
        返回:
            JSON: 数据源详细信息
        """
        datasource = DataSource.query.get(id)
        if not datasource:
            return error_response(message='数据源不存在', code=404)
        
        return success_response(data=datasource.to_dict())
    
    @api_bp.route('/datasources', methods=['POST'])
    def create_datasource():
        """
        创建新的数据源配置
        
        方法: POST
        
        请求体(JSON):
            - name: 数据源名称（必填，唯一）
            - source_type: 类型（必填）
            - url: URL地址
            - description: 描述
            - config: 配置参数（JSON对象）
            - crawl_rule: 爬取规则（JSON对象）
            - data_mapping: 字段映射（JSON对象）
            - priority: 优先级
            
        返回:
            JSON: 创建的数据源信息
        """
        data = request.get_json()
        
        if not data or 'name' not in data or 'source_type' not in data:
            return error_response(message='缺少必要参数: name, source_type', code=400)
        
        try:
            # 创建数据源对象
            datasource = DataSource(
                name=data['name'],
                source_type=data['source_type'],
                url=data.get('url'),
                description=data.get('description'),
                config=data.get('config'),
                crawl_rule=data.get('crawl_rule'),
                data_mapping=data.get('data_mapping'),
                priority=data.get('priority', 0),
                is_active=data.get('is_active', True)
            )
            
            db.session.add(datasource)
            db.session.commit()
            
            logger.info(f"✅ 创建数据源成功 | ID: {datasource.id} | 名称: {datasource.name}")
            
            return success_response(data=datasource.to_dict(), message='数据源创建成功', code=201)
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"创建数据源失败: {str(e)}")
            return error_response(message=f'创建失败: {str(e)}', code=500)
    
    @api_bp.route('/datasources/<int:id>', methods=['PUT'])
    def update_datasource(id):
        """
        更新数据源配置
        
        方法: PUT
        
        路径参数:
            id: 数据源ID
            
        请求体(JSON): 要更新的字段（部分更新）
            
        返回:
            JSON: 更新后的数据源信息
        """
        datasource = DataSource.query.get(id)
        if not datasource:
            return error_response(message='数据源不存在', code=404)
        
        data = request.get_json()
        if not data:
            return error_response(message='请求体不能为空', code=400)
        
        try:
            # 更新允许的字段
            updatable_fields = ['name', 'source_type', 'url', 'description', 
                              'config', 'crawl_rule', 'data_mapping', 
                              'priority', 'is_active']
            
            for field in updatable_fields:
                if field in data:
                    setattr(datasource, field, data[field])
            
            db.session.commit()
            
            logger.info(f"✅ 更新数据源成功 | ID: {id}")
            
            return success_response(data=datasource.to_dict(), message='数据源更新成功')
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"更新数据源失败: {str(e)}")
            return error_response(message=f'更新失败: {str(e)}', code=500)
    
    @api_bp.route('/datasources/<int:id>', methods=['DELETE'])
    def delete_datasource(id):
        """
        删除数据源
        
        方法: DELETE
        
        路径参数:
            id: 数据源ID
            
        返回:
            JSON: 操作结果
        """
        datasource = DataSource.query.get(id)
        if not datasource:
            return error_response(message='数据源不存在', code=404)
        
        try:
            name = datasource.name
            db.session.delete(datasource)
            db.session.commit()
            
            logger.info(f"✅ 删除数据源成功 | ID: {id} | 名称: {name}")
            
            return success_response(message=f'数据源 "{name}" 已删除')
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"删除数据源失败: {str(e)}")
            return error_response(message=f'删除失败: {str(e)}', code=500)
    
    # ==================== 采集记录管理接口 ====================
    
    @api_bp.route('/crawlrecords', methods=['GET'])
    def list_crawl_records():
        """
        获取采集记录列表（支持多条件筛选）
        
        方法: GET
        
        查询参数:
            - page, per_page: 分页参数
            - datasource_id: 按数据源ID筛选
            - status: 按状态筛选（success/failed/running/cancelled）
            - start_date: 开始日期（YYYY-MM-DD）
            - end_date: 结束日期（YYYY-MM-DD）
            - task_id: 任务ID
            
        返回:
            JSON: 分页的采集记录列表
        """
        try:
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            datasource_id = request.args.get('datasource_id', type=int)
            status = request.args.get('status')
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            task_id = request.args.get('task_id')
            
            query = CrawlRecord.query
            
            # 筛选条件
            if datasource_id:
                query = query.filter(CrawlRecord.datasource_id == datasource_id)
            
            if status:
                query = query.filter(CrawlRecord.status == status)
            
            if start_date:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                query = query.filter(CrawlRecord.created_at >= start_dt)
            
            if end_date:
                end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                query = query.filter(CrawlRecord.created_at < end_dt)
            
            if task_id:
                query = query.filter(CrawlRecord.task_id == task_id)
            
            # 按创建时间倒序排列
            query = query.order_by(desc(CrawlRecord.created_at))
            
            result = paginate_query(query, page, per_page)
            
            return success_response(data=result, message='获取采集记录成功')
            
        except ValueError as ve:
            return error_response(message=f'参数格式错误: {str(ve)}', code=400)
        except Exception as e:
            logger.error(f"获取采集记录失败: {str(e)}")
            return error_response(message=f'服务器错误: {str(e)}', code=500)
    
    @api_bp.route('/crawlrecords/export', methods=['GET'])
    def export_crawl_records():
        """
        导出采集记录为CSV文件
        
        方法: GET
        
        查询参数:
            - datasource_id: 数据源ID（可选）
            - status: 状态筛选（可选）
            - start_date, end_date: 日期范围（可选）
            
        返回:
            File: CSV文件下载
        """
        try:
            # 构建查询（复用上面的逻辑）
            datasource_id = request.args.get('datasource_id', type=int)
            status = request.args.get('status')
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            
            query = CrawlRecord.query
            
            if datasource_id:
                query = query.filter(CrawlRecord.datasource_id == datasource_id)
            if status:
                query = query.filter(CrawlRecord.status == status)
            if start_date:
                query = query.filter(CrawlRecord.created_at >= datetime.strptime(start_date, '%Y-%m-%d'))
            if end_date:
                query = query.filter(CrawlRecord.created_at < datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1))
            
            records = query.all()
            
            if not records:
                return error_response(message='没有可导出的数据', code=404)
            
            # 生成CSV内容
            output = io.StringIO()
            writer = csv.writer(output)
            
            # 写入表头
            headers = ['ID', '数据源ID', '数据源名称', '任务ID', '状态', 
                      '总条数', '成功数', '失败数', '重复数', 
                      '开始时间', '结束时间', '耗时(秒)', '创建时间']
            writer.writerow(headers)
            
            # 写入数据行
            for record in records:
                row = [
                    record.id,
                    record.datasource_id,
                    record.datasource_name,
                    record.task_id,
                    record.status,
                    record.total_count,
                    record.success_count,
                    record.failed_count,
                    record.duplicate_count,
                    record.start_time.isoformat() if record.start_time else '',
                    record.end_time.isoformat() if record.end_time else '',
                    record.duration,
                    record.created_at.isoformat() if record.created_at else ''
                ]
                writer.writerow(row)
            
            # 转换为字节流
            output.seek(0)
            csv_content = output.getvalue().encode('utf-8-sig')  # BOM头支持Excel中文
            
            # 生成文件名
            filename = f'crawl_records_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            
            logger.info(f"📥 导出采集记录 | 记录数: {len(records)}")
            
            return Response(
                csv_content,
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename={filename}'}
            )
            
        except Exception as e:
            logger.error(f"导出采集记录失败: {str(e)}")
            return error_response(message=f'导出失败: {str(e)}', code=500)
    
    # ==================== 统计数据接口 ====================
    
    def _check_db_connection():
        """检查数据库连接是否可用"""
        try:
            db.session.execute(db.text('SELECT 1'))
            return True
        except Exception:
            return False
    
    @api_bp.route('/statistics/overview', methods=['GET'])
    def statistics_overview():
        """
        获取系统统计概览（用于仪表盘展示）
        
        方法: GET
        
        返回:
            JSON: 包含以下统计数据：
                  - total_datasources: 总数据源数
                  - active_datasources: 启用的数据源数
                  - today_crawls: 今日采集次数
                  - success_rate: 今日成功率
                  - recent_records: 最近10条采集记录
        """
        # 检查数据库连接
        if not _check_db_connection():
            logger.warning("数据库不可用，返回空统计概览")
            return success_response(
                data={
                    'total_datasources': 0,
                    'active_datasources': 0,
                    'today_crawls': 0,
                    'today_success': 0,
                    'today_failed': 0,
                    'success_rate': 0,
                    'recent_records': [],
                    'db_status': 'unavailable',
                    'message': '数据库服务未启动，当前显示为演示数据'
                },
                message='获取统计概览成功（数据库不可用，返回默认值）'
            )
        
        try:
            today = datetime.now().date()
            today_start = datetime.combine(today, datetime.min.time())
            
            # 统计数据源
            total_ds = DataSource.query.count()
            active_ds = DataSource.query.filter_by(is_active=True).count()
            
            # 统计今日采集情况
            today_records = CrawlRecord.query.filter(
                CrawlRecord.created_at >= today_start
            ).all()
            
            today_crawls = len(today_records)
            success_count = sum(1 for r in today_records if r.status == 'success')
            success_rate = (success_count / today_crawls * 100) if today_crawls > 0 else 0
            
            # 最近10条记录
            recent_records = CrawlRecord.query.order_by(
                desc(CrawlRecord.created_at)
            ).limit(10).all()
            
            overview_data = {
                'total_datasources': total_ds,
                'active_datasources': active_ds,
                'today_crawls': today_crawls,
                'today_success': success_count,
                'today_failed': today_crawls - success_count,
                'success_rate': round(success_rate, 2),
                'recent_records': [r.to_dict() for r in recent_records],
                'db_status': 'connected'
            }
            
            return success_response(data=overview_data, message='获取统计概览成功')
            
        except Exception as e:
            logger.error(f"获取统计概览失败: {str(e)}")
            return error_response(message=f'统计失败: {str(e)}', code=500)
    
    @api_bp.route('/statistics/trend', methods=['GET'])
    def statistics_trend():
        """
        获取采集趋势数据（按天/周/月聚合）- 用于ECharts折线图
        
        方法: GET
        
        查询参数:
            - period: 时间周期 daily/weekly/monthly（默认daily）
            - days: 查询最近多少天的数据（默认30天，最大365）
            - datasource_id: 可选，指定数据源
            
        返回:
            JSON: 包含dates（日期数组）和counts（对应采集次数数组）
        """
        # 检查数据库连接
        if not _check_db_connection():
            logger.warning("数据库不可用，返回空趋势数据")
            return success_response(
                data={
                    'dates': [],
                    'counts': [],
                    'success_counts': [],
                    'db_status': 'unavailable'
                },
                message='获取趋势数据成功（数据库不可用）'
            )
        
        try:
            period = request.args.get('period', 'daily')
            days = min(request.args.get('days', 30, type=int), 365)
            datasource_id = request.args.get('datasource_id', type=int)
            
            # 计算起始日期
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # 构建查询
            query = db.session.query(
                func.date(CrawlRecord.created_at).label('date'),
                func.count(CrawlRecord.id).label('count'),
                func.sum(case([(CrawlRecord.status == 'success', 1)], else_=0)).label('success_count')
            )
            
            query = query.filter(CrawlRecord.created_at >= start_date)
            
            if datasource_id:
                query = query.filter(CrawlRecord.datasource_id == datasource_id)
            
            query = query.group_by(func.date(CrawlRecord.created_at))
            query = query.order_by(func.date(CrawlRecord.created_at))
            
            results = query.all()
            
            # 组织成图表需要的格式
            dates = []
            counts = []
            success_counts = []
            
            for date, count, success_cnt in results:
                dates.append(date.strftime('%Y-%m-%d'))
                counts.append(count)
                success_counts.append(success_cnt)
            
            trend_data = {
                'period': period,
                'days': days,
                'dates': dates,
                'counts': counts,
                'success_counts': success_counts,
                'failed_counts': [c - s for c, s in zip(counts, success_counts)]
            }
            
            return success_response(data=trend_data, message='获取趋势数据成功')
            
        except Exception as e:
            logger.error(f"获取趋势数据失败: {str(e)}")
            return error_response(message=f'趋势统计失败: {str(e)}', code=500)
    
    @api_bp.route('/statistics/by-datasource', methods=['GET'])
    def statistics_by_datasource():
        """
        按数据源统计采集数据 - 用于ECharts饼图或柱状图
        
        方法: GET
        
        返回:
            JSON: 各数据源的采集统计（名称、总次数、成功率）
        """
        # 检查数据库连接
        if not _check_db_connection():
            logger.warning("数据库不可用，返回空数据源统计")
            return success_response(
                data=[],
                message='获取数据源统计成功（数据库不可用）'
            )
        
        try:
            results = db.session.query(
                DataSource.id,
                DataSource.name,
                func.count(CrawlRecord.id).label('total'),
                func.sum(case([(CrawlRecord.status == 'success', 1)], else_=0)).label('success')
            ).outerjoin(
                CrawlRecord, DataSource.id == CrawlRecord.datasource_id
            ).group_by(DataSource.id).all()
            
            stats_data = []
            for ds_id, ds_name, total, success in results:
                rate = (success / total * 100) if total > 0 else 0
                stats_data.append({
                    'datasource_id': ds_id,
                    'name': ds_name,
                    'total': total,
                    'success': int(success) if success else 0,
                    'success_rate': round(rate, 2)
                })
            
            return success_response(data=stats_data, message='获取数据源统计成功')
            
        except Exception as e:
            logger.error(f"按数据源统计失败: {str(e)}")
            return error_response(message=f'统计失败: {str(e)}', code=500)
    
    # ==================== 缓存管理接口 ====================
    
    @api_bp.route('/cache/stats', methods=['GET'])
    def cache_stats():
        """
        获取缓存统计信息和命中率
        
        方法: GET
        
        返回:
            JSON: 缓存统计数据（命中率、容量使用率等）
        """
        try:
            cache = get_cache()
            stats = cache.get_stats()
            hot_keys = cache.get_hot_keys(top_n=10)
            
            result = {
                **stats,
                'hot_keys': hot_keys
            }
            
            return success_response(data=result, message='获取缓存统计成功')
            
        except Exception as e:
            logger.error(f"获取缓存统计失败: {str(e)}")
            return error_response(message=str(e), code=500)
    
    @api_bp.route('/cache/clear', methods=['POST'])
    def clear_cache():
        """
        清空全部缓存（谨慎使用）
        
        方法: POST
        
        返回:
            JSON: 操作结果
        """
        try:
            cache = get_cache()
            cache.clear()
            return success_response(message='缓存已清空')
        except Exception as e:
            return error_response(message=f'清空缓存失败: {str(e)}', code=500)
    
    # ==================== 手动触发采集接口 ====================
    
    @api_bp.route('/crawl/trigger', methods=['POST'])
    def trigger_crawl():
        """
        手动触发一次数据采集任务
        
        方法: POST
        
        请求体(JSON):
            - datasource_id: 要采集的数据源ID（必填）
            
        返回:
            JSON: 采集任务信息（异步执行，立即返回任务ID）
        """
        data = request.get_json()
        
        if not data or 'datasource_id' not in data:
            return error_response(message='缺少参数: datasource_id', code=400)
        
        datasource_id = data['datasource_id']
        datasource = DataSource.query.get(datasource_id)
        
        if not datasource:
            return error_response(message='数据源不存在', code=404)
        
        if not datasource.is_active:
            return error_response(message='该数据源未启用', code=400)
        
        try:
            # 创建采集记录
            record = CrawlRecord(
                datasource_id=datasource_id,
                datasource_name=datasource.name,
                status='running',
                start_time=datetime.now(),
                created_at=datetime.now()
            )
            
            db.session.add(record)
            db.session.commit()
            
            # TODO: 这里应该异步执行实际的爬取任务
            # 可以使用Celery或APScheduler触发异步任务
            # 目前仅模拟：直接调用爬虫服务进行采集
            from services.crawler import DataCrawler
            from config import CrawlerConfig
            
            crawler = DataCrawler(config=CrawlerConfig.__dict__)
            
            if datasource.url:
                result = crawler.crawl_single(datasource.url)
                
                if result.success:
                    # 使用DataProcessor清洗数据
                    processor = DataProcessor(result.data if isinstance(result.data, list) else [result.data])
                    cleaned_data = processor.process()
                    
                    # 更新采集记录
                    record.status = 'success'
                    record.total_count = len(cleaned_data) if cleaned_data else 1
                    record.success_count = len(cleaned_data) if cleaned_data else 1
                    record.processed_data = cleaned_data
                else:
                    record.status = 'failed'
                    record.error_message = result.error_message
                
                record.end_time = datetime.now()
                record.duration = (record.end_time - record.start_time).total_seconds()
                
                # 更新数据源统计
                datasource.total_crawls += 1
                datasource.last_crawl_time = datetime.now()
                datasource.last_crawl_status = record.status
                
                crawler.close()
            
            db.session.commit()
            
            logger.info(f"✅ 手动采集完成 | 记录ID: {record.id} | 状态: {record.status}")
            
            return success_response(
                data={
                    'record_id': record.id,
                    'status': record.status,
                    'message': '采集任务已完成'
                },
                message='采集任务执行完成',
                code=200 if record.status == 'success' else 202
            )
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"手动采集失败: {str(e)}")
            return error_response(message=f'采集失败: {str(e)}', code=500)
    
    @api_bp.route('/crawl/direct', methods=['POST'])
    def direct_crawl():
        """
        直接采集指定URL的数据（无需数据库，支持无MySQL模式）
        
        方法: POST
        
        请求体(JSON):
            - url: 要采集的URL地址（必填）
            - name: 数据源名称（可选，用于标识）
            
        返回:
            JSON: 采集结果数据
        """
        data = request.get_json()
        
        if not data or 'url' not in data:
            return error_response(message='缺少参数: url', code=400)
        
        url = data['url'].strip()
        name = data.get('name', '直接采集').strip()
        
        # 验证URL格式
        if not (url.startswith('http://') or url.startswith('https://')):
            return error_response(message='URL必须以 http:// 或 https:// 开头', code=400)
        
        logger.info(f"🚀 开始直接采集 | URL: {url} | 名称: {name}")
        
        try:
            # 直接使用requests获取页面（更好的编码控制）
            import requests
            from bs4 import BeautifulSoup
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            }
            
            start_time = datetime.now()
            
            # 发送HTTP请求
            response = requests.get(url, headers=headers, timeout=30)
            
            # 智能编码检测：优先使用UTF-8
            content_type = response.headers.get('content-type', '').lower()
            
            if 'charset=utf-8' in content_type or 'charset=utf8' in content_type:
                response.encoding = 'utf-8'
            else:
                # 尝试从HTML meta标签检测
                import re
                charset_match = re.search(r'charset=["\']?([^"\'>\s]+)', response.content[:1000].decode('ascii', errors='ignore'))
                if charset_match:
                    detected = charset_match.group(1).lower()
                    response.encoding = 'utf-8' if detected in ['utf-8', 'utf8'] else detected
                else:
                    response.encoding = response.apparent_encoding or 'utf-8'
            
            raw_data = response.text
            status_code = response.status_code
            crawl_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"✅ 采集成功 | URL: {url} | 耗时: {crawl_time:.2f}s | 状态码: {status_code} | 编码: {response.encoding}")
            
            # 初始化解析后的数据
            parsed_data = None
            data_type = 'unknown'
            
            # 判断数据类型并智能处理
            if isinstance(raw_data, str):
                # 尝试解析为JSON
                try:
                    import json
                    json_data = json.loads(raw_data)
                    data_type = 'json'
                    raw_data = json_data  # 转换为JSON对象
                except:
                    # 不是JSON，检查是否是HTML
                    if '<html' in raw_data.lower() or '<!doctype' in raw_data.lower():
                        data_type = 'html'
                        try:
                            # 使用BeautifulSoup解析HTML（强制UTF-8）
                            soup = BeautifulSoup(raw_data, 'html.parser', from_encoding='utf-8')
                            
                            # 提取页面标题
                            title = soup.title.string.strip() if soup.title and soup.title.string else '无标题'
                            
                            # 提取meta描述
                            meta_desc = ''
                            meta_tag = soup.find('meta', attrs={'name': 'description'})
                            if meta_tag and meta_tag.get('content'):
                                meta_desc = meta_tag.get('content').strip()
                            
                            # 提取所有文本内容（去除多余空白）
                            text_content = soup.get_text(separator='\n', strip=True)
                            # 清理文本：移除过多空行
                            lines = [line.strip() for line in text_content.split('\n') if line.strip()]
                            clean_text = '\n'.join(lines[:50])  # 限制前50行
                            if len(lines) > 50:
                                clean_text += f'\n\n... (共{len(lines)}行，已截断前50行)'
                            
                            # 提取所有链接（转换相对路径为绝对路径）
                            links = []
                            for link in soup.find_all('a', href=True)[:20]:  # 限制前20个链接
                                link_url = link['href']
                                # 转换相对路径为绝对路径
                                if link_url and not link_url.startswith(('http://', 'https://', 'javascript:', 'mailto:', '#')):
                                    from urllib.parse import urljoin
                                    link_url = urljoin(url, link_url)
                                # 过滤无效链接
                                if link_url and link_url.startswith('http'):
                                    links.append({
                                        'text': link.get_text(strip=True)[:100],
                                        'url': link_url
                                    })
                            
                            # 提取图片（转换相对路径为绝对路径）
                            images = []
                            for img in soup.find_all('img', src=True)[:10]:
                                img_src = img['src']
                                # 转换相对路径为绝对路径
                                if img_src and not img_src.startswith(('http://', 'https://', 'data:')):
                                    from urllib.parse import urljoin
                                    img_src = urljoin(url, img_src)
                                    # 处理协议相对URL（//example.com/image.jpg）
                                    if img_src.startswith('//'):
                                        img_src = 'https:' + img_src
                                # 只添加有效的图片URL
                                if img_src and (img_src.startswith('http') or img_src.startswith('data:')):
                                    images.append({
                                        'alt': img.get('alt', '')[:100] or '图片',
                                        'src': img_src
                                    })
                            
                            # 构建结构化数据
                            parsed_data = {
                                'type': 'html_page',
                                'title': title,
                                'description': meta_desc,
                                'content_preview': clean_text,
                                'links': links,
                                'images': images,
                                'total_links': len(soup.find_all('a', href=True)),
                                'total_images': len(soup.find_all('img', src=True))
                            }
                        except Exception as e:
                            logger.warning(f"HTML解析失败: {str(e)}")
                            parsed_data = {
                                'type': 'html_raw',
                                'preview': raw_data[:2000] + ('...' if len(raw_data) > 2000 else ''),
                                'length': len(raw_data)
                            }
                    else:
                        # 纯文本
                        data_type = 'text'
                        parsed_data = {
                            'type': 'plain_text',
                            'content': raw_data[:3000] + ('...' if len(raw_data) > 3000 else ''),
                            'length': len(raw_data)
                        }
            elif isinstance(raw_data, (dict, list)):
                data_type = 'json'
            
            # 返回成功响应
            return success_response(
                data={
                    'success': True,
                    'url': url,
                    'datasource_name': name,
                    'status_code': status_code,
                    'crawl_time': crawl_time,
                    'raw_data': raw_data if data_type == 'json' else None,  # JSON才返回原始数据
                    'parsed_data': parsed_data,  # 返回解析后的数据
                    'data_type': data_type,
                    'message': f'成功获取{data_type.upper()}数据，耗时 {crawl_time:.2f} 秒',
                    'human_readable': data_type != 'json'  # 标记是否为人类可读格式
                },
                message=f'✅ 数据采集完成！获取到{data_type.upper()}类型数据'
            )
                
        except Exception as e:
            logger.error(f"❌ 直接采集异常 | URL: {url} | 错误: {str(e)}", exc_info=True)
            
            return error_response(
                message=f'采集过程发生错误: {str(e)}',
                code=500,
                suggestions=['请检查后端日志获取详细错误信息']
            )
    
    @api_bp.route('/crawl/targeted', methods=['POST'])
    def targeted_crawl():
        """
        定向采集 - 使用CSS选择器提取特定数据字段
        
        方法: POST
        
        请求体(Json):
            - url: 要采集的URL地址(必填)
            - name: 数据源名称(可选)
            - fields: 字段配置列表(必填)
              - name: 字段名称
              - selector: CSS选择器
              - attr: 提取属性(text/href/src/alt等)
              
        返回:
            JSON: 提取的结构化数据表格
        """
        data = request.get_json()
        
        if not data or 'url' not in data:
            return error_response(message='缺少参数: url', code=400)
        
        if 'fields' not in data or len(data['fields']) == 0:
            return error_response(message='缺少参数: fields 或字段为空', code=400)
        
        url = data['url'].strip()
        name = data.get('name', '定向采集').strip()
        fields_config = data['fields']
        
        # 验证URL格式
        if not (url.startswith('http://') or url.startswith('https://')):
            return error_response(message='URL必须以 http:// 或 https:// 开头', code=400)
        
        logger.info(f"🎯 开始定向采集 | URL: {url} | 字段数: {len(fields_config)}")
        logger.info(f"📋 字段配置: {fields_config}")
        
        try:
            import requests
            from bs4 import BeautifulSoup
            from urllib.parse import urljoin
            
            # 设置请求头，模拟浏览器访问
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive'
            }
            
            start_time = datetime.now()
            
            # 发送HTTP请求获取页面内容
            response = requests.get(url, headers=headers, timeout=30)
            
            # 智能编码检测：优先使用UTF-8，避免乱码
            content_type = response.headers.get('content-type', '').lower()
            
            if 'charset=utf-8' in content_type or 'charset=utf8' in content_type:
                response.encoding = 'utf-8'
                logger.info(f"📝 使用UTF-8编码 (来自HTTP头)")
            else:
                # 尝试从HTML meta标签检测
                try:
                    import re
                    charset_match = re.search(r'charset=["\']?([^"\'>\s]+)', response.content[:1000].decode('ascii', errors='ignore'))
                    if charset_match:
                        detected_charset = charset_match.group(1).lower()
                        if detected_charset in ['utf-8', 'utf8']:
                            response.encoding = 'utf-8'
                            logger.info(f"📝 使用UTF-8编码 (来自meta标签)")
                        else:
                            response.encoding = detected_charset
                            logger.info(f"📝 使用{detected_charset}编码 (来自meta标签)")
                    else:
                        # 最后尝试自动检测
                        response.encoding = response.apparent_encoding or 'utf-8'
                        logger.info(f"📝 使用{response.encoding}编码 (自动检测)")
                except:
                    response.encoding = 'utf-8'
                    logger.info(f"📝 默认使用UTF-8编码")
            
            html_content = response.text
            status_code = response.status_code
            
            crawl_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"✅ 页面获取成功 | 状态码: {status_code} | 大小: {len(html_content)}字节 | 编码: {response.encoding}")
            
            # 使用BeautifulSoup解析HTML（强制使用UTF-8）
            soup = BeautifulSoup(html_content, 'html.parser', from_encoding='utf-8')
            
            # 提取每个字段的值
            extracted_data = []
            
            # 首先找到所有匹配第一个选择器的元素数量，确定记录数
            first_selector = fields_config[0]['selector']
            base_elements = soup.select(first_selector)
            record_count = len(base_elements)
            
            logger.info(f"📊 找到 {record_count} 条记录")
            
            # 为每条记录提取所有字段
            for i in range(record_count):
                record = {}
                
                for field in fields_config:
                    field_name = field['name']
                    selector = field['selector']
                    attr_type = field.get('attr', 'text')
                    
                    try:
                        # 查找元素
                        elements = soup.select(selector)
                        
                        if i < len(elements):
                            element = elements[i]
                            
                            # 根据属性类型提取值
                            if attr_type == 'text':
                                value = element.get_text(strip=True)
                            elif attr_type == 'href':
                                value = element.get('href', '')
                                # 转换相对路径为绝对路径
                                if value and not value.startswith(('http://', 'https://')):
                                    value = urljoin(url, value)
                            elif attr_type == 'src':
                                value = element.get('src', '')
                                # 转换相对路径为绝对路径
                                if value and not value.startswith(('http://', 'https://')):
                                    value = urljoin(url, value)
                                    # 处理协议相对URL
                                    if value.startswith('//'):
                                        value = 'https:' + value
                            elif attr_type == 'alt':
                                value = element.get('alt', '')
                            elif attr_type == 'data-*':
                                # 自定义data属性
                                data_attrs = [attr for attr in element.attrs if attr.startswith('data-')]
                                value = ', '.join([f"{attr}: {element[attr]}" for attr in data_attrs]) if data_attrs else ''
                            else:
                                # 其他属性
                                value = element.get(attr_type, '') or element.get_text(strip=True)
                            
                            record[field_name] = value.strip() if isinstance(value, str) else str(value)
                        else:
                            record[field_name] = None
                            
                    except Exception as e:
                        logger.warning(f"⚠️ 字段 '{field_name}' 提取失败: {str(e)}")
                        record[field_name] = None
                
                extracted_data.append(record)
            
            # 如果没有找到任何元素，尝试单条记录模式
            if record_count == 0:
                logger.info("🔄 未找到多条记录，尝试单条记录模式...")
                record = {}
                
                for field in fields_config:
                    field_name = field['name']
                    selector = field['selector']
                    attr_type = field.get('attr', 'text')
                    
                    try:
                        elements = soup.select(selector)
                        
                        if elements:
                            # 取第一个匹配元素的所有值（用逗号分隔）
                            values = []
                            for elem in elements[:10]:  # 限制前10个
                                if attr_type == 'text':
                                    values.append(elem.get_text(strip=True))
                                elif attr_type == 'href':
                                    val = elem.get('href', '')
                                    if val and not val.startswith(('http://', 'https://')):
                                        val = urljoin(url, val)
                                    values.append(val)
                                elif attr_type == 'src':
                                    val = elem.get('src', '')
                                    if val and not val.startswith(('http://', 'https://')):
                                        val = urljoin(url, val)
                                        if val.startswith('//'):
                                            val = 'https:' + val
                                    values.append(val)
                                elif attr_type == 'alt':
                                    values.append(elem.get('alt', ''))
                                else:
                                    values.append(elem.get(attr_type, '') or elem.get_text(strip=True))
                            
                            record[field_name] = '; '.join(values) if values else None
                        else:
                            record[field_name] = None
                            
                    except Exception as e:
                        logger.warning(f"⚠️ 字段 '{field_name}' 提取失败: {str(e)}")
                        record[field_name] = None
                
                if any(v is not None for v in record.values()):
                    extracted_data.append(record)
            
            logger.info(f"✅ 定向采集完成 | 提取记录数: {len(extracted_data)} | 耗时: {crawl_time:.2f}s")
            
            return success_response(
                data={
                    'success': True,
                    'url': url,
                    'datasource_name': name,
                    'status_code': status_code,
                    'crawl_time': crawl_time,
                    'extracted_data': extracted_data,
                    'total_records': len(extracted_data),
                    'fields_config': fields_config,
                    'message': f'成功提取{len(extracted_data)}条记录，包含{len(fields_config)}个字段'
                },
                message=f'✅ 定向采集完成！成功提取{len(extracted_data)}条记录'
            )
            
        except requests.exceptions.Timeout:
            logger.error(f"❌ 请求超时 | URL: {url}")
            return error_response(
                message='请求超时，目标网站响应时间过长',
                code=408,
                suggestions=['请稍后重试', '检查网络连接', '目标网站可能暂时不可用']
            )
        except requests.exceptions.ConnectionError as e:
            logger.error(f"❌ 连接失败 | URL: {url} | 错误: {str(e)}")
            return error_response(
                message='无法连接到目标网站',
                code=503,
                suggestions=['检查URL是否正确', '确认网站是否可访问', '检查网络连接']
            )
        except Exception as e:
            logger.error(f"❌ 定向采集异常 | URL: {url} | 错误: {str(e)}", exc_info=True)
            return error_response(
                message=f'采集过程发生错误: {str(e)}',
                code=500,
                suggestions=['请检查CSS选择器是否正确', '查看后端日志获取详细信息']
            )

    return api_bp
