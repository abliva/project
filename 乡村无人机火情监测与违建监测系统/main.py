import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_gui():
    from ui.monitor_gui import launch_gui
    launch_gui()


def run_image_mode(image_path: str):
    import cv2
    from models.detector import DualDetectionEngine
    from processors.image_processor import ImageProcessor, draw_detections
    from storage.db_manager import AlertManager, DatabaseManager
    engine = DualDetectionEngine()
    processor = ImageProcessor(engine)
    alert_mgr = AlertManager(DatabaseManager())
    print(f"🔍 正在分析图像: {image_path}")
    vis_frame, result = processor.process_image(image_path)
    fire_n = len(result.get("fires", []))
    smoke_n = len(result.get("smokes", []))
    build_n = len(result.get("illegal_builds", []))
    print(f"\n{'='*50}")
    print(f"  检测结果:")
    print(f"  🔥 火情: {fire_n} 处")
    print(f"  💨 烟雾: {smoke_n} 处")
    print(f"  🏗️ 违建/建筑: {build_n} 处")
    if result.get("has_alert"):
        print(f"\n  ⚠️  发现异常! 共 {len(result.get('alerts', []))} 条警报")
        for a in result.get("alerts", []):
            print(f"     - [{a.detection_type}] {a.class_name} ({a.confidence:.1%})")
    else:
        print(f"\n  ✅ 未发现异常")
    print(f"{'='*50}\n")
    alert_mgr.process_detection_result(result, vis_frame, source_type="image_cli", source_path=image_path)
    output_path = image_path.rsplit('.', 1)[0] + "_detected.jpg"
    cv2.imwrite(output_path, vis_frame)
    print(f"📁 结果已保存至: {output_path}")


def run_video_mode(video_path: str, output_path: str = None):
    from models.detector import DualDetectionEngine
    from processors.image_processor import VideoProcessor
    from storage.db_manager import AlertManager, DatabaseManager
    engine = DualDetectionEngine()
    processor = VideoProcessor(engine)
    alert_mgr = AlertManager(DatabaseManager())
    if not output_path:
        name = os.path.basename(video_path).rsplit('.', 1)[0]
        output_path = os.path.join("output", f"{name}_detected.mp4")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    def on_frame(frame, result):
        alert_mgr.process_detection_result(result, frame, source_type="video_cli")

    print(f"🎬 正在分析视频: {video_path}")
    results = processor.process_video_file(
        video_path, output_path=output_path,
        callback=on_frame, show_display=True
    )
    total = len(results)
    alerts = sum(1 for r in results if r.get("has_alert"))
    print(f"\n✅ 视频分析完成! 共 {total} 帧, {alerts} 帧有异常")
    print(f"📁 输出视频: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="🚁 乡村无人机自动巡检系统 - 违建与火情智能监测",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python main.py                    # 启动 GUI 界面
  python main.py --image test.jpg   # 检测单张图片
  python main.py --video test.mp4   # 检测视频文件
  python main.py --camera           # 启动摄像头实时检测
        """
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--image", "-i", type=str, help="检测指定图片路径")
    group.add_argument("--video", "-v", type=str, help="检测指定视频路径")
    group.add_argument("--camera", "-c", action="store_true", help="启动摄像头实时检测")
    group.add_argument("--output", "-o", type=str, help="输出文件路径 (仅视频模式)")
    args = parser.parse_args()
    print("=" * 55)
    print("  🚁 乡村无人机自动巡检系统")
    print("  违建与火情智能监测 | YOLOv8 + PyTorch")
    print("=" * 55 + "\n")
    if args.image:
        if not os.path.exists(args.image):
            print(f"❌ 文件不存在: {args.image}")
            sys.exit(1)
        run_image_mode(args.image)
    elif args.video:
        if not os.path.exists(args.video):
            print(f"❌ 文件不存在: {args.video}")
            sys.exit(1)
        run_video_mode(args.video, args.output)
    elif args.camera:
        run_camera_mode()
    else:
        print("🖥️  启动图形界面...\n")
        run_gui()


def run_camera_mode():
    import cv2
    from models.detector import DualDetectionEngine
    from processors.image_processor import VideoProcessor, draw_detections
    from storage.db_manager import AlertManager, DatabaseManager
    engine = DualDetectionEngine()
    processor = VideoProcessor(engine)
    alert_mgr = AlertManager(DatabaseManager())
    print("📷 摄像头实时检测中... 按 'q' 退出\n")
    for frame, result in processor.process_camera(show_display=True):
        alert_mgr.process_detection_result(result, frame, source_type="camera_cli")


if __name__ == "__main__":
    main()
