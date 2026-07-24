"""Day 13 - Compare per-frame allocation with a preallocated preprocess buffer."""

import json
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


RUN_COUNT = 1000
FRAME_SHAPE = (480, 640, 3)
MODEL_SHAPE = (640, 640, 3)
OUTPUT_DIR = Path(__file__).parent
rng = np.random.default_rng(1313)


def percentile(values, percent=95):
    return float(np.percentile(np.asarray(values), percent))


def preprocess_allocating(frame):
    """Baseline: allocate a new model-sized float buffer for every frame."""
    resized = np.zeros(MODEL_SHAPE, dtype=np.float32)
    height, width = frame.shape[:2]
    resized[:height, :width] = frame.astype(np.float32) / 255.0
    return np.transpose(resized, (2, 0, 1))[np.newaxis]


class PreallocatedPreprocessor:
    """Reuse one model-sized buffer: an object-pool style allocation strategy."""

    def __init__(self):
        self.buffer = np.empty(MODEL_SHAPE, dtype=np.float32)

    def process(self, frame):
        self.buffer.fill(0.0)
        height, width = frame.shape[:2]
        np.multiply(
            frame,
            1.0 / 255.0,
            out=self.buffer[:height, :width],
            casting="unsafe",
        )
        return np.transpose(self.buffer, (2, 0, 1))[np.newaxis]


def measure(label, function):
    durations_us = []
    checksum = 0.0
    frame_rng = np.random.default_rng(1313)
    for _ in range(RUN_COUNT):
        # Simulate camera capture before the timer starts.
        frame = frame_rng.integers(0, 256, FRAME_SHAPE, dtype=np.uint8)
        start_ns = time.perf_counter_ns()
        output = function(frame)
        durations_us.append((time.perf_counter_ns() - start_ns) / 1000.0)
        checksum += float(output[0, 0, 0, 0])

    result = {
        "mean_us": float(np.mean(durations_us)),
        "p95_us": percentile(durations_us),
        "max_us": float(np.max(durations_us)),
        "checksum": checksum,
    }
    print(
        f"{label:<18} mean={result['mean_us']:8.1f} us  "
        f"P95={result['p95_us']:8.1f} us  max={result['max_us']:8.1f} us"
    )
    return durations_us, result


def main():
    preallocated = PreallocatedPreprocessor()

    print("=== Day 13: Preallocation Optimization ===")
    baseline_times, baseline_summary = measure("Allocate every frame", preprocess_allocating)
    optimized_times, optimized_summary = measure("Reuse work buffer", preallocated.process)
    speedup = baseline_summary["mean_us"] / optimized_summary["mean_us"]
    print(f"Mean-latency speedup: {speedup:.2f}x")

    figure_path = OUTPUT_DIR / "day13_preprocess_optimization.png"
    json_path = OUTPUT_DIR / "day13_preprocess_optimization.json"
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    axes[0].hist(baseline_times, bins=35, alpha=0.72, label="allocate every frame")
    axes[0].hist(optimized_times, bins=35, alpha=0.72, label="reuse work buffer")
    axes[0].set_title("Preprocess latency distribution")
    axes[0].set_xlabel("Latency (us)")
    axes[0].set_ylabel("Count")
    axes[0].grid(alpha=0.25)
    axes[0].legend()

    axes[1].bar(
        ["allocate\nevery frame", "reuse\nwork buffer"],
        [baseline_summary["mean_us"], optimized_summary["mean_us"]],
        color=["tab:red", "tab:green"],
    )
    axes[1].set_title("Mean preprocessing latency")
    axes[1].set_ylabel("Latency (us)")
    axes[1].grid(axis="y", alpha=0.25)
    fig.suptitle("Day 13: Python Memory Allocation Optimization", fontsize=14)
    fig.tight_layout()
    fig.savefig(figure_path, dpi=150)
    plt.close(fig)

    json_path.write_text(
        json.dumps(
            {"baseline": baseline_summary, "optimized": optimized_summary, "speedup": speedup},
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Chart saved: {figure_path.name}")
    print(f"Summary saved: {json_path.name}")


if __name__ == "__main__":
    main()
