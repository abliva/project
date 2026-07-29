import os

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
