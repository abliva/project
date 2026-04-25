import cv2
import numpy as np
import os
from typing import Optional, Callable, Generator, Tuple, List
from datetime import datetime
from models.detector import DetectionResult, DualDetectionEngine
import config


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
        image = cv2.resize(image, (config.DISPLAY_WIDTH, config.DISPLAY_HEIGHT))
        result = self.engine.detect(image)
        vis_frame = draw_detections(image, result)
        if save_path and config.AUTO_SAVE_ALERT_IMAGE and result.get("has_alert"):
            cv2.imwrite(save_path, vis_frame)
        return vis_frame, result

    def process_image_array(self, image: np.ndarray) -> Tuple[np.ndarray, dict]:
        if image is None or image.size == 0:
            raise ValueError("[错误] 无效的图像输入")
        if len(image.shape) == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        image = cv2.resize(image, (config.DISPLAY_WIDTH, config.DISPLAY_HEIGHT))
        result = self.engine.detect(image)
        vis_frame = draw_detections(image, result)
        return vis_frame, result


class VideoProcessor:

    def __init__(self, engine: DualDetectionEngine):
        self.engine = engine
        self._running = False

    def process_video_file(
        self,
        video_path: str,
        output_path: str = None,
        callback: Callable[[np.ndarray, dict], None] = None,
        show_display: bool = True
    ) -> List[dict]:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"[错误] 无法打开视频文件: {video_path}\n请确认文件路径正确且格式受支持")
        writer = None
        if output_path:
            fps = cap.get(cv2.CAP_PROP_FPS) or config.VIDEO_FPS
            vw = config.DISPLAY_WIDTH
            vh = config.DISPLAY_HEIGHT
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
        try:
            while self._running:
                ret, frame = cap.read()
                if not ret:
                    break
                frame = cv2.resize(frame, (config.DISPLAY_WIDTH, config.DISPLAY_HEIGHT))
                result = self.engine.detect(frame)
                vis_frame = draw_detections(frame, result)
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
        callback: Callable[[np.ndarray, dict], None] = None,
        show_display: bool = True
    ) -> Generator[Tuple[np.ndarray, dict], None, None]:
        cap = cv2.VideoCapture(camera_id)
        if not cap.isOpened():
            raise ValueError(f"[错误] 无法打开摄像头: {camera_id}")
        self._running = True
        try:
            while self._running:
                ret, frame = cap.read()
                if not ret:
                    break
                frame = cv2.resize(frame, (config.DISPLAY_WIDTH, config.DISPLAY_HEIGHT))
                result = self.engine.detect(frame)
                vis_frame = draw_detections(frame, result)
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
