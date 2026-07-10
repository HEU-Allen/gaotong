import json
from datetime import datetime

import cv2

from edge_ai_system import EdgeAISystem


def main():
    system = EdgeAISystem(model_path="yolov10n.onnx")

    cap = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)

    if not cap.isOpened():
        print("❌ 摄像头打开失败")
        print("请检查：Mac 是否给了终端/VS Code 摄像头权限")
        return

    print("\n🚀 摄像头实时检测系统已启动")
    print("按 q 键退出程序\n")

    frame_id = 0

    while True:
        ret, frame = cap.read()

        if not ret:
            print("❌ 读取摄像头画面失败")
            break

        frame_id += 1

        result = system.process_one_frame(frame)
        system.monitor.update(result["fps"], result["latency_ms"])

        log_item = {
            "frame": frame_id,
            "latency_ms": round(result["latency_ms"], 2),
            "infer_ms": round(result["infer_ms"], 2),
            "fps": round(result["fps"], 2),
            "n_det": result["n_det"],
            "time": datetime.now().isoformat(timespec="seconds"),
        }
        system.logs.append(log_item)

        text1 = f"FPS: {result['fps']:.1f}"
        text2 = f"Latency: {result['latency_ms']:.1f} ms"
        text3 = f"Detections: {result['n_det']}"

        cv2.putText(frame, text1, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(frame, text2, (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(frame, text3, (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        cv2.imshow("Day 5 Edge AI Camera System", frame)

        if frame_id % 30 == 0:
            s = system.monitor.stats()
            print(
                f"已处理 {frame_id:>4} 帧 | "
                f"平均 FPS: {s['avg_fps']:.1f} | "
                f"平均延迟: {s['avg_latency_ms']:.1f} ms"
            )

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()

    summary = system.monitor.stats()

    result_data = {
        "summary": summary,
        "logs_last_20": system.logs[-20:],
    }

    with open("camera_results.json", "w", encoding="utf-8") as f:
        json.dump(result_data, f, indent=2, ensure_ascii=False)

    system.monitor.save_plot("camera_perf_monitor.png")

    print("\n✅ 摄像头检测结束")
    print("✅ 结果日志已保存：camera_results.json")
    print("✅ 性能曲线已保存：camera_perf_monitor.png")


if __name__ == "__main__":
    main()