# -*- coding: utf-8 -*-
"""
数据清洗与格式转换模块
功能：
1. 数据去重处理（基于指定字段或全字段MD5）
2. 空值处理（填充默认值、删除空值行、插值法）
3. 格式标准化（日期格式、数值精度、字符串清洗）
4. 字段映射与重命名
5. 数据类型转换与验证
6. 异常值检测与处理
"""

import re
import hashlib
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, Callable
from copy import deepcopy

# 配置日志
logger = logging.getLogger(__name__)


class DataProcessor:
    """
    数据处理器 - 对原始采集数据进行清洗、转换、标准化处理
    
    支持链式调用，方便组合多个数据处理步骤：
    >>> processor = DataProcessor(raw_data)
    >>> cleaned_data = processor.remove_duplicates(['id']).fillna({'value': 0}).standardize_dates('date_field').process()
    """
    
    def __init__(self, data: Union[List[Dict], Dict]):
        """
        初始化数据处理器
        
        参数:
            data: 待处理的原始数据，可以是字典列表或单个字典
                 通常是从爬虫获取的JSON数据
        """
        # 深拷贝数据，避免修改原始数据
        self.original_data = deepcopy(data) if isinstance(data, list) else [deepcopy(data)]
        self.data = deepcopy(self.original_data)
        
        # 处理流水线记录（用于调试和日志）
        self.processing_log = []
        
        # 统计信息
        self.stats = {
            'original_count': len(self.data),
            'current_count': len(self.data),
            'removed_duplicates': 0,
            'filled_nulls': 0,
            'converted_types': 0,
            'removed_invalid': 0
        }
        
        logger.info(f"📥 数据处理器初始化 | 原始数据条数: {len(self.data)}")
    
    def remove_duplicates(self, fields: List[str] = None, 
                         keep: str = 'first') -> 'DataProcessor':
        """
        数据去重 - 移除重复记录
        
        参数:
            fields: 用于判断重复的字段列表，如果为None则基于所有字段生成指纹
            keep: 保留规则：'first'保留第一条 / 'last'保留最后一条
            
        返回:
            DataProcessor: 支持链式调用的自身实例
        """
        original_count = len(self.data)
        seen = set()
        unique_data = []
        
        for idx, record in enumerate(self.data):
            # 生成记录的唯一标识
            if fields:
                # 基于指定字段生成标识
                key_parts = []
                for field in fields:
                    value = record.get(field)
                    key_parts.append(str(value) if value is not None else '')
                identifier = '|'.join(key_parts)
            else:
                # 基于所有字段生成MD5哈希作为唯一标识
                record_str = str(sorted(record.items()))
                identifier = hashlib.md5(record_str.encode()).hexdigest()
            
            # 根据keep参数决定是否保留
            if identifier not in seen:
                seen.add(identifier)
                unique_data.append(record)
            elif keep == 'last':
                # 如果是last模式，移除之前添加的相同记录，添加当前记录
                unique_data = [r for r in unique_data if self._generate_key(r, fields) != identifier]
                unique_data.append(record)
        
        # 更新数据和统计
        removed_count = original_count - len(unique_data)
        self.data = unique_data
        self.stats['removed_duplicates'] += removed_count
        self.stats['current_count'] = len(self.data)
        
        log_msg = f"去重完成 | 移除{removed_count}条重复数据 | 保留{len(self.data)}条"
        self.processing_log.append(('remove_duplicates', log_msg))
        logger.info(f"✅ {log_msg}")
        
        return self
    
    def _generate_key(self, record: Dict, fields: List[str] = None) -> str:
        """生成记录的唯一键（辅助方法）"""
        if fields:
            key_parts = [str(record.get(f, '')) for f in fields]
            return '|'.join(key_parts)
        else:
            record_str = str(sorted(record.items()))
            return hashlib.md5(record_str.encode()).hexdigest()
    
    def fillna(self, fill_map: Dict[str, Any] = None, 
               strategy: str = 'constant') -> 'DataProcessor':
        """
        空值处理 - 填充或删除空值
        
        参数:
            fill_map: 字段名到填充值的映射字典，例如：{'age': 0, 'name': 'unknown'}
                     如果为None，则根据strategy参数处理
            strategy: 填充策略：
                     - 'constant': 使用固定值填充（需提供fill_map）
                     - 'drop': 删除包含空值的整行记录
                     - 'ffill': 前向填充（使用前一个有效值）
                     - 'mean': 使用平均值填充（仅数值型字段）
                     
        返回:
            DataProcessor: 支持链式调用的自身实例
        """
        filled_count = 0
        
        if strategy == 'drop':
            # 删除包含空值的记录
            original_count = len(self.data)
            self.data = [
                record for record in self.data 
                if all(v is not None and v != '' and v != 'null' for v in record.values())
            ]
            filled_count = original_count - len(self.data)
            log_msg = f"删除空值行 | 移除{filled_count}条含空值的记录"
            
        elif strategy == 'constant' and fill_map:
            # 使用固定值填充
            for record in self.data:
                for field, default_value in fill_map.items():
                    if field in record and (record[field] is None or record[field] == '' or record[field] == 'null'):
                        record[field] = default_value
                        filled_count += 1
            log_msg = f"固定值填充 | 共填充{filled_count}个空值"
            
        elif strategy == 'ffill':
            # 前向填充（使用前一条记录的有效值）
            last_valid_values = {}
            for record in self.data:
                for key, value in record.items():
                    if value is None or value == '' or value == 'null':
                        if key in last_valid_values:
                            record[key] = last_valid_values[key]
                            filled_count += 1
                    else:
                        last_valid_values[key] = value
            log_msg = f"前向填充 | 共填充{filled_count}个空值"
            
        elif strategy == 'mean':
            # 计算各字段的平均值并填充（仅适用于数值型字段）
            from statistics import mean
            
            # 先计算平均值
            field_sums = {}
            field_counts = {}
            for record in self.data:
                for key, value in record.items():
                    if isinstance(value, (int, float)) and value is not None:
                        field_sums[key] = field_sums.get(key, 0) + value
                        field_counts[key] = field_counts.get(key, 0) + 1
            
            field_means = {
                k: field_sums[k] / field_counts[k] 
                for k in field_sums 
                if field_counts[k] > 0
            }
            
            # 填充值
            for record in self.data:
                for key, value in record.items():
                    if value is None and key in field_means:
                        record[key] = field_means[key]
                        filled_count += 1
            log_msg = f"均值填充 | 共填充{filled_count}个空值"
        
        else:
            raise ValueError(f"不支持的填充策略: {strategy}")
        
        self.stats['filled_nulls'] += filled_count
        self.processing_log.append(('fillna', log_msg))
        logger.info(f"✅ {log_msg}")
        
        return self
    
    def standardize_dates(self, date_fields: List[str], 
                          input_format: str = None,
                          output_format: str = '%Y-%m-%d %H:%M:%S') -> 'DataProcessor':
        """
        日期格式标准化 - 将各种日期格式统一转换为标准格式
        
        参数:
            date_fields: 需要标准化的日期字段名列表
            input_format: 输入日期的格式（如果为None则自动检测常见格式）
            output_format: 输出的目标日期格式
            
        返回:
            DataProcessor: 支持链式调用的自身实例
        """
        converted_count = 0
        common_formats = [
            '%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d',
            '%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S',
            '%Y年%m月%d日', '%Y%m%d',
            '%m/%d/%Y', '%d-%m-%Y',
            '%b %d, %Y', '%B %d, %Y'
        ]
        
        for record in self.data:
            for field in date_fields:
                if field not in record or record[field] is None:
                    continue
                
                date_value = str(record[field]).strip()
                
                try:
                    if input_format:
                        # 使用指定的输入格式解析
                        dt = datetime.strptime(date_value, input_format)
                    else:
                        # 自动尝试多种常见格式
                        dt = None
                        for fmt in common_formats:
                            try:
                                dt = datetime.strptime(date_value, fmt)
                                break
                            except ValueError:
                                continue
                        
                        if dt is None:
                            logger.warning(f"⚠️ 无法识别日期格式: {date_value} (字段: {field})")
                            continue
                    
                    # 转换为目标格式
                    record[field] = dt.strftime(output_format)
                    converted_count += 1
                    
                except Exception as e:
                    logger.warning(f"⚠️ 日期转换失败 | 字段: {field} | 值: {date_value} | 错误: {str(e)}")
        
        self.stats['converted_types'] += converted_count
        log_msg = f"日期标准化 | 转换{converted_count}个日期值 | 目标格式: {output_format}"
        self.processing_log.append(('standardize_dates', log_msg))
        logger.info(f"✅ {log_msg}")
        
        return self
    
    def standardize_numbers(self, number_fields: List[str],
                           precision: int = 2,
                           remove_non_numeric: bool = True) -> 'DataProcessor':
        """
        数值标准化 - 清洗数值字段，统一精度
        
        参数:
            number_fields: 数值字段名列表
            precision: 小数点后保留位数
            remove_non_numeric: 是否移除非数字字符（如货币符号、千分位逗号等）
            
        返回:
            DataProcessor: 支持链式调用的自身实例
        """
        converted_count = 0
        
        for record in self.data:
            for field in number_fields:
                if field not in record or record[field] is None:
                    continue
                
                value = str(record[field]).strip()
                
                try:
                    # 移除非数字字符（可选）
                    if remove_non_numeric:
                        # 保留数字、小数点、负号、科学计数法符号
                        value = re.sub(r'[^\d.\-eE+]', '', value)
                    
                    # 转换为浮点数并四舍五入
                    num_value = float(value)
                    record[field] = round(num_value, precision)
                    converted_count += 1
                    
                except (ValueError, TypeError) as e:
                    logger.warning(f"⚠️ 数值转换失败 | 字段: {field} | 值: {value}")
        
        self.stats['converted_types'] += converted_count
        log_msg = f"数值标准化 | 转换{converted_count}个数值 | 精度: {precision}位小数"
        self.processing_log.append(('standardize_numbers', log_msg))
        logger.info(f"✅ {log_msg}")
        
        return self
    
    def clean_strings(self, string_fields: List[str] = None,
                     strip_whitespace: bool = True,
                     lowercase: bool = False,
                     remove_special_chars: bool = False) -> 'DataProcessor':
        """
        字符串清洗 - 处理文本类字段
        
        参数:
            string_fields: 要处理的字段列表，如果为None则处理所有字符串类型字段
            strip_whitespace: 是否去除首尾空白字符
            lowercase: 是否转换为小写
            remove_special_chars: 是否移除特殊字符（只保留中文、字母、数字、常用标点）
            
        返回:
            DataProcessor: 支持链式调用的自身实例
        """
        cleaned_count = 0
        
        for record in self.data:
            for key, value in record.items():
                # 如果指定了字段列表，只处理这些字段
                if string_fields and key not in string_fields:
                    continue
                
                # 只处理字符串类型的值
                if not isinstance(value, str):
                    continue
                
                original_value = value
                
                if strip_whitespace:
                    value = value.strip()
                
                if lowercase:
                    value = value.lower()
                
                if remove_special_chars:
                    # 保留中文、字母、数字、空格、常用标点
                    value = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\s\.,!?;:\'\"]+', '', value)
                
                if value != original_value:
                    record[key] = value
                    cleaned_count += 1
        
        log_msg = f"字符串清洗 | 处理{cleaned_count}个字段"
        self.processing_log.append(('clean_strings', log_msg))
        logger.info(f"✅ {log_msg}")
        
        return self
    
    def map_fields(self, field_mapping: Dict[str, str]) -> 'DataProcessor':
        """
        字段映射与重命名 - 将源字段名映射为目标字段名
        
        参数:
            field_mapping: 字段映射字典 {源字段名: 目标字段名}
                          例如：{'old_name': 'new_name', 'title': 'product_name'}
                          
        返回:
            DataProcessor: 支持链式调用的自身实例
        """
        mapped_count = 0
        
        for record in self.data:
            new_record = {}
            for old_key, value in record.items():
                # 如果字段在映射表中，使用新的字段名
                new_key = field_mapping.get(old_key, old_key)
                new_record[new_key] = value
                if new_key != old_key:
                    mapped_count += 1
            
            # 替换原记录
            record.clear()
            record.update(new_record)
        
        log_msg = f"字段映射完成 | 重命名{mapped_count}个字段"
        self.processing_log.append(('map_fields', log_msg))
        logger.info(f"✅ {log_msg}")
        
        return self
    
    def filter_records(self, condition: Callable[[Dict], bool]) -> 'DataProcessor':
        """
        条件过滤 - 根据自定义条件筛选记录
        
        参数:
            condition: 过滤函数，接收一条记录（dict），返回布尔值
                      返回True表示保留该记录，False表示删除
                      
        返回:
            DataProcessor: 支持链式调用的自身实例
        """
        original_count = len(self.data)
        self.data = [record for record in self.data if condition(record)]
        
        filtered_count = original_count - len(self.data)
        self.stats['removed_invalid'] += filtered_count
        self.stats['current_count'] = len(self.data)
        
        log_msg = f"条件过滤 | 过滤掉{filtered_count}条不满足条件的记录 | 保留{len(self.data)}条"
        self.processing_log.append(('filter_records', log_msg))
        logger.info(f"✅ {log_msg}")
        
        return self
    
    def add_computed_field(self, field_name: str, 
                           compute_func: Callable[[Dict], Any]) -> 'DataProcessor':
        """
        添加计算字段 - 基于现有字段派生新字段
        
        参数:
            field_name: 新字段的名称
            compute_func: 计算函数，接收一条记录，返回新字段的值
            
        返回:
            DataProcessor: 支持链式调用的自身实例
        """
        for record in self.data:
            try:
                record[field_name] = compute_func(record)
            except Exception as e:
                logger.warning(f"⚠️ 计算字段失败 | 字段: {field_name} | 错误: {str(e)}")
                record[field_name] = None
        
        log_msg = f"添加计算字段: {field_name}"
        self.processing_log.append(('add_computed_field', log_msg))
        logger.info(f"✅ {log_msg}")
        
        return self
    
    def validate_data(self, rules: Dict[str, Callable[[Any], bool]]) -> 'DataProcessor':
        """
        数据验证 - 根据验证规则检查数据有效性
        
        参数:
            rules: 验证规则字典 {字段名: 验证函数}
                   验证函数接收字段值，返回布尔值表示是否有效
                   
        返回:
            DataProcessor: 支持链式调用的自身实例
        """
        invalid_count = 0
        valid_data = []
        
        for record in self.data:
            is_valid = True
            for field, validator in rules.items():
                if field in record:
                    if not validator(record[field]):
                        is_valid = False
                        logger.warning(f"⚠️ 数据验证失败 | 字段: {field} | 值: {record[field]}")
                        break
            
            if is_valid:
                valid_data.append(record)
            else:
                invalid_count += 1
        
        self.data = valid_data
        self.stats['removed_invalid'] += invalid_count
        self.stats['current_count'] = len(self.data)
        
        log_msg = f"数据验证 | 移除{invalid_count}条无效数据 | 保留{len(self.data)}条"
        self.processing_log.append(('validate_data', log_msg))
        logger.info(f"✅ {log_msg}")
        
        return self
    
    def process(self) -> List[Dict]:
        """
        执行数据处理管道，返回最终结果
        
        返回:
            list[Dict]: 处理后的干净数据列表
        """
        self.stats['final_count'] = len(self.data)
        
        # 输出处理摘要
        summary = (
            f"\n{'='*50}\n"
            f"📊 数据处理报告\n"
            f"{'='*50}\n"
            f"原始数据条数: {self.stats['original_count']}\n"
            f"处理后条数:   {self.stats['current_count']}\n"
            f"去重数量:     {self.stats['removed_duplicates']}\n"
            f"填充空值数:   {self.stats['filled_nulls']}\n"
            f"类型转换数:   {self.stats['converted_types']}\n"
            f"移除无效数:   {self.stats['removed_invalid']}\n"
            f"{'='*50}\n"
        )
        logger.info(summary)
        print(summary)
        
        return self.data
    
    def get_processing_log(self) -> List[tuple]:
        """
        获取处理日志
        
        返回:
            list: 处理步骤日志列表，每项为(步骤名称, 日志消息)元组
        """
        return self.processing_log
    
    def get_stats(self) -> Dict:
        """
        获取处理统计信息
        
        返回:
            dict: 统计信息字典
        """
        return self.stats.copy()


# ==================== 使用示例 ====================
if __name__ == '__main__':
    # 模拟爬虫采集的原始数据（包含各种脏数据）
    raw_data = [
        {'id': 1, 'name': '张三', 'age': 25, 'score': 85.5, 'date': '2024-01-15', 'email': 'zhangsan@test.com'},
        {'id': 2, 'name': '李四 ', 'age': None, 'score': 92.123456, 'date': '2024/01/16', 'email': 'lisi@test.com'},
        {'id': 2, 'name': '李四', 'age': 30, 'score': 78.0, 'date': '2024-01-17', 'email': 'lisi@test.com'},  # 重复
        {'id': 3, 'name': '', 'age': 28, 'score': 'N/A', 'date': 'Jan 18, 2024', 'email': None},
        {'id': 4, 'name': '王五', 'age': '35', 'score': 88.888, 'date': '2024.01.19', 'email': 'wangwu@test.com'},
        {'id': 5, 'name': '赵六', 'age': None, 'score': 76.5, 'date': None, 'email': 'zhaoliu@test.com'},
    ]
    
    print("=" * 60)
    print("📋 原始数据:")
    print("=" * 60)
    for item in raw_data:
        print(item)
    
    print("\n" + "=" * 60)
    print("🔄 开始数据清洗...")
    print("=" * 60)
    
    # 创建数据处理器并执行清洗流程（链式调用）
    processor = DataProcessor(raw_data)
    
    cleaned_data = (
        processor
        .remove_duplicates(fields=['id'])  # 基于ID去重
        .fillna(fill_map={'age': 0, 'name': '未知', 'email': 'unknown@temp.com'}, strategy='constant')  # 固定值填充
        .fillna(strategy='drop')  # 删除其他仍含空值的记录
        .standardize_dates(date_fields=['date'], output_format='%Y-%m-%d')  # 日期标准化
        .standardize_numbers(number_fields=['age', 'score'], precision=1)  # 数值标准化
        .clean_strings(string_fields=['name'], strip_whitespace=True)  # 字符串清洗
        .map_fields({'name': 'user_name', 'score': 'exam_score'})  # 字段重命名
        .filter_records(lambda x: x.get('exam_score', 0) >= 70)  # 分数>=70才保留
        .process()  # 执行并返回结果
    )
    
    print("\n" + "=" * 60)
    print("✅ 清洗后的数据:")
    print("=" * 60)
    for item in cleaned_data:
        print(item)
    
    # 查看处理日志
    print("\n📝 处理步骤日志:")
    for step, msg in processor.get_processing_log():
        print(f"  [{step}] {msg}")
    
    # 查看统计信息
    print("\n📈 统计信息:")
    for key, value in processor.get_stats().items():
        print(f"  {key}: {value}")
