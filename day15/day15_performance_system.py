"""Day 15 - reproducible performance-optimization benchmark.

This is a model-free teaching version of the PDF's YOLOv10 optimization
project.  It preserves the same pipeline ideas: preprocessing, inference,
preallocated input buffers, warm-up, graph-operation fusion and multi-thread
execution.  A synthetic detector is used because no trained YOLO ONNX model is
included in this repository.
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import threading
import time
from pathlib import Path

# This script runs from a terminal, so force a non-GUI backend before pyplot.
MPL_CACHE_DIR = Path(__file__).resolve().parent / ".matplotlib-cache"
MPL_CACHE_DIR.mkdir(exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CACHE_DIR))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


FRAME_HEIGHT = 480
FRAME_WIDTH = 640
MODEL_SIZE = 320
CHANNELS = 3
FRAMES_TO_TEST = 80
WARMUP_RUNS = 5
WORKERS = min(4, os.cpu_count() or 1)


def nearest_indices(source_length: int, target_length: int) -> np.ndarray:
    """Precompute nearest-neighbour lookup indices once, not once per frame."""
    return (np.arange(target_length) * source_length // target_length).astype(np.intp)


Y_INDEX = nearest_indices(FRAME_HEIGHT, MODEL_SIZE)
X_INDEX = nearest_indices(FRAME_WIDTH, MODEL_SIZE)


def baseline_detect(frame: np.ndarray) -> float:
    """Reference pipeline: allocates temporary arrays in every stage."""
    resized = frame[Y_INDEX[:, None], X_INDEX[None, :], :]
    normalized = resized.astype(np.float32) / 255.0
    tensor = np.transpose(normalized, (2, 0, 1))[np.newaxis, ...].copy()

    # Synthetic detection graph: three channel weights followed by ReLU.
    feature = tensor[0, 0] * 0.40 + tensor[0, 1] * 0.35 + tensor[0, 2] * 0.25
    activated = np.maximum(feature - 0.50, 0.0)
    return float(activated.mean())


class OptimizedDetector:
    """Worker-local buffers emulate an optimized ONNX Runtime detector."""

    def __init__(self) -> None:
        self.local = threading.local()

    def _buffers(self) -> tuple[np.ndarray, np.ndarray]:
        if not hasattr(self.local, "input_buf"):
            # Allocate once per worker, then reuse for every frame.
            self.local.input_buf = np.empty((1, CHANNELS, MODEL_SIZE, MODEL_SIZE), dtype=np.float32)
            self.local.feature_buf = np.empty((MODEL_SIZE, MODEL_SIZE), dtype=np.float32)
        return self.local.input_buf, self.local.feature_buf

    def detect(self, frame: np.ndarray) -> float:
        input_buf, feature_buf = self._buffers()

        # Directly copy HWC uint8 pixels into the reusable NCHW float buffer.
        resized_view = frame[Y_INDEX[:, None], X_INDEX[None, :], :]
        np.copyto(input_buf[0], np.transpose(resized_view, (2, 0, 1)), casting="unsafe")
        np.multiply(input_buf, 1.0 / 255.0, out=input_buf)

        # Fused/in-place version of the same synthetic detection graph.
        np.multiply(input_buf[0, 0], 0.40, out=feature_buf)
        feature_buf += input_buf[0, 1] * 0.35
        feature_buf += input_buf[0, 2] * 0.25
        np.maximum(feature_buf - 0.50, 0.0, out=feature_buf)
        return float(feature_buf.mean())


def percentile(values: list[float], q: float) -> float:
    return float(np.percentile(np.asarray(values), q))


def benchmark_baseline(frames: list[np.ndarray]) -> tuple[list[float], list[float]]:
    latencies_ms: list[float] = []
    scores: list[float] = []
    for frame in frames:
        start = time.perf_counter()
        scores.append(baseline_detect(frame))
        latencies_ms.append((time.perf_counter() - start) * 1000.0)
    return latencies_ms, scores


def benchmark_optimized(
    detector: OptimizedDetector, frames: list[np.ndarray]
) -> tuple[float, list[float], list[float]]:
    # Warm-up creates the per-worker buffers and removes first-call effects.
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        list(pool.map(detector.detect, frames[:WARMUP_RUNS]))

        def timed_detect(frame: np.ndarray) -> tuple[float, float]:
            start = time.perf_counter()
            score = detector.detect(frame)
            return score, (time.perf_counter() - start) * 1000.0

        start_total = time.perf_counter()
        results = list(pool.map(timed_detect, frames))
        elapsed_total_ms = (time.perf_counter() - start_total) * 1000.0

    scores = [score for score, _ in results]
    service_times_ms = [service_time for _, service_time in results]
    return elapsed_total_ms, service_times_ms, scores


def print_stats(name: str, times_ms: list[float]) -> None:
    print(
        f"{name:<20} mean={np.mean(times_ms):6.3f} ms  "
        f"P95={percentile(times_ms, 95):6.3f} ms  max={max(times_ms):6.3f} ms"
    )


def summary(times_ms: list[float]) -> dict[str, float]:
    return {
        "mean_ms": float(np.mean(times_ms)),
        "p95_ms": percentile(times_ms, 95),
        "max_ms": float(max(times_ms)),
    }


def save_report(
    baseline_times: list[float],
    optimized_service_times: list[float],
    baseline_total_ms: float,
    optimized_total_ms: float,
) -> None:
    """Save machine-readable numbers and one compact comparison chart."""
    output_dir = Path(__file__).resolve().parent
    baseline = summary(baseline_times)
    optimized = summary(optimized_service_times)
    speedup = baseline_total_ms / optimized_total_ms

    report = {
        "frames": FRAMES_TO_TEST,
        "workers": WORKERS,
        "warmup_runs": WARMUP_RUNS,
        "baseline_sequential": baseline,
        "optimized_worker_task": optimized,
        "baseline_total_ms": baseline_total_ms,
        "optimized_parallel_total_ms": optimized_total_ms,
        "parallel_throughput_equivalent_ms_per_frame": optimized_total_ms / FRAMES_TO_TEST,
        "throughput_speedup": speedup,
        "correctness_check": "pass",
        "note": "Synthetic detector benchmark; no trained YOLO ONNX model is bundled.",
    }
    json_path = output_dir / "day15_benchmark.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    labels = ["Mean", "P95", "Max"]
    baseline_values = [baseline["mean_ms"], baseline["p95_ms"], baseline["max_ms"]]
    optimized_values = [optimized["mean_ms"], optimized["p95_ms"], optimized["max_ms"]]
    x = np.arange(len(labels))
    width = 0.36

    baseline_fps = FRAMES_TO_TEST / (baseline_total_ms / 1000.0)
    optimized_fps = FRAMES_TO_TEST / (optimized_total_ms / 1000.0)

    figure, (axis_latency, axis_throughput) = plt.subplots(1, 2, figsize=(12, 5))
    axis_latency.bar(x - width / 2, baseline_values, width, label="baseline sequential")
    axis_latency.bar(x + width / 2, optimized_values, width, label="optimized worker task")
    axis_latency.set_title("Per-task latency")
    axis_latency.set_ylabel("Milliseconds")
    axis_latency.set_xticks(x, labels)
    axis_latency.grid(axis="y", alpha=0.3)
    axis_latency.legend()

    bars = axis_throughput.bar(["baseline", "optimized parallel"], [baseline_fps, optimized_fps],
                               color=["tab:red", "tab:green"])
    axis_throughput.set_title("End-to-end throughput")
    axis_throughput.set_ylabel("Frames per second")
    axis_throughput.grid(axis="y", alpha=0.3)
    for bar, value in zip(bars, [baseline_fps, optimized_fps]):
        axis_throughput.text(bar.get_x() + bar.get_width() / 2, value, f"{value:.1f} FPS",
                             ha="center", va="bottom")
    axis_throughput.text(0.5, max(baseline_fps, optimized_fps) * 0.5, f"Speedup: {speedup:.2f}x",
                         ha="center", va="center", fontsize=13, fontweight="bold")

    figure.suptitle("Day 15 Embedded AI Performance Optimization")
    figure.tight_layout()
    chart_path = output_dir / "day15_benchmark.png"
    figure.savefig(chart_path, dpi=160)
    plt.close(figure)

    print(f"Benchmark data saved: {json_path.name}")
    print(f"Benchmark chart saved: {chart_path.name}")


def main() -> None:
    rng = np.random.default_rng(20260724)
    frames = [
        rng.integers(0, 256, size=(FRAME_HEIGHT, FRAME_WIDTH, CHANNELS), dtype=np.uint8)
        for _ in range(FRAMES_TO_TEST)
    ]

    print("=== Day 15: Embedded AI Performance Optimization System ===")
    print("Pipeline: resize -> normalize -> HWC-to-NCHW -> synthetic inference")
    print(f"Frames: {FRAMES_TO_TEST}, input: {FRAME_WIDTH}x{FRAME_HEIGHT}x{CHANNELS}")
    print(f"Optimized workers: {WORKERS}, warm-up runs: {WARMUP_RUNS}")
    print("Model note: synthetic detector used; no trained YOLO ONNX model is bundled.\n")

    baseline_times, baseline_scores = benchmark_baseline(frames)
    detector = OptimizedDetector()
    optimized_total, optimized_service_times, optimized_scores = benchmark_optimized(detector, frames)

    if not np.allclose(baseline_scores, optimized_scores, rtol=1e-5, atol=1e-6):
        raise RuntimeError("Optimization changed the detector result; benchmark is invalid.")

    print("--- Benchmark result ---")
    print_stats("Baseline sequential", baseline_times)
    print_stats("Optimized worker task", optimized_service_times)

    baseline_total = sum(baseline_times)
    speedup = baseline_total / optimized_total
    equivalent_ms_per_frame = optimized_total / len(frames)
    print(f"\nThroughput speedup: {speedup:.2f}x")
    print(f"Parallel throughput equivalent: {equivalent_ms_per_frame:.3f} ms/frame")
    print("Note: worker-task latency and parallel throughput are different metrics.")
    print("Correctness check: PASS (baseline and optimized scores match)")
    print("\nApplied optimizations:")
    print("1. Preallocated worker-local input/feature buffers")
    print("2. In-place normalization and fused feature operations")
    print("3. Warm-up before the timed benchmark")
    print("4. Multi-worker frame processing")

    if speedup >= 2.0:
        print("Target check: PASS - reached the PDF goal of at least 2x speedup.")
    else:
        print("Target check: NOT YET - rerun once, then inspect worker count and system load.")

    save_report(baseline_times, optimized_service_times, baseline_total, optimized_total)


if __name__ == "__main__":
    main()
