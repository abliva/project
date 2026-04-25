import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import tkinter.messagebox as messagebox
import tkinter.simpledialog as simpledialog
from tkinter.scrolledtext import ScrolledText
import sqlite3
import json
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates
from matplotlib.figure import Figure
import numpy as np
import pandas as pd
import csv
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading
import random
# 在文件顶部的导入部分，添加以下代码
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']  # 设置中文字体
matplotlib.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

class HealthRecord:
    """健康记录类"""

    def __init__(self, date: str, height: float, weight: float,
                 blood_pressure: str, blood_sugar: float, heart_rate: int = 0, notes: str = ""):
        self.date = date
        self.height = height  # 米
        self.weight = weight  # 千克
        self.blood_pressure = blood_pressure  # 格式: "120/80"
        self.blood_sugar = blood_sugar  # 血糖，单位: mmol/L
        self.heart_rate = heart_rate  # 心率
        self.notes = notes

    @property
    def bmi(self) -> float:
        """计算BMI"""
        if self.height > 0:
            return round(self.weight / (self.height ** 2), 2)
        return 0

    @property
    def bmi_category(self) -> str:
        """BMI分类"""
        bmi = self.bmi
        if bmi < 18.5:
            return "偏瘦"
        elif bmi < 24:
            return "正常"
        elif bmi < 28:
            return "超重"
        else:
            return "肥胖"

    @property
    def bmi_color(self) -> str:
        """根据BMI分类返回颜色"""
        bmi = self.bmi
        if bmi < 18.5:
            return "#4A90E2"  # 蓝色
        elif bmi < 24:
            return "#7ED321"  # 绿色
        elif bmi < 28:
            return "#F5A623"  # 橙色
        else:
            return "#D0021B"  # 红色

    @property
    def blood_pressure_sys(self) -> int:
        """获取收缩压（高压）"""
        if '/' in self.blood_pressure:
            try:
                return int(self.blood_pressure.split('/')[0])
            except:
                return 0
        return 0

    @property
    def blood_pressure_dia(self) -> int:
        """获取舒张压（低压）"""
        if '/' in self.blood_pressure:
            try:
                return int(self.blood_pressure.split('/')[1])
            except:
                return 0
        return 0

    @property
    def blood_pressure_category(self) -> str:
        """血压分类"""
        sys_bp = self.blood_pressure_sys
        dia_bp = self.blood_pressure_dia

        if sys_bp < 90 or dia_bp < 60:
            return "低血压"
        elif sys_bp < 120 and dia_bp < 80:
            return "正常"
        elif sys_bp < 130 and dia_bp < 80:
            return "正常偏高"
        elif sys_bp < 140 or dia_bp < 90:
            return "高血压1级"
        elif sys_bp < 180 or dia_bp < 120:
            return "高血压2级"
        else:
            return "高血压危象"

    @property
    def blood_sugar_category(self) -> str:
        """血糖分类"""
        if self.blood_sugar < 3.9:
            return "低血糖"
        elif self.blood_sugar <= 6.1:
            return "正常"
        elif self.blood_sugar <= 7.0:
            return "糖尿病前期"
        else:
            return "糖尿病"

    @property
    def heart_rate_category(self) -> str:
        """心率分类"""
        if self.heart_rate < 60:
            return "心动过缓"
        elif self.heart_rate <= 100:
            return "正常"
        else:
            return "心动过速"

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "date": self.date,
            "height": self.height,
            "weight": self.weight,
            "blood_pressure": self.blood_pressure,
            "blood_sugar": self.blood_sugar,
            "heart_rate": self.heart_rate,
            "notes": self.notes,
            "bmi": self.bmi,
            "bmi_category": self.bmi_category,
            "bmi_color": self.bmi_color,
            "blood_pressure_category": self.blood_pressure_category,
            "blood_sugar_category": self.blood_sugar_category,
            "heart_rate_category": self.heart_rate_category
        }


class HealthDatabase:
    """健康数据库管理类"""

    def __init__(self, db_path='health_records.db'):
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """初始化数据库"""
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

        # 创建用户表
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                role TEXT DEFAULT 'user',  -- user, family, admin
                full_name TEXT,
                birth_date TEXT,
                gender TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        ''')

        # 创建家属关系表
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS family_relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                family_user_id INTEGER NOT NULL,
                relationship TEXT,  -- 父亲, 母亲, 子女, 配偶等
                can_edit INTEGER DEFAULT 0,  -- 是否可以编辑
                can_view INTEGER DEFAULT 1,  -- 是否可以查看
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (family_user_id) REFERENCES users (id),
                UNIQUE(user_id, family_user_id)
            )
        ''')

        # 创建健康记录表
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS health_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                height REAL,
                weight REAL,
                blood_pressure TEXT,
                blood_sugar REAL,
                heart_rate INTEGER,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

        # 创建提醒表
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS health_reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                reminder_type TEXT,  -- medication, appointment, exercise, etc.
                reminder_time TEXT NOT NULL,  -- HH:MM
                days_of_week TEXT,  -- 1,2,3,4,5,6,7
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

        # 创建报警记录表
        self.cursor.execute('''
                    CREATE TABLE IF NOT EXISTS health_alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        user_name TEXT NOT NULL,
                        alert_type TEXT NOT NULL,
                        alert_value TEXT,
                        normal_range TEXT,
                        deviation TEXT,
                        alert_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_notified INTEGER DEFAULT 0,
                        notification_method TEXT,  -- email, sms
                        FOREIGN KEY (user_id) REFERENCES users (id)
                    )
                ''')

        # 创建标准参考值表
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS health_standards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                indicator_name TEXT NOT NULL,
                min_normal REAL,
                max_normal REAL,
                unit TEXT,
                age_group TEXT,  -- all, child, adult, elderly
                gender TEXT,  -- all, male, female
                description TEXT
            )
        ''')

        # 创建个人设置表
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                setting_key TEXT NOT NULL,
                setting_value TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                UNIQUE(user_id, setting_key)
            )
        ''')

        # 插入默认管理员用户 (用户名: admin, 密码: admin123)
        try:
            password_hash = hashlib.sha256("admin123".encode()).hexdigest()
            self.cursor.execute('''
                INSERT OR IGNORE INTO users (username, password_hash, email, role, full_name)
                VALUES (?, ?, ?, ?, ?)
            ''', ('admin', password_hash, 'admin@health.com', 'admin', '系统管理员'))
        except:
            pass

        # 插入默认标准参考值
        self._init_health_standards()

        # 插入测试用户
        self._create_test_users()

        self.conn.commit()

    def _init_health_standards(self):
        """初始化标准参考值"""
        standards = [
            # BMI标准
            ('BMI', 18.5, 24.0, 'kg/m²', 'adult', 'all', '身体质量指数'),
            # 血压标准
            ('血压收缩压', 90, 140, 'mmHg', 'adult', 'all', '收缩压（高压）正常范围'),
            ('血压舒张压', 60, 90, 'mmHg', 'adult', 'all', '舒张压（低压）正常范围'),
            # 血糖标准
            ('空腹血糖', 3.9, 6.1, 'mmol/L', 'adult', 'all', '空腹血糖正常范围'),
            ('餐后2小时血糖', 4.4, 7.8, 'mmol/L', 'adult', 'all', '餐后2小时血糖正常范围'),
            # 心率标准
            ('静息心率', 60, 100, '次/分钟', 'adult', 'all', '静息心率正常范围'),
            # 体重标准
            ('体重指数', 0, 0, 'kg', 'adult', 'all', '需根据身高计算'),
        ]

        for std in standards:
            self.cursor.execute('''
                INSERT OR IGNORE INTO health_standards 
                (indicator_name, min_normal, max_normal, unit, age_group, gender, description)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', std)

    def _create_test_users(self):
        """创建测试用户和虚拟数据"""
        # 测试用户列表
        test_users = [
            ('张三', 'zhangsan', 'zhangsan123', 'user', 'zhangsan@test.com', '1990-05-15', '男'),
            ('李四', 'lisi', 'lisi123', 'user', 'lisi@test.com', '1985-08-22', '男'),
            ('王五', 'wangwu', 'wangwu123', 'user', 'wangwu@test.com', '1992-11-30', '女'),
            ('赵六', 'zhaoliu', 'zhaoliu123', 'family', 'zhaoliu@test.com', '1995-03-10', '女'),
            ('家属用户', 'family1', 'family123', 'family', 'family@test.com', '1978-12-05', '男'),
        ]

        for full_name, username, password, role, email, birth_date, gender in test_users:
            try:
                password_hash = hashlib.sha256(password.encode()).hexdigest()
                self.cursor.execute('''
                    INSERT OR IGNORE INTO users (username, password_hash, email, role, full_name, birth_date, gender)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (username, password_hash, email, role, full_name, birth_date, gender))
            except:
                continue

        # 为测试用户创建虚拟健康数据
        self._create_virtual_health_data()

    def _create_virtual_health_data(self):
        """为测试用户创建虚拟健康数据"""
        # 获取测试用户
        self.cursor.execute("SELECT id FROM users WHERE username IN ('zhangsan', 'lisi', 'wangwu')")
        user_ids = [row[0] for row in self.cursor.fetchall()]

        for user_id in user_ids:
            # 为每个用户创建30天的虚拟数据
            for i in range(30):
                date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')

                # 生成虚拟数据
                height = round(random.uniform(1.65, 1.85), 2)  # 身高 1.65-1.85米
                weight = round(random.uniform(60, 80), 1)  # 体重 60-80kg

                # 血压
                sys_bp = random.randint(110, 130)
                dia_bp = random.randint(70, 85)
                blood_pressure = f"{sys_bp}/{dia_bp}"

                # 血糖
                blood_sugar = round(random.uniform(4.5, 6.5), 1)

                # 心率
                heart_rate = random.randint(65, 85)

                # 备注
                notes = "测试数据"

                # 插入记录
                self.cursor.execute('''
                    INSERT OR IGNORE INTO health_records 
                    (user_id, date, height, weight, blood_pressure, blood_sugar, heart_rate, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, date, height, weight, blood_pressure, blood_sugar, heart_rate, notes))

        self.conn.commit()

    def add_user(self, username, password, email=None, phone=None, role='user',
                 full_name=None, birth_date=None, gender=None):
        """添加用户"""
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        try:
            self.cursor.execute('''
                INSERT INTO users (username, password_hash, email, phone, role, full_name, birth_date, gender)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (username, password_hash, email, phone, role, full_name, birth_date, gender))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.IntegrityError:
            return None

    def authenticate_user(self, username, password):
        """验证用户"""
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        self.cursor.execute('''
            SELECT id, username, email, role, full_name, birth_date, gender FROM users 
            WHERE username = ? AND password_hash = ? AND is_active = 1
        ''', (username, password_hash))

        user = self.cursor.fetchone()
        if user:
            return {
                'id': user[0],
                'username': user[1],
                'email': user[2],
                'role': user[3],
                'full_name': user[4],
                'birth_date': user[5],
                'gender': user[6]
            }
        return None

    def get_user_by_id(self, user_id):
        """根据ID获取用户"""
        self.cursor.execute('SELECT id, username, email, role, full_name, birth_date, gender FROM users WHERE id = ?',
                            (user_id,))
        user = self.cursor.fetchone()
        if user:
            return {
                'id': user[0],
                'username': user[1],
                'email': user[2],
                'role': user[3],
                'full_name': user[4],
                'birth_date': user[5],
                'gender': user[6]
            }
        return None

    # 修正后的get_user_health_records方法
    def get_user_health_records(self, user_id) -> list:
        """获取用户的健康记录"""
        self.cursor.execute('''
            SELECT * FROM health_records 
            WHERE user_id = ? 
            ORDER BY date DESC
        ''', (user_id,))
        rows = self.cursor.fetchall()

        records = []
        for row in rows:
            record = HealthRecord(
                date=row[2],
                height=row[3],
                weight=row[4],
                blood_pressure=row[5],
                blood_sugar=row[6],
                heart_rate=row[7],
                notes=row[8]
            )
            records.append(record.to_dict())

        return records

    def add_record(self, user_id, record: HealthRecord):
        """添加健康记录到数据库"""
        try:
            self.cursor.execute('''
                INSERT INTO health_records 
                (user_id, date, height, weight, blood_pressure, blood_sugar, heart_rate, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                record.date,
                record.height,
                record.weight,
                record.blood_pressure,
                record.blood_sugar,
                record.heart_rate,
                record.notes
            ))

            record_id = self.cursor.lastrowid
            self.conn.commit()

            # 检查健康报警
            alerts = self._check_health_alerts(user_id, record)

            return record_id,alerts
        except Exception as e:
            print(f"添加记录失败: {e}")
            self.conn.rollback()
            return None

    def get_user_alerts(self, user_id, limit=20):
        """获取用户的报警记录"""
        self.cursor.execute('''
            SELECT id, alert_type, alert_value, normal_range, 
                   alert_time, is_notified, notification_method
            FROM health_alerts 
            WHERE user_id = ? 
            ORDER BY alert_time DESC
            LIMIT ?
        ''', (user_id, limit))

        alerts = []
        for row in self.cursor.fetchall():
            alerts.append({
                'id': row[0],
                'alert_type': row[1],
                'alert_value': row[2],
                'normal_range': row[3],
                'alert_time': row[4],
                'is_notified': bool(row[5]),
                'notification_method': row[6]
            })
        return alerts

    def mark_alert_notified(self, alert_id):
        """标记报警为已通知"""
        self.cursor.execute('''
            UPDATE health_alerts 
            SET is_notified = 1 
            WHERE id = ?
        ''', (alert_id,))
        self.conn.commit()
        return self.cursor.rowcount > 0

    # 添加设置相关的方法
    def get_user_settings(self, user_id):
        """获取用户的所有设置"""
        self.cursor.execute('''
            SELECT setting_key, setting_value FROM user_settings 
            WHERE user_id = ?
        ''', (user_id,))

        settings = {}
        for row in self.cursor.fetchall():
            settings[row[0]] = row[1]
        return settings

    def set_user_setting(self, user_id, key, value):
        """设置用户配置项"""
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO user_settings (user_id, setting_key, setting_value, updated_at)
                VALUES (?, ?, ?, ?)
            ''', (user_id, key, value, datetime.now()))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"保存设置失败: {e}")
            return False

    def delete_user_setting(self, user_id, key):
        """删除用户配置项"""
        try:
            self.cursor.execute('''
                DELETE FROM user_settings WHERE user_id = ? AND setting_key = ?
            ''', (user_id, key))
            self.conn.commit()
            return True
        except:
            return False

    def add_family_member(self, user_id, family_username, relationship, can_edit=0, can_view=1):
        """添加家属成员"""
        # 首先查找家属用户
        self.cursor.execute('SELECT id FROM users WHERE username = ?', (family_username,))
        family_user = self.cursor.fetchone()

        if not family_user:
            return False, "用户不存在"

        family_user_id = family_user[0]

        # 检查是否已经是家属
        self.cursor.execute('''
            SELECT id FROM family_relationships 
            WHERE user_id = ? AND family_user_id = ?
        ''', (user_id, family_user_id))

        if self.cursor.fetchone():
            return False, "已经是家属成员"

        try:
            self.cursor.execute('''
                INSERT INTO family_relationships (user_id, family_user_id, relationship, can_edit, can_view)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, family_user_id, relationship, can_edit, can_view))
            self.conn.commit()
            return True, "添加成功"
        except Exception as e:
            return False, str(e)

    def get_family_members(self, user_id):
        """获取家属成员"""
        self.cursor.execute('''
            SELECT u.id, u.username, u.full_name, u.email, fr.relationship, fr.can_edit, fr.can_view
            FROM family_relationships fr
            JOIN users u ON fr.family_user_id = u.id
            WHERE fr.user_id = ? AND u.is_active = 1
        ''', (user_id,))

        members = []
        for row in self.cursor.fetchall():
            members.append({
                'id': row[0],
                'username': row[1],
                'full_name': row[2],
                'email': row[3],
                'relationship': row[4],
                'can_edit': row[5],
                'can_view': row[6]
            })

        return members

    def get_family_health_records(self, user_id, family_user_id):
        """获取家属的健康记录"""
        # 检查是否有权限
        self.cursor.execute('''
            SELECT can_view FROM family_relationships 
            WHERE user_id = ? AND family_user_id = ?
        ''', (user_id, family_user_id))

        permission = self.cursor.fetchone()
        if not permission or permission[0] == 0:
            return []

        return self.get_user_health_records(family_user_id)



    def _check_health_alerts(self, user_id, record):
        """检查健康报警（增强版）"""
        alerts = []

        # 获取用户信息用于报警信息
        self.cursor.execute("SELECT full_name, username FROM users WHERE id = ?", (user_id,))
        user_info = self.cursor.fetchone()
        user_name = user_info[0] if user_info[0] else user_info[1]

        # 检查BMI
        bmi = record.bmi
        if bmi < 18.5:
            deviation = f"偏低 {18.5 - bmi:.1f}"
            alerts.append(('BMI异常', f"偏瘦: {bmi}", "正常范围: 18.5-24.0", deviation, user_id, user_name))
        elif bmi >= 24 and bmi < 28:
            deviation = f"偏高 {bmi - 24:.1f}"
            alerts.append(('BMI异常', f"超重: {bmi}", "正常范围: 18.5-24.0", deviation, user_id, user_name))
        elif bmi >= 28:
            deviation = f"严重偏高 {bmi - 24:.1f}"
            alerts.append(('BMI异常', f"肥胖: {bmi}", "正常范围: 18.5-24.0", deviation, user_id, user_name))

        # 检查血压
        sys_bp = record.blood_pressure_sys
        dia_bp = record.blood_pressure_dia

        if sys_bp < 90:
            deviation = f"偏低 {90 - sys_bp}"
            alerts.append(
                ('血压异常', f"低血压: {sys_bp}/{dia_bp}", "正常范围: 90-140/60-90", deviation, user_id, user_name))
        elif sys_bp >= 140:
            deviation = f"偏高 {sys_bp - 140}"
            alerts.append(
                ('血压异常', f"高血压: {sys_bp}/{dia_bp}", "正常范围: 90-140/60-90", deviation, user_id, user_name))

        if dia_bp < 60:
            deviation = f"偏低 {60 - dia_bp}"
            alerts.append(
                ('血压异常', f"低血压: {sys_bp}/{dia_bp}", "正常范围: 90-140/60-90", deviation, user_id, user_name))
        elif dia_bp >= 90:
            deviation = f"偏高 {dia_bp - 90}"
            alerts.append(
                ('血压异常', f"高血压: {sys_bp}/{dia_bp}", "正常范围: 90-140/60-90", deviation, user_id, user_name))

        # 检查血糖
        if record.blood_sugar < 3.9:
            deviation = f"偏低 {3.9 - record.blood_sugar:.1f}"
            alerts.append(
                ('血糖异常', f"低血糖: {record.blood_sugar}", "正常范围: 3.9-6.1", deviation, user_id, user_name))
        elif record.blood_sugar > 6.1:
            deviation = f"偏高 {record.blood_sugar - 6.1:.1f}"
            alerts.append(
                ('血糖异常', f"高血糖: {record.blood_sugar}", "正常范围: 3.9-6.1", deviation, user_id, user_name))

        # 检查心率
        if record.heart_rate > 0:
            if record.heart_rate < 60:
                deviation = f"偏低 {60 - record.heart_rate}"
                alerts.append(
                    ('心率异常', f"心动过缓: {record.heart_rate}", "正常范围: 60-100", deviation, user_id, user_name))
            elif record.heart_rate > 100:
                deviation = f"偏高 {record.heart_rate - 100}"
                alerts.append(
                    ('心率异常', f"心动过速: {record.heart_rate}", "正常范围: 60-100", deviation, user_id, user_name))

        # 记录报警
        for alert_type, alert_value, normal_range, deviation, user_id, user_name in alerts:
            self.cursor.execute('''
                INSERT INTO health_alerts (user_id, user_name, alert_type, alert_value, normal_range, deviation, alert_time, is_notified)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, user_name, alert_type, alert_value, normal_range, deviation, datetime.now(), 0))

        # 如果有报警，尝试发送通知
        if alerts:
            self._try_send_notifications(user_id, alerts)

    def _try_send_notifications(self, user_id, alerts):
        """尝试发送通知（改进版）"""
        try:
            # 获取用户信息
            self.cursor.execute("SELECT username, full_name FROM users WHERE id = ?", (user_id,))
            user_info = self.cursor.fetchone()

            if user_info:
                username, full_name = user_info
                user_name = full_name or username

                # 构建报警信息
                alert_data = []
                for alert in alerts:
                    alert_type, alert_value, normal_range, deviation, alert_user_id, alert_user_name = alert
                    alert_data.append({
                        'type': alert_type,
                        'value': alert_value,
                        'range': normal_range,
                        'deviation': deviation,
                        'user_name': alert_user_name
                    })

                # 这里可以添加邮件或短信通知逻辑
                # 例如：self._send_email_notification(user_id, alert_data)

                print(f"健康报警：用户 {user_name} 有 {len(alerts)} 条报警")

                # 返回报警信息供GUI使用
                return alert_data

        except Exception as e:
            print(f"发送通知失败: {e}")

        return None

    def add_reminder(self, user_id, title, description, reminder_type, reminder_time, days_of_week):
        """添加提醒"""
        self.cursor.execute('''
            INSERT INTO health_reminders (user_id, title, description, reminder_type, reminder_time, days_of_week)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, title, description, reminder_type, reminder_time, days_of_week))
        self.conn.commit()
        return self.cursor.lastrowid

    def get_user_reminders(self, user_id):
        """获取用户的提醒"""
        self.cursor.execute('''
            SELECT * FROM health_reminders 
            WHERE user_id = ? AND is_active = 1
            ORDER BY reminder_time
        ''', (user_id,))

        reminders = []
        for row in self.cursor.fetchall():
            reminders.append({
                'id': row[0],
                'title': row[2],
                'description': row[3],
                'type': row[4],
                'time': row[5],
                'days': row[6]
            })

        return reminders

    def get_health_standards(self):
        """获取健康标准参考值"""
        self.cursor.execute('SELECT * FROM health_standards')

        standards = []
        for row in self.cursor.fetchall():
            standards.append({
                'id': row[0],
                'name': row[1],
                'min_normal': row[2],
                'max_normal': row[3],
                'unit': row[4],
                'age_group': row[5],
                'gender': row[6],
                'description': row[7]
            })

        return standards

    def backup_database(self, backup_path):
        """备份数据库"""
        import shutil
        try:
            shutil.copy2(self.db_path, backup_path)
            return True, "备份成功"
        except Exception as e:
            return False, str(e)

    def restore_database(self, backup_path):
        """恢复数据库"""
        import shutil
        try:
            # 先关闭当前连接
            self.conn.close()
            # 恢复备份
            shutil.copy2(backup_path, self.db_path)
            # 重新连接
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
            return True, "恢复成功"
        except Exception as e:
            return False, str(e)

    def get_all_users(self):
        """获取所有用户（管理员用）"""
        self.cursor.execute('''
            SELECT id, username, email, role, full_name, birth_date, gender, created_at, is_active
            FROM users ORDER BY created_at DESC
        ''')

        users = []
        for row in self.cursor.fetchall():
            users.append({
                'id': row[0],
                'username': row[1],
                'email': row[2],
                'role': row[3],
                'full_name': row[4],
                'birth_date': row[5],
                'gender': row[6],
                'created_at': row[7],
                'is_active': row[8]
            })

        return users

    def update_user_role(self, user_id, role):
        """更新用户角色"""
        self.cursor.execute('UPDATE users SET role = ? WHERE id = ?', (role, user_id))
        self.conn.commit()
        return self.cursor.rowcount > 0

    def deactivate_user(self, user_id):
        """停用用户"""
        self.cursor.execute('UPDATE users SET is_active = 0 WHERE id = ?', (user_id,))
        self.conn.commit()
        return self.cursor.rowcount > 0

    def activate_user(self, user_id):
        """激活用户"""
        self.cursor.execute('UPDATE users SET is_active = 1 WHERE id = ?', (user_id,))
        self.conn.commit()
        return self.cursor.rowcount > 0

    def update_user_info(self, user_id, email=None, phone=None, full_name=None, birth_date=None, gender=None):
        """更新用户信息"""
        try:
            # 构建更新语句
            updates = []
            params = []

            if email is not None:
                updates.append("email = ?")
                params.append(email)
            if phone is not None:
                updates.append("phone = ?")
                params.append(phone)
            if full_name is not None:
                updates.append("full_name = ?")
                params.append(full_name)
            if birth_date is not None:
                updates.append("birth_date = ?")
                params.append(birth_date)
            if gender is not None:
                updates.append("gender = ?")
                params.append(gender)

            if not updates:
                return False

            params.append(user_id)

            sql = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
            self.cursor.execute(sql, params)
            self.conn.commit()
            return self.cursor.rowcount > 0
        except Exception as e:
            print(f"更新用户信息失败: {e}")
            return False

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()


class LoginWindow:
    """登录窗口"""

    def __init__(self, root, db):
        self.root = root
        self.db = db

        self.root.title("健康管理系统 - 登录")
        self.root.geometry("400x300")

        # 设置样式
        self.colors = {
            "primary": "#2E86C1",
            "light": "#F8F9F9",
            "dark": "#212121"
        }

        self.title_font = ("Microsoft YaHei", 18, "bold")
        self.heading_font = ("Microsoft YaHei", 12, "bold")
        self.normal_font = ("Microsoft YaHei", 10)

        # 创建界面
        self.create_widgets()

        # 居中显示
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

    def create_widgets(self):
        """创建界面组件"""
        # 主框架
        main_frame = tk.Frame(self.root, bg="white", padx=30, pady=30)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 标题
        title_label = tk.Label(main_frame, text="健康管理系统",
                               font=self.title_font, bg="white",
                               fg=self.colors["primary"])
        title_label.pack(pady=(0, 20))

        # 用户名
        tk.Label(main_frame, text="用户名:", font=self.normal_font,
                 bg="white").pack(anchor=tk.W, pady=(10, 0))

        self.username_var = tk.StringVar()
        username_entry = tk.Entry(main_frame, textvariable=self.username_var,
                                  font=self.normal_font, width=30)
        username_entry.pack(pady=5)
        username_entry.focus()

        # 密码
        tk.Label(main_frame, text="密码:", font=self.normal_font,
                 bg="white").pack(anchor=tk.W, pady=(10, 0))

        self.password_var = tk.StringVar()
        password_entry = tk.Entry(main_frame, textvariable=self.password_var,
                                  font=self.normal_font, width=30, show="*")
        password_entry.pack(pady=5)

        # 测试账号提示
        test_frame = tk.Frame(main_frame, bg="white")
        test_frame.pack(pady=(10, 0))

        tk.Label(test_frame, text="测试账号:", font=("Microsoft YaHei", 8),
                 bg="white", fg="gray").pack(side=tk.LEFT)

        test_users = [
            ("admin/admin123", "管理员"),
            ("zhangsan/zhangsan123", "普通用户1"),
            ("lisi/lisi123", "普通用户2"),
            ("family1/family123", "家属用户")
        ]

        for i, (account, role) in enumerate(test_users):
            tk.Label(test_frame, text=f"{account} ({role})",
                     font=("Microsoft YaHei", 8), bg="white", fg="blue",
                     cursor="hand2").pack(side=tk.LEFT, padx=(5, 0))
            if i < len(test_users) - 1:
                tk.Label(test_frame, text="|", font=("Microsoft YaHei", 8),
                         bg="white", fg="gray").pack(side=tk.LEFT, padx=2)

        # 登录按钮
        login_btn = tk.Button(main_frame, text="登录", font=self.heading_font,
                              bg=self.colors["primary"], fg="white",
                              width=20, pady=10, command=self.login)
        login_btn.pack(pady=20)

        # 注册按钮
        register_btn = tk.Button(main_frame, text="注册新用户", font=self.normal_font,
                                 bg="white", fg=self.colors["primary"],
                                 command=self.show_register, cursor="hand2")
        register_btn.pack()

        # 绑定回车键
        username_entry.bind('<Return>', lambda e: password_entry.focus())
        password_entry.bind('<Return>', lambda e: self.login())

    def login(self):
        """登录"""
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()

        if not username or not password:
            messagebox.showerror("错误", "请输入用户名和密码")
            return

        user = self.db.authenticate_user(username, password)

        if user:
            self.root.destroy()
            # 启动主应用
            main_root = tk.Tk()
            app = HealthApp(main_root, self.db, user)
            main_root.mainloop()
        else:
            messagebox.showerror("错误", "用户名或密码错误")

    def show_register(self):
        """显示注册窗口"""
        RegisterWindow(tk.Toplevel(self.root), self.db)


class RegisterWindow:
    """注册窗口"""

    def __init__(self, root, db):
        self.root = root
        self.db = db

        self.root.title("注册新用户")
        self.root.geometry("500x500")

        # 设置样式
        self.colors = {
            "primary": "#2E86C1",
            "secondary": "#3498DB",
            "success": "#28B463",
            "warning": "#F39C12",
            "danger": "#E74C3C",
            "light": "#F8F9F9",
            "dark": "#212121",
            "info": "#17A2B8",
            "gray": "#95A5A6"
        }

        self.title_font = ("Microsoft YaHei", 16, "bold")
        self.heading_font = ("Microsoft YaHei", 12, "bold")
        self.normal_font = ("Microsoft YaHei", 10)

        # 创建界面
        self.create_widgets()

        # 居中显示
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

        # 设置模态
        self.root.transient()
        self.root.grab_set()

    def create_widgets(self):
        """创建界面组件"""
        # 主框架
        main_frame = tk.Frame(self.root, padx=30, pady=30)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 标题
        title_label = tk.Label(main_frame, text="注册新用户",
                               font=self.title_font, fg=self.colors["primary"])
        title_label.pack(pady=(0, 20))

        # 创建表单
        fields = [
            ("用户名*:", "entry", "", True),
            ("密码*:", "entry", "", True, "*"),
            ("确认密码*:", "entry", "", True, "*"),
            ("邮箱:", "entry", ""),
            ("电话:", "entry", ""),
            ("姓名:", "entry", ""),
            ("出生日期:", "entry", "YYYY-MM-DD"),
            ("性别:", "combo", ["", "男", "女"]),
        ]

        self.form_vars = {}

        for i, (label, field_type, default, *options) in enumerate(fields):
            frame = tk.Frame(main_frame)
            frame.pack(fill=tk.X, pady=10)

            tk.Label(frame, text=label, font=self.normal_font,
                     width=15, anchor=tk.W).pack(side=tk.LEFT)

            if field_type == "entry":
                var = tk.StringVar(value=default)
                show_char = "*" if len(options) > 1 and options[1] == "*" else ""
                entry = tk.Entry(frame, textvariable=var, font=self.normal_font,
                                 width=25, show=show_char)
                entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
                self.form_vars[label[:-1]] = var
            elif field_type == "combo":
                var = tk.StringVar(value=default[0])
                combo = ttk.Combobox(frame, textvariable=var,
                                     values=default, state="readonly", width=23)
                combo.pack(side=tk.LEFT)
                self.form_vars[label[:-1]] = var

        # 按钮框架
        button_frame = tk.Frame(main_frame)
        button_frame.pack(pady=30)

        # 注册按钮
        register_btn = tk.Button(button_frame, text="注册",
                                 bg=self.colors["primary"], fg="white",
                                 font=self.heading_font, padx=30, pady=10,
                                 command=self.register)
        register_btn.pack(side=tk.LEFT, padx=10)

        # 取消按钮
        cancel_btn = tk.Button(button_frame, text="取消",
                               bg="gray", fg="white",
                               font=self.heading_font, padx=30, pady=10,
                               command=self.root.destroy)
        cancel_btn.pack(side=tk.LEFT, padx=10)

    def register(self):
        """注册用户"""
        # 获取表单数据
        username = self.form_vars["用户名"].get().strip()
        password = self.form_vars["密码"].get().strip()
        confirm_password = self.form_vars["确认密码"].get().strip()
        email = self.form_vars["邮箱"].get().strip()
        phone = self.form_vars["电话"].get().strip()
        full_name = self.form_vars["姓名"].get().strip()
        birth_date = self.form_vars["出生日期"].get().strip()
        gender = self.form_vars["性别"].get().strip()

        # 验证
        if not username or not password:
            messagebox.showerror("错误", "用户名和密码不能为空")
            return

        if password != confirm_password:
            messagebox.showerror("错误", "两次输入的密码不一致")
            return

        if len(password) < 6:
            messagebox.showerror("错误", "密码长度不能少于6位")
            return

        # 注册用户
        user_id = self.db.add_user(username, password, email, phone,
                                   'user', full_name, birth_date, gender)

        if user_id:
            messagebox.showinfo("成功", "注册成功！请使用新账户登录")
            self.root.destroy()
        else:
            messagebox.showerror("错误", "用户名已存在")


class HealthApp:
    """健康管理应用主窗口"""

    def __init__(self, root, db, current_user):
        self.root = root
        self.db = db
        self.current_user = current_user

        self.root.title(f"个人健康管理档案系统 - {current_user['full_name'] or current_user['username']}")
        self.root.geometry("1200x700")
        # 设置应用图标和样式
        self.setup_style()
        # 创建界面
        self.create_widgets()
        # 更新统计信息
        self.update_statistics()
        # 检查并显示未读报警
        self.root.after(1000, self.check_and_show_alerts)
    def setup_style(self):
        """设置样式"""
        # 设置颜色主题
        self.colors = {
            "primary": "#2E86C1",
            "secondary": "#3498DB",
            "success": "#28B463",
            "warning": "#F39C12",
            "danger": "#E74C3C",
            "light": "#F8F9F9",
            "dark": "#212121",
            "gray": "#95A5A6"
        }

        # 设置字体
        self.title_font = ("Microsoft YaHei", 16, "bold")
        self.heading_font = ("Microsoft YaHei", 12, "bold")
        self.normal_font = ("Microsoft YaHei", 10)

        # 配置样式
        style = ttk.Style()
        style.theme_use('clam')

        # 配置Treeview样式
        style.configure("Treeview.Heading", font=self.heading_font,
                        background=self.colors["primary"], foreground="white")
        style.configure("Treeview", font=self.normal_font, rowheight=25)
        style.map("Treeview", background=[('selected', self.colors["secondary"])])

    def create_widgets(self):
        """创建界面组件"""
        # 创建主容器
        main_container = tk.Frame(self.root, bg=self.colors["light"])
        main_container.pack(fill=tk.BOTH, expand=True)

        # 左侧面板 - 功能菜单
        left_panel = tk.Frame(main_container, width=250, bg=self.colors["dark"])
        left_panel.pack(side=tk.LEFT, fill=tk.Y)
        left_panel.pack_propagate(False)

        # 用户信息
        user_frame = tk.Frame(left_panel, bg=self.colors["dark"])
        user_frame.pack(fill=tk.X, padx=10, pady=20)

        user_icon = tk.Label(user_frame, text="👤", font=("Arial", 24),
                             bg=self.colors["dark"], fg="white")
        user_icon.pack(side=tk.LEFT, padx=(0, 10))

        user_info = tk.Frame(user_frame, bg=self.colors["dark"])
        user_info.pack(side=tk.LEFT)

        tk.Label(user_info, text=self.current_user['full_name'] or self.current_user['username'],
                 font=self.heading_font, bg=self.colors["dark"],
                 fg="white", anchor=tk.W).pack(fill=tk.X)

        role_text = "管理员" if self.current_user['role'] == 'admin' else "用户"
        tk.Label(user_info, text=f"角色: {role_text}",
                 font=self.normal_font, bg=self.colors["dark"],
                 fg=self.colors["gray"], anchor=tk.W).pack(fill=tk.X)

        # 应用标题
        title_label = tk.Label(left_panel, text="健康管理系统",
                               font=self.title_font, bg=self.colors["dark"],
                               fg="white", pady=10)
        title_label.pack(fill=tk.X)

        # 功能按钮
        self.create_menu_buttons(left_panel)

        # 右侧面板 - 主内容区
        right_panel = tk.Frame(main_container, bg=self.colors["light"])
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # 创建顶部工具栏
        self.create_toolbar(right_panel)

        # 创建内容区域
        self.content_frame = tk.Frame(right_panel, bg=self.colors["light"])
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 默认显示仪表板
        self.show_dashboard()

    def create_menu_buttons(self, parent):
        """创建菜单按钮"""
        # 基础功能按钮
        buttons_info = [
            ("📊 仪表板", self.show_dashboard),
            ("➕ 添加记录", self.show_add_record),
            ("📋 我的记录", self.show_my_records),
            ("📈 数据分析", self.show_analysis),
            ("📊 健康报告", self.show_report),
        ]

        for text, command in buttons_info:
            btn = tk.Button(parent, text=text, font=self.heading_font,
                            bg=self.colors["primary"], fg="white",
                            activebackground=self.colors["secondary"],
                            activeforeground="white",
                            relief=tk.FLAT, padx=20, pady=15,
                            command=command, cursor="hand2")
            btn.pack(fill=tk.X, padx=10, pady=2)

        # 家属/监护人模块按钮
        if self.current_user['role'] in ['user', 'family']:
            tk.Label(parent, text="家属管理", font=self.heading_font,
                     bg=self.colors["dark"], fg=self.colors["gray"],
                     pady=10).pack(fill=tk.X, padx=10)

            family_buttons = [
                ("👨‍👩‍👧 家属列表", self.show_family_list),
                ("🔔 健康提醒", self.show_reminders),
                ("⚠️ 报警通知", self.show_alerts),
            ]

            for text, command in family_buttons:
                btn = tk.Button(parent, text=text, font=self.heading_font,
                                bg="#8E44AD", fg="white",  # 紫色表示家属功能
                                activebackground="#9B59B6",
                                activeforeground="white",
                                relief=tk.FLAT, padx=20, pady=10,
                                command=command, cursor="hand2")
                btn.pack(fill=tk.X, padx=10, pady=2)

        # 管理员模块按钮
        if self.current_user['role'] == 'admin':
            tk.Label(parent, text="管理员功能", font=self.heading_font,
                     bg=self.colors["dark"], fg=self.colors["gray"],
                     pady=10).pack(fill=tk.X, padx=10)

            admin_buttons = [
                ("👥 用户管理", self.show_user_management),
                ("📊 数据统计", self.show_admin_stats),
                ("⚙️ 系统设置", self.show_admin_settings),
                ("💾 备份恢复", self.show_backup_restore),
            ]

            for text, command in admin_buttons:
                btn = tk.Button(parent, text=text, font=self.heading_font,
                                bg="#D35400", fg="white",  # 橙色表示管理员功能
                                activebackground="#E67E22",
                                activeforeground="white",
                                relief=tk.FLAT, padx=20, pady=10,
                                command=command, cursor="hand2")
                btn.pack(fill=tk.X, padx=10, pady=2)

        # 通用功能
        tk.Label(parent, text="其他功能", font=self.heading_font,
                 bg=self.colors["dark"], fg=self.colors["gray"],
                 pady=10).pack(fill=tk.X, padx=10)

        other_buttons = [
            ("⚙️ 个人设置", self.show_personal_settings),
            ("❓ 帮助", self.show_help),
            ("🚪 退出", self.logout),
        ]

        for text, command in other_buttons:
            btn = tk.Button(parent, text=text, font=self.heading_font,
                            bg=self.colors["gray"], fg="white",
                            activebackground="#AAB7B8",
                            activeforeground="white",
                            relief=tk.FLAT, padx=20, pady=10,
                            command=command, cursor="hand2")
            btn.pack(fill=tk.X, padx=10, pady=2)

    def create_toolbar(self, parent):
        """创建工具栏"""
        toolbar = tk.Frame(parent, bg=self.colors["primary"], height=50)
        toolbar.pack(fill=tk.X)
        toolbar.pack_propagate(False)

        # 标题标签
        self.toolbar_title = tk.Label(toolbar, text="仪表板",
                                      font=self.title_font,
                                      bg=self.colors["primary"],
                                      fg="white")
        self.toolbar_title.pack(side=tk.LEFT, padx=20)

        # 用户信息和退出按钮
        user_frame = tk.Frame(toolbar, bg=self.colors["primary"])
        user_frame.pack(side=tk.RIGHT, padx=20)

        user_label = tk.Label(user_frame,
                              text=f"{self.current_user['full_name'] or self.current_user['username']}",
                              bg=self.colors["primary"], fg="white",
                              font=self.normal_font)
        user_label.pack(side=tk.LEFT, padx=5)

    def clear_content(self):
        """清空内容区域"""
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def show_dashboard(self):
        """显示仪表板"""
        self.clear_content()
        self.toolbar_title.config(text="仪表板")

        # 获取统计数据
        records = self.db.get_user_health_records(self.current_user['id'])

        if not records:
            # 没有记录的情况
            self.show_no_data_dashboard()
            return

        # 创建仪表板布局
        dashboard_frame = tk.Frame(self.content_frame, bg=self.colors["light"])
        dashboard_frame.pack(fill=tk.BOTH, expand=True)

        # 顶部卡片 - 统计信息
        stats = self.calculate_statistics(records)
        stats_frame = tk.Frame(dashboard_frame, bg=self.colors["light"])
        stats_frame.pack(fill=tk.X, pady=(0, 20))

        stats_cards = [
            ("总记录数", f"{stats['total_records']}", "#3498DB", "📊"),
            ("平均体重", f"{stats['avg_weight']} kg", "#2ECC71", "⚖️"),
            ("平均BMI", f"{stats['avg_bmi']}", "#F39C12", "📈"),
            ("平均血糖", f"{stats['avg_blood_sugar']}", "#E74C3C", "🩸")
        ]

        for i, (title, value, color, icon) in enumerate(stats_cards):
            card = self.create_stat_card(stats_frame, title, value, color, icon)
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10) if i < 3 else 0)

        # 中间部分 - 图表和记录
        middle_frame = tk.Frame(dashboard_frame, bg=self.colors["light"])
        middle_frame.pack(fill=tk.BOTH, expand=True)

        # 左侧 - 最近记录
        recent_frame = tk.LabelFrame(middle_frame, text="最近记录",
                                     font=self.heading_font, bg=self.colors["light"])
        recent_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        self.create_recent_records_table(recent_frame, records[:5])  # 只显示最近的5条

        # 右侧 - BMI分布图
        chart_frame = tk.LabelFrame(middle_frame, text="BMI分布",
                                    font=self.heading_font, bg=self.colors["light"])
        chart_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.create_bmi_chart(chart_frame, stats['bmi_distribution'])

        # 底部 - 健康建议和提醒
        bottom_frame = tk.Frame(dashboard_frame, bg=self.colors["light"])
        bottom_frame.pack(fill=tk.BOTH, expand=True, pady=(20, 0))

        # 健康提醒
        reminders_frame = tk.LabelFrame(bottom_frame, text="今日提醒",
                                        font=self.heading_font, bg=self.colors["light"])
        reminders_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        self.create_reminders_list(reminders_frame)

        # 健康建议
        tips_frame = tk.LabelFrame(bottom_frame, text="健康建议",
                                   font=self.heading_font, bg=self.colors["light"])
        tips_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.create_health_tips(tips_frame, records[-1] if records else None)

    def show_no_data_dashboard(self):
        """显示无数据的仪表板"""
        welcome_frame = tk.Frame(self.content_frame, bg=self.colors["light"])
        welcome_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(welcome_frame, text="👋 欢迎使用健康管理系统！",
                 font=("Microsoft YaHei", 24, "bold"),
                 bg=self.colors["light"], fg=self.colors["primary"]).pack(pady=50)

        tk.Label(welcome_frame, text="您还没有任何健康记录",
                 font=self.title_font, bg=self.colors["light"]).pack(pady=10)

        tk.Label(welcome_frame, text="点击左侧菜单开始记录您的健康数据",
                 font=self.normal_font, bg=self.colors["light"],
                 fg=self.colors["gray"]).pack(pady=5)

        # 添加快速操作按钮
        button_frame = tk.Frame(welcome_frame, bg=self.colors["light"])
        button_frame.pack(pady=50)

        add_record_btn = tk.Button(button_frame, text="➕ 添加第一条健康记录",
                                   font=self.heading_font,
                                   bg=self.colors["primary"], fg="white",
                                   padx=30, pady=15,
                                   command=self.show_add_record)
        add_record_btn.pack(side=tk.LEFT, padx=10)

        import_btn = tk.Button(button_frame, text="📁 导入健康数据",
                               font=self.heading_font,
                               bg=self.colors["success"], fg="white",
                               padx=30, pady=15,
                               command=self.import_csv_data)
        import_btn.pack(side=tk.LEFT, padx=10)

    def calculate_statistics(self, records):
        """计算统计数据"""
        if not records:
            return {
                "total_records": 0,
                "avg_weight": 0,
                "avg_bmi": 0,
                "avg_blood_sugar": 0,
                "bmi_distribution": {"偏瘦": 0, "正常": 0, "超重": 0, "肥胖": 0},
                "health_trend": "无数据"
            }

        weights = [r['weight'] for r in records]
        bmis = [r['bmi'] for r in records]
        blood_sugars = [r['blood_sugar'] for r in records]

        # BMI分布统计
        bmi_distribution = {"偏瘦": 0, "正常": 0, "超重": 0, "肥胖": 0}
        for record in records:
            bmi_distribution[record['bmi_category']] += 1

        # 健康趋势
        if len(records) >= 2:
            first_weight = weights[-1]  # 最旧的记录
            last_weight = weights[0]  # 最新的记录

            if last_weight < first_weight:
                health_trend = "下降"
            elif last_weight > first_weight:
                health_trend = "上升"
            else:
                health_trend = "稳定"
        else:
            health_trend = "稳定"

        return {
            "total_records": len(records),
            "avg_weight": round(np.mean(weights), 2),
            "avg_bmi": round(np.mean(bmis), 2),
            "avg_blood_sugar": round(np.mean(blood_sugars), 2),
            "min_weight": round(min(weights), 2),
            "max_weight": round(max(weights), 2),
            "min_bmi": round(min(bmis), 2),
            "max_bmi": round(max(bmis), 2),
            "bmi_distribution": bmi_distribution,
            "health_trend": health_trend
        }

    def create_stat_card(self, parent, title, value, color, icon):
        """创建统计卡片"""
        card = tk.Frame(parent, bg="white", relief=tk.RAISED, borderwidth=1)

        # 卡片头部
        header = tk.Frame(card, bg=color, height=5)
        header.pack(fill=tk.X)

        # 卡片内容
        content = tk.Frame(card, bg="white", padx=20, pady=15)
        content.pack(fill=tk.BOTH, expand=True)

        # 图标和标题
        icon_label = tk.Label(content, text=icon, font=("Arial", 24),
                              bg="white", fg=color)
        icon_label.pack(anchor=tk.W)

        title_label = tk.Label(content, text=title, font=self.normal_font,
                               bg="white", fg=self.colors["gray"])
        title_label.pack(anchor=tk.W, pady=(10, 5))

        value_label = tk.Label(content, text=value, font=("Microsoft YaHei", 20, "bold"),
                               bg="white", fg=self.colors["dark"])
        value_label.pack(anchor=tk.W)

        return card

    def create_recent_records_table(self, parent, records):
        """创建最近记录表格"""
        # 创建Treeview
        columns = ("日期", "体重", "BMI", "分类", "血压", "血糖")
        tree = ttk.Treeview(parent, columns=columns, show="headings", height=6)

        # 设置列
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=100)

        tree.column("日期", width=120)
        tree.column("分类", width=80)

        # 添加滚动条
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 加载数据
        for record in records:
            tree.insert("", tk.END, values=(
                record['date'],
                f"{record['weight']} kg",
                record['bmi'],
                record['bmi_category'],
                record['blood_pressure'],
                f"{record['blood_sugar']} mmol/L"
            ))

    def create_bmi_chart(self, parent, distribution):
        """创建BMI分布图表"""
        # 创建Matplotlib图形
        fig = Figure(figsize=(6, 4), dpi=80, facecolor=self.colors["light"])
        ax = fig.add_subplot(111)

        # 准备数据
        categories = list(distribution.keys())
        values = list(distribution.values())
        colors = ["#4A90E2", "#7ED321", "#F5A623", "#D0021B"]

        # 绘制饼图
        ax.pie(values, labels=categories, colors=colors, autopct='%1.1f%%',
               startangle=90, textprops={'fontsize': 10})
        ax.axis('equal')
        ax.set_title('BMI分布情况', fontsize=12, fontweight='bold')

        # 将图表嵌入Tkinter
        canvas = FigureCanvasTkAgg(fig, parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def create_reminders_list(self, parent):
        """创建提醒列表"""
        # 获取今天的提醒
        reminders = self.db.get_user_reminders(self.current_user['id'])
        # 获取未读报警
        unread_alerts = [a for a in self.db.get_user_alerts(self.current_user['id'])
                         if not a['is_notified']]
        if not reminders:
            tk.Label(parent, text="今天没有提醒", font=self.normal_font,
                     bg=self.colors["light"], fg=self.colors["gray"]).pack(pady=20)
            return

        # 显示报警提醒
        for alert in unread_alerts[:2]:  # 只显示最近的2个未读报警
            alert_frame = tk.Frame(parent, bg="#FFF3CD", relief=tk.RAISED,
                                    borderwidth=1, padx=10, pady=8)
            alert_frame.pack(fill=tk.X, pady=2)

            tk.Label(alert_frame, text="⚠️ 健康报警", font=self.normal_font,
                        bg="#FFF3CD", fg=self.colors["danger"]).pack(side=tk.LEFT)

            tk.Label(alert_frame, text=f"{alert['alert_type']}: {alert['alert_value']}",
                        font=self.normal_font, bg="#FFF3CD").pack(side=tk.LEFT, padx=10)

            tk.Label(alert_frame, text=f"正常范围: {alert['normal_range']}",
                        font=self.normal_font, bg="#FFF3CD", fg=self.colors["gray"]).pack(side=tk.LEFT)

        # 显示普通提醒
        for reminder in reminders[:3]:  # 只显示最近的3个提醒
            reminder_frame = tk.Frame(parent, bg="white", relief=tk.RAISED,
                                          borderwidth=1, padx=10, pady=8)
            reminder_frame.pack(fill=tk.X, pady=2)

            # 时间和标题
            time_title_frame = tk.Frame(reminder_frame, bg="white")
            time_title_frame.pack(fill=tk.X)

            tk.Label(time_title_frame, text=f"⏰ {reminder['time']}",
                         font=self.normal_font, bg="white", fg=self.colors["primary"]).pack(side=tk.LEFT)
            tk.Label(time_title_frame, text=reminder['title'],
                         font=self.heading_font, bg="white").pack(side=tk.RIGHT)

            # 描述
            if reminder['description']:
                tk.Label(reminder_frame, text=reminder['description'],
                             font=self.normal_font, bg="white", fg=self.colors["gray"],
                             wraplength=300, justify=tk.LEFT).pack(anchor=tk.W, pady=(5, 0))

    def create_health_tips(self, parent, latest_record=None):
        """创建健康建议"""
        tips_frame = tk.Frame(parent, bg=self.colors["light"])
        tips_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        if latest_record:
            # 基于最新记录的建议
            tips = []

            # BMI建议
            bmi_category = latest_record['bmi_category']
            if bmi_category == "偏瘦":
                tips.append("💡 您的BMI偏低，建议增加营养摄入，适当进行力量训练增肌")
            elif bmi_category == "超重":
                tips.append("💡 您的BMI偏高，建议控制饮食，增加有氧运动")
            elif bmi_category == "肥胖":
                tips.append("💡 您的BMI属于肥胖范围，建议咨询专业医生制定减肥计划")
            else:
                tips.append("💡 您的BMI正常，请继续保持健康的生活方式")

            # 血压建议
            bp_category = latest_record['blood_pressure_category']
            if bp_category != "正常":
                tips.append(f"💡 您的血压分类为{bp_category}，建议定期监测血压")

            # 血糖建议
            sugar_category = latest_record['blood_sugar_category']
            if sugar_category != "正常":
                tips.append(f"💡 您的血糖分类为{sugar_category}，建议注意饮食控制")

            # 通用建议
            tips.append("💡 每天保持7-8小时的充足睡眠")
            tips.append("💡 饮食均衡，多吃蔬菜水果")
            tips.append("💡 每周至少进行150分钟中等强度运动")

            for tip in tips:
                tk.Label(tips_frame, text=tip, font=self.normal_font,
                         bg=self.colors["light"], anchor=tk.W, wraplength=300,
                         justify=tk.LEFT).pack(anchor=tk.W, pady=2)
        else:
            # 默认建议
            default_tips = [
                "💡 每天保持7-8小时的充足睡眠",
                "💡 饮食均衡，多吃蔬菜水果",
                "💡 每周至少进行150分钟中等强度运动",
                "💡 保持健康体重，控制BMI在18.5-24之间",
                "💡 定期测量血压和血糖",
                "💡 多喝水，少喝含糖饮料",
                "💡 减少盐分摄入，控制血压"
            ]

            for tip in default_tips:
                tk.Label(tips_frame, text=tip, font=self.normal_font,
                         bg=self.colors["light"], anchor=tk.W, wraplength=300,
                         justify=tk.LEFT).pack(anchor=tk.W, pady=2)

    def show_add_record(self):
        """显示添加记录界面"""
        self.clear_content()
        self.toolbar_title.config(text="添加健康记录")

        # 创建表单框架
        form_frame = tk.Frame(self.content_frame, bg="white", relief=tk.RAISED,
                              borderwidth=1, padx=30, pady=30)
        form_frame.pack(expand=True)

        # 表单标题
        tk.Label(form_frame, text="添加健康记录", font=self.title_font,
                 bg="white", fg=self.colors["primary"]).pack(pady=(0, 20))

        # 初始化表单变量字典
        self.form_vars = {}

        # 创建表单字段
        fields = [
            ("日期:", "date", "entry", datetime.now().strftime("%Y-%m-%d")),
            ("身高 (米):", "height", "entry", "1.75"),
            ("体重 (千克):", "weight", "entry", "65"),
            ("血压 (格式: 120/80):", "bp", "entry", "120/80"),
            ("血糖 (mmol/L):", "bs", "entry", "5.2"),
            ("心率 (次/分钟):", "hr", "entry", "72"),
            ("备注:", "notes", "text", "")
        ]

        for label, key, field_type, default in fields:
            frame = tk.Frame(form_frame, bg="white")
            frame.pack(fill=tk.X, pady=10)

            tk.Label(frame, text=label, font=self.normal_font,
                     bg="white", width=15, anchor=tk.W).pack(side=tk.LEFT)

            if field_type == "entry":
                var = tk.StringVar(value=default)
                entry = tk.Entry(frame, textvariable=var, font=self.normal_font,
                                 width=30, relief=tk.SOLID, borderwidth=1)
                entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

                # 存储变量引用
                self.form_vars[key] = var
            else:  # text
                text_frame = tk.Frame(frame, bg="white")
                text_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

                text = tk.Text(text_frame, font=self.normal_font, height=3,
                               relief=tk.SOLID, borderwidth=1)
                text.insert("1.0", default)
                text.pack(fill=tk.BOTH, expand=True)

                # 存储Text小部件引用
                self.form_vars[key] = text

        # CSV导入按钮
        import_frame = tk.Frame(form_frame, bg="white")
        import_frame.pack(fill=tk.X, pady=10)

        import_btn = tk.Button(import_frame, text="📁 导入CSV文件",
                               font=self.normal_font,
                               bg=self.colors["secondary"], fg="white",
                               command=self.import_csv_data)
        import_btn.pack(side=tk.LEFT)

        tk.Label(import_frame, text="支持批量导入健康数据",
                 font=self.normal_font, bg="white", fg=self.colors["gray"]).pack(side=tk.LEFT, padx=10)

        # 按钮框架
        button_frame = tk.Frame(form_frame, bg="white")
        button_frame.pack(pady=30)

        # 添加按钮
        add_btn = tk.Button(button_frame, text="添加记录",
                            bg=self.colors["success"], fg="white",
                            font=self.heading_font, padx=30, pady=10,
                            command=self.add_record, cursor="hand2")
        add_btn.pack(side=tk.LEFT, padx=10)

        # 重置按钮
        reset_btn = tk.Button(button_frame, text="重置",
                              bg=self.colors["warning"], fg="white",
                              font=self.heading_font, padx=30, pady=10,
                              command=self.reset_form, cursor="hand2")
        reset_btn.pack(side=tk.LEFT, padx=10)

        # 计算BMI按钮
        calc_btn = tk.Button(button_frame, text="计算BMI",
                             bg=self.colors["primary"], fg="white",
                             font=self.heading_font, padx=30, pady=10,
                             command=self.calculate_bmi, cursor="hand2")
        calc_btn.pack(side=tk.LEFT, padx=10)

        # 在创建输入框时添加验证函数
        def validate_numeric_input(P):
            """验证数字输入"""
            if P == "" or P == "-":  # 允许空字符串和负号
                return True
            try:
                float(P)
                return True
            except ValueError:
                return False

        # 注册验证函数
        vcmd = (self.root.register(validate_numeric_input), '%P')

        # 在创建身高、体重、血糖、心率输入框时添加验证
        height_entry = tk.Entry(frame, textvariable=var, font=self.normal_font,
                                width=30, relief=tk.SOLID, borderwidth=1,
                                validate='key', validatecommand=vcmd)

    def add_record(self):
        """添加记录到数据库"""
        try:
            # 检查form_vars是否存在
            if not hasattr(self, 'form_vars') or not self.form_vars:
                messagebox.showerror("错误", "表单未初始化")
                return

            print("开始添加记录...")  # 调试信息
            print(f"表单变量keys: {list(self.form_vars.keys())}")  # 调试信息

            # 获取表单数据
            date = self.form_vars["date"].get()
            print(f"日期: {date}")  # 调试信息

            try:
                height_str = self.form_vars["height"].get().strip()
                height = float(height_str)
                print(f"身高: {height}")  # 调试信息
            except (ValueError, KeyError) as e:
                messagebox.showerror("输入错误", f"身高输入无效: '{height_str}'，请输入数字\n错误详情: {e}")
                return

            try:
                weight_str = self.form_vars["weight"].get().strip()
                weight = float(weight_str)
                print(f"体重: {weight}")  # 调试信息
            except (ValueError, KeyError) as e:
                messagebox.showerror("输入错误", f"体重输入无效: '{weight_str}'，请输入数字\n错误详情: {e}")
                return

            blood_pressure = self.form_vars["bp"].get().strip()
            print(f"血压: {blood_pressure}")  # 调试信息

            try:
                blood_sugar_str = self.form_vars["bs"].get().strip()
                blood_sugar = float(blood_sugar_str)
                print(f"血糖: {blood_sugar}")  # 调试信息
            except (ValueError, KeyError) as e:
                messagebox.showerror("输入错误", f"血糖输入无效: '{blood_sugar_str}'，请输入数字\n错误详情: {e}")
                return

            try:
                heart_rate_str = self.form_vars["hr"].get().strip()
                heart_rate = int(heart_rate_str)
                print(f"心率: {heart_rate}")  # 调试信息
            except (ValueError, KeyError) as e:
                messagebox.showerror("输入错误", f"心率输入无效: '{heart_rate_str}'，请输入整数\n错误详情: {e}")
                return

            # 获取备注
            notes_widget = self.form_vars["notes"]
            if isinstance(notes_widget, tk.Text):
                notes = notes_widget.get("1.0", tk.END).strip()
            else:
                notes = notes_widget.get()
            print(f"备注: {notes}")  # 调试信息

            # 数据验证
            if not self.validate_blood_pressure(blood_pressure):
                messagebox.showerror("错误", f"血压格式错误: '{blood_pressure}'，请使用 120/80 格式")
                return

            # 如果数据超出正常范围，但仍在可接受范围内，询问用户是否继续
            if not self.confirm_unusual_values(height, weight, blood_pressure, blood_sugar, heart_rate):
                return

            # 创建记录对象
            record = HealthRecord(date, height, weight, blood_pressure, blood_sugar, heart_rate, notes)

            # 添加到数据库
            record_id,alerts = self.db.add_record(self.current_user['id'], record)

            if record_id:
                # 显示成功消息
                success_msg = "健康记录添加成功！\n\n"
                success_msg += f"• 日期: {record.date}\n"
                success_msg += f"• 身高: {record.height} 米\n"
                success_msg += f"• 体重: {record.weight} 千克\n"
                success_msg += f"• BMI: {record.bmi} ({record.bmi_category})\n"
                success_msg += f"• 血压: {record.blood_pressure} ({record.blood_pressure_category})\n"
                success_msg += f"• 血糖: {record.blood_sugar} mmol/L ({record.blood_sugar_category})\n"
                success_msg += f"• 心率: {record.heart_rate} 次/分钟 ({record.heart_rate_category})"

                if notes:
                    success_msg += f"\n• 备注: {notes}"
                # 如果有报警，显示报警窗口
                if alerts:
                    # 延迟显示报警窗口，先显示成功消息
                    self.root.after(500, lambda: self.show_alert_window(alerts))

                    success_msg += f"\n\n⚠️ 检测到 {len(alerts)} 条健康报警，请查看报警通知！"

                messagebox.showinfo("成功", success_msg)

                # 重置表单
                self.reset_form()

                # 更新仪表板
                self.show_dashboard()
                # 刷新报警显示
                self.refresh_alerts_display()
            else:
                messagebox.showerror("错误", "添加记录失败")

        except ValueError as e:
            messagebox.showerror("输入错误", f"请检查输入数据的格式：\n{str(e)}")
        except Exception as e:
            messagebox.showerror("错误", f"添加记录失败：\n{str(e)}")

    def import_csv_data(self):
        """导入CSV数据"""
        filename = filedialog.askopenfilename(
            title="选择CSV文件",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )

        if not filename:
            return

        try:
            with open(filename, 'r', encoding='utf-8') as file:
                csv_reader = csv.DictReader(file)
                imported_count = 0

                for row in csv_reader:
                    try:
                        # 解析CSV行
                        date = row.get('date', datetime.now().strftime("%Y-%m-%d"))
                        height = float(row.get('height', 1.75))
                        weight = float(row.get('weight', 65))
                        blood_pressure = row.get('blood_pressure', '120/80')
                        blood_sugar = float(row.get('blood_sugar', 5.2))
                        heart_rate = int(row.get('heart_rate', 72))
                        notes = row.get('notes', '')

                        # 创建记录对象
                        record = HealthRecord(date, height, weight, blood_pressure,
                                              blood_sugar, heart_rate, notes)

                        # 添加到数据库
                        self.db.add_record(self.current_user['id'], record)
                        imported_count += 1

                    except (ValueError, KeyError) as e:
                        print(f"跳过无效行: {e}")
                        continue

                messagebox.showinfo("成功", f"成功导入 {imported_count} 条记录")

                # 更新界面
                self.show_dashboard()

        except Exception as e:
            messagebox.showerror("错误", f"导入失败: {str(e)}")

    def reset_form(self):
        """重置表单"""
        # 检查form_vars是否存在
        if not hasattr(self, 'form_vars') or not self.form_vars:
            print("警告: form_vars不存在或为空")  # 调试信息
            return

        # 调试信息：查看form_vars中的键
        print(f"reset_form: form_vars keys = {list(self.form_vars.keys())}")

        try:
            # 重置日期为今天
            if "date" in self.form_vars:
                self.form_vars["date"].set(datetime.now().strftime("%Y-%m-%d"))
                print(f"重置日期为: {self.form_vars['date'].get()}")
            else:
                print("警告: date键不存在")

            # 重置其他字段
            defaults = {
                "height": "1.75",
                "weight": "65",
                "bp": "120/80",
                "bs": "5.2",
                "hr": "72"
            }

            for key, value in defaults.items():
                if key in self.form_vars:
                    self.form_vars[key].set(value)
                    print(f"重置{key}为: {value}")
                else:
                    print(f"警告: {key}键不存在")

            # 重置备注
            if "notes" in self.form_vars:
                notes_widget = self.form_vars["notes"]
                if isinstance(notes_widget, tk.Text):
                    notes_widget.delete("1.0", tk.END)
                    print("重置备注")
            else:
                print("警告: notes键不存在")

            print("表单重置完成")

        except Exception as e:
            print(f"重置表单时发生错误: {e}")

    def calculate_bmi(self):
        """计算BMI"""
        try:
            # 检查form_vars是否存在
            if not hasattr(self, 'form_vars') or not self.form_vars:
                messagebox.showerror("错误", "表单未初始化")
                return

            print(f"calculate_bmi: form_vars keys = {list(self.form_vars.keys())}")  # 调试信息

            # 获取身高和体重
            height_str = self.form_vars["height"].get()
            weight_str = self.form_vars["weight"].get()

            print(f"身高: {height_str}, 体重: {weight_str}")  # 调试信息

            height = float(height_str)
            weight = float(weight_str)

            # 创建临时记录对象计算BMI
            record = HealthRecord("", height, weight, "", 0, 0)
            bmi = record.bmi
            category = record.bmi_category

            messagebox.showinfo("BMI计算结果",
                                f"您的BMI: {bmi}\n"
                                f"分类: {category}")
        except KeyError as e:
            messagebox.showerror("错误", f"无法找到表单字段: {e}\n请确保表单已正确加载")
        except ValueError as e:
            messagebox.showerror("错误", f"输入格式错误: {e}\n请检查身高和体重是否输入正确")
        except Exception as e:
            messagebox.showerror("错误", f"计算BMI时发生未知错误: {e}")

    def validate_blood_pressure(self, bp_str):
        """验证血压格式"""
        try:
            if '/' not in bp_str:
                return False
            parts = bp_str.split('/')
            if len(parts) != 2:
                return False
            sys_bp = int(parts[0])  # 收缩压
            dia_bp = int(parts[1])  # 舒张压

            # 基本范围验证
            if sys_bp <= 0 or dia_bp <= 0:
                return False
            if sys_bp > 300 or dia_bp > 200:
                return False
            if sys_bp < dia_bp:  # 收缩压应大于舒张压
                return False

            return True
        except ValueError:
            return False

    def confirm_unusual_values(self, height, weight, blood_pressure, blood_sugar, heart_rate):
        """确认异常值"""
        # 定义正常范围
        normal_ranges = [
            ("身高", height, 1.5, 2.0, "米"),
            ("体重", weight, 45, 90, "千克"),
            ("血糖", blood_sugar, 3.9, 6.1, "mmol/L"),
            ("心率", heart_rate, 60, 100, "次/分钟"),
        ]

        # 检查血压
        try:
            sys_bp, dia_bp = map(int, blood_pressure.split('/'))
            if not (90 <= sys_bp <= 140) or not (60 <= dia_bp <= 90):
                normal_ranges.append(("血压", f"{sys_bp}/{dia_bp}", "90-140/60-90", "", "mmHg"))
        except:
            pass

        # 收集超出正常范围的值
        unusual_values = []
        for name, value, min_val, max_val, unit in normal_ranges:
            if name == "血压":
                unusual_values.append((name, value, min_val))
            elif value < min_val or value > max_val:
                unusual_values.append((name, value, f"{min_val}-{max_val}{unit}"))

        if unusual_values:
            msg = "以下数据超出正常范围：\n\n"
            for name, value, normal_range in unusual_values:
                msg += f"• {name}: {value} (正常范围: {normal_range})\n"
            msg += "\n是否继续保存？"
            return messagebox.askyesno("确认异常数据", msg)

        return True

    def show_my_records(self):
        """显示我的记录"""
        self.clear_content()
        self.toolbar_title.config(text="我的健康记录")

        # 创建记录管理框架
        records_frame = tk.Frame(self.content_frame, bg=self.colors["light"])
        records_frame.pack(fill=tk.BOTH, expand=True)

        # 顶部工具栏
        toolbar = tk.Frame(records_frame, bg=self.colors["light"])
        toolbar.pack(fill=tk.X, pady=(0, 10))

        # 筛选选项
        filter_frame = tk.Frame(toolbar, bg=self.colors["light"])
        filter_frame.pack(side=tk.LEFT)

        tk.Label(filter_frame, text="日期范围:", font=self.normal_font,
                 bg=self.colors["light"]).pack(side=tk.LEFT, padx=5)

        self.start_date_var = tk.StringVar()
        self.end_date_var = tk.StringVar()

        tk.Entry(filter_frame, textvariable=self.start_date_var,
                 width=10, font=self.normal_font).pack(side=tk.LEFT, padx=5)
        tk.Label(filter_frame, text="-", bg=self.colors["light"]).pack(side=tk.LEFT)
        tk.Entry(filter_frame, textvariable=self.end_date_var,
                 width=10, font=self.normal_font).pack(side=tk.LEFT, padx=5)

        # BMI分类筛选
        tk.Label(filter_frame, text="BMI分类:", font=self.normal_font,
                 bg=self.colors["light"]).pack(side=tk.LEFT, padx=(10, 5))

        self.bmi_filter_var = tk.StringVar(value="全部")
        bmi_options = ["全部", "偏瘦", "正常", "超重", "肥胖"]
        bmi_combo = ttk.Combobox(filter_frame, textvariable=self.bmi_filter_var,
                                 values=bmi_options, state="readonly", width=10)
        bmi_combo.pack(side=tk.LEFT, padx=5)

        # 筛选按钮
        filter_btn = tk.Button(filter_frame, text="筛选", bg=self.colors["primary"],
                               fg="white", font=self.normal_font,
                               command=self.filter_my_records, cursor="hand2")
        filter_btn.pack(side=tk.LEFT, padx=5)

        # 导出按钮
        export_btn = tk.Button(toolbar, text="导出数据", bg=self.colors["success"],
                               fg="white", font=self.normal_font,
                               command=self.export_data, cursor="hand2")
        export_btn.pack(side=tk.RIGHT, padx=5)

        # 创建记录表格
        self.create_my_records_table(records_frame)

    def create_my_records_table(self, parent):
        """创建我的记录表格"""
        # 创建Treeview
        columns = ("日期", "身高", "体重", "BMI", "分类", "血压", "血糖", "心率", "备注")
        self.records_tree = ttk.Treeview(parent, columns=columns, show="headings", height=15)

        # 设置列
        column_widths = {"日期": 100, "身高": 60, "体重": 60, "BMI": 60,
                         "分类": 80, "血压": 80, "血糖": 60, "心率": 60, "备注": 150}

        for col in columns:
            self.records_tree.heading(col, text=col)
            self.records_tree.column(col, width=column_widths.get(col, 100))

        # 添加滚动条
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.records_tree.yview)
        self.records_tree.configure(yscrollcommand=scrollbar.set)

        # 按钮框架
        button_frame = tk.Frame(parent, bg=self.colors["light"])
        button_frame.pack(fill=tk.X, pady=(10, 0))

        # 操作按钮
        edit_btn = tk.Button(button_frame, text="编辑", bg=self.colors["primary"],
                             fg="white", font=self.normal_font,
                             command=self.edit_my_record, cursor="hand2")
        edit_btn.pack(side=tk.LEFT, padx=5)

        delete_btn = tk.Button(button_frame, text="删除", bg=self.colors["danger"],
                               fg="white", font=self.normal_font,
                               command=self.delete_my_record, cursor="hand2")
        delete_btn.pack(side=tk.LEFT, padx=5)

        refresh_btn = tk.Button(button_frame, text="刷新", bg=self.colors["warning"],
                                fg="white", font=self.normal_font,
                                command=self.refresh_my_records, cursor="hand2")
        refresh_btn.pack(side=tk.LEFT, padx=5)

        # 布局
        self.records_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        button_frame.pack(fill=tk.X)

        # 加载数据
        self.load_my_records()

    def load_my_records(self):
        """加载我的记录到表格"""
        # 清空现有数据
        for item in self.records_tree.get_children():
            self.records_tree.delete(item)

        # 获取我的记录
        records = self.db.get_user_health_records(self.current_user['id'])

        # 添加数据到表格
        for record in records:
            self.records_tree.insert("", tk.END, values=(
                record['date'],
                f"{record['height']} m",
                f"{record['weight']} kg",
                record['bmi'],
                record['bmi_category'],
                record['blood_pressure'],
                f"{record['blood_sugar']} mmol/L",
                f"{record['heart_rate']} bpm" if record['heart_rate'] > 0 else "-",
                record['notes'][:30] + "..." if len(record['notes']) > 30 else record['notes']
            ))

    def filter_my_records(self):
        """筛选我的记录"""
        # 简化筛选，实际应实现数据库筛选
        self.load_my_records()

    def edit_my_record(self):
        """编辑我的记录"""
        # 简化实现
        messagebox.showinfo("提示", "编辑功能正在开发中")

    def delete_my_record(self):
        """删除我的记录"""
        selection = self.records_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请选择要删除的记录！")
            return

        # 简化实现
        messagebox.showinfo("提示", "删除功能正在开发中")

    def refresh_my_records(self):
        """刷新我的记录列表"""
        self.load_my_records()

    def show_analysis(self):
        """显示数据分析界面"""
        self.clear_content()
        self.toolbar_title.config(text="数据分析")

        # 创建分析框架
        analysis_frame = tk.Frame(self.content_frame, bg=self.colors["light"])
        analysis_frame.pack(fill=tk.BOTH, expand=True)

        # 创建图表区域
        chart_frame = tk.Frame(analysis_frame, bg="white", relief=tk.RAISED, borderwidth=1)
        chart_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 创建多个图表
        self.create_analysis_charts(chart_frame)

    def create_analysis_charts(self, parent):
        """创建分析图表"""
        # 获取数据
        records = self.db.get_user_health_records(self.current_user['id'])

        if len(records) < 2:
            tk.Label(parent, text="至少需要2条记录才能进行数据分析",
                     font=self.heading_font, bg="white").pack(expand=True)
            return

        # 准备数据
        dates = [datetime.strptime(r['date'], '%Y-%m-%d') for r in records]
        weights = [r['weight'] for r in records]
        bmis = [r['bmi'] for r in records]
        blood_sugars = [r['blood_sugar'] for r in records]

        # 创建Matplotlib图形
        fig = Figure(figsize=(10, 8), dpi=100, facecolor=self.colors["light"])

        # 体重趋势图
        ax1 = fig.add_subplot(221)
        ax1.plot(dates, weights, 'o-', color=self.colors["primary"], linewidth=2)
        ax1.set_title('体重趋势', fontsize=12, fontweight='bold')
        ax1.set_xlabel('日期')
        ax1.set_ylabel('体重 (kg)')
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))

        # BMI趋势图
        ax2 = fig.add_subplot(222)
        ax2.plot(dates, bmis, 's-', color=self.colors["success"], linewidth=2)
        ax2.set_title('BMI趋势', fontsize=12, fontweight='bold')
        ax2.set_xlabel('日期')
        ax2.set_ylabel('BMI')
        ax2.grid(True, alpha=0.3)
        ax2.axhline(y=18.5, color='green', linestyle='--', alpha=0.5)
        ax2.axhline(y=24, color='blue', linestyle='--', alpha=0.5)
        ax2.axhline(y=28, color='red', linestyle='--', alpha=0.5)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))

        # 血糖趋势图
        ax3 = fig.add_subplot(223)
        ax3.plot(dates, blood_sugars, '^-', color=self.colors["danger"], linewidth=2)
        ax3.set_title('血糖趋势', fontsize=12, fontweight='bold')
        ax3.set_xlabel('日期')
        ax3.set_ylabel('血糖 (mmol/L)')
        ax3.grid(True, alpha=0.3)
        ax3.axhline(y=3.9, color='green', linestyle='--', alpha=0.5, label='低血糖线')
        ax3.axhline(y=6.1, color='blue', linestyle='--', alpha=0.5, label='正常线')
        ax3.axhline(y=7.0, color='red', linestyle='--', alpha=0.5, label='糖尿病线')
        ax3.legend(fontsize=8)
        ax3.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))

        # 散点图：体重 vs BMI
        ax4 = fig.add_subplot(224)
        scatter = ax4.scatter(weights, bmis, c=bmis, cmap='RdYlGn_r', s=100, alpha=0.7)
        ax4.set_title('体重-BMI关系', fontsize=12, fontweight='bold')
        ax4.set_xlabel('体重 (kg)')
        ax4.set_ylabel('BMI')
        ax4.grid(True, alpha=0.3)

        fig.colorbar(scatter, ax=ax4, label='BMI值')

        fig.tight_layout()

        # 将图表嵌入Tkinter
        canvas = FigureCanvasTkAgg(fig, parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def show_report(self):
        """显示健康报告"""
        self.clear_content()
        self.toolbar_title.config(text="健康报告")

        # 获取数据
        records = self.db.get_user_health_records(self.current_user['id'])

        if not records:
            tk.Label(self.content_frame, text="没有健康记录数据",
                     font=self.heading_font, bg=self.colors["light"]).pack(expand=True)
            return

        stats = self.calculate_statistics(records)

        # 创建报告框架
        report_frame = tk.Frame(self.content_frame, bg=self.colors["light"])
        report_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 报告标题
        title_frame = tk.Frame(report_frame, bg=self.colors["primary"])
        title_frame.pack(fill=tk.X, pady=(0, 20))

        tk.Label(title_frame, text="个人健康报告", font=("Microsoft YaHei", 18, "bold"),
                 bg=self.colors["primary"], fg="white", pady=15).pack()

        # 报告内容
        content_frame = tk.Frame(report_frame, bg="white", relief=tk.RAISED, borderwidth=1)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 创建可滚动的文本区域
        text_frame = tk.Frame(content_frame, bg="white")
        text_frame.pack(fill=tk.BOTH, expand=True)

        # 滚动条
        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 文本框
        report_text = tk.Text(text_frame, wrap=tk.WORD, yscrollcommand=scrollbar.set,
                              font=self.normal_font, bg="white", padx=20, pady=20)
        report_text.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=report_text.yview)

        # 生成报告内容
        report_content = self.generate_report_content(stats, records)
        report_text.insert("1.0", report_content)
        report_text.config(state=tk.DISABLED)  # 设置为只读

        # 导出报告按钮
        export_frame = tk.Frame(report_frame, bg=self.colors["light"])
        export_frame.pack(fill=tk.X, pady=(10, 0))

        export_btn = tk.Button(export_frame, text="导出报告", bg=self.colors["success"],
                               fg="white", font=self.heading_font, padx=30,
                               command=lambda: self.export_report(report_content))
        export_btn.pack()

    def generate_report_content(self, stats, records):
        """生成报告内容"""
        latest_record = records[0] if records else None

        content = "=" * 60 + "\n"
        content += "          个人健康分析报告\n"
        content += "=" * 60 + "\n\n"

        content += f"用户: {self.current_user['full_name'] or self.current_user['username']}\n"
        content += f"生成时间: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}\n"
        content += f"统计周期: 共 {stats['total_records']} 条记录\n\n"

        content += "一、总体健康状况\n"
        content += "-" * 40 + "\n"

        if stats['total_records'] > 0:
            content += f"平均体重: {stats['avg_weight']} kg\n"
            content += f"平均BMI: {stats['avg_bmi']}\n"
            content += f"平均血糖: {stats['avg_blood_sugar']} mmol/L\n"
            content += f"体重趋势: {stats['health_trend']}\n\n"

            content += "BMI分布情况:\n"
            for category, count in stats['bmi_distribution'].items():
                percentage = (count / stats['total_records']) * 100 if stats['total_records'] > 0 else 0
                content += f"  {category}: {count} 次 ({percentage:.1f}%)\n"

        if latest_record:
            content += "\n二、最新健康数据\n"
            content += "-" * 40 + "\n"
            content += f"测量日期: {latest_record['date']}\n"
            content += f"身高: {latest_record['height']} 米\n"
            content += f"体重: {latest_record['weight']} 千克\n"
            content += f"BMI: {latest_record['bmi']} ({latest_record['bmi_category']})\n"
            content += f"血压: {latest_record['blood_pressure']} ({latest_record['blood_pressure_category']})\n"
            content += f"血糖: {latest_record['blood_sugar']} mmol/L ({latest_record['blood_sugar_category']})\n"

        content += "\n三、健康建议\n"
        content += "-" * 40 + "\n"

        if latest_record:
            # BMI建议
            bmi_category = latest_record['bmi_category']
            if bmi_category == "偏瘦":
                content += "1. BMI偏低，建议增加营养摄入，适当进行力量训练增肌\n"
            elif bmi_category == "超重":
                content += "1. BMI偏高，建议控制饮食，增加有氧运动\n"
            elif bmi_category == "肥胖":
                content += "1. BMI属于肥胖范围，建议咨询专业医生制定减肥计划\n"
            else:
                content += "1. BMI正常，请继续保持健康的生活方式\n"

            # 血压建议
            bp_category = latest_record['blood_pressure_category']
            if bp_category != "正常":
                content += f"2. 血压分类为{bp_category}，建议定期监测血压\n"

            # 血糖建议
            sugar_category = latest_record['blood_sugar_category']
            if sugar_category != "正常":
                content += f"3. 血糖分类为{sugar_category}，建议注意饮食控制\n"

        content += "4. 通用健康建议：\n"
        content += "   - 保持均衡饮食，多吃蔬菜水果\n"
        content += "   - 每周至少进行150分钟中等强度运动\n"
        content += "   - 保证充足睡眠，每晚7-8小时\n"
        content += "   - 多喝水，少喝含糖饮料\n"
        content += "   - 定期进行健康检查\n"

        content += "\n" + "=" * 60 + "\n"
        content += "报告结束\n"
        content += "=" * 60 + "\n"

        return content

    def export_report(self, content):
        """导出报告到文件"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
                initialfile=f"健康报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )

            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                messagebox.showinfo("成功", f"报告已保存到:\n{filename}")
        except Exception as e:
            messagebox.showerror("错误", f"保存报告失败: {str(e)}")

    def export_data(self):
        """导出数据到Excel"""
        try:
            records = self.db.get_user_health_records(self.current_user['id'])

            if not records:
                messagebox.showwarning("警告", "没有数据可以导出！")
                return

            # 转换为DataFrame
            df = pd.DataFrame(records)

            # 选择保存位置
            filename = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel文件", "*.xlsx"), ("所有文件", "*.*")],
                initialfile=f"健康数据_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            )

            if filename:
                df.to_excel(filename, index=False)
                messagebox.showinfo("成功", f"数据已导出到:\n{filename}")

        except ImportError:
            messagebox.showerror("错误", "需要安装pandas和openpyxl库才能导出Excel！\n"
                                         "请运行: pip install pandas openpyxl")
        except Exception as e:
            messagebox.showerror("错误", f"导出数据失败: {str(e)}")

    def show_family_list(self):
        """显示家属列表"""
        self.clear_content()
        self.toolbar_title.config(text="家属管理")

        family_frame = tk.Frame(self.content_frame, bg=self.colors["light"])
        family_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 标题
        title_frame = tk.Frame(family_frame, bg=self.colors["light"])
        title_frame.pack(fill=tk.X, pady=(0, 20))

        tk.Label(title_frame, text="家属管理", font=self.title_font,
                 bg=self.colors["light"], fg=self.colors["primary"]).pack(side=tk.LEFT)

        # 添加家属按钮
        add_btn = tk.Button(title_frame, text="添加家属", bg=self.colors["success"],
                            fg="white", font=self.heading_font, padx=20,
                            command=self.show_add_family)
        add_btn.pack(side=tk.RIGHT)

        # 家属列表
        members = self.db.get_family_members(self.current_user['id'])

        if not members:
            tk.Label(family_frame, text="暂无家属成员", font=self.heading_font,
                     bg=self.colors["light"]).pack(expand=True)
            return

        # 创建家属列表
        for member in members:
            member_frame = tk.Frame(family_frame, bg="white", relief=tk.RAISED,
                                    borderwidth=1, padx=15, pady=10)
            member_frame.pack(fill=tk.X, pady=5)

            # 基本信息
            info_frame = tk.Frame(member_frame, bg="white")
            info_frame.pack(fill=tk.X)

            tk.Label(info_frame, text=member['full_name'] or member['username'],
                     font=self.heading_font, bg="white").pack(side=tk.LEFT)

            tk.Label(info_frame, text=f"关系: {member['relationship']}",
                     font=self.normal_font, bg="white", fg=self.colors["gray"]).pack(side=tk.LEFT, padx=20)

            tk.Label(info_frame, text=f"邮箱: {member['email']}",
                     font=self.normal_font, bg="white", fg=self.colors["gray"]).pack(side=tk.LEFT, padx=20)

            # 权限和操作
            action_frame = tk.Frame(member_frame, bg="white")
            action_frame.pack(fill=tk.X, pady=(5, 0))

            permissions = []
            if member['can_view']:
                permissions.append("查看")
            if member['can_edit']:
                permissions.append("编辑")

            tk.Label(action_frame, text=f"权限: {', '.join(permissions)}",
                     font=self.normal_font, bg="white", fg=self.colors["gray"]).pack(side=tk.LEFT)

            # 操作按钮
            btn_frame = tk.Frame(action_frame, bg="white")
            btn_frame.pack(side=tk.RIGHT)

            view_btn = tk.Button(btn_frame, text="查看健康记录",
                                 font=self.normal_font, padx=10,
                                 command=lambda m=member: self.view_family_health(m))
            view_btn.pack(side=tk.LEFT, padx=2)

            edit_btn = tk.Button(btn_frame, text="编辑",
                                 font=self.normal_font, padx=10,
                                 bg=self.colors["primary"], fg="white")
            edit_btn.pack(side=tk.LEFT, padx=2)

            delete_btn = tk.Button(btn_frame, text="删除",
                                   font=self.normal_font, padx=10,
                                   bg=self.colors["danger"], fg="white")
            delete_btn.pack(side=tk.LEFT, padx=2)

    def show_add_family(self):
        """显示添加家属窗口"""
        add_window = tk.Toplevel(self.root)
        add_window.title("添加家属成员")
        add_window.geometry("400x300")

        # 设置模态
        add_window.transient(self.root)
        add_window.grab_set()

        # 创建表单
        form_frame = tk.Frame(add_window, padx=30, pady=30)
        form_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(form_frame, text="添加家属成员", font=self.title_font).pack(pady=(0, 20))

        # 表单字段
        fields = [
            ("家属用户名:", "entry"),
            ("关系:", "entry", "例如: 父亲、母亲、子女"),
            ("允许查看:", "check", True),
            ("允许编辑:", "check", False),
        ]

        form_vars = {}

        for label, field_type, *default in fields:
            frame = tk.Frame(form_frame)
            frame.pack(fill=tk.X, pady=10)

            tk.Label(frame, text=label, width=15, anchor=tk.W).pack(side=tk.LEFT)

            if field_type == "entry":
                var = tk.StringVar(value=default[0] if default else "")
                entry = tk.Entry(frame, textvariable=var, width=25)
                entry.pack(side=tk.LEFT)
                form_vars[label[:-1]] = var
            elif field_type == "check":
                var = tk.BooleanVar(value=default[0] if default else False)
                check = tk.Checkbutton(frame, variable=var)
                check.pack(side=tk.LEFT)
                form_vars[label[:-1]] = var

        # 按钮
        button_frame = tk.Frame(form_frame)
        button_frame.pack(pady=30)

        def add_family():
            """添加家属"""
            family_username = form_vars["家属用户名"].get().strip()
            relationship = form_vars["关系"].get().strip()
            can_view = form_vars["允许查看"].get()
            can_edit = form_vars["允许编辑"].get()

            if not family_username:
                messagebox.showerror("错误", "请输入家属用户名")
                return

            if not relationship:
                messagebox.showerror("错误", "请输入关系")
                return

            success, msg = self.db.add_family_member(
                self.current_user['id'],
                family_username,
                relationship,
                can_edit,
                can_view
            )

            if success:
                messagebox.showinfo("成功", msg)
                add_window.destroy()
                self.show_family_list()
            else:
                messagebox.showerror("错误", msg)

        add_btn = tk.Button(button_frame, text="添加", bg=self.colors["success"],
                            fg="white", padx=30, command=add_family)
        add_btn.pack(side=tk.LEFT, padx=10)

        cancel_btn = tk.Button(button_frame, text="取消", bg="gray",
                               fg="white", padx=30, command=add_window.destroy)
        cancel_btn.pack(side=tk.LEFT, padx=10)

    def view_family_health(self, family_member):
        """查看家属健康记录"""
        self.clear_content()
        self.toolbar_title.config(text=f"家属健康记录 - {family_member['full_name']}")

        records = self.db.get_family_health_records(self.current_user['id'], family_member['id'])

        if not records:
            tk.Label(self.content_frame, text="家属暂无健康记录",
                     font=self.heading_font, bg=self.colors["light"]).pack(expand=True)
            return

        # 显示家属记录
        records_frame = tk.Frame(self.content_frame, bg=self.colors["light"])
        records_frame.pack(fill=tk.BOTH, expand=True)

        # 创建Treeview
        columns = ("日期", "体重", "BMI", "分类", "血压", "血糖", "备注")
        tree = ttk.Treeview(records_frame, columns=columns, show="headings", height=15)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=100)

        tree.column("日期", width=120)
        tree.column("备注", width=150)

        # 添加滚动条
        scrollbar = ttk.Scrollbar(records_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 加载数据
        for record in records:
            tree.insert("", tk.END, values=(
                record['date'],
                f"{record['weight']} kg",
                record['bmi'],
                record['bmi_category'],
                record['blood_pressure'],
                f"{record['blood_sugar']} mmol/L",
                record['notes'][:30] + "..." if len(record['notes']) > 30 else record['notes']
            ))

    def show_reminders(self):
        """显示提醒设置"""
        self.clear_content()
        self.toolbar_title.config(text="健康提醒")

        reminders_frame = tk.Frame(self.content_frame, bg=self.colors["light"])
        reminders_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 标题和添加按钮
        title_frame = tk.Frame(reminders_frame, bg=self.colors["light"])
        title_frame.pack(fill=tk.X, pady=(0, 20))

        tk.Label(title_frame, text="健康提醒设置", font=self.title_font,
                 bg=self.colors["light"], fg=self.colors["primary"]).pack(side=tk.LEFT)

        add_btn = tk.Button(title_frame, text="添加提醒", bg=self.colors["success"],
                            fg="white", font=self.heading_font, padx=20,
                            command=self.show_add_reminder)
        add_btn.pack(side=tk.RIGHT)

        # 提醒列表
        reminders = self.db.get_user_reminders(self.current_user['id'])

        if not reminders:
            tk.Label(reminders_frame, text="暂无提醒设置", font=self.heading_font,
                     bg=self.colors["light"]).pack(expand=True)
            return

        # 显示提醒列表
        for reminder in reminders:
            reminder_frame = tk.Frame(reminders_frame, bg="white", relief=tk.RAISED,
                                      borderwidth=1, padx=15, pady=10)
            reminder_frame.pack(fill=tk.X, pady=5)

            # 提醒信息
            tk.Label(reminder_frame, text=f"⏰ {reminder['time']} - {reminder['title']}",
                     font=self.heading_font, bg="white").pack(anchor=tk.W)

            if reminder['description']:
                tk.Label(reminder_frame, text=reminder['description'],
                         font=self.normal_font, bg="white", fg=self.colors["gray"]).pack(anchor=tk.W, pady=(5, 0))

            # 提醒类型
            type_frame = tk.Frame(reminder_frame, bg="white")
            type_frame.pack(fill=tk.X, pady=(5, 0))

            tk.Label(type_frame, text=f"类型: {reminder['type']}",
                     font=self.normal_font, bg="white").pack(side=tk.LEFT)

            if reminder['days']:
                tk.Label(type_frame, text=f"重复: {reminder['days']}",
                         font=self.normal_font, bg="white", fg=self.colors["gray"]).pack(side=tk.LEFT, padx=10)

    def show_add_reminder(self):
        """显示添加提醒窗口"""
        add_window = tk.Toplevel(self.root)
        add_window.title("添加健康提醒")
        add_window.geometry("500x400")

        # 设置模态
        add_window.transient(self.root)
        add_window.grab_set()

        # 创建表单
        form_frame = tk.Frame(add_window, padx=30, pady=30)
        form_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(form_frame, text="添加健康提醒", font=self.title_font).pack(pady=(0, 20))

        # 表单字段
        fields = [
            ("提醒标题*:", "entry", "服药提醒"),
            ("提醒时间*:", "entry", "08:00"),
            ("提醒类型:", "combo", ["服药", "复诊", "运动", "测量", "其他"]),
            ("重复周期:", "combo", ["每天", "工作日", "周末", "不重复"]),
            ("提醒描述:", "text", ""),
        ]

        form_vars = {}

        for label, field_type, default in fields:
            frame = tk.Frame(form_frame)
            frame.pack(fill=tk.X, pady=10)

            tk.Label(frame, text=label, width=15, anchor=tk.W).pack(side=tk.LEFT)

            if field_type == "entry":
                var = tk.StringVar(value=default)
                entry = tk.Entry(frame, textvariable=var, width=25)
                entry.pack(side=tk.LEFT)
                form_vars[label[:-1]] = var
            elif field_type == "combo":
                var = tk.StringVar(value=default[0])
                combo = ttk.Combobox(frame, textvariable=var,
                                     values=default, state="readonly", width=23)
                combo.pack(side=tk.LEFT)
                form_vars[label[:-1]] = var
            elif field_type == "text":
                text_frame = tk.Frame(frame)
                text_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

                text = tk.Text(text_frame, height=3)
                text.insert("1.0", default)
                text.pack(fill=tk.BOTH, expand=True)
                form_vars[label[:-1]] = text

        # 按钮
        button_frame = tk.Frame(form_frame)
        button_frame.pack(pady=30)

        def add_reminder():
            """添加提醒"""
            title = form_vars["提醒标题"].get().strip()
            time = form_vars["提醒时间"].get().strip()
            reminder_type = form_vars["提醒类型"].get().strip()
            repeat = form_vars["重复周期"].get().strip()

            text_widget = form_vars["提醒描述"]
            if isinstance(text_widget, tk.Text):
                description = text_widget.get("1.0", tk.END).strip()
            else:
                description = text_widget.get().strip()

            if not title or not time:
                messagebox.showerror("错误", "标题和时间不能为空")
                return

            # 转换重复周期为数字
            days_map = {
                "每天": "1,2,3,4,5,6,7",
                "工作日": "1,2,3,4,5",
                "周末": "6,7",
                "不重复": ""
            }
            days_of_week = days_map.get(repeat, "")

            # 添加到数据库
            reminder_id = self.db.add_reminder(
                self.current_user['id'],
                title,
                description,
                reminder_type,
                time,
                days_of_week
            )

            if reminder_id:
                messagebox.showinfo("成功", "提醒添加成功")
                add_window.destroy()
                self.show_reminders()
            else:
                messagebox.showerror("错误", "添加提醒失败")

        add_btn = tk.Button(button_frame, text="添加", bg=self.colors["success"],
                            fg="white", padx=30, command=add_reminder)
        add_btn.pack(side=tk.LEFT, padx=10)

        cancel_btn = tk.Button(button_frame, text="取消", bg="gray",
                               fg="white", padx=30, command=add_window.destroy)
        cancel_btn.pack(side=tk.LEFT, padx=10)

    def show_alerts(self,window_mode=True):
        """显示报警通知"""
        if window_mode:
            # 获取所有报警记录
            alerts_data = self.db.get_user_alerts(self.current_user['id'])

            if not alerts_data:
                messagebox.showinfo("提示", "暂无报警记录")
                return

            # 转换为 show_alert_window 需要的格式
            formatted_alerts = []
            for alert in alerts_data:
                formatted_alerts.append((
                    alert['alert_type'],
                    alert['alert_value'],
                    alert['normal_range'],
                    alert.get('deviation', ''),
                    self.current_user['id'],
                    self.current_user['full_name'] or self.current_user['username']
                ))

            self.show_alert_window(formatted_alerts)
        else:
            # 原有的面板模式代码保持不变
            self.clear_content()
            self.toolbar_title.config(text="健康报警")


        alerts_frame = tk.Frame(self.content_frame, bg=self.colors["light"])
        alerts_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 标题和清除按钮
        title_frame = tk.Frame(alerts_frame, bg=self.colors["light"])
        title_frame.pack(fill=tk.X, pady=(0, 20))

        tk.Label(title_frame, text="健康报警记录", font=self.title_font,
                 bg=self.colors["light"], fg=self.colors["primary"]).pack(side=tk.LEFT)

        clear_btn = tk.Button(title_frame, text="清除所有已读", bg=self.colors["warning"],
                              fg="white", font=self.normal_font, padx=15,
                              command=self.clear_read_alerts)
        clear_btn.pack(side=tk.RIGHT)

        refresh_btn = tk.Button(title_frame, text="刷新", bg=self.colors["secondary"],
                                fg="white", font=self.normal_font, padx=15,
                                command=self.show_alerts)
        refresh_btn.pack(side=tk.RIGHT, padx=5)

        # 获取报警记录
        alerts = self.db.get_user_alerts(self.current_user['id'])


        if not alerts:
            # 没有报警记录
            no_alerts_frame = tk.Frame(alerts_frame, bg="white", relief=tk.RAISED,
                                       borderwidth=1, padx=30, pady=30)
            no_alerts_frame.pack(fill=tk.BOTH, expand=True)

            tk.Label(no_alerts_frame, text="✅", font=("Arial", 48),
                     bg="white", fg=self.colors["success"]).pack(pady=20)

            tk.Label(no_alerts_frame, text="暂无健康报警", font=self.heading_font,
                     bg="white").pack(pady=10)

            tk.Label(no_alerts_frame, text="您的健康数据均在正常范围内",
                     font=self.normal_font, bg="white", fg=self.colors["gray"]).pack()
            return

        # 创建报警列表
        list_frame = tk.Frame(alerts_frame, bg=self.colors["light"])
        list_frame.pack(fill=tk.BOTH, expand=True)

        # 统计信息
        total_alerts = len(alerts)
        unread_alerts = len([a for a in alerts if not a['is_notified']])

        stats_frame = tk.Frame(list_frame, bg="white", relief=tk.RAISED,
                               borderwidth=1, padx=15, pady=10)
        stats_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(stats_frame, text=f"📊 报警统计: 共 {total_alerts} 条记录",
                 font=self.normal_font, bg="white").pack(side=tk.LEFT)

        if unread_alerts > 0:
            tk.Label(stats_frame, text=f"⚠️ 未读报警: {unread_alerts} 条",
                     font=self.normal_font, bg="white", fg=self.colors["danger"]).pack(side=tk.LEFT, padx=20)

        # 报警列表容器
        alerts_container = tk.Frame(list_frame, bg=self.colors["light"])
        alerts_container.pack(fill=tk.BOTH, expand=True)

        # 创建滚动区域
        canvas = tk.Canvas(alerts_container, bg=self.colors["light"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(alerts_container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.colors["light"])

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 显示每条报警记录
        for alert in alerts:
            alert_frame = tk.Frame(scrollable_frame, bg="white", relief=tk.RAISED,
                                   borderwidth=1, padx=15, pady=10)
            alert_frame.pack(fill=tk.X, pady=5)

            # 设置不同的颜色
            if alert['is_notified']:
                bg_color = "#F8F9F9"
                fg_color = self.colors["gray"]
            else:
                bg_color = "#FFF3CD"
                fg_color = self.colors["dark"]

            alert_frame.config(bg=bg_color)

            # 报警类型和时间
            header_frame = tk.Frame(alert_frame, bg=bg_color)
            header_frame.pack(fill=tk.X)

            # 报警图标
            alert_type = alert['alert_type']
            if "BMI" in alert_type:
                icon = "📊"
                color = self.colors["warning"]
            elif "血压" in alert_type:
                icon = "🩸"
                color = self.colors["danger"]
            elif "血糖" in alert_type:
                icon = "🩸"
                color = self.colors["danger"]
            elif "心率" in alert_type:
                icon = "❤️"
                color = self.colors["primary"]
            else:
                icon = "⚠️"
                color = self.colors["warning"]

            tk.Label(header_frame, text=icon, font=("Arial", 16),
                     bg=bg_color, fg=color).pack(side=tk.LEFT)

            # 报警类型和状态
            type_frame = tk.Frame(header_frame, bg=bg_color)
            type_frame.pack(side=tk.LEFT, padx=10)

            tk.Label(type_frame, text=alert['alert_type'],
                     font=self.heading_font, bg=bg_color, fg=fg_color).pack(anchor=tk.W)

            status_text = "✅ 已处理" if alert['is_notified'] else "🔄 未处理"
            status_color = self.colors["success"] if alert['is_notified'] else self.colors["warning"]

            tk.Label(type_frame, text=status_text, font=self.normal_font,
                     bg=bg_color, fg=status_color).pack(anchor=tk.W)

            # 报警时间
            # 处理可能包含毫秒的时间格式
            alert_time_str = alert['alert_time']
            try:
                # 尝试解析带毫秒的时间格式
                alert_time_dt = datetime.strptime(alert_time_str, '%Y-%m-%d %H:%M:%S.%f')
            except ValueError:
                try:
                    # 尝试解析不带毫秒的时间格式
                    alert_time_dt = datetime.strptime(alert_time_str, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    # 如果两种格式都不匹配，使用当前时间
                    alert_time_dt = datetime.now()

            alert_time = alert_time_dt.strftime('%Y-%m-%d %H:%M')
            tk.Label(header_frame, text=f"📅 {alert_time}", font=self.normal_font,
                     bg=bg_color, fg=self.colors["gray"]).pack(side=tk.RIGHT)

            # 报警详情
            detail_frame = tk.Frame(alert_frame, bg=bg_color)
            detail_frame.pack(fill=tk.X, pady=(10, 0))

            # 当前值和正常范围
            tk.Label(detail_frame, text=f"当前值: {alert['alert_value']}",
                     font=self.normal_font, bg=bg_color, fg=fg_color).pack(side=tk.LEFT)

            tk.Label(detail_frame, text=f"正常范围: {alert['normal_range']}",
                     font=self.normal_font, bg=bg_color, fg=self.colors["success"]).pack(side=tk.LEFT, padx=20)

            # 如果不是已读状态，添加标记为已读按钮
            if not alert['is_notified']:
                action_frame = tk.Frame(alert_frame, bg=bg_color)
                action_frame.pack(fill=tk.X, pady=(10, 0))

                def mark_as_read(alert_id=alert['id']):
                    if self.db.mark_alert_notified(alert_id):
                        self.show_alerts()  # 刷新页面

                read_btn = tk.Button(action_frame, text="标记为已读",
                                     bg=self.colors["primary"], fg="white",
                                     font=self.normal_font, padx=15,
                                     command=mark_as_read)
                read_btn.pack(anchor=tk.W)

        # 配置按钮
        config_frame = tk.Frame(alerts_frame, bg=self.colors["light"])
        config_frame.pack(fill=tk.X, pady=(20, 0))

        config_btn = tk.Button(config_frame, text="⚙️ 配置通知设置",
                               bg=self.colors["primary"], fg="white",
                               font=self.heading_font, padx=30, pady=10,
                               command=self.show_notification_settings)
        config_btn.pack()

    def show_alert_window(self, alerts):
        """显示报警窗口"""
        alert_window = tk.Toplevel(self.root)
        alert_window.title("健康报警通知")
        alert_window.geometry("800x600")
        alert_window.transient(self.root)
        alert_window.grab_set()

        # 设置窗口图标（可选）
        try:
            alert_window.iconbitmap("alert.ico")
        except:
            pass

        # 标题
        title_frame = tk.Frame(alert_window, bg=self.colors["danger"], height=60)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)

        tk.Label(title_frame, text="⚠️ 健康报警通知",
                 font=("Microsoft YaHei", 18, "bold"),
                 bg=self.colors["danger"], fg="white").pack(expand=True)

        tk.Label(title_frame, text=f"检测到 {len(alerts)} 条报警信息",
                 font=("Microsoft YaHei", 10),
                 bg=self.colors["danger"], fg="white").pack()

        # 主内容区
        main_frame = tk.Frame(alert_window, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 报警详情
        tk.Label(main_frame, text="报警详情：",
                 font=("Microsoft YaHei", 12, "bold"),
                 anchor=tk.W).pack(fill=tk.X, pady=(0, 10))

        # 创建滚动文本框
        text_frame = tk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)

        text_widget = ScrolledText(text_frame, wrap=tk.WORD,
                                   font=("Microsoft YaHei", 10),
                                   padx=10, pady=10)
        text_widget.pack(fill=tk.BOTH, expand=True)

        # 构建报警文本
        alert_text = "=" * 60 + "\n"
        alert_text += "             健康数据异常报警通知\n"
        alert_text += "=" * 60 + "\n\n"
        alert_text += f"生成时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}\n"
        alert_text += f"用户：{self.current_user['full_name'] or self.current_user['username']}\n"
        alert_text += f"报警数量：{len(alerts)} 条\n"
        alert_text += "=" * 60 + "\n\n"

        for i, alert in enumerate(alerts, 1):
            alert_type, alert_value, normal_range, deviation, user_id, user_name = alert
            alert_text += f"报警 #{i}：\n"
            alert_text += f"  • 类型：{alert_type}\n"
            alert_text += f"  • 用户：{user_name}\n"
            alert_text += f"  • 异常值：{alert_value}\n"
            alert_text += f"  • 正常范围：{normal_range}\n"
            alert_text += f"  • 偏离程度：{deviation}\n"
            alert_text += "-" * 40 + "\n\n"

        alert_text += "处理建议：\n"
        alert_text += "1. 请及时确认报警信息的准确性\n"
        alert_text += "2. 如有需要，请咨询专业医生\n"
        alert_text += "3. 保持健康的生活方式\n"
        alert_text += "4. 定期监测相关指标\n\n"
        alert_text += "=" * 60 + "\n"
        alert_text += "请注意：此报警信息仅供参考，如有不适请及时就医。\n"
        alert_text += "=" * 60

        # 插入文本并设置为只读
        text_widget.insert("1.0", alert_text)
        text_widget.config(state=tk.DISABLED)

        # 按钮区域
        button_frame = tk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        def mark_as_read():
            """标记为已读"""
            # 更新数据库中所有未读报警
            user_alerts = self.db.get_user_alerts(self.current_user['id'])
            for alert in user_alerts:
                if not alert['is_notified']:
                    self.db.mark_alert_notified(alert['id'])
            messagebox.showinfo("成功", "所有报警已标记为已读")
            alert_window.destroy()
            self.refresh_alerts_display()

        def export_alerts():
            """导出报警"""
            try:
                filename = filedialog.asksaveasfilename(
                    defaultextension=".txt",
                    filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
                    initialfile=f"报警记录_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                )

                if filename:
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(alert_text)
                    messagebox.showinfo("成功", f"报警记录已导出到：\n{filename}")
            except Exception as e:
                messagebox.showerror("错误", f"导出失败：{str(e)}")

        def show_alert_settings():
            """显示报警设置"""
            alert_window.destroy()
            self.show_notification_settings()

        # 按钮
        read_btn = tk.Button(button_frame, text="标记为已读",
                             bg=self.colors["primary"], fg="white",
                             font=("Microsoft YaHei", 10),
                             padx=20, command=mark_as_read)
        read_btn.pack(side=tk.LEFT, padx=5)

        export_btn = tk.Button(button_frame, text="导出报警",
                               bg=self.colors["success"], fg="white",
                               font=("Microsoft YaHei", 10),
                               padx=20, command=export_alerts)
        export_btn.pack(side=tk.LEFT, padx=5)

        settings_btn = tk.Button(button_frame, text="报警设置",
                                 bg=self.colors["warning"], fg="white",
                                 font=("Microsoft YaHei", 10),
                                 padx=20, command=show_alert_settings)
        settings_btn.pack(side=tk.LEFT, padx=5)

        close_btn = tk.Button(button_frame, text="关闭窗口",
                              bg=self.colors["gray"], fg="white",
                              font=("Microsoft YaHei", 10),
                              padx=20, command=alert_window.destroy)
        close_btn.pack(side=tk.RIGHT, padx=5)

        # 居中显示
        alert_window.update_idletasks()
        width = alert_window.winfo_width()
        height = alert_window.winfo_height()
        x = (alert_window.winfo_screenwidth() // 2) - (width // 2)
        y = (alert_window.winfo_screenheight() // 2) - (height // 2)
        alert_window.geometry(f'{width}x{height}+{x}+{y}')

        # 设置窗口关闭时的行为
        def on_closing():
            if messagebox.askyesno("确认", "确定要关闭报警窗口吗？"):
                alert_window.destroy()

        alert_window.protocol("WM_DELETE_WINDOW", on_closing)

    def refresh_alerts_display(self):
        """刷新报警显示"""
        # 如果有未读报警，在工具栏显示小红点
        unread_alerts = [a for a in self.db.get_user_alerts(self.current_user['id'])
                         if not a['is_notified']]

        if unread_alerts:
            # 在工具栏标题旁显示未读数量
            if hasattr(self, 'alert_indicator'):
                self.alert_indicator.destroy()

            self.alert_indicator = tk.Label(self.toolbar_title.master,
                                            text=f"  ⚠️{len(unread_alerts)}",
                                            font=("Microsoft YaHei", 10, "bold"),
                                            bg=self.colors["primary"],
                                            fg="white",
                                            cursor="hand2")
            self.alert_indicator.pack(side=tk.LEFT, padx=(10, 0))
            self.alert_indicator.bind("<Button-1>", lambda e: self.show_alerts())
        else:
            if hasattr(self, 'alert_indicator'):
                self.alert_indicator.destroy()

    def check_and_show_alerts(self):
        """检查并显示未读报警"""
        unread_alerts = [a for a in self.db.get_user_alerts(self.current_user['id'])
                         if not a['is_notified']]

        if unread_alerts:
            response = messagebox.askyesno("新报警",
                                           f"您有 {len(unread_alerts)} 条未读健康报警\n\n"
                                           "是否立即查看？")
            if response:
                self.show_alerts()

    def refresh_alerts(self):
        """刷新报警列表"""
        self.show_alerts()

    def mark_all_alerts_read(self):
        """标记所有报警为已读"""
        if messagebox.askyesno("确认", "确定要标记所有报警为已读吗？"):
            self.cursor.execute("UPDATE health_alerts SET is_notified = 1")
            self.conn.commit()
            messagebox.showinfo("成功", "所有报警已标记为已读")
            self.show_alerts()

    def export_alerts(self):
        """导出报警记录"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV文件", "*.csv"), ("文本文件", "*.txt"), ("所有文件", "*.*")],
                initialfile=f"报警记录_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )

            if filename:
                self.cursor.execute('''
                    SELECT alert_time, user_name, alert_type, alert_value, 
                           normal_range, deviation, is_notified 
                    FROM health_alerts 
                    ORDER BY alert_time DESC
                ''')
                alerts = self.cursor.fetchall()

                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['报警时间', '用户', '报警类型', '异常值', '正常范围', '偏离', '处理状态'])

                    for alert in alerts:
                        alert_time, user_name, alert_type, alert_value, normal_range, deviation, is_notified = alert
                        status = "已处理" if is_notified else "待处理"
                        writer.writerow(
                            [alert_time, user_name, alert_type, alert_value, normal_range, deviation, status])

                messagebox.showinfo("成功", f"报警记录已导出到:\n{filename}")

        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {str(e)}")

    def clear_read_alerts(self):
        """清除已读报警记录"""
        if messagebox.askyesno("确认", "确定要清除所有已读报警记录吗？"):
            # 这里可以添加数据库操作来删除已读记录
            # 暂时先刷新页面
            self.show_alerts()

    def show_notification_settings(self):
        """显示通知设置"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("通知设置")
        settings_window.geometry("500x400")

        # 设置模态
        settings_window.transient(self.root)
        settings_window.grab_set()

        # 创建设置表单
        form_frame = tk.Frame(settings_window, padx=30, pady=30)
        form_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(form_frame, text="通知设置", font=self.title_font).pack(pady=(0, 20))

        # 获取当前设置
        current_settings = self.db.get_user_settings(self.current_user['id'])

        settings_fields = [
            ("启用邮件通知:", "check", current_settings.get('email_notifications', 'true') == 'true'),
            ("启用短信通知:", "check", current_settings.get('sms_notifications', 'false') == 'true'),
            ("报警阈值 (BMI):", "entry", current_settings.get('bmi_threshold', '24')),
            ("报警阈值 (血压高压):", "entry", current_settings.get('bp_sys_threshold', '140')),
            ("报警阈值 (血压低压):", "entry", current_settings.get('bp_dia_threshold', '90')),
            ("报警阈值 (血糖):", "entry", current_settings.get('blood_sugar_threshold', '6.1')),
            ("报警阈值 (心率):", "entry", current_settings.get('heart_rate_threshold', '100')),
        ]

        form_vars = {}

        for i, (label, field_type, default) in enumerate(settings_fields):
            frame = tk.Frame(form_frame)
            frame.pack(fill=tk.X, pady=10)

            tk.Label(frame, text=label, width=20, anchor=tk.W).pack(side=tk.LEFT)

            if field_type == "check":
                var = tk.BooleanVar(value=default)
                check = tk.Checkbutton(frame, variable=var)
                check.pack(side=tk.LEFT)
                form_vars[label[:-1]] = var
            elif field_type == "entry":
                var = tk.StringVar(value=str(default))
                entry = tk.Entry(frame, textvariable=var, width=15)
                entry.pack(side=tk.LEFT)
                form_vars[label[:-1]] = var

        def save_settings():
            """保存通知设置"""
            for key, var in form_vars.items():
                if isinstance(var, tk.BooleanVar):
                    value = 'true' if var.get() else 'false'
                else:
                    value = var.get()

                setting_key = key.lower().replace(' ', '_').replace('(', '').replace(')', '').replace('：', '')
                self.db.set_user_setting(self.current_user['id'], setting_key, value)

            messagebox.showinfo("成功", "通知设置已保存")
            settings_window.destroy()

        button_frame = tk.Frame(form_frame)
        button_frame.pack(pady=30)

        save_btn = tk.Button(button_frame, text="保存", bg=self.colors["success"],
                             fg="white", padx=30, command=save_settings)
        save_btn.pack(side=tk.LEFT, padx=10)

        cancel_btn = tk.Button(button_frame, text="取消", bg="gray",
                               fg="white", padx=30, command=settings_window.destroy)
        cancel_btn.pack(side=tk.LEFT, padx=10)

    def show_user_management(self):
        """显示用户管理（管理员功能）"""
        if self.current_user['role'] != 'admin':
            messagebox.showerror("权限不足", "只有管理员可以访问此功能")
            return

        self.clear_content()
        self.toolbar_title.config(text="用户管理")

        # 获取所有用户
        users = self.db.get_all_users()

        # 创建用户管理界面
        users_frame = tk.Frame(self.content_frame, bg=self.colors["light"])
        users_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 标题
        title_frame = tk.Frame(users_frame, bg=self.colors["light"])
        title_frame.pack(fill=tk.X, pady=(0, 20))

        tk.Label(title_frame, text="用户管理", font=self.title_font,
                 bg=self.colors["light"], fg=self.colors["primary"]).pack(side=tk.LEFT)

        tk.Label(title_frame, text=f"共 {len(users)} 个用户",
                 font=self.normal_font, bg=self.colors["light"],
                 fg=self.colors["gray"]).pack(side=tk.RIGHT)

        # 用户列表
        list_frame = tk.Frame(users_frame, bg="white", relief=tk.RAISED, borderwidth=1)
        list_frame.pack(fill=tk.BOTH, expand=True)

        # 创建Treeview
        columns = ("ID", "用户名", "姓名", "邮箱", "角色", "状态", "注册时间")
        self.users_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=15)

        # 设置列
        for col in columns:
            self.users_tree.heading(col, text=col)
            self.users_tree.column(col, width=100)

        self.users_tree.column("用户名", width=120)
        self.users_tree.column("邮箱", width=150)
        self.users_tree.column("注册时间", width=120)

        # 添加滚动条
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.users_tree.yview)
        self.users_tree.configure(yscrollcommand=scrollbar.set)

        self.users_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 加载用户数据
        for user in users:
            status = "活跃" if user['is_active'] else "停用"
            role_map = {"admin": "管理员", "user": "用户", "family": "家属"}
            role = role_map.get(user['role'], user['role'])

            self.users_tree.insert("", tk.END, values=(
                user['id'],
                user['username'],
                user['full_name'] or "-",
                user['email'] or "-",
                role,
                status,
                user['created_at']
            ))

        # 操作按钮
        button_frame = tk.Frame(users_frame, bg=self.colors["light"])
        button_frame.pack(fill=tk.X, pady=(10, 0))

        # 查看用户数据按钮
        view_data_btn = tk.Button(button_frame, text="查看用户数据",
                                  bg=self.colors["secondary"], fg="white",
                                  font=self.normal_font,
                                  command=self.view_user_data)
        view_data_btn.pack(side=tk.LEFT, padx=5)

        def change_user_role():
            """更改用户角色"""
            selection = self.users_tree.selection()
            if not selection:
                messagebox.showwarning("警告", "请选择用户")
                return

            item = self.users_tree.item(selection[0])
            user_id = item['values'][0]
            current_role = item['values'][4]

            # 创建角色选择窗口
            role_window = tk.Toplevel(self.root)
            role_window.title("更改用户角色")
            role_window.geometry("300x200")

            tk.Label(role_window, text=f"用户: {item['values'][1]}",
                     font=self.heading_font).pack(pady=20)

            role_var = tk.StringVar(value=current_role)

            roles_frame = tk.Frame(role_window)
            roles_frame.pack(pady=10)

            for role in ["管理员", "用户", "家属"]:
                rb = tk.Radiobutton(roles_frame, text=role, value=role,
                                    variable=role_var)
                rb.pack(anchor=tk.W)

            def save_role():
                """保存角色"""
                new_role = {"管理员": "admin", "用户": "user", "家属": "family"}[role_var.get()]
                if self.db.update_user_role(user_id, new_role):
                    messagebox.showinfo("成功", "角色更新成功")
                    role_window.destroy()
                    self.show_user_management()
                else:
                    messagebox.showerror("错误", "更新失败")

            button_frame = tk.Frame(role_window)
            button_frame.pack(pady=20)

            tk.Button(button_frame, text="保存", bg=self.colors["success"],
                      fg="white", command=save_role).pack(side=tk.LEFT, padx=10)
            tk.Button(button_frame, text="取消", bg="gray",
                      fg="white", command=role_window.destroy).pack(side=tk.LEFT, padx=10)

        def toggle_user_status():
            """切换用户状态"""
            selection = self.users_tree.selection()
            if not selection:
                messagebox.showwarning("警告", "请选择用户")
                return

            item = self.users_tree.item(selection[0])
            user_id = item['values'][0]
            current_status = item['values'][5]

            if current_status == "活跃":
                if messagebox.askyesno("确认", "确定要停用此用户吗？"):
                    if self.db.deactivate_user(user_id):
                        messagebox.showinfo("成功", "用户已停用")
                        self.show_user_management()
            else:
                if self.db.activate_user(user_id):
                    messagebox.showinfo("成功", "用户已激活")
                    self.show_user_management()

        role_btn = tk.Button(button_frame, text="更改角色", bg=self.colors["primary"],
                             fg="white", font=self.normal_font,
                             command=change_user_role)
        role_btn.pack(side=tk.LEFT, padx=5)

        status_btn = tk.Button(button_frame, text="切换状态", bg=self.colors["warning"],
                               fg="white", font=self.normal_font,
                               command=toggle_user_status)
        status_btn.pack(side=tk.LEFT, padx=5)

        refresh_btn = tk.Button(button_frame, text="刷新", bg=self.colors["gray"],
                                fg="white", font=self.normal_font,
                                command=self.show_user_management)
        refresh_btn.pack(side=tk.LEFT, padx=5)

    def view_user_data(self):
        """查看用户所有数据（管理员）"""
        selection = self.users_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请选择一个用户")
            return

        item = self.users_tree.item(selection[0])
        user_id = item['values'][0]
        username = item['values'][1]

        # 获取用户所有健康记录
        self.cursor.execute('''
            SELECT * FROM health_records 
            WHERE user_id = ? 
            ORDER BY date DESC
        ''', (user_id,))
        records = self.cursor.fetchall()

        # 在新窗口中显示数据
        data_window = tk.Toplevel(self.root)
        data_window.title(f"用户数据 - {username}")
        data_window.geometry("1000x600")

        # 创建Treeview显示所有数据
        columns = ("日期", "身高(m)", "体重(kg)", "血压", "血糖", "心率", "BMI", "备注")
        tree = ttk.Treeview(data_window, columns=columns, show="headings", height=20)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=100)

        tree.column("日期", width=120)
        tree.column("备注", width=200)

        # 添加滚动条
        scrollbar = ttk.Scrollbar(data_window, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 加载数据
        for record in records:
            # 计算BMI
            height = record[3]  # 索引3是height
            weight = record[4]  # 索引4是weight
            bmi = round(weight / (height ** 2), 2) if height > 0 else 0

            tree.insert("", tk.END, values=(
                record[2],  # date
                height,
                weight,
                record[5],  # blood_pressure
                record[6],  # blood_sugar
                record[7],  # heart_rate
                bmi,
                record[8]  # notes
            ))

    def show_admin_stats(self):
        """显示管理员统计"""
        if self.current_user['role'] != 'admin':
            messagebox.showerror("权限不足", "只有管理员可以访问此功能")
            return

        self.clear_content()
        self.toolbar_title.config(text="数据统计")

        # 获取统计信息
        users = self.db.get_all_users()
        user_count = len(users)
        active_users = len([u for u in users if u['is_active']])
        admin_count = len([u for u in users if u['role'] == 'admin'])

        # 创建统计界面
        stats_frame = tk.Frame(self.content_frame, bg=self.colors["light"])
        stats_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(stats_frame, text="系统数据统计", font=self.title_font,
                 bg=self.colors["light"], fg=self.colors["primary"]).pack(pady=(0, 20))

        # 统计卡片
        cards_frame = tk.Frame(stats_frame, bg=self.colors["light"])
        cards_frame.pack(fill=tk.X, pady=(0, 20))

        stats_cards = [
            ("总用户数", f"{user_count}", "#3498DB", "👥"),
            ("活跃用户", f"{active_users}", "#2ECC71", "✅"),
            ("管理员数", f"{admin_count}", "#F39C12", "👑"),
            ("家属用户", f"{len([u for u in users if u['role'] == 'family'])}", "#9B59B6", "👨‍👩‍👧"),
        ]

        for i, (title, value, color, icon) in enumerate(stats_cards):
            card = self.create_stat_card(cards_frame, title, value, color, icon)
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10) if i < 3 else 0)

        # 用户角色分布图
        chart_frame = tk.LabelFrame(stats_frame, text="用户角色分布",
                                    font=self.heading_font, bg=self.colors["light"])
        chart_frame.pack(fill=tk.BOTH, expand=True)

        # 计算角色分布
        role_counts = {}
        for user in users:
            role = user['role']
            role_counts[role] = role_counts.get(role, 0) + 1

        # 创建图表
        fig = Figure(figsize=(8, 4), dpi=100, facecolor=self.colors["light"])
        ax = fig.add_subplot(111)

        labels = ["管理员", "普通用户", "家属用户"]
        sizes = [
            role_counts.get('admin', 0),
            role_counts.get('user', 0),
            role_counts.get('family', 0)
        ]
        colors = ["#F39C12", "#3498DB", "#9B59B6"]

        ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%',
               startangle=90, textprops={'fontsize': 10})
        ax.axis('equal')
        ax.set_title('用户角色分布图', fontsize=12, fontweight='bold')

        canvas = FigureCanvasTkAgg(fig, chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def show_admin_settings(self):
        """显示管理员设置"""
        if self.current_user['role'] != 'admin':
            messagebox.showerror("权限不足", "只有管理员可以访问此功能")
            return

        self.clear_content()
        self.toolbar_title.config(text="系统设置")

        # 获取健康标准
        standards = self.db.get_health_standards()

        # 创建设置界面
        settings_frame = tk.Frame(self.content_frame, bg=self.colors["light"])
        settings_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(settings_frame, text="健康标准参考值设置", font=self.title_font,
                 bg=self.colors["light"], fg=self.colors["primary"]).pack(pady=(0, 20))

        # 标准值表格
        table_frame = tk.Frame(settings_frame, bg="white", relief=tk.RAISED, borderwidth=1)
        table_frame.pack(fill=tk.BOTH, expand=True)

        # 创建Treeview
        columns = ("指标", "最小值", "最大值", "单位", "适用人群", "性别", "描述")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=10)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=100)

        tree.column("指标", width=120)
        tree.column("描述", width=150)

        # 添加滚动条
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 加载标准值
        for std in standards:
            tree.insert("", tk.END, values=(
                std['name'],
                std['min_normal'],
                std['max_normal'],
                std['unit'],
                std['age_group'],
                std['gender'],
                std['description']
            ))

        # 操作按钮
        button_frame = tk.Frame(settings_frame, bg=self.colors["light"])
        button_frame.pack(fill=tk.X, pady=(10, 0))

        def edit_standard():
            """编辑标准值"""
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("警告", "请选择要编辑的标准")
                return

            messagebox.showinfo("提示", "编辑功能正在开发中")

        def add_standard():
            """添加标准值"""
            messagebox.showinfo("提示", "添加功能正在开发中")

        edit_btn = tk.Button(button_frame, text="编辑标准", bg=self.colors["primary"],
                             fg="white", font=self.normal_font,
                             command=edit_standard)
        edit_btn.pack(side=tk.LEFT, padx=5)

        add_btn = tk.Button(button_frame, text="添加标准", bg=self.colors["success"],
                            fg="white", font=self.normal_font,
                            command=add_standard)
        add_btn.pack(side=tk.LEFT, padx=5)

    def show_backup_restore(self):
        """显示备份恢复界面"""
        if self.current_user['role'] != 'admin':
            messagebox.showerror("权限不足", "只有管理员可以访问此功能")
            return

        self.clear_content()
        self.toolbar_title.config(text="备份与恢复")

        backup_frame = tk.Frame(self.content_frame, bg=self.colors["light"])
        backup_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(backup_frame, text="数据备份与恢复", font=self.title_font,
                 bg=self.colors["light"], fg=self.colors["primary"]).pack(pady=(0, 20))

        # 功能说明
        info_text = """
        数据备份与恢复功能说明：

        1. 备份功能：
           - 将当前数据库完整备份到指定位置
           - 备份文件包含所有用户数据、健康记录和设置
           - 建议定期备份以防数据丢失

        2. 恢复功能：
           - 从备份文件恢复数据库
           - 恢复会覆盖当前所有数据
           - 请谨慎操作，恢复前建议先备份当前数据

        3. 自动备份：
           - 可设置自动备份计划
           - 备份到指定目录
           - 保留最近N个备份文件

        注意：备份和恢复操作需要管理员权限。
        """

        text_widget = tk.Text(backup_frame, wrap=tk.WORD, font=self.normal_font,
                              bg="white", padx=20, pady=20, height=12)
        text_widget.insert("1.0", info_text)
        text_widget.config(state=tk.DISABLED)
        text_widget.pack(fill=tk.X, pady=(0, 20))

        # 操作按钮
        button_frame = tk.Frame(backup_frame, bg=self.colors["light"])
        button_frame.pack()

        def backup_data():
            """备份数据"""
            filename = filedialog.asksaveasfilename(
                title="选择备份位置",
                defaultextension=".db",
                filetypes=[("数据库文件", "*.db"), ("所有文件", "*.*")],
                initialfile=f"health_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            )

            if filename:
                success, msg = self.db.backup_database(filename)
                if success:
                    messagebox.showinfo("成功", f"备份成功：\n{filename}")
                else:
                    messagebox.showerror("错误", f"备份失败：\n{msg}")

        def restore_data():
            """恢复数据"""
            if not messagebox.askyesno("警告", "恢复将覆盖当前所有数据！\n是否继续？"):
                return

            filename = filedialog.askopenfilename(
                title="选择备份文件",
                filetypes=[("数据库文件", "*.db"), ("所有文件", "*.*")]
            )

            if filename:
                success, msg = self.db.restore_database(filename)
                if success:
                    messagebox.showinfo("成功", "恢复成功！请重新登录")
                    self.logout()
                else:
                    messagebox.showerror("错误", f"恢复失败：\n{msg}")

        backup_btn = tk.Button(button_frame, text="备份数据库",
                               bg=self.colors["primary"], fg="white",
                               font=self.heading_font, padx=30, pady=10,
                               command=backup_data)
        backup_btn.pack(side=tk.LEFT, padx=10)

        restore_btn = tk.Button(button_frame, text="恢复数据库",
                                bg=self.colors["danger"], fg="white",
                                font=self.heading_font, padx=30, pady=10,
                                command=restore_data)
        restore_btn.pack(side=tk.LEFT, padx=10)

    def show_personal_settings(self):
        """显示个人设置（动态版）"""
        self.clear_content()
        self.toolbar_title.config(text="个人设置")

        settings_frame = tk.Frame(self.content_frame, bg=self.colors["light"])
        settings_frame.pack(fill=tk.BOTH, expand=True, padx=50, pady=30)

        # 主标题
        title_frame = tk.Frame(settings_frame, bg=self.colors["light"])
        title_frame.pack(fill=tk.X, pady=(0, 20))

        tk.Label(title_frame, text="个人设置", font=self.title_font,
                 bg=self.colors["light"], fg=self.colors["primary"]).pack(side=tk.LEFT)

        save_btn = tk.Button(title_frame, text="保存设置", bg=self.colors["success"],
                             fg="white", font=self.heading_font, padx=20,
                             command=self.save_personal_settings)
        save_btn.pack(side=tk.RIGHT)

        # 创建选项卡
        notebook = ttk.Notebook(settings_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        # 个人信息选项卡
        personal_frame = tk.Frame(notebook, bg=self.colors["light"], padx=20, pady=20)
        notebook.add(personal_frame, text="个人信息")

        # 创建个人信息表单
        personal_fields = [
            ("用户名:", "label", self.current_user['username'], False),
            ("姓名:", "entry", self.current_user['full_name'] or ""),
            ("邮箱:", "entry", self.current_user['email'] or ""),
            ("电话:", "entry", ""),
            ("出生日期:", "entry", self.current_user['birth_date'] or ""),
            ("性别:", "combo", ["男", "女"], self.current_user['gender'] or "男"),
        ]

        self.personal_vars = {}

        for label, field_type, default, *options in personal_fields:
            frame = tk.Frame(personal_frame, bg=self.colors["light"])
            frame.pack(fill=tk.X, pady=10)

            tk.Label(frame, text=label, font=self.normal_font,
                     bg=self.colors["light"], width=10, anchor=tk.W).pack(side=tk.LEFT)

            if field_type == "entry":
                var = tk.StringVar(value=default)
                entry = tk.Entry(frame, textvariable=var, font=self.normal_font,
                                 width=30, relief=tk.SOLID, borderwidth=1)
                entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
                self.personal_vars[label[:-1]] = var
            elif field_type == "combo":
                var = tk.StringVar(value=default[1] if isinstance(default, list) else default)
                combo = ttk.Combobox(frame, textvariable=var,
                                     values=default[0] if isinstance(default, list) else default,
                                     state="readonly", width=28)
                combo.pack(side=tk.LEFT)
                self.personal_vars[label[:-1]] = var
            elif field_type == "label":
                tk.Label(frame, text=default, font=self.normal_font,
                         bg=self.colors["light"], anchor=tk.W).pack(side=tk.LEFT)

        # 隐私设置选项卡
        privacy_frame = tk.Frame(notebook, bg=self.colors["light"], padx=20, pady=20)
        notebook.add(privacy_frame, text="隐私设置")

        # 获取当前设置
        current_settings = self.db.get_user_settings(self.current_user['id'])

        privacy_fields = [
            ("数据分享:", "check", "允许家属查看我的健康数据",
             current_settings.get('allow_family_view', 'true') == 'true'),
            ("数据导出:", "check", "允许导出我的健康数据",
             current_settings.get('allow_data_export', 'true') == 'true'),
            ("数据备份:", "check", "允许系统备份我的数据",
             current_settings.get('allow_data_backup', 'true') == 'true'),
            ("匿名统计:", "check", "允许匿名使用统计数据",
             current_settings.get('allow_anonymous_stats', 'true') == 'true'),
        ]

        self.privacy_vars = {}

        for label, field_type, description, default in privacy_fields:
            frame = tk.Frame(privacy_frame, bg=self.colors["light"])
            frame.pack(fill=tk.X, pady=10)

            var = tk.BooleanVar(value=default)
            check = tk.Checkbutton(frame, text=description, variable=var,
                                   font=self.normal_font, bg=self.colors["light"],
                                   anchor=tk.W)
            check.pack(fill=tk.X)
            self.privacy_vars[label[:-1]] = var

        # 通知设置选项卡
        notification_frame = tk.Frame(notebook, bg=self.colors["light"], padx=20, pady=20)
        notebook.add(notification_frame, text="通知设置")

        notification_fields = [
            ("邮件通知:", "check", "接收健康报告邮件通知",
             current_settings.get('email_notifications', 'true') == 'true'),
            ("提醒通知:", "check", "接收健康提醒通知",
             current_settings.get('reminder_notifications', 'true') == 'true'),
            ("报警通知:", "check", "接收健康报警通知",
             current_settings.get('alert_notifications', 'true') == 'true'),
            ("通知频率:", "combo", ["实时", "每日", "每周", "每月"],
             current_settings.get('notification_frequency', '实时')),
            # 添加报警阈值设置
            ("BMI报警阈值:", "entry", current_settings.get('bmi_alert_threshold', '28'),
             "超过此BMI值将触发报警"),
            ("血压报警阈值:", "entry", current_settings.get('bp_alert_threshold', '140/90'),
             "超过此血压值将触发报警"),
        ]

        self.notification_vars = {}

        for i, (label, field_type, *options) in enumerate(notification_fields):
            frame = tk.Frame(notification_frame, bg=self.colors["light"])
            frame.pack(fill=tk.X, pady=10)

            if field_type == "check":
                var = tk.BooleanVar(value=options[1])
                check = tk.Checkbutton(frame, text=options[0], variable=var,
                                       font=self.normal_font, bg=self.colors["light"],
                                       anchor=tk.W)
                check.pack(fill=tk.X)
                self.notification_vars[label[:-1]] = var
            elif field_type == "combo":
                tk.Label(frame, text=label, font=self.normal_font,
                         bg=self.colors["light"], width=10, anchor=tk.W).pack(side=tk.LEFT)

                var = tk.StringVar(value=options[1])
                combo = ttk.Combobox(frame, textvariable=var,
                                     values=options[0], state="readonly", width=15)
                combo.pack(side=tk.LEFT)
                self.notification_vars[label[:-1]] = var

        # 界面设置选项卡
        interface_frame = tk.Frame(notebook, bg=self.colors["light"], padx=20, pady=20)
        notebook.add(interface_frame, text="界面设置")

        interface_fields = [
            ("主题颜色:", "combo", ["蓝色", "绿色", "橙色", "紫色", "红色"],
             current_settings.get('theme_color', '蓝色')),
            ("字体大小:", "combo", ["小", "中", "大"],
             current_settings.get('font_size', '中')),
            ("语言:", "combo", ["中文", "English"],
             current_settings.get('language', '中文')),
            ("自动刷新:", "check", "自动刷新数据",
             current_settings.get('auto_refresh', 'true') == 'true'),
        ]

        self.interface_vars = {}

        for label, field_type, *options in interface_fields:
            frame = tk.Frame(interface_frame, bg=self.colors["light"])
            frame.pack(fill=tk.X, pady=10)

            tk.Label(frame, text=label, font=self.normal_font,
                     bg=self.colors["light"], width=10, anchor=tk.W).pack(side=tk.LEFT)

            if field_type == "combo":
                var = tk.StringVar(value=options[1])
                combo = ttk.Combobox(frame, textvariable=var,
                                     values=options[0], state="readonly", width=15)
                combo.pack(side=tk.LEFT)
                self.interface_vars[label[:-1]] = var
            elif field_type == "check":
                var = tk.BooleanVar(value=options[1])
                check = tk.Checkbutton(frame, text=options[0], variable=var,
                                       font=self.normal_font, bg=self.colors["light"])
                check.pack(side=tk.LEFT)
                self.interface_vars[label[:-1]] = var

    def save_personal_settings(self):
        """保存个人设置"""
        try:
            # 保存个人信息
            full_name = self.personal_vars["姓名"].get() if "姓名" in self.personal_vars else None
            email = self.personal_vars["邮箱"].get() if "邮箱" in self.personal_vars else None
            phone = self.personal_vars["电话"].get() if "电话" in self.personal_vars else None
            birth_date = self.personal_vars["出生日期"].get() if "出生日期" in self.personal_vars else None
            gender = self.personal_vars["性别"].get() if "性别" in self.personal_vars else None

            if full_name is not None or email is not None:
                self.db.update_user_info(
                    self.current_user['id'],
                    email=email,
                    phone=phone,
                    full_name=full_name,
                    birth_date=birth_date,
                    gender=gender
                )

            # 保存隐私设置
            for key, var in self.privacy_vars.items():
                value = 'true' if var.get() else 'false'
                self.db.set_user_setting(self.current_user['id'], key.lower().replace(' ', '_'), value)

            # 保存通知设置
            for key, var in self.notification_vars.items():
                if isinstance(var, tk.BooleanVar):
                    value = 'true' if var.get() else 'false'
                else:
                    value = var.get()
                self.db.set_user_setting(self.current_user['id'], key.lower().replace(' ', '_'), value)

            # 保存界面设置
            for key, var in self.interface_vars.items():
                if isinstance(var, tk.BooleanVar):
                    value = 'true' if var.get() else 'false'
                else:
                    value = var.get()
                self.db.set_user_setting(self.current_user['id'], key.lower().replace(' ', '_'), value)

            # 更新当前用户信息
            updated_user = self.db.get_user_by_id(self.current_user['id'])
            if updated_user:
                self.current_user.update(updated_user)

            messagebox.showinfo("成功", "个人设置已保存！")

            # 重新加载个人设置界面以显示更新后的数据
            self.show_personal_settings()

        except Exception as e:
            messagebox.showerror("错误", f"保存设置失败: {str(e)}")

    def show_help(self):
        """显示帮助界面"""
        self.clear_content()
        self.toolbar_title.config(text="帮助")

        help_frame = tk.Frame(self.content_frame, bg=self.colors["light"])
        help_frame.pack(fill=tk.BOTH, expand=True, padx=50, pady=50)

        tk.Label(help_frame, text="使用帮助", font=self.title_font,
                 bg=self.colors["light"]).pack(pady=(0, 30))

        help_text = """
        个人健康管理档案系统使用说明

        主要功能：
        1. 用户模块
           - 仪表板：查看健康数据概览和统计信息
           - 添加记录：记录身高、体重、血压、血糖等健康数据
           - 我的记录：管理所有健康记录，支持编辑和删除
           - 数据分析：查看健康数据的变化趋势图表
           - 健康报告：生成详细的健康分析报告

        2. 家属/监护人模块
           - 家属列表：绑定家人账户，协助维护健康记录
           - 健康提醒：设置服药时间、复诊提醒等
           - 报警通知：接收异常数据报警通知

        3. 管理员模块
           - 用户管理：管理用户账户与隐私权限
           - 数据统计：查看系统使用情况统计
           - 标准参考值：提供健康标准参考值对照表
           - 备份恢复：数据备份与恢复机制

        使用提示：
        - 定期记录健康数据以获得准确的分析结果
        - 系统会自动计算BMI并分类
        - 可以导出数据到Excel进行进一步分析
        - 健康报告包含个性化的健康建议

        技术支持：
        如有问题，请联系系统管理员或查看用户手册。
        """

        text_widget = tk.Text(help_frame, wrap=tk.WORD, font=self.normal_font,
                              bg="white", padx=20, pady=20, height=20)
        text_widget.insert("1.0", help_text)
        text_widget.config(state=tk.DISABLED)
        text_widget.pack(fill=tk.BOTH, expand=True)

    def update_statistics(self):
        """更新统计信息"""
        # 这里可以添加定期更新统计信息的逻辑
        pass

    def logout(self):
        """退出登录"""
        if messagebox.askokcancel("退出", "确定要退出当前账户吗？"):
            self.db.close()
            self.root.destroy()

            # 重新显示登录窗口
            login_root = tk.Tk()
            db = HealthDatabase()
            login_app = LoginWindow(login_root, db)
            login_root.mainloop()


def main():
    """主函数"""
    # 创建登录窗口
    login_root = tk.Tk()
    db = HealthDatabase()
    login_app = LoginWindow(login_root, db)
    login_root.mainloop()


if __name__ == "__main__":
    main()