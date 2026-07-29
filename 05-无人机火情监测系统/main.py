import argparse
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ==================== 配置部分 ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
ALERT_DIR = os.path.join(OUTPUT_DIR, "alerts")
REPORT_DIR = os.path.join(OUTPUT_DIR, "reports")
LOG_DIR = os.path.join(BASE_DIR, "logs")

for d in [DATA_DIR, OUTPUT_DIR, ALERT_DIR, REPORT_DIR, LOG_DIR]:
    os.makedirs(d, exist_ok=True)

ILLEGAL_BUILD_MODEL = "yolov8n.pt"
FIRE_MODEL = "yolov8n.pt"

CONFIDENCE_THRESHOLD = 0.25
IOU_THRESHOLD = 0.45

ILLEGAL_BUILD_CLASSES = {0: "building"}
FIRE_CLASSES = {0: "fire", 1: "smoke"}

ALERT_SOUND_ENABLED = True
AUTO_SAVE_ALERT_IMAGE = True

VIDEO_FPS = 30
DISPLAY_WIDTH = 1280
DISPLAY_HEIGHT = 720

DB_PATH = os.path.join(BASE_DIR, "data", "inspection.db")

# ==================== 检测引擎部分 ====================
import cv2
import numpy as np
import torch
from ultralytics import YOLO
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any, Generator, Callable
from datetime import datetime


@dataclass
class DetectionResult:
    class_id: int
    class_name: str
    confidence: float
    bbox: Tuple[int, int, int, int]
    detection_type: str
    timestamp: datetime = field(default_factory=datetime.now)


def _load_yolo_model(model_name="yolov8n.pt"):
    cache_dir = os.path.join(os.path.expanduser("~"), ".ultralytics", "models")
    cache_file = os.path.join(cache_dir, model_name)
    local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), model_name)
    for path in [cache_file, local_path]:
        if os.path.exists(path):
            try:
                size = os.path.getsize(path)
                if size < 500000:
                    continue
                model = YOLO(path)
                print(f"[模型] 加载成功: {path} ({size/1024/1024:.1f}MB)")
                return model
            except Exception as e:
                print(f"[模型] 加载失败 {path}: {e}")
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except:
                        pass
    print(f"[模型] 正在从网络下载 {model_name}...")
    model = YOLO(model_name)
    print(f"[模型] 下载并加载完成")
    return model


class IllegalBuildDetector:

    def __init__(self, model_path: str = None):
        self.model = _load_yolo_model(model_path or "yolov8n.pt")
        self.target_classes = [0, 1, 2, 3]
        self.building_related = [
            "person", "car", "motorcycle", "truck", "bus",
            "chair", "couch", "bed", "dining table", "tv",
            "laptop", "cell phone", "toilet", "sink", "oven"
        ]
        self._base_image = None
        self._base_detections = []

    def set_base_image(self, image: np.ndarray):
        self._base_image = image.copy()
        results = self.detect(image)
        self._base_detections = results

    def detect(self, image: np.ndarray, conf: float = CONFIDENCE_THRESHOLD) -> List[DetectionResult]:
        results = self.model(image, conf=conf, iou=IOU_THRESHOLD, verbose=False)[0]
        detections = []
        if results.boxes is not None:
            for box in results.boxes:
                cls_id = int(box.cls[0])
                conf_val = float(box.conf[0])
                xyxy = box.xyxy[0].cpu().numpy().astype(int)
                class_name = self.model.names.get(cls_id, f"class_{cls_id}")
                det = DetectionResult(
                    class_id=cls_id,
                    class_name=class_name,
                    confidence=conf_val,
                    bbox=tuple(xyxy),
                    detection_type="illegal_build"
                )
                detections.append(det)
        return detections

    def compare_with_base(self, current_image: np.ndarray) -> List[DetectionResult]:
        if self._base_image is None:
            return self.detect(current_image)
        current_dets = self.detect(current_image)
        new_constructions = []
        for cur_det in current_dets:
            is_new = True
            for base_det in self._base_detections:
                iou = self._calculate_iou(cur_det.bbox, base_det.bbox)
                if iou > 0.3 and cur_det.class_name == base_det.class_name:
                    is_new = False
                    break
            if is_new:
                cur_det.detection_type = "new_illegal_build"
                new_constructions.append(cur_det)
        return new_constructions

    @staticmethod
    def _calculate_iou(box1: Tuple, box2: Tuple) -> float:
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])
        inter_area = max(0, x2 - x1) * max(0, y2 - y1)
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union_area = area1 + area2 - inter_area
        return inter_area / union_area if union_area > 0 else 0


class FireDetector:

    def __init__(self, model_path: str = None):
        self.model = _load_yolo_model(model_path or "yolov8n.pt")
        self._fire_history = []
        self._max_history = 10
        # 多帧验证：使用时空一致性
        self._detection_buffer = []
        self._buffer_size = 3
        # 智能误检过滤系统
        self._false_positive_memory = {}  # {region_hash: (count, last_seen)}
        self._confirmed_fires = {}  # 已确认的真实火情
        # 动态特征追踪
        self._prev_frame_gray = None
        self._prev_fire_mask = None
        self._frame_count = 0

    def _compute_region_hash(self, center_x: int, center_y: int) -> str:
        """计算区域位置哈希，用于跟踪同一区域"""
        grid_x = center_x // 50  # 50像素网格
        grid_y = center_y // 50
        return f"{grid_x}_{grid_y}"

    def _analyze_fire_dynamics(self, image: np.ndarray, x: int, y: int,
                                w: int, h: int) -> dict:
        """分析火焰动态特征：闪烁、抖动、大小变化"""
        if x < 0 or y < 0 or x+w > image.shape[1] or y+h > image.shape[0]:
            return {"flicker": 0.5, "size_change": 0.5, "motion_energy": 0}

        roi = image[y:y+h, x:x+w]
        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        dynamics = {"flicker": 0.5, "size_change": 0.5, "motion_energy": 0}

        # 1. 闪烁分析：亮度标准差（火焰闪烁明显）
        brightness_std = np.std(roi_gray)
        dynamics["flicker"] = min(brightness_std / 60.0, 1.0)

        # 2. 运动能量：与上一帧比较
        if self._prev_frame_gray is not None:
            prev_roi = self._prev_frame_gray[y:y+h, x:x+w] if (y+h <= self._prev_frame_gray.shape[0] and x+w <= self._prev_frame_gray.shape[1]) else None
            if prev_roi is not None and prev_roi.shape == roi_gray.shape:
                diff = cv2.absdiff(roi_gray, prev_roi)
                motion = np.mean(diff)
                dynamics["motion_energy"] = min(motion / 30.0, 1.0)

        # 3. 大小变化：如果之前有该区域的记录
        region_key = self._compute_region_hash(x + w//2, y + h//2)
        if hasattr(self, '_region_sizes') and region_key in self._region_sizes:
            prev_size = self._region_sizes[region_key]
            curr_size = w * h
            if prev_size > 0:
                size_ratio = curr_size / prev_size
                # 火焰大小会在一定范围内波动（0.7-1.5倍）
                if 0.7 < size_ratio < 1.5:
                    dynamics["size_change"] = 0.8
                elif 0.5 < size_ratio < 2.0:
                    dynamics["size_change"] = 0.6
                else:
                    dynamics["size_change"] = 0.2  # 变化太大或太小都不像火焰

        return dynamics

    def _is_likely_false_positive(self, color_info: dict, texture_info: dict,
                                   dynamics: dict, area: int,
                                   aspect_ratio: float, fire_pixel_ratio: float) -> tuple:
        """
        智能判断是否为误检
        返回: (is_false_positive, confidence_penalty, reason)
        """
        reasons = []
        penalty = 0

        # 1. 红色衣物/物体检测（最常见的误检源）
        if color_info.get("mean_sat", 0) < 40:
            # 低饱和度红色 → 可能是暗红色物体
            penalty += 0.25
            reasons.append("低饱和度")

        if color_info.get("std_hue", 0) < 8:
            # 颜色太均匀 → 不是火焰（火焰有渐变）
            penalty += 0.20
            reasons.append("颜色均匀")

        if texture_info.get("brightness_var", 0) < 25:
            # 亮度几乎不变 → 不像火焰（火焰会闪烁）
            penalty += 0.20
            reasons.append("无闪烁")

        # 2. 强光/反光检测
        if color_info.get("mean_val", 0) > 230:
            # 太亮了 → 可能是强光/反光
            penalty += 0.15
            reasons.append("过亮")

        if area > 20000 and fire_pixel_ratio > 0.8:
            # 大面积且几乎全是"火焰色" → 可能是夕阳/红色背景
            penalty += 0.20
            reasons.append("大面积单色")

        # 3. 形状异常检测
        if aspect_ratio > 6 or aspect_ratio < 0.15:
            # 极端的长条形或扁平形 → 不像火焰
            penalty += 0.15
            reasons.append("形状异常")

        # 4. 动态特征检查
        if dynamics.get("motion_energy", 0) < 0.1 and dynamics.get("flicker", 0) < 0.3:
            # 几乎没有动态变化 → 很可能是静止物体
            penalty += 0.25
            reasons.append("静态物体")

        # 判断结果
        is_false_positive = penalty >= 0.5 or len(reasons) >= 3

        return is_false_positive, penalty, ", ".join(reasons) if reasons else "正常"

    def _analyze_vegetation_features(self, image: np.ndarray, x: int, y: int,
                                      w: int, h: int, hsv_roi: np.ndarray) -> dict:
        """
        分析植被特征：区分树木和真实火情
        树木即使变红/黄，仍保留部分绿色成分和特定纹理
        """
        if x < 0 or y < 0 or x + w > image.shape[1] or y + h > image.shape[0]:
            return {"is_vegetation": False, "vegetation_score": 0, "green_ratio": 0,
                    "texture_regularity": 0, "edge_orientation": 0}

        roi = image[y:y+h, x:x+w]
        roi_bgr = cv2.cvtColor(roi, cv2.COLOR_RGB2BGR) if len(roi.shape) == 3 and roi.shape[2] == 3 else roi

        features = {
            "is_vegetation": False,
            "vegetation_score": 0,
            "green_ratio": 0,
            "texture_regularity": 0,
            "edge_orientation": 0,
            "ndvi_like": 0  # 归一化植被指数的近似值
        }

        # 1. 绿色成分分析（关键特征！）
        # 火焰几乎没有绿色，但树木即使变红/黄仍有绿色
        b, g, r = cv2.split(roi_bgr)
        total_pixels = w * h

        # 计算绿色像素占比（在HSV中H=35-85是绿色范围）
        if hsv_roi is not None:
            h_channel = hsv_roi[:, :, 0]
            green_mask = (h_channel >= 35) & (h_channel <= 85)
            green_pixel_count = np.sum(green_mask)
            features["green_ratio"] = green_pixel_count / total_pixels if total_pixels > 0 else 0

            # NDVI-like指数：(红-绿)/(红+绿) 的变体
            # 对于植被，这个值应该为负（绿色>红色）
            s_channel = hsv_roi[:, :, 1]
            v_channel = hsv_roi[:, :, 2]

            # 使用ExG (Excess Green Index): 2*G - R - B
            mean_r = np.mean(r)
            mean_g = np.mean(g)
            mean_b = np.mean(b)

            exg = 2 * mean_g - mean_r - mean_b
            features["ndvi_like"] = exg / 255.0  # 归一化到[-1, 1]

        # 2. 纹理规律性分析
        # 树叶纹理有重复模式（叶片、枝干），火焰纹理更随机
        roi_gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)

        # 使用局部二值模式(LBP)的思想：计算局部纹理的一致性
        # 简化版：使用灰度共生矩阵的特征
        from scipy import ndimage

        # 计算梯度方向直方图（树木有更多垂直/水平边缘 - 枝干）
        sobel_x = cv2.Sobel(roi_gray, cv2.CV_64F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(roi_gray, cv2.CV_64F, 0, 1, ksize=3)

        # 边缘方向分布
        orientations = np.arctan2(sobel_y, sobel_x)
        edge_strength = np.sqrt(sobel_x**2 + sobel_y**2)

        # 只考虑强边缘
        strong_edges = edge_strength > np.mean(edge_strength)
        if np.sum(strong_edges) > 10:
            orient_hist, _ = np.histogram(orientations[strong_edges], bins=8, range=(-np.pi, np.pi))
            orient_hist = orient_hist / np.sum(orient_hist)  # 归一化

            # 计算方向集中度（树木边缘更集中在某些方向）
            features["edge_orientation"] = np.max(orient_hist)  # 最大方向的占比

        # 3. 纹理规则性（使用灰度差分统计）
        # 水平和垂直方向的像素差异
        diff_h = np.abs(roi_gray[:, 1:] - roi_gray[:, :-1]) if w > 1 else np.array([0])
        diff_v = np.abs(roi_gray[1:, :] - roi_gray[:-1, :]) if h > 1 else np.array([0])

        # 树木纹理更规则（差异分布更均匀），火焰更随机
        if len(diff_h) > 0 and len(diff_v) > 0:
            h_std = np.std(diff_h)
            v_std = np.std(diff_v)
            # 规则性：水平和垂直方向的标准差接近（树木）vs 差异大（火焰）
            texture_regularity = 1.0 - abs(h_std - v_std) / max(h_std, v_std, 1)
            features["texture_regularity"] = max(0, min(1, texture_regularity))

        # 4. 综合判断是否为植被
        veg_score = 0
        veg_indicators = 0

        # 绿色成分指标（权重最高）
        if features["green_ratio"] > 0.15:  # 超过15%的绿色像素
            veg_score += 0.35
            veg_indicators += 1
        elif features["green_ratio"] > 0.08:  # 少量绿色
            veg_score += 0.20
            veg_indicators += 1

        # ExG指数（负值表示绿色占优）
        if features["ndvi_like"] > 0.05:  # ExG为正，说明绿色通道强
            veg_score += 0.25
            veg_indicators += 1
        elif features["ndvi_like"] > -0.05:
            veg_score += 0.10

        # 边缘方向集中度（树木有明显的枝干方向）
        if features["edge_orientation"] > 0.35:  # 某个方向占比超过35%
            veg_score += 0.20
            veg_indicators += 1

        # 纹理规则性
        if features["texture_regularity"] > 0.6:
            veg_score += 0.15
            veg_indicators += 1
        elif features["texture_regularity"] > 0.4:
            veg_score += 0.08

        features["vegetation_score"] = veg_score

        # 最终判断：多个指标同时满足才认为是植被
        features["is_vegetation"] = (veg_score >= 0.50 and veg_indicators >= 2)

        return features

    def _calculate_adaptive_confidence(self, fire_pixel_ratio: float, area: int,
                                        color_info: dict, texture_info: dict,
                                        dynamics: dict, aspect_ratio: float,
                                        extent: float) -> float:
        """
        自适应置信度计算：基于多维特征的加权评分
        """
        score = 0.0
        weights_total = 0.0

        # 1. 基础分：火焰像素占比（权重0.25）
        base_score = min(fire_pixel_ratio * 2.5, 0.6)
        weight = 0.25
        score += base_score * weight
        weights_total += weight

        # 2. 颜色特征分（权重0.25）
        color_score = 0
        # 火焰典型颜色分布
        if color_info.get("is_true_fire_color", False):
            color_score = 0.9
        elif color_info.get("red_dominant", 0) > 0.65 and color_info.get("mean_sat", 0) > 70:
            color_score = 0.7
        elif color_info.get("orange_present", 0) > 0.25:
            color_score = 0.6
        else:
            color_score = 0.3

        # 颜色多样性加成（火焰有红-橙-黄渐变）
        color_diversity = (
            (1 if color_info.get("orange_present", 0) > 0.15 else 0) +
            (1 if color_info.get("yellow_tint", 0) > 0.1 else 0)
        ) / 2.0
        color_score = color_score * 0.7 + color_diversity * 0.3

        weight = 0.25
        score += color_score * weight
        weights_total += weight

        # 3. 纹理特征分（权重0.20）
        texture_score = 0
        # 纹理复杂度（火焰纹理丰富）
        if texture_info.get("texture_score", 0) > 0.4:
            texture_score += 0.4
        # 亮度变化（火焰闪烁）
        if texture_info.get("brightness_var", 0) > 45:
            texture_score += 0.35
        elif texture_info.get("brightness_var", 0) > 30:
            texture_score += 0.2
        # 边缘密度（火焰边缘模糊不规则）
        if 0.02 < texture_info.get("edge_density", 0) < 0.15:
            texture_score += 0.25  # 适中密度最好

        weight = 0.20
        score += min(texture_score, 1.0) * weight
        weights_total += weight

        # 4. 动态特征分（权重0.20）- 这是区分火焰和静态物体的关键
        dynamic_score = 0
        # 闪烁强度
        flicker = dynamics.get("flicker", 0.5)
        if flicker > 0.5:
            dynamic_score += 0.4
        elif flicker > 0.3:
            dynamic_score += 0.25
        # 运动能量
        motion = dynamics.get("motion_energy", 0)
        if motion > 0.4:
            dynamic_score += 0.35
        elif motion > 0.2:
            dynamic_score += 0.2
        # 大小变化的合理性
        size_change = dynamics.get("size_change", 0.5)
        dynamic_score += size_change * 0.25

        weight = 0.20
        score += min(dynamic_score, 1.0) * weight
        weights_total += weight

        # 5. 形状特征分（权重0.10）
        shape_score = 0
        # 宽高比（火焰通常是竖直的）
        if 0.4 < aspect_ratio < 3.0:
            shape_score += 0.5
        elif 0.2 < aspect_ratio < 5.0:
            shape_score += 0.3
        # 紧凑度（火焰形状不规则但不会太稀疏）
        if extent > 0.3:
            shape_score += 0.3
        # 面积合理性
        if 200 < area < 30000:
            shape_score += 0.2

        weight = 0.10
        score += min(shape_score, 1.0) * weight
        weights_total += weight

        # 归一化并返回最终分数
        final_score = score / weights_total if weights_total > 0 else 0.3
        return max(0.05, min(final_score, 0.98))

    def _analyze_color_distribution(self, hsv_roi: np.ndarray) -> dict:
        """分析颜色分布特征"""
        h_channel = hsv_roi[:, :, 0]
        s_channel = hsv_roi[:, :, 1]
        v_channel = hsv_roi[:, :, 2]

        mean_hue = np.mean(h_channel)
        mean_sat = np.mean(s_channel)
        mean_val = np.mean(v_channel)
        std_hue = np.std(h_channel)
        std_sat = np.std(s_channel)

        # 火焰颜色范围统计
        hue_in_fire_range = np.sum((h_channel < 25) | (h_channel > 155)) / h_channel.size
        sat_above_threshold = np.sum(s_channel > 100) / s_channel.size
        val_above_threshold = np.sum(v_channel > 150) / v_channel.size

        # 判断是否为真实火焰颜色
        is_true_fire_color = (
            ((mean_hue < 20 or mean_hue > 160) and mean_sat > 80 and mean_val > 120) or
            (hue_in_fire_range > 0.6 and sat_above_threshold > 0.5 and val_above_threshold > 0.4)
        )

        # 颜色成分分析
        red_dominant = np.sum((h_channel < 15) | (h_channel > 165)) / h_channel.size
        orange_present = np.sum((h_channel >= 10) & (h_channel <= 25)) / h_channel.size
        yellow_tint = np.sum((h_channel > 25) & (h_channel <= 40)) / h_channel.size

        return {
            "mean_hue": mean_hue,
            "mean_sat": mean_sat,
            "mean_val": mean_val,
            "std_hue": std_hue,
            "std_sat": std_sat,
            "hue_in_fire_range": hue_in_fire_range,
            "sat_above_threshold": sat_above_threshold,
            "val_above_threshold": val_above_threshold,
            "is_true_fire_color": is_true_fire_color,
            "red_dominant": red_dominant,
            "orange_present": orange_present,
            "yellow_tint": yellow_tint
        }

    def _analyze_texture_features(self, image: np.ndarray, x: int, y: int,
                                   w: int, h: int) -> dict:
        """分析纹理特征"""
        if x < 0 or y < 0 or x + w > image.shape[1] or y + h > image.shape[0]:
            return {"texture_score": 0.0, "brightness_var": 0, "edge_density": 0}

        roi = image[y:y+h, x:x+w]
        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        brightness_var = np.std(roi_gray)

        # 边缘检测（火焰边缘模糊不规则）
        edges = cv2.Canny(roi_gray, 50, 150)
        edge_density = np.sum(edges > 0) / (w * h) if (w * h) > 0 else 0

        # 纹理复杂度（拉普拉斯方差）
        laplacian_var = cv2.Laplacian(roi_gray, cv2.CV_64F).var()
        texture_score = min(laplacian_var / 500.0, 1.0)

        return {
            "texture_score": texture_score,
            "brightness_var": brightness_var,
            "edge_density": edge_density,
            "laplacian_var": laplacian_var
        }

    def detect_fire_color(self, image: np.ndarray) -> Tuple[np.ndarray, List[DetectionResult]]:
        """
        极简火焰检测 v2.0
        核心策略：严格的颜色 + 强制动态检测
        """
        self._frame_count += 1

        # 准备帧间比较
        current_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        if self._prev_frame_gray is None:
            self._prev_frame_gray = current_gray.copy()

        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # ===== 关键改进：更严格的火焰颜色范围 =====
        # 原来的范围太宽，导致树木、建筑都被包含进来
        lower_fire1 = np.array([0, 120, 150])  # 高饱和度、高亮度
        upper_fire1 = np.array([15, 255, 255])
        lower_fire2 = np.array([165, 140, 160])  # 深红也要严格
        upper_fire2 = np.array([180, 255, 255])
        lower_fire3 = np.array([15, 100, 180])  # 黄色必须很亮
        upper_fire3 = np.array([28, 220, 255])

        mask1 = cv2.inRange(hsv, lower_fire1, upper_fire1)
        mask2 = cv2.inRange(hsv, lower_fire2, upper_fire2)
        mask3 = cv2.inRange(hsv, lower_fire3, upper_fire3)

        fire_mask = cv2.bitwise_or(mask1, mask2)
        fire_mask = cv2.bitwise_or(fire_mask, mask3)

        # 形态学去噪
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        fire_mask = cv2.morphologyEx(fire_mask, cv2.MORPH_OPEN, kernel)
        fire_mask = cv2.morphologyEx(fire_mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(fire_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        fire_detections = []

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 200:  # 提高最小面积
                continue

            x, y, w, h = cv2.boundingRect(contour)

            # 形状约束
            aspect_ratio = float(w) / h if h > 0 else 0
            if not (0.3 < aspect_ratio < 4.0):  # 收紧范围
                continue

            extent = area / (w * h) if (w * h) > 0 else 0
            if extent < 0.20:  # 提高紧凑度要求
                continue

            # 火焰像素占比
            if y+h <= fire_mask.shape[0] and x+w <= fire_mask.shape[1]:
                region_mask = fire_mask[y:y+h, x:x+w]
                fire_ratio = np.sum(region_mask > 0) / (w * h) if (w * h) > 0 else 0
            else:
                continue

            if fire_ratio < 0.30:  # 提高像素占比要求
                continue

            # ===== 核心改进：强制动态检测 =====
            is_static = False
            motion_score = 0.5
            flicker_score = 0.5

            if x >= 0 and y >= 0 and x+w <= image.shape[1] and y+h <= image.shape[0]:
                roi_gray = current_gray[y:y+h, x:x+w]

                # 闪烁检测
                flicker_score = min(np.std(roi_gray) / 50.0, 1.0)

                # 运动检测
                if self._prev_frame_gray is not None:
                    if y+h <= self._prev_frame_gray.shape[0] and x+w <= self._prev_frame_gray.shape[1]:
                        prev_roi = self._prev_frame_gray[y:y+h, x:x+w]
                        if prev_roi.shape == roi_gray.shape:
                            diff = cv2.absdiff(roi_gray, prev_roi)
                            motion_score = min(np.mean(diff) / 25.0, 1.0)

                # 判定是否为静态物体
                if motion_score < 0.15 and flicker_score < 0.35:
                    is_static = True

            # 静态物体直接排除！
            if is_static:
                continue

            # 计算置信度（简单加权）
            confidence = min(fire_ratio * 1.2, 0.40) + motion_score * 0.30 + flicker_score * 0.20

            # 形状加成
            if 0.5 < aspect_ratio < 2.5:
                confidence += 0.08
            if extent > 0.35:
                confidence += 0.05

            confidence = max(0.05, min(confidence, 0.98))

            if confidence < 0.45:  # 提高置信度门槛
                continue

            det = DetectionResult(
                class_id=0, class_name="fire",
                confidence=float(confidence),
                bbox=(x, y, x + w, y + h),
                detection_type="fire"
            )
            fire_detections.append(det)

        # 更新状态
        self._prev_frame_gray = current_gray.copy()

        self._fire_history.append({
            "detection_count": len(fire_detections),
            "timestamp": datetime.now()
        })
        if len(self._fire_history) > self._max_history:
            self._fire_history = self._fire_history[-self._max_history:]

        return fire_mask, fire_detections

    def detect_smoke_color(self, image: np.ndarray) -> List[DetectionResult]:
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        lower_smoke1 = np.array([0, 0, 100])
        upper_smoke1 = np.array([180, 50, 240])
        lower_smoke2 = np.array([0, 0, 150])
        upper_smoke2 = np.array([180, 30, 220])
        smoke_mask1 = cv2.inRange(hsv, lower_smoke1, upper_smoke1)
        smoke_mask2 = cv2.inRange(hsv, lower_smoke2, upper_smoke2)
        smoke_mask = cv2.bitwise_or(smoke_mask1, smoke_mask2)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l_channel = lab[:, :, 0]
        _, bright_mask = cv2.threshold(l_channel, 140, 255, cv2.THRESH_BINARY)
        local_contrast = cv2.absdiff(cv2.GaussianBlur(gray, (21, 21), 0),
                                      cv2.GaussianBlur(gray, (101, 101), 0))
        _, low_contrast_mask = cv2.threshold(local_contrast, 15, 255, cv2.THRESH_BINARY_INV)
        potential_smoke = cv2.bitwise_and(smoke_mask, bright_mask)
        potential_smoke = cv2.bitwise_and(potential_smoke, low_contrast_mask)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        potential_smoke = cv2.morphologyEx(potential_smoke, cv2.MORPH_CLOSE, kernel)
        potential_smoke = cv2.morphologyEx(potential_smoke, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(potential_smoke, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        smoke_detections = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 800:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = float(w) / h if h > 0 else 0
            if not (0.3 < aspect_ratio < 10.0):
                continue
            if w < 40 or h < 25:
                continue
            roi_gray = gray[y:y+h, x:x+w] if y+h <= gray.shape[0] and x+w <= gray.shape[1] else None
            if roi_gray is not None:
                std_dev = np.std(roi_gray)
                mean_intensity = np.mean(roi_gray)
                roi_hsv = hsv[y:y+h, x:x+w] if y+h <= hsv.shape[0] and x+w <= hsv.shape[1] else None
                saturation_check = True
                if roi_hsv is not None:
                    mean_sat = np.mean(roi_hsv[:, :, 1])
                    saturation_check = mean_sat < 60
                contrast_local = np.std(local_contrast[y:y+h, x:x+w]) if (y+h <= local_contrast.shape[0] and x+w <= local_contrast.shape[1]) else 100
                is_low_contrast = contrast_local < 25
                is_bright = mean_intensity > 120
                base_confidence = min(std_dev / 50.0 + 0.3, 0.7)
                confidence = base_confidence
                if saturation_check:
                    confidence += 0.08
                if is_low_contrast:
                    confidence += 0.1
                if is_bright:
                    confidence += 0.07
                if area > 2000:
                    confidence += 0.05
                if aspect_ratio > 1.5:
                    confidence += 0.03
                confidence = max(0.15, min(confidence, 0.95))
            else:
                confidence = 0.35
            det = DetectionResult(
                class_id=1, class_name="smoke",
                confidence=float(confidence), bbox=(x, y, x + w, y + h),
                detection_type="smoke"
            )
            smoke_detections.append(det)
        return smoke_detections

    def detect_motion_anomaly(self, prev_image: np.ndarray, curr_image: np.ndarray) -> List[DetectionResult]:
        if prev_image is None or curr_image is None:
            return []
        prev_gray = cv2.cvtColor(prev_image, cv2.COLOR_BGR2GRAY)
        curr_gray = cv2.cvtColor(curr_image, cv2.COLOR_BGR2GRAY)
        diff = cv2.absdiff(prev_gray, curr_gray)
        _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (10, 10))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        anomalies = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 1000:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            if y+h <= curr_image.shape[0] and x+w <= curr_image.shape[1]:
                roi_hsv = cv2.cvtColor(curr_image[y:y+h, x:x+w], cv2.COLOR_BGR2HSV)
                mean_hue = np.mean(roi_hsv[:, :, 0])
                mean_sat = np.mean(roi_hsv[:, :, 1])
                is_fire_like = (mean_hue < 25 or mean_hue > 155) and mean_sat > 40
                if is_fire_like or area > 5000:
                    det = DetectionResult(
                        class_id=0, class_name="fire_motion",
                        confidence=min(area / 10000.0, 0.9), bbox=(x, y, x + w, y + h),
                        detection_type="fire_anomaly"
                    )
                    anomalies.append(det)
        return anomalies

    def _multi_frame_validation(self, current_detections: List[DetectionResult]) -> List[DetectionResult]:
        """改进的多帧验证：结合时空一致性和误检记忆（优化版：更灵敏）"""
        # 将当前帧检测结果加入缓冲区
        self._detection_buffer.append(current_detections)
        if len(self._detection_buffer) > self._buffer_size:
            self._detection_buffer.pop(0)

        # 如果缓冲区未满，返回当前检测结果
        if len(self._detection_buffer) < self._buffer_size:
            return [det for det in current_detections]

        validated_detections = []
        for det in current_detections:
            center_x = (det.bbox[0] + det.bbox[2]) / 2
            center_y = (det.bbox[1] + det.bbox[3]) / 2
            region_key = self._compute_region_hash(center_x, center_y)

            # 检查是否在误检记忆中（该位置多次被判定为误检）
            if region_key in self._false_positive_memory:
                fp_count, last_seen = self._false_positive_memory[region_key]
                time_since_last = (datetime.now() - last_seen).total_seconds()
                # 如果在8秒内被判定为误检超过2次，且当前置信度不高，则过滤
                if fp_count >= 2 and time_since_last < 8.0 and det.confidence < 0.60:  # 提高阈值
                    continue

            # 统计在历史帧中的匹配情况（降低IOU阈值使匹配更容易）
            match_count = 0
            max_confidence = det.confidence

            for hist_dets in self._detection_buffer[:-1]:
                for hist_det in hist_dets:
                    iou = IllegalBuildDetector._calculate_iou(det.bbox, hist_det.bbox)
                    if iou > 0.10 and det.class_name == hist_det.class_name:  # 进一步降低IOU阈值
                        match_count += 1
                        max_confidence = max(max_confidence, hist_det.confidence)
                        break

            # 根据匹配情况调整置信度（更宽松的输出策略）
            if match_count >= 2:  # 在多数帧中出现 → 高置信度
                det.confidence = min(max_confidence * 1.08, 0.98)
                validated_detections.append(det)
            elif match_count >= 1:  # 在部分帧出现 → 正常输出
                det.confidence = max(det.confidence * 0.97, 0.38)  # 保证最低置信度并提高
                validated_detections.append(det)
            else:
                # 首次出现：根据置信度决定是否保留（降低门槛）
                if det.confidence > 0.50:  # 高置信度首次检测也保留
                    validated_detections.append(det)
                elif det.confidence > 0.38:  # 中等置信度，标记为观察中（降低门槛）
                    det.detection_type = f"{det.detection_type}_observing"
                    det.confidence *= 0.95  # 轻微降权
                    validated_detections.append(det)
                # 只有低置信度且无历史匹配才完全过滤

        return validated_detections

    def detect(self, image: np.ndarray, prev_image: np.ndarray = None) -> List[DetectionResult]:
        """极简版：只返回火情检测结果（已包含动态过滤）"""
        _, fire_dets = self.detect_fire_color(image)
        return sorted(fire_dets, key=lambda x: x.confidence, reverse=True)


class DualDetectionEngine:

    def __init__(self):
        print("[引擎] 正在初始化火情检测引擎...")
        self.fire_detector = FireDetector()
        self.prev_frame = None
        self.detection_history = []
        self.alert_cooldown = {}
        self.cooldown_seconds = 3  # 缩短冷却时间，更快响应
        print("[引擎] 火情检测引擎初始化完成")

    def detect(self, frame: np.ndarray) -> dict:
        """简化版：只进行火情检测"""
        timestamp = datetime.now()
        result = {
            "timestamp": timestamp,
            "fires": [],
            "smokes": [],
            "has_alert": False,
            "alert_types": []
        }

        # 只执行火情检测
        fire_dets = self.fire_detector.detect(frame, self.prev_frame)
        result["fires"] = fire_dets

        # 警报冷却过滤（避免重复报警）
        filtered_alerts = []
        for alert in fire_dets:
            alert_key = f"fire_{int(alert.bbox[0]/50)}_{int(alert.bbox[1]/50)}"
            last_time = self.alert_cooldown.get(alert_key)
            if last_time is None or (timestamp - last_time).total_seconds() > self.cooldown_seconds:
                self.alert_cooldown[alert_key] = timestamp
                filtered_alerts.append(alert)

        result["has_alert"] = len(filtered_alerts) > 0
        result["alerts"] = filtered_alerts

        if result["has_alert"]:
            result["alert_types"] = ["fire"]

        self.prev_frame = frame.copy()
        self.detection_history.append(result)

        if len(self.detection_history) > 100:
            self.detection_history = self.detection_history[-100:]

        return result


# ==================== 图像处理部分 ====================
COLOR_FIRE = (0, 0, 255)
COLOR_SMOKE = (128, 128, 128)
COLOR_BUILDING = (0, 255, 255)
_COLOR_ALERT = (0, 0, 255)
_COLOR_NORMAL = (0, 255, 0)

LABEL_FIRE = "[FIRE]"
_LABEL_FIRE_HIGH = "[FIRE!!]"
_LABEL_SMOKE = "[SMOKE]"
_LABEL_BUILDING = "[BUILD]"
_LABEL_NEW_BUILD = "[NEW!]"
_LABEL_ALERT = "[ALERT]"
_LABEL_OK = "[OK]"


def draw_detections(frame: np.ndarray, detection_result: dict) -> np.ndarray:
    vis_frame = frame.copy()
    h, w = frame.shape[:2]
    fire_count = len(detection_result.get("fires", []))
    smoke_count = len(detection_result.get("smokes", []))
    build_count = len(detection_result.get("illegal_builds", []))
    alert_status = _LABEL_ALERT if detection_result.get("has_alert") else _LABEL_OK
    status_color = _COLOR_ALERT if detection_result.get("has_alert") else _COLOR_NORMAL
    overlay = vis_frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 50), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, vis_frame, 0.4, 0, vis_frame)
    title_text = f"Drone Monitor {alert_status}"
    cv2.putText(vis_frame, title_text, (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
    stats_text = f"Build:{build_count}  Fire:{fire_count}  Smoke:{smoke_count}"
    text_w = int(len(stats_text) * 11)
    cv2.putText(vis_frame, stats_text, (w - text_w - 20, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
    timestamp_str = detection_result["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
    ts_w = int(len(timestamp_str) * 11)
    cv2.putText(vis_frame, timestamp_str, (w - ts_w - 10, h - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
    for det in detection_result.get("illegal_builds", []):
        x1, y1, x2, y2 = det.bbox
        color = COLOR_BUILDING
        label = f"{_LABEL_BUILDING} {det.class_name}"
        if det.detection_type == "new_illegal_build":
            label = f"{_LABEL_NEW_BUILD} {det.class_name}"
            color = (0, 165, 255)
        cv2.rectangle(vis_frame, (x1, y1), (x2, y2), color, 2)
        conf_text = f"{label} {det.confidence:.1%}"
        (tw, th), _ = cv2.getTextSize(conf_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(vis_frame, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)
        cv2.putText(vis_frame, conf_text, (x1 + 2, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    for det in detection_result.get("fires", []) + [d for d in detection_result.get("anomalies", []) if d.class_name == "fire_motion"]:
        x1, y1, x2, y2 = det.bbox
        color = COLOR_FIRE
        label = LABEL_FIRE
        if det.confidence > 0.75:
            label = _LABEL_FIRE_HIGH
            color = (0, 0, 220)
        cv2.rectangle(vis_frame, (x1, y1), (x2, y2), color, 3)
        conf_text = f"{label} {det.confidence:.1%}"
        (tw, th), _ = cv2.getTextSize(conf_text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        cv2.rectangle(vis_frame, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)
        cv2.putText(vis_frame, conf_text, (x1 + 2, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
    for det in detection_result.get("smokes", []):
        x1, y1, x2, y2 = det.bbox
        color = COLOR_SMOKE
        cv2.rectangle(vis_frame, (x1, y1), (x2, y2), color, 2)
        label = f"{_LABEL_SMOKE} {det.confidence:.1%}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(vis_frame, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)
        cv2.putText(vis_frame, label, (x1 + 2, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    return vis_frame


class ImageProcessor:

    def __init__(self, engine: DualDetectionEngine):
        self.engine = engine

    def process_image(self, image_path: str, save_path: str = None) -> Tuple[np.ndarray, dict]:
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"[错误] 无法读取图像: {image_path}")
        image = cv2.resize(image, (DISPLAY_WIDTH, DISPLAY_HEIGHT))
        result = self.engine.detect(image)
        vis_frame = draw_detections(image, result)
        if save_path and AUTO_SAVE_ALERT_IMAGE and result.get("has_alert"):
            cv2.imwrite(save_path, vis_frame)
        return vis_frame, result

    def process_image_array(self, image: np.ndarray) -> Tuple[np.ndarray, dict]:
        if image is None or image.size == 0:
            raise ValueError("[错误] 无效的图像输入")
        if len(image.shape) == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        image = cv2.resize(image, (DISPLAY_WIDTH, DISPLAY_HEIGHT))
        result = self.engine.detect(image)
        vis_frame = draw_detections(image, result)
        return vis_frame, result


class VideoProcessor:

    def __init__(self, engine: DualDetectionEngine):
        self.engine = engine
        self._running = False
        # 性能优化参数：平衡速度和准确性
        self._detect_interval = 2  # 每2帧检测一次（更频繁但更准确）
        self._detect_resolution = (640, 480)  # 提高检测分辨率（更好的准确性）
        self._display_resolution = (DISPLAY_WIDTH, DISPLAY_HEIGHT)  # 显示分辨率
        self._frame_count = 0
        self._last_result = None  # 缓存上一次检测结果

    def process_video_file(
        self,
        video_path: str,
        output_path: str = None,
        callback=None,
        show_display: bool = True
    ) -> List[dict]:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"[错误] 无法打开视频文件: {video_path}\n请确认文件路径正确且格式受支持")
        writer = None
        if output_path:
            fps = cap.get(cv2.CAP_PROP_FPS) or VIDEO_FPS
            vw = DISPLAY_WIDTH
            vh = DISPLAY_HEIGHT
            fourcc = cv2.VideoWriter_fourcc(*'avc1')
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            writer = cv2.VideoWriter(output_path, fourcc, fps, (vw, vh))
            if not writer.isOpened():
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                writer = cv2.VideoWriter(output_path, fourcc, fps, (vw, vh))
            if not writer.isOpened():
                print(f"[警告] 无法创建输出视频: {output_path}, 将仅做检测不保存")
                writer = None
        all_results = []
        frame_idx = 0
        self._running = True
        self._frame_count = 0
        self._last_result = None
        try:
            while self._running:
                ret, frame = cap.read()
                if not ret:
                    break

                # 性能优化：跳帧检测
                self._frame_count += 1
                should_detect = (self._frame_count % self._detect_interval == 0) or (self._last_result is None)

                if should_detect:
                    # 在低分辨率下进行检测（提升速度）
                    detect_frame = cv2.resize(frame, self._detect_resolution)
                    result = self.engine.detect(detect_frame)
                    # 将检测结果坐标映射回显示分辨率
                    scale_x = self._display_resolution[0] / self._detect_resolution[0]
                    scale_y = self._display_resolution[1] / self._detect_resolution[1]
                    for key in ['fires', 'smokes', 'illegal_builds', 'anomalies']:
                        for det in result.get(key, []):
                            det.bbox = (
                                int(det.bbox[0] * scale_x),
                                int(det.bbox[1] * scale_y),
                                int(det.bbox[2] * scale_x),
                                int(det.bbox[3] * scale_y)
                            )
                    self._last_result = result
                else:
                    # 复用上一次的检测结果
                    result = self._last_result if self._last_result else {"timestamp": datetime.now(), "fires": [], "smokes": [], "illegal_builds": [], "anomalies": [], "has_alert": False, "alert_types": []}

                # 显示时使用原始分辨率的帧
                display_frame = cv2.resize(frame, self._display_resolution)
                vis_frame = draw_detections(display_frame, result)
                all_results.append(result)
                if writer is not None:
                    writer.write(vis_frame)
                if callback is not None:
                    try:
                        callback(vis_frame, result)
                    except Exception:
                        pass
                if show_display:
                    cv2.imshow("[检测中] Drone Inspection Monitor", vis_frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q'):
                        break
                    elif key == ord(' '):
                        cv2.waitKey(0)
                frame_idx += 1
        finally:
            cap.release()
            if writer is not None:
                writer.release()
            cv2.destroyAllWindows()
        return all_results

    def process_camera(
        self,
        camera_id: int = 0,
        callback=None,
        show_display: bool = True
    ) -> Generator[Tuple[np.ndarray, dict], None, None]:
        cap = cv2.VideoCapture(camera_id)
        if not cap.isOpened():
            raise ValueError(f"[错误] 无法打开摄像头: {camera_id}")
        self._running = True
        self._frame_count = 0
        self._last_result = None
        try:
            while self._running:
                ret, frame = cap.read()
                if not ret:
                    break

                # 性能优化：跳帧检测
                self._frame_count += 1
                should_detect = (self._frame_count % self._detect_interval == 0) or (self._last_result is None)

                if should_detect:
                    # 在低分辨率下进行检测（提升速度）
                    detect_frame = cv2.resize(frame, self._detect_resolution)
                    result = self.engine.detect(detect_frame)
                    # 将检测结果坐标映射回显示分辨率
                    scale_x = self._display_resolution[0] / self._detect_resolution[0]
                    scale_y = self._display_resolution[1] / self._detect_resolution[1]
                    for key in ['fires', 'smokes', 'illegal_builds', 'anomalies']:
                        for det in result.get(key, []):
                            det.bbox = (
                                int(det.bbox[0] * scale_x),
                                int(det.bbox[1] * scale_y),
                                int(det.bbox[2] * scale_x),
                                int(det.bbox[3] * scale_y)
                            )
                    self._last_result = result
                else:
                    # 复用上一次的检测结果
                    result = self._last_result if self._last_result else {"timestamp": datetime.now(), "fires": [], "smokes": [], "illegal_builds": [], "anomalies": [], "has_alert": False, "alert_types": []}

                # 显示时使用原始分辨率的帧
                display_frame = cv2.resize(frame, self._display_resolution)
                vis_frame = draw_detections(display_frame, result)
                if callback is not None:
                    try:
                        callback(vis_frame, result)
                    except Exception:
                        pass
                yield vis_frame, result
                if show_display:
                    cv2.imshow("[实时检测] Drone Live Monitor", vis_frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q'):
                        break
        finally:
            cap.release()
            cv2.destroyAllWindows()

    def stop(self):
        self._running = False


# ==================== 数据库和警报管理部分 ====================
import json
import sqlite3
from dataclasses import asdict
import threading


class DatabaseManager:

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
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

    def save_inspection(self, result: dict, source_type: str = "image",
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
            REPORT_DIR,
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
            REPORT_DIR,
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
        result: dict,
        frame=None,
        source_type: str = "realtime",
        source_path: str = None
    ) -> List[Dict]:
        if not result.get("has_alert"):
            return []
        new_alerts = []
        image_path = None
        if frame is not None and AUTO_SAVE_ALERT_IMAGE:
            filename = f"alert_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
            image_path = os.path.join(ALERT_DIR, filename)
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


# ==================== GUI界面部分 ====================
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont
from typing import Optional, Callable, Generator


class ModuleCard(tk.Frame):

    def __init__(self, parent, title: str, icon: str, color: str,
                 value_text: str = "0", detail_text: str = "",
                 on_click=None, **kw):
        super().__init__(parent, **kw)
        self.on_click = on_click
        self.title = title
        self.icon = icon
        self.color = color
        self.selected = False
        self.configure(bg="#1e293b", cursor="hand2")
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self._build_ui(title, icon, color, value_text, detail_text)

    def _build_ui(self, title, icon, color, value_text, detail_text):
        self.inner = tk.Frame(self, bg="#0f172a")
        self.inner.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.header_frame = tk.Frame(self.inner, bg="#0f172a")
        self.header_frame.pack(fill=tk.X, padx=10, pady=(8, 2))
        self.icon_label = tk.Label(
            self.header_frame, text=icon,
            font=("Segoe UI Emoji", 14), bg="#0f172a", fg=color
        )
        self.icon_label.pack(side=tk.LEFT)
        self.title_label = tk.Label(
            self.header_frame, text=title,
            font=("Microsoft YaHei UI", 11, "bold"), bg="#0f172a", fg="#e2e8f0"
        )
        self.title_label.pack(side=tk.LEFT, padx=(6, 0))
        self.value_label = tk.Label(
            self.inner, text=value_text,
            font=("Microsoft YaHei UI", 24, "bold"),
            bg="#0f172a", fg="#ffffff"
        )
        self.value_label.pack(anchor=tk.W, padx=10)
        self.detail_label = tk.Label(
            self.inner, text=detail_text,
            font=("Microsoft YaHei UI", 9),
            bg="#0f172a", fg="#94a3b8"
        )
        self.detail_label.pack(anchor=tk.W, padx=10, pady=(0, 8))

    def update_value(self, value_text: str, detail_text: str = ""):
        self.value_label.config(text=value_text)
        if detail_text:
            self.detail_label.config(text=detail_text)

    def set_selected(self, selected: bool):
        self.selected = selected
        if selected:
            self.configure(bg=self.color)
        else:
            self.configure(bg="#1e293b")

    def _on_enter(self, e):
        if not self.selected:
            self.configure(bg="#334155")

    def _on_leave(self, e):
        if not self.selected:
            self.configure(bg="#1e293b")

    def _on_click(self, e):
        if self.on_click:
            self.on_click(self)


class DetailPanel(ttk.Frame):

    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self.configure(style="Detail.TFrame")
        self._build()

    def _build(self):
        self.title_bar = tk.Frame(self, bg="#1e40af")
        self.title_bar.pack(fill=tk.X)
        self.detail_title = tk.Label(
            self.title_bar, text="详细信息",
            font=("Microsoft YaHei UI", 11, "bold"),
            bg="#1e40af", fg="white"
        )
        self.detail_title.pack(side=tk.LEFT, padx=10, pady=5)
        self.close_btn = tk.Label(
            self.title_bar, text=" ✕ ",
            font=("Microsoft YaHei UI", 12, "bold"),
            bg="#1e40af", fg="white", cursor="hand2"
        )
        self.close_btn.pack(side=tk.RIGHT, padx=5, pady=5)
        self.content = tk.Text(
            self, font=("Microsoft YaHei UI", 10),
            bg="#0f172a", fg="#e2e8f0",
            relief=tk.FLAT, padx=10, pady=10,
            wrap=tk.WORD, state=tk.DISABLED,
            height=20
        )
        self.content.pack(fill=tk.BOTH, expand=True)

    def show_content(self, title: str, content: str, on_close=None):
        self.detail_title.config(text=title)
        self.content.config(state=tk.NORMAL)
        self.content.delete(1.0, tk.END)
        self.content.insert(1.0, content)
        self.content.config(state=tk.DISABLED)
        if on_close:
            self.close_btn.unbind("<Button-1>")
            self.close_btn.bind("<Button-1>", lambda e: on_close())


class DroneMonitorGUI:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("乡村无人机自动巡检系统 - 智能监测平台")
        self.root.geometry("1450x920")
        self.root.configure(bg="#0f172a")
        self.engine = DualDetectionEngine()
        self.img_processor = ImageProcessor(self.engine)
        self.video_processor = VideoProcessor(self.engine)
        self.alert_manager = AlertManager(DatabaseManager())
        self.alert_manager.register_callback(self._on_new_alert)
        self._running = False
        self._video_thread: Optional[threading.Thread] = None
        self._camera_thread: Optional[threading.Thread] = None
        self._current_mode = "idle"
        self.current_image_tk: Optional[ImageTk.PhotoImage] = None
        self.alert_log_data = []
        self.module_cards = {}
        self.current_module = None
        # GUI性能优化：限制显示更新频率
        self._last_display_time = 0
        self._display_interval = 0.033  # 33ms更新一次（约30FPS，更流畅）
        self._setup_ui()
        self._update_stats()

    def _setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        self._build_header()
        self._build_main_area()
        self._build_control_panel()
        self._build_status_bar()

    def _build_header(self):
        header = tk.Frame(self.root, bg="#1e293b", height=65)
        header.pack(fill=tk.X, padx=0, pady=0)
        header.pack_propagate(False)
        left_group = tk.Frame(header, bg="#1e293b")
        left_group.pack(side=tk.LEFT, padx=20, pady=8)
        title_label = tk.Label(
            left_group, text="🚁 乡村无人机自动巡检系统",
            font=("Microsoft YaHei UI", 18, "bold"),
            fg="#38bdf8", bg="#1e293b"
        )
        title_label.pack(anchor=tk.W)
        subtitle = tk.Label(
            left_group, text="违建与火情智能监测平台  |  YOLOv8 + PyTorch 深度学习引擎",
            font=("Microsoft YaHei UI", 9), fg="#94a3b8", bg="#1e293b"
        )
        subtitle.pack(anchor=tk.W)
        status_indicator = tk.Label(
            header, text="● 系统就绪",
            font=("Microsoft YaHei UI", 11, "bold"),
            fg="#22c55e", bg="#1e293b"
        )
        status_indicator.pack(side=tk.RIGHT, padx=25, pady=18)
        self.status_indicator = status_indicator

    def _build_main_area(self):
        main_frame = tk.Frame(self.root, bg="#0f172a")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        left_panel = tk.Frame(main_frame, bg="#1e293b", relief=tk.RIDGE, bd=2)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        video_title = tk.Label(
            left_panel, text="📹 实时监控画面",
            font=("Microsoft YaHei UI", 12, "bold"), fg="#38bdf8", bg="#1e293b"
        )
        video_title.pack(anchor=tk.W, padx=10, pady=(6, 3))
        self.video_label = tk.Label(left_panel, bg="#020617",
                                    text="⏳  等待输入源...\n\n点击下方按钮开始检测\n支持图片 / 视频 / 摄像头",
                                    font=("Microsoft YaHei UI", 13), fg="#64748b", justify=tk.CENTER)
        self.video_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        right_container = tk.Frame(main_frame, bg="#0f172a", width=400)
        right_container.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        right_container.pack_propagate(False)
        self._build_module_grid(right_container)
        sep = tk.Frame(right_container, bg="#334155", height=1)
        sep.pack(fill=tk.X, padx=8, pady=8)
        self._build_log_section(right_container)

    def _build_module_grid(self, parent):
        grid_frame = tk.Frame(parent, bg="#0f172a")
        grid_frame.pack(fill=tk.X, padx=5, pady=(5, 0))
        grid_title = tk.Label(
            grid_frame, text="📊 监测模块",
            font=("Microsoft YaHei UI", 11, "bold"), fg="#38bdf8", bg="#0f172a"
        )
        grid_title.pack(anchor=tk.W, padx=5, pady=(0, 6))
        cards_frame = tk.Frame(grid_frame, bg="#0f172a")
        cards_frame.pack(fill=tk.X)
        modules = [
            ("fire", "🔥 火情监测", "#ef4444", "0", "实时火焰智能检测"),
            ("camera", "📹 摄像头监测", "#10b981", "0", "无人机/摄像头实时流"),
        ]
        for key, title, color, val, detail in modules:
            card = ModuleCard(
                cards_frame, title=title, icon=title.split()[0],
                color=color, value_text=val, detail_text=detail,
                on_click=lambda c, k=key: self._on_module_click(k, c),
                width=24, height=75
            )
            card.pack(fill=tk.X, pady=3)
            self.module_cards[key] = card

    def _build_log_section(self, parent):
        log_frame = tk.Frame(parent, bg="#0f172a")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        log_title = tk.Label(
            log_frame, text="🔔 预警日志（最近30条）",
            font=("Microsoft YaHei UI", 11, "bold"), fg="#38bdf8", bg="#0f172a"
        )
        log_title.pack(anchor=tk.W, padx=5, pady=(4, 4))
        log_container = tk.Frame(log_frame, bg="#0f172a")
        log_container.pack(fill=tk.BOTH, expand=True)
        scrollbar = tk.Scrollbar(log_container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.alert_listbox = tk.Listbox(
            log_container, yscrollcommand=scrollbar.set,
            font=("Microsoft YaHei UI", 9), bg="#0f172a", fg="#e2e8f0",
            selectbackground="#3b82f6", selectforeground="white",
            height=12, relief=tk.FLAT, bd=0
        )
        self.alert_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.alert_listbox.yview)

    def _build_control_panel(self):
        control_frame = tk.Frame(self.root, bg="#1e293b", height=80)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        control_frame.pack_propagate(False)
        btn_left = tk.Frame(control_frame, bg="#1e293b")
        btn_left.pack(side=tk.LEFT, padx=15, pady=12)
        buttons = [
            ("🖼️ 打开图片", self._open_image, "#3b82f6"),
            ("🎬 打开视频", self._open_video, "#8b5cf6"),
            ("📷 启动摄像头", self._toggle_camera, "#10b981"),
        ]
        for text, cmd, color in buttons:
            btn = tk.Button(btn_left, text=text, command=cmd,
                            font=("Microsoft YaHei UI", 10, "bold"),
                            bg=color, fg="white", activebackground=color,
                            width=14, height=2, cursor="hand2",
                            relief=tk.FLAT, bd=0)
            btn.pack(side=tk.LEFT, padx=4)
            if text == "🖼️ 打开图片":
                self.btn_open_img = btn
            elif text == "🎬 打开视频":
                self.btn_open_video = btn
            elif text == "📷 启动摄像头":
                self.btn_camera = btn
        btn_right = tk.Frame(control_frame, bg="#1e293b")
        btn_right.pack(side=tk.RIGHT, padx=15, pady=12)
        self.btn_stop = tk.Button(
            btn_right, text="⏹ 停止检测", command=self._stop_detection,
            font=("Microsoft YaHei UI", 10, "bold"), bg="#ef4444", fg="white",
            activebackground="#dc2626", width=13, height=2, cursor="hand2",
            relief=tk.FLAT, bd=0, state=tk.DISABLED
        )
        self.btn_stop.pack(side=tk.LEFT, padx=4)
        self.btn_report = tk.Button(
            btn_right, text="📋 导出报告", command=self._export_report,
            font=("Microsoft YaHei UI", 10, "bold"), bg="#f59e0b", fg="white",
            activebackground="#d97706", width=13, height=2, cursor="hand2",
            relief=tk.FLAT, bd=0
        )
        self.btn_report.pack(side=tk.LEFT, padx=4)

    def _build_status_bar(self):
        status_bar = tk.Frame(self.root, bg="#020617", height=30)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_var = tk.StringVar(value="✅ 系统就绪  |  等待操作...")
        status_label = tk.Label(
            status_bar, textvariable=self.status_var,
            font=("Microsoft YaHei UI", 9), fg="#94a3b8", bg="#020617", anchor=tk.W
        )
        status_label.pack(side=tk.LEFT, padx=12, pady=5)
        time_label = tk.Label(
            status_bar, text="", font=("Microsoft YaHei UI", 9),
            fg="#64748b", bg="#020617", anchor=tk.E
        )
        time_label.pack(side=tk.RIGHT, padx=12, pady=5)
        self._update_clock(time_label)

    def _update_clock(self, label):
        label.config(text=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.root.after(1000, lambda: self._update_clock(label))

    def _on_module_click(self, module_key: str, card: ModuleCard):
        for k, c in self.module_cards.items():
            c.set_selected(k == module_key)
        self.current_module = module_key
        self._show_module_detail(module_key)

    def _show_module_detail(self, key: str):
        summary = self.alert_manager.get_alert_summary()
        db_full = summary.get("db_full", {})
        if key == "fire":
            fire_count = summary.get("fire_count", 0)
            recent_fire = [a for a in self.alert_manager.get_recent_alerts(30) if "fire" in a.get("type", "")]
            content = f"═══ 🔥 火情监测详情 ═══\n\n"
            content += f"▸ 本轮检测火情警报数：{fire_count}\n"
            content += f"▸ 数据库累计火情警报：{db_full.get('fire_total', 0)}\n"
            content += f"▸ 高严重度警报：{db_full.get('high_severity_count', 0)}\n\n"
            content += f"─── 最近火情记录 ───\n"
            if recent_fire:
                for i, a in enumerate(recent_fire[:10], 1):
                    content += f"\n{i}. [{a['timestamp']}] {a.get('label','')}\n   置信度: {a.get('confidence',0):.1%} | 严重度: {a.get('severity','')}"
            else:
                content += "\n  暂无火情警报记录"
            messagebox.showinfo("🔥 火情监测详情", content)
        elif key == "smoke":
            smoke_count = summary.get("smoke_count", 0)
            recent_smoke = [a for a in self.alert_manager.get_recent_alerts(30) if a.get("type") == "smoke"]
            content = f"═══ 💨 烟雾监测详情 ═══\n\n"
            content += f"▸ 本轮检测烟雾警报数：{smoke_count}\n"
            content += f"▸ 数据库累计烟雾警报：{db_full.get('smoke_total', 0)}\n\n"
            content += f"─── 最近烟雾记录 ───\n"
            if recent_smoke:
                for i, a in enumerate(recent_smoke[:10], 1):
                    content += f"\n{i}. [{a['timestamp']}] {a.get('label','')}\n   置信度: {a.get('confidence',0):.1%} | 严重度: {a.get('severity','')}"
            else:
                content += "\n  暂无烟雾警报记录"
            messagebox.showinfo("💨 烟雾监测详情", content)
        elif key == "camera":
            # 摄像头/无人机监测模块（空壳功能）
            content = f"═══ 📹 摄像头监测模块 ═══\n\n"
            content += f"▸ 模块状态：已就绪\n"
            content += f"▸ 支持设备：USB摄像头 / 网络摄像头 / 无人机图传\n\n"
            content += f"─── 接入方式 ───\n"
            content += f"  • 本地摄像头：点击「启动摄像头」按钮\n"
            content += f"  • 网络流地址：RTSP/RTMP/HLS等协议\n"
            content += f"  • 无人机接入：支持主流无人机SDK\n\n"
            content += f"─── 功能特性 ───\n"
            content += f"  ✓ 实时视频流显示\n"
            content += f"  ✓ 自动火情检测\n"
            content += f"  ✓ 违建识别监测\n"
            content += f"  ✓ 录制与截图保存\n"
            content += f"  ✓ 预警信息推送\n\n"
            content += f"─── 当前状态 ───\n"
            if hasattr(self, '_camera_active') and self._camera_active:
                content += f"  🟢 摄像头运行中\n"
                content += f"  分辨率: {getattr(self, '_camera_resolution', 'N/A')}\n"
                content += f"  帧率: {getattr(self, '_camera_fps', 'N/A')} FPS"
            else:
                content += f"  ⚪ 待机中（未连接）\n"
                content += f"  请使用下方控制面板启动摄像头"
            messagebox.showinfo("📹 摄像头监测", content)
        elif key == "build":
            build_count = summary.get("illegal_build_count", 0)
            recent_build = [a for a in self.alert_manager.get_recent_alerts(30) if "build" in a.get("type", "")]
            content = f"═══ 🏗️ 违建监测详情 ═══\n\n"
            content += f"▸ 本轮检测违建警报数：{build_count}\n"
            content += f"▸ 数据库累计违建警报：{db_full.get('build_total', 0)}\n\n"
            content += f"─── 最近违建记录 ───\n"
            if recent_build:
                for i, a in enumerate(recent_build[:10], 1):
                    content += f"\n{i}. [{a['timestamp']}] {a.get('label','')}\n   目标: {a.get('class_name','')} | 置信度: {a.get('confidence',0):.1%}"
            else:
                content += "\n  暂无违建警报记录"
            messagebox.showinfo("🏗️ 违建监测详情", content)
        elif key == "total":
            total_inspections = db_full.get("total_inspections", 0)
            total_alerts = db_full.get("total_alerts", 0)
            first_time = db_full.get("first_inspection_time", "N/A")
            last_time = db_full.get("last_inspection_time", "N/A")
            content = f"═══ 📈 巡检总览 ═══\n\n"
            content += f"▸ 总巡检次数：{total_inspections}\n"
            content += f"▸ 累计警报总数：{total_alerts}\n"
            content += f"▸ 火情警报：{db_full.get('fire_total', 0)}\n"
            content += f"▸ 烟雾警报：{db_full.get('smoke_total', 0)}\n"
            content += f"▸ 违建警报：{db_full.get('build_total', 0)}\n"
            content += f"▸ 高危警报：{db_full.get('high_severity_count', 0)}\n\n"
            content += f"▸ 首次巡检时间：{first_time}\n"
            content += f"▸ 最近巡检时间：{last_time}\n\n"
            content += f"─── 引擎信息 ───\n"
            content += f"  检测引擎: YOLOv8 + PyTorch\n"
            content += f"  图像分辨率: {DISPLAY_WIDTH}x{DISPLAY_HEIGHT}\n"
            content += f"  置信度阈值: {CONFIDENCE_THRESHOLD}"
            messagebox.showinfo("📈 巡检总览", content)

    def _update_display(self, frame_np: np.ndarray):
        # 性能优化：限制GUI更新频率，避免卡顿
        current_time = time.time()
        if current_time - self._last_display_time < self._display_interval:
            return  # 跳过这次更新
        self._last_display_time = current_time

        try:
            if len(frame_np.shape) == 3:
                rgb = cv2.cvtColor(frame_np, cv2.COLOR_BGR2RGB)
            else:
                rgb = cv2.cvtColor(frame_np, cv2.COLOR_GRAY2RGB)
            image = Image.fromarray(rgb)
            display_w = self.video_label.winfo_width() or 900
            display_h = self.video_label.winfo_height() or 550
            image.thumbnail((display_w - 10, display_h - 10), Image.Resampling.LANCZOS)
            self.current_image_tk = ImageTk.PhotoImage(image)
            self.video_label.config(image=self.current_image_tk, text="")
        except Exception as e:
            print(f"[显示错误] {e}")

    def _on_new_alert(self, alerts):
        self.root.after(0, lambda: self._process_gui_alerts(alerts))

    def _process_gui_alerts(self, alerts):
        for alert in alerts:
            ts = alert.get("timestamp", "")[-8:]
            label = alert.get("label", "")
            conf = alert.get("confidence", 0)
            severity = alert.get("severity", "medium")
            type_map = {"high": "【高危】", "medium": "【中等】", "low": "【低危】"}
            prefix = type_map.get(severity, "")
            entry = f"{prefix}[{ts}] {label} ({conf:.1%})"
            self.alert_listbox.insert(0, entry)
            color_map = {"high": "#ef4444", "medium": "#f59e0b", "low": "#22c55e"}
            self.alert_listbox.itemconfig(0, {'fg': color_map.get(severity, "#ffffff")})
        total = self.alert_listbox.size()
        if total > 50:
            self.alert_listbox.delete(50, tk.END)
        self._update_stats()
        if any(a.get("severity") == "high" for a in alerts):
            self._flash_warning()

    def _flash_warning(self):
        original_bg = self.root.cget("bg")
        colors = ["#450a0a", original_bg, "#450a0a", original_bg]
        delays = [200, 200, 200]

        def flash_step(step=0):
            if step < len(colors):
                self.root.configure(bg=colors[step])
                self.root.after(delays[step], lambda: flash_step(step + 1))
            else:
                self.root.configure(bg=original_bg)
        flash_step()

    def _update_stats(self):
        summary = self.alert_manager.get_alert_summary()
        fire_cnt = summary.get("fire_count", 0)
        db_full = summary.get("db_full", {})
        total_insp = db_full.get("total_inspections", 0)
        total_alerts = fire_cnt
        self.module_cards["fire"].update_value(str(fire_cnt), f"本轮检测到 {fire_cnt} 条火情警报")
        self.module_cards["camera"].update_value(
            "运行中" if (hasattr(self, '_camera_active') and self._camera_active) else "待机",
            "无人机/摄像头实时监测" if (hasattr(self, '_camera_active') and self._camera_active) else "点击启动摄像头"
        )

    def _set_status(self, msg: str, is_alert: bool = False):
        self.status_var.set(msg)
        if is_alert:
            self.status_indicator.config(text="● 警报中!", fg="#ef4444")
        else:
            self.status_indicator.config(text="● 运行中", fg="#22c55e")

    def _open_image(self):
        path = filedialog.askopenfilename(
            title="选择巡检图像",
            filetypes=[
                ("图像文件", "*.jpg *.jpeg *.png *.bmp *.tiff *.webp"),
                ("所有文件", "*.*")
            ]
        )
        if not path:
            return
        self._set_status(f"正在分析图像: {os.path.basename(path)}...")
        self.root.update()
        try:
            vis_frame, result = self.img_processor.process_image(path)
            self._update_display(vis_frame)
            self.alert_manager.process_detection_result(result, vis_frame, source_type="image", source_path=path)
            fire_n = len(result.get("fires", []))
            smoke_n = len(result.get("smokes", []))
            build_n = len(result.get("illegal_builds", []))
            status_msg = f"分析完成 | 🔥火情:{fire_n} 💨烟雾:{smoke_n} 🏗违建:{build_n}"
            if result.get("has_alert"):
                self._set_status(status_msg, is_alert=True)
            else:
                self._set_status(status_msg)
        except Exception as e:
            messagebox.showerror("错误", f"图像处理失败:\n{str(e)}")
            self._set_status("图像处理失败")

    def _open_video(self):
        path = filedialog.askopenfilename(
            title="选择视频文件",
            filetypes=[
                ("视频文件", "*.mp4 *.avi *.mov *.mkv *.flv *.wmv *.ts *.m2ts *.webm *.3gp *.m4v"),
                ("所有文件", "*.*")
            ]
        )
        if not path:
            return
        self._stop_detection()
        self._current_mode = "video"
        self._running = True
        self.btn_stop.config(state=tk.NORMAL)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_name = os.path.splitext(os.path.basename(path))[0]
        safe_name = "".join(c for c in safe_name if c.isalnum() or c in "_- ")
        output_path = os.path.join(OUTPUT_DIR, f"detect_{safe_name}_{ts}.mp4")

        def run_video():
            self._set_status(f"正在分析视频: {os.path.basename(path)}...")
            try:
                results = self.video_processor.process_video_file(
                    path, output_path=output_path,
                    callback=lambda f, r: self._video_callback(f, r),
                    show_display=False
                )
                self.root.after(0, lambda: self._on_video_done(results, output_path))
            except Exception as e:
                err_msg = str(e)
                self.root.after(0, lambda: messagebox.showerror("错误", f"视频处理失败:\n{err_msg}"))
                self.root.after(0, lambda: self._on_detection_stopped())

        self._video_thread = threading.Thread(target=run_video, daemon=True)
        self._video_thread.start()

    def _video_callback(self, frame, result):
        try:
            self.alert_manager.process_detection_result(result, frame, source_type="video")
            self.root.after(0, lambda: self._update_display(frame))
        except Exception:
            pass

    def _on_video_done(self, results, output_path):
        total = len(results)
        alert_count = sum(1 for r in results if r.get("has_alert"))
        messagebox.showinfo("视频分析完成",
                             f"✅ 分析完成！\n\n"
                             f"总帧数: {total}\n"
                             f"异常帧数: {alert_count}\n\n"
                             f"结果已保存至:\n{output_path}")
        self._on_detection_stopped()

    def _toggle_camera(self):
        if self._current_mode == "camera":
            self._stop_detection()
            return
        self._stop_detection()
        self._current_mode = "camera"
        self._running = True
        self.btn_camera.config(text="⏹ 关闭摄像头", bg="#ef4444")
        self.btn_stop.config(state=tk.NORMAL)

        def run_camera():
            self._set_status("摄像头实时检测中... 按 '停止' 结束")
            try:
                for frame, result in self.video_processor.process_camera(
                    callback=lambda f, r: self._camera_callback(f, r),
                    show_display=False
                ):
                    if not self._running:
                        break
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("错误", f"摄像头错误:\n{str(e)}"))
            finally:
                self.root.after(0, lambda: self._on_detection_stopped())

        self._camera_thread = threading.Thread(target=run_camera, daemon=True)
        self._camera_thread.start()

    def _camera_callback(self, frame, result):
        try:
            self.alert_manager.process_detection_result(result, frame, source_type="camera")
            self.root.after(0, lambda: self._update_display(frame))
        except Exception:
            pass

    def _stop_detection(self):
        self._running = False
        self.video_processor.stop()
        self._current_mode = "idle"
        self.btn_stop.config(state=tk.DISABLED)
        self.btn_camera.config(text="📷 启动摄像头", bg="#10b981")
        self.status_indicator.config(text="● 系统就绪", fg="#22c55e")
        self._set_status("已停止检测")

    def _on_detection_stopped(self):
        self._running = False
        self._current_mode = "idle"
        self.btn_stop.config(state=tk.DISABLED)
        self.btn_camera.config(text="📷 启动摄像头", bg="#10b981")
        self.status_indicator.config(text="● 系统就绪", fg="#22c55e")
        self._set_status("检测已停止")

    def _export_report(self):
        try:
            report_path = self.alert_manager.generate_report_html()
            messagebox.showinfo("报告导出成功", f"HTML可视化报告已生成！\n\n保存路径:\n{report_path}")
            os.startfile(report_path)
        except Exception as e:
            messagebox.showerror("错误", f"导出失败:\n{str(e)}")

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _on_close(self):
        self._running = False
        self.video_processor.stop()
        self.root.quit()
        self.root.destroy()


def launch_gui():
    app = DroneMonitorGUI()
    app.run()


if __name__ == "__main__":
    launch_gui()