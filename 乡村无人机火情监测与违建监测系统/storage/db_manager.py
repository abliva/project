import os
import cv2
import json
import sqlite3
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import asdict
import threading
import config
from models.detector import DetectionResult


class DatabaseManager:

    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DB_PATH
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.executescript('''
                CREATE TABLE IF NOT EXISTS inspections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    source_type TEXT NOT NULL DEFAULT 'unknown',
                    source_path TEXT,
                    fire_count INTEGER DEFAULT 0,
                    smoke_count INTEGER DEFAULT 0,
                    illegal_build_count INTEGER DEFAULT 0,
                    has_alert INTEGER DEFAULT 0,
                    image_path TEXT,
                    notes TEXT
                );
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    inspection_id INTEGER,
                    timestamp TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    class_name TEXT,
                    confidence REAL,
                    bbox_x1 INTEGER,
                    bbox_y1 INTEGER,
                    bbox_x2 INTEGER,
                    bbox_y2 INTEGER,
                    severity TEXT DEFAULT 'medium',
                    status TEXT DEFAULT 'active',
                    image_path TEXT,
                    notes TEXT,
                    FOREIGN KEY (inspection_id) REFERENCES inspections(id)
                );
                CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp);
                CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(alert_type);
                CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
            ''')
            conn.commit()
            conn.close()

    def save_inspection(self, result: Dict[str, Any], source_type: str = "image",
                        source_path: str = None, image_path: str = None) -> int:
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            ts = result["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute('''
                INSERT INTO inspections (timestamp, source_type, source_path,
                    fire_count, smoke_count, illegal_build_count, has_alert, image_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                ts, source_type, source_path,
                len(result.get("fires", [])),
                len(result.get("smokes", [])),
                len(result.get("illegal_builds", [])),
                1 if result.get("has_alert") else 0,
                image_path
            ))
            inspection_id = cursor.lastrowid
            for alert in result.get("alerts", []):
                severity = "high" if alert.confidence > 0.75 else ("medium" if alert.confidence > 0.5 else "low")
                cursor.execute('''
                    INSERT INTO alerts (inspection_id, timestamp, alert_type,
                        class_name, confidence, bbox_x1, bbox_y1, bbox_x2, bbox_y2, severity)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    inspection_id, alert.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    alert.detection_type, alert.class_name, round(alert.confidence, 4),
                    alert.bbox[0], alert.bbox[1], alert.bbox[2], alert.bbox[3],
                    severity
                ))
            conn.commit()
            conn.close()
            return inspection_id

    def get_alerts(self, limit: int = 50, status: str = None,
                   alert_type: str = None, start_date: str = None,
                   end_date: str = None) -> List[Dict]:
        with self._lock:
            conn = self._get_conn()
            query = "SELECT * FROM alerts WHERE 1=1"
            params = []
            if status:
                query += " AND status = ?"
                params.append(status)
            if alert_type:
                query += " AND alert_type = ?"
                params.append(alert_type)
            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date)
            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date)
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            cursor = conn.execute(query, params)
            results = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return results

    def get_inspection_stats(self, days: int = 7) -> Dict[str, Any]:
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT
                    COUNT(*) as total_inspections,
                    SUM(has_alert) as total_alerts,
                    COALESCE(SUM(fire_count), 0) as total_fires,
                    COALESCE(SUM(smoke_count), 0) as total_smokes,
                    COALESCE(SUM(illegal_build_count), 0) as total_builds,
                    DATE(timestamp) as date
                FROM inspections
                WHERE timestamp >= date('now', ?)
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
            ''', (f"-{days} days",))
            daily_stats = [dict(row) for row in cursor.fetchall()]
            cursor.execute('''
                SELECT COUNT(*), alert_type FROM alerts
                WHERE status = 'active'
                GROUP BY alert_type
            ''')
            type_breakdown = {row[1]: row[0] for row in cursor.fetchall()}
            cursor.execute('''
                SELECT
                    COALESCE(SUM(CASE WHEN alert_type LIKE '%fire%' THEN 1 ELSE 0 END), 0) as fire_total,
                    COALESCE(SUM(CASE WHEN alert_type = 'smoke' THEN 1 ELSE 0 END), 0) as smoke_total,
                    COALESCE(SUM(CASE WHEN alert_type LIKE '%build%' THEN 1 ELSE 0 END), 0) as build_total,
                    COUNT(*) as grand_total
                FROM alerts WHERE status = 'active'
            ''')
            row = cursor.fetchone()
            if row:
                totals_row = {"fire_total": row[0], "smoke_total": row[1], "build_total": row[2], "grand_total": row[3]}
            else:
                totals_row = {"fire_total": 0, "smoke_total": 0, "build_total": 0, "grand_total": 0}
            conn.close()
            return {
                "daily_stats": daily_stats,
                "type_breakdown": type_breakdown,
                "totals": totals_row,
                "period_days": days
            }

    def get_full_summary(self) -> Dict[str, Any]:
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM inspections")
            total_inspections = cursor.fetchone()[0] or 0
            cursor.execute("SELECT COUNT(*) FROM alerts WHERE status='active'")
            total_alerts = cursor.fetchone()[0] or 0
            cursor.execute("SELECT COUNT(*) FROM alerts WHERE alert_type LIKE '%fire%' AND status='active'")
            fire_total = cursor.fetchone()[0] or 0
            cursor.execute("SELECT COUNT(*) FROM alerts WHERE alert_type='smoke' AND status='active'")
            smoke_total = cursor.fetchone()[0] or 0
            cursor.execute("SELECT COUNT(*) FROM alerts WHERE alert_type LIKE '%build%' AND status='active'")
            build_total = cursor.fetchone()[0] or 0
            cursor.execute("SELECT COUNT(*) FROM alerts WHERE severity='high' AND status='active'")
            high_severity = cursor.fetchone()[0] or 0
            cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM inspections")
            time_range = cursor.fetchone()
            first_time = time_range[0] or "N/A"
            last_time = time_range[1] or "N/A"
            cursor.execute("""
                SELECT i.timestamp, i.fire_count, i.smoke_count, i.illegal_build_count,
                       (SELECT COUNT(*) FROM alerts a WHERE a.inspection_id=i.id) as alert_cnt
                FROM inspections i ORDER BY i.id DESC LIMIT 10
            """)
            recent_inspections = [dict(row) for row in cursor.fetchall()]
            cursor.execute("""
                SELECT * FROM alerts WHERE status='active'
                ORDER BY timestamp DESC LIMIT 20
            """)
            recent_alerts = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return {
                "total_inspections": total_inspections,
                "total_alerts": total_alerts,
                "fire_total": fire_total,
                "smoke_total": smoke_total,
                "build_total": build_total,
                "high_severity_count": high_severity,
                "first_inspection_time": first_time,
                "last_inspection_time": last_time,
                "recent_inspections": recent_inspections,
                "recent_alerts": recent_alerts
            }

    def mark_alert_resolved(self, alert_id: int, notes: str = ""):
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "UPDATE alerts SET status = 'resolved', notes = ? WHERE id = ?",
                (notes, alert_id)
            )
            conn.commit()
            conn.close()

    def export_report_html(self, output_path: str = None) -> str:
        summary = self.get_full_summary()
        recent_alerts = summary.get("recent_alerts", [])
        recent_inspections = summary.get("recent_inspections", [])
        type_cn = {"fire": "火情", "smoke": "烟雾", "illegal_build": "违建", "new_illegal_build": "新违建", "fire_anomaly": "火情异常", "fire_motion": "动态火情"}
        sev_cn = {"high": "高危", "medium": "中等", "low": "低危"}
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>乡村无人机巡检报告</title>
<style>
body {{ font-family: 'Microsoft YaHei UI', 'Segoe UI', Arial, sans-serif; margin: 20px; background: #0f172a; color: #e2e8f0; }}
.header {{ background: linear-gradient(135deg, #1a1a2e, #16213e); color: white; padding: 30px; border-radius: 10px; margin-bottom: 20px; }}
.header h1 {{ margin: 0 0 10px 0; font-size: 24px; }}
.header p {{ margin: 0; opacity: 0.8; }}
.stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 25px; }}
.stat-card {{ background: #1e293b; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.3); text-align: center; border-left: 4px solid #38bdf8; }}
.stat-card .number {{ font-size: 36px; font-weight: bold; margin: 10px 0; color: #ffffff; }}
.stat-card .label {{ color: #94a3b8; font-size: 14px; }}
.fire {{ border-left-color: #ef4444 !important; }} .fire .number {{ color: #ef4444; }}
.smoke {{ border-left-color: #9ca3af !important; }} .smoke .number {{ color: #9ca3af; }}
.build {{ border-left-color: #f59e0b !important; }} .build .number {{ color: #f59e0b; }}
.total {{ border-left-color: #3b82f6 !important; }} .total .number {{ color: #3b82f6; }}
.section {{ background: #1e293b; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.3); margin-bottom: 20px; }}
.section h2 {{ margin-top: 0; padding-bottom: 10px; border-bottom: 2px solid #334155; color: #38bdf8; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #334155; font-size: 13px; }}
th {{ background: #0f172a; font-weight: 600; color: #94a3b8; }}
.high {{ color: #ef4444; font-weight: bold; }}
.medium {{ color: #f59e0b; }}
.low {{ color: #22c55e; }}
.footer {{ text-align: center; color: #64748b; margin-top: 30px; font-size: 12px; }}
tr:hover td {{ background: #16213e; }}
</style>
</head>
<body>
<div class="header">
<h1>🚁 乡村无人机自动巡检系统 - 检测报告</h1>
<p>违建与火情智能监测平台 | YOLOv8 + PyTorch 深度学习引擎 | 报告生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
</div>

<div class="stats-grid">
<div class="stat-card total"><div class="label">总巡检次数</div><div class="number">{summary['total_inspections']}</div></div>
<div class="stat-card fire"><div class="label">火情警报</div><div class="number">{summary['fire_total']}</div></div>
<div class="stat-card smoke"><div class="label">烟雾警报</div><div class="number">{summary['smoke_total']}</div></div>
<div class="stat-card build"><div class="label">违建警报</div><div class="number">{summary['build_total']}</div></div>
<div class="stat-card total"><div class="label">累计警报总数</div><div class="number">{summary['total_alerts']}</div></div>
<div class="stat-card fire"><div class="label">高危警报数</div><div class="number">{summary['high_severity_count']}</div></div>
</div>

<div class="section">
<h2>🔔 最近预警记录（最近20条）</h2>
<table>
<tr><th>#</th><th>检测时间</th><th>警报类型</th><th>目标类别</th><th>置信度</th><th>严重程度</th></tr>
"""
        for i, alert in enumerate(recent_alerts[:20], 1):
            sev_class = alert.get('severity', 'medium')
            atype = alert.get('alert_type', '')
            atype_cn = type_cn.get(atype, atype)
            html_content += f"""<tr>
<td>{i}</td><td>{alert.get('timestamp', '')}</td><td>{atype_cn}</td>
<td>{alert.get('class_name', '')}</td><td>{alert.get('confidence', 0):.1%}</td>
<td class="{sev_class}">{sev_cn.get(sev_class, sev_class)}</td>
</tr>\n"""
        html_content += """</table></div>

<div class="section">
<h2>📋 最近巡检记录（最近10次）</h2>
<table>
<tr><th>#</th><th>巡检时间</th><th>火情数</th><th>烟雾数</th><th>违建数</th><th>警报数</th></tr>
"""
        for i, insp in enumerate(recent_inspections[:10], 1):
            html_content += f"""<tr>
<td>{i}</td><td>{insp.get('timestamp', '')}</td>
<td>{insp.get('fire_count', 0)}</td><td>{insp.get('smoke_count', 0)}</td>
<td>{insp.get('illegal_build_count', 0)}</td><td>{insp.get('alert_cnt', 0)}</td>
</tr>\n"""
        html_content += f"""</table></div>

<div class="footer">
<p>统计周期：{summary.get('first_inspection_time', 'N/A')} ~ {summary.get('last_inspection_time', 'N/A')} |
技术支持：YOLOv8 + PyTorch 深度学习引擎</p>
</div>
</body>
</html>"""
        output_path = output_path or os.path.join(
            config.REPORT_DIR,
            f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        )
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        return output_path

    def export_report_json(self, output_path: str = None) -> str:
        summary = self.get_full_summary()
        stats = self.get_inspection_stats(days=30)
        recent_alerts = self.get_alerts(limit=100)
        report_data = {
            "generated_at": datetime.now().isoformat(),
            "summary": summary,
            "statistics": stats,
            "recent_alerts": recent_alerts
        }
        output_path = output_path or os.path.join(
            config.REPORT_DIR,
            f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2, default=str)
        return output_path


class AlertManager:

    SEVERITY_COLORS = {
        "high": "#FF0000",
        "medium": "#FFA500",
        "low": "#FFFF00"
    }

    ALERT_TYPE_LABELS = {
        "fire": "[FIRE] 火情警报",
        "smoke": "[SMOKE] 烟雾警报",
        "fire_anomaly": "[FIRE] 火情异常",
        "fire_motion": "[FIRE] 动态火情",
        "illegal_build": "[BUILD] 违规建筑",
        "new_illegal_build": "[NEW!] 新增违建!"
    }

    def __init__(self, db_manager: DatabaseManager = None):
        self.db = db_manager or DatabaseManager()
        self.alert_history: List[Dict] = []
        self.alert_callbacks = []
        self._alert_count = {"fire": 0, "smoke": 0, "illegal_build": 0}

    def register_callback(self, callback):
        self.alert_callbacks.append(callback)

    def process_detection_result(
        self,
        result: Dict[str, Any],
        frame=None,
        source_type: str = "realtime",
        source_path: str = None
    ) -> List[Dict]:
        if not result.get("has_alert"):
            return []
        new_alerts = []
        image_path = None
        if frame is not None and config.AUTO_SAVE_ALERT_IMAGE:
            filename = f"alert_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
            image_path = os.path.join(config.ALERT_DIR, filename)
            cv2.imwrite(image_path, frame)
        inspection_id = self.db.save_inspection(
            result, source_type=source_type,
            source_path=source_path, image_path=image_path
        )
        for alert in result.get("alerts", []):
            alert_info = {
                "id": len(self.alert_history) + 1,
                "inspection_id": inspection_id,
                "timestamp": alert.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "type": alert.detection_type,
                "class_name": alert.class_name,
                "confidence": round(alert.confidence, 4),
                "bbox": alert.bbox,
                "severity": "high" if alert.confidence > 0.75 else ("medium" if alert.confidence > 0.5 else "low"),
                "label": self.ALERT_TYPE_LABELS.get(alert.detection_type, f"[{alert.detection_type}]"),
                "image_path": image_path
            }
            self.alert_history.append(alert_info)
            new_alerts.append(alert_info)
            if "fire" in alert.detection_type:
                self._alert_count["fire"] += 1
            elif alert.detection_type == "smoke":
                self._alert_count["smoke"] += 1
            elif "build" in alert.detection_type:
                self._alert_count["illegal_build"] += 1
        for cb in self.alert_callbacks:
            try:
                cb(new_alerts)
            except Exception:
                pass
        return new_alerts

    def get_recent_alerts(self, n: int = 20) -> List[Dict]:
        return self.alert_history[-n:]

    def get_alert_summary(self) -> Dict[str, Any]:
        return {
            "fire": self._alert_count["fire"],
            "fire_count": self._alert_count["fire"],
            "smoke": self._alert_count["smoke"],
            "smoke_count": self._alert_count["smoke"],
            "illegal_build": self._alert_count["illegal_build"],
            "illegal_build_count": self._alert_count["illegal_build"],
            "total": sum(self._alert_count.values()),
            "db_stats": self.db.get_inspection_stats(days=7),
            "db_full": self.db.get_full_summary()
        }

    def generate_report_html(self) -> str:
        return self.db.export_report_html()

    def generate_report(self) -> str:
        return self.db.export_report_json()
