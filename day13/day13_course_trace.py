"""Day 13 course-aligned trace: YOLO preprocessing, PID and Kalman update."""

import functools
import json
import math
import threading
import time
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


RUN_COUNT = 1000
OUTPUT_DIR = Path(__file__).parent
rng = np.random.default_rng(13)


class FunctionTracer:
    """A lightweight cross-platform replacement for OS-level trace viewers."""

    def __init__(self):
        self.events = defaultdict(list)
        self.lock = threading.Lock()

    def trace(self, function):
        @functools.wraps(function)
        def wrapper(*args, **kwargs):
            start_ns = time.perf_counter_ns()
            result = function(*args, **kwargs)
            latency_us = (time.perf_counter_ns() - start_ns) / 1000.0
            with self.lock:
                self.events[function.__name__].append(latency_us)
            return result

        return wrapper

    def report(self):
        summary = {}
        print("=== Day 13: Course-aligned Function Trace ===")
        print(f"{'Function':<24} {'Calls':>7} {'Mean(us)':>12} {'P95(us)':>12} {'Max(us)':>12}")
        print("-" * 72)
        for name, latencies in sorted(self.events.items()):
            values = np.asarray(latencies)
            summary[name] = {
                "calls": int(values.size),
                "mean_us": float(np.mean(values)),
                "p95_us": float(np.percentile(values, 95)),
                "max_us": float(np.max(values)),
            }
            print(
                f"{name:<24} {values.size:>7} {np.mean(values):>12.1f} "
                f"{np.percentile(values, 95):>12.1f} {np.max(values):>12.1f}"
            )
        return summary

    def save_json(self, summary, path):
        path.write_text(
            json.dumps({"summary": summary, "latency_us": self.events}, indent=2),
            encoding="utf-8",
        )

    def plot(self, path):
        names = sorted(self.events)
        fig, axes = plt.subplots(2, 2, figsize=(12, 8))
        axes = axes.ravel()

        for axis, name in zip(axes[:3], names):
            values = np.asarray(self.events[name])
            axis.hist(values, bins=35, color="steelblue", edgecolor="black", alpha=0.8)
            axis.axvline(np.percentile(values, 95), color="crimson", linestyle="--", label="P95")
            axis.set_title(f"{name}: latency distribution")
            axis.set_xlabel("Latency (us)")
            axis.set_ylabel("Count")
            axis.grid(alpha=0.25)
            axis.legend()

        for name in names:
            axes[3].plot(self.events[name], label=name, linewidth=1.0)
        axes[3].set_title("Latency timeline")
        axes[3].set_xlabel("Call index")
        axes[3].set_ylabel("Latency (us)")
        axes[3].grid(alpha=0.25)
        axes[3].legend()
        fig.suptitle("Day 13: YOLO Preprocess + PID + Kalman Function Trace", fontsize=14)
        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)


tracer = FunctionTracer()


@tracer.trace
def yolov10_preprocess(frame_size=(480, 640)):
    """Simulate the resize, normalization and CHW conversion before YOLO inference."""
    frame = rng.integers(0, 256, (*frame_size, 3), dtype=np.uint8)
    resized = np.zeros((640, 640, 3), dtype=np.float32)
    height = min(frame_size[0], 640)
    width = min(frame_size[1], 640)
    resized[:height, :width] = frame[:height, :width].astype(np.float32) / 255.0
    return np.transpose(resized, (2, 0, 1))[np.newaxis]


@tracer.trace
def pid_compute(setpoint, measurement, state):
    """Run one PID control update with integral limiting."""
    dt = 0.001
    error = setpoint - measurement
    state["integral"] = float(np.clip(state["integral"] + error * dt, -10, 10))
    derivative = (error - state["previous_error"]) / dt
    state["previous_error"] = error
    return float(np.clip(2.0 * error + 0.5 * state["integral"] + 0.1 * derivative, -100, 100))


@tracer.trace
def kalman_update(x, p, measurement):
    """Run a compact two-measurement Kalman filter update."""
    h = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], dtype=float)
    r = np.eye(2) * 5.0
    innovation_covariance = h @ p @ h.T + r
    gain = p @ h.T @ np.linalg.inv(innovation_covariance)
    x = x + gain @ (measurement - h @ x)
    p = (np.eye(4) - gain @ h) @ p
    return x, p


def main():
    print("=== Day 13: Embedded Performance Trace (course version) ===")
    print("Tracked functions: YOLOv10 preprocess + PID compute + Kalman update")
    print(f"Runs: {RUN_COUNT}")

    pid_state = {"integral": 0.0, "previous_error": 0.0}
    x = np.zeros(4)
    p = np.eye(4) * 100

    for _ in range(RUN_COUNT):
        yolov10_preprocess()
        pid_compute(1.0, 0.8, pid_state)
        measurement = np.array([320.0 + rng.random(), 240.0 + rng.random()])
        x, p = kalman_update(x, p, measurement)

    summary = tracer.report()
    json_path = OUTPUT_DIR / "day13_course_trace.json"
    chart_path = OUTPUT_DIR / "day13_course_latency.png"
    tracer.save_json(summary, json_path)
    tracer.plot(chart_path)
    print(f"\nTrace data saved: {json_path.name}")
    print(f"Latency chart saved: {chart_path.name}")


if __name__ == "__main__":
    main()
