import os
import cv2
import numpy as np
import torch
from ultralytics import YOLO
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from datetime import datetime
import config


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
    local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", model_name)
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

    def detect(self, image: np.ndarray, conf: float = config.CONFIDENCE_THRESHOLD) -> List[DetectionResult]:
        results = self.model(image, conf=conf, iou=config.IOU_THRESHOLD, verbose=False)[0]
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

    def _analyze_fire_texture(self, image: np.ndarray, x: int, y: int, w: int, h: int) -> dict:
        if x < 0 or y < 0 or x + w > image.shape[1] or y + h > image.shape[0]:
            return {"texture_score": 0.0, "brightness_var": 0, "edge_density": 0}
        roi = image[y:y+h, x:x+w]
        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        brightness_var = np.std(roi_gray)
        edges = cv2.Canny(roi_gray, 50, 150)
        edge_density = np.sum(edges > 0) / (w * h) if (w * h) > 0 else 0
        laplacian_var = cv2.Laplacian(roi_gray, cv2.CV_64F).var()
        texture_score = min(laplacian_var / 500.0, 1.0)
        return {
            "texture_score": texture_score,
            "brightness_var": brightness_var,
            "edge_density": edge_density,
            "laplacian_var": laplacian_var
        }

    def _check_flicker(self, current_mask: np.ndarray, region_bbox: tuple) -> float:
        x, y, w, h = region_bbox
        if x < 0 or y < 0:
            return 0.5
        current_region = current_mask[y:y+h, x:x+w] if y+h <= current_mask.shape[0] and x+w <= current_mask.shape[1] else None
        if current_region is None or len(self._fire_history) < 3:
            return 0.5
        current_ratio = np.sum(current_region > 0) / (w * h) if (w * h) > 0 else 0
        ratios = [h.get("ratio", 0) for h in self._fire_history[-5:]]
        if len(ratios) < 2:
            return 0.5
        variance = np.var(ratios + [current_ratio])
        flicker_score = min(variance * 10, 1.0)
        return flicker_score

    def _analyze_color_distribution(self, hsv_roi: np.ndarray) -> dict:
        h_channel = hsv_roi[:, :, 0]
        s_channel = hsv_roi[:, :, 1]
        v_channel = hsv_roi[:, :, 2]
        mean_hue = np.mean(h_channel)
        mean_sat = np.mean(s_channel)
        mean_val = np.mean(v_channel)
        std_hue = np.std(h_channel)
        std_sat = np.std(s_channel)
        hue_in_fire_range = np.sum((h_channel < 25) | (h_channel > 155)) / h_channel.size
        sat_above_threshold = np.sum(s_channel > 100) / s_channel.size
        val_above_threshold = np.sum(v_channel > 150) / v_channel.size
        is_true_fire_color = (
            ((mean_hue < 20 or mean_hue > 160) and mean_sat > 80 and mean_val > 120) or
            (hue_in_fire_range > 0.6 and sat_above_threshold > 0.5 and val_above_threshold > 0.4)
        )
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

    def _calculate_fire_confidence(self, fire_pixel_ratio: float, area: int,
                                    texture_info: dict, color_info: dict,
                                    flicker_score: float, aspect_ratio: float,
                                    extent: float) -> float:
        score = 0.0
        base_score = min(fire_pixel_ratio * 2.0, 0.4)
        score += base_score
        if color_info["is_true_fire_color"]:
            score += 0.2
        elif color_info["red_dominant"] > 0.7 and color_info["mean_sat"] > 60:
            score += 0.1
        else:
            score -= 0.15
        if texture_info["texture_score"] > 0.3:
            score += 0.15
        if texture_info["brightness_var"] > 40:
            score += 0.1
        if flicker_score > 0.3:
            score += 0.15
        elif flicker_score < 0.1 and len(self._fire_history) >= 5:
            score -= 0.1
        if color_info["orange_present"] > 0.2:
            score += 0.08
        if color_info["yellow_tint"] > 0.15:
            score += 0.05
        if 0.5 < aspect_ratio < 3.0:
            score += 0.05
        if extent > 0.4:
            score += 0.05
        if area > 500 and area < 50000:
            score += 0.05
        final_confidence = max(0.05, min(score, 0.98))
        return final_confidence

    def detect_fire_color(self, image: np.ndarray) -> Tuple[np.ndarray, List[DetectionResult]]:
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        lower_fire1 = np.array([0, 60, 60])
        upper_fire1 = np.array([18, 255, 255])
        lower_fire2 = np.array([162, 60, 60])
        upper_fire2 = np.array([180, 255, 255])
        mask1 = cv2.inRange(hsv, lower_fire1, upper_fire1)
        mask2 = cv2.inRange(hsv, lower_fire2, upper_fire2)
        fire_mask = cv2.bitwise_or(mask1, mask2)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        fire_mask = cv2.morphologyEx(fire_mask, cv2.MORPH_OPEN, kernel)
        fire_mask = cv2.morphologyEx(fire_mask, cv2.MORPH_CLOSE, kernel)
        total_fire_pixels = np.sum(fire_mask > 0)
        total_pixels = image.shape[0] * image.shape[1]
        global_fire_ratio = total_fire_pixels / total_pixels if total_pixels > 0 else 0
        contours, _ = cv2.findContours(fire_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        fire_detections = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 150:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = float(w) / h if h > 0 else 0
            extent = area / (w * h) if (w * h) > 0 else 0
            if not (0.15 < aspect_ratio < 6.0):
                continue
            if extent < 0.12:
                continue
            mask_region = fire_mask[y:y+h, x:x+w] if y+h <= fire_mask.shape[0] and x+w <= fire_mask.shape[1] else None
            fire_pixel_ratio = np.sum(mask_region > 0) / (w * h) if (mask_region is not None and w * h > 0) else 0
            if fire_pixel_ratio < 0.15:
                continue
            texture_info = self._analyze_fire_texture(image, x, y, w, h)
            hsv_roi = hsv[y:y+h, x:x+w] if y+h <= hsv.shape[0] and x+w <= hsv.shape[1] else None
            color_info = self._analyze_color_distribution(hsv_roi) if hsv_roi is not None else {"is_true_fire_color": False, "red_dominant": 0, "orange_present": 0, "yellow_tint": 0, "mean_sat": 0}
            flicker_score = self._check_flicker(fire_mask, (x, y, w, h))
            confidence = self._calculate_fire_confidence(
                fire_pixel_ratio, area, texture_info, color_info,
                flicker_score, aspect_ratio, extent
            )
            if confidence < 0.35:
                continue
            det = DetectionResult(
                class_id=0, class_name="fire",
                confidence=float(confidence), bbox=(x, y, x + w, y + h),
                detection_type="fire"
            )
            fire_detections.append(det)
        self._fire_history.append({
            "ratio": global_fire_ratio,
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

    def detect(self, image: np.ndarray, prev_image: np.ndarray = None) -> List[DetectionResult]:
        all_detections = []
        _, fire_dets = self.detect_fire_color(image)
        all_detections.extend(fire_dets)
        smoke_dets = self.detect_smoke_color(image)
        all_detections.extend(smoke_dets)
        if prev_image is not None:
            motion_dets = self.detect_motion_anomaly(prev_image, image)
            for m_det in motion_dets:
                overlap = False
                for existing in all_detections:
                    iou = IllegalBuildDetector._calculate_iou(m_det.bbox, existing.bbox)
                    if iou > 0.2:
                        overlap = True
                        break
                if not overlap:
                    all_detections.append(m_det)
        return sorted(all_detections, key=lambda x: x.confidence, reverse=True)


class DualDetectionEngine:

    def __init__(self):
        print("[引擎] 正在初始化检测引擎...")
        self.build_detector = IllegalBuildDetector()
        self.fire_detector = FireDetector()
        self.prev_frame = None
        self.detection_history = []
        self.alert_cooldown = {}
        self.cooldown_seconds = 5
        print("[引擎] 检测引擎初始化完成")

    def detect(self, frame: np.ndarray, enable_build: bool = True, enable_fire: bool = True) -> dict:
        timestamp = datetime.now()
        result = {
            "timestamp": timestamp,
            "illegal_builds": [],
            "fires": [],
            "smokes": [],
            "anomalies": [],
            "has_alert": False,
            "alert_types": []
        }
        if enable_build:
            build_dets = self.build_detector.detect(frame)
            result["illegal_builds"] = build_dets
        if enable_fire:
            fire_dets = self.fire_detector.detect(frame, self.prev_frame)
            for det in fire_dets:
                if det.detection_type in ("fire", "fire_anomaly", "fire_motion"):
                    result["fires"].append(det)
                elif det.detection_type == "smoke":
                    result["smokes"].append(det)
                else:
                    result["anomalies"].append(det)
        all_alerts = (
            result["illegal_builds"] +
            result["fires"] +
            result["smokes"] +
            result["anomalies"]
        )
        filtered_alerts = []
        for alert in all_alerts:
            alert_key = f"{alert.detection_type}_{alert.class_name}_{int(alert.bbox[0]/50)}_{int(alert.bbox[1]/50)}"
            last_time = self.alert_cooldown.get(alert_key)
            if last_time is None or (timestamp - last_time).total_seconds() > self.cooldown_seconds:
                self.alert_cooldown[alert_key] = timestamp
                filtered_alerts.append(alert)
        result["has_alert"] = len(filtered_alerts) > 0
        result["alerts"] = filtered_alerts
        if result["has_alert"]:
            result["alert_types"] = list(set(a.detection_type for a in filtered_alerts))
        self.prev_frame = frame.copy()
        self.detection_history.append(result)
        if len(self.detection_history) > 100:
            self.detection_history = self.detection_history[-100:]
        return result
