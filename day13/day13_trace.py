"""Day 13 - Lightweight embedded-style function latency tracing."""

import functools
import json
import math
import random
import statistics
import threading
import time
from collections import defaultdict
from pathlib import Path

import matplotlib

# Save a PNG directly; do not depend on a desktop GUI backend.
matplotlib.use("Agg")
import matplotlib.pyplot as plt


RUN_COUNT = 120
OUTPUT_DIR = Path(__file__).parent


class FunctionTracer:
    """Records call count, start time and duration for decorated functions."""

    def __init__(self):
        self.traces = defaultdict(list)
        self.lock = threading.Lock()

    def trace(self, function):
        @functools.wraps(function)
        def wrapper(*args, **kwargs):
            start_ns = time.perf_counter_ns()
            result = function(*args, **kwargs)
            duration_us = (time.perf_counter_ns() - start_ns) / 1000.0

            with self.lock:
                self.traces[function.__name__].append(
                    {"start_ns": start_ns, "duration_us": duration_us}
                )
            return result

        return wrapper

    @staticmethod
    def percentile(values, percent):
        """Return a simple nearest-rank percentile without extra dependencies."""
        ordered = sorted(values)
        index = max(0, math.ceil(percent / 100 * len(ordered)) - 1)
        return ordered[index]

    def report(self):
        print("\n=== Day 13: Function Latency Trace Report ===")
        print(f"{'Function':<20} {'Calls':>7} {'Mean(us)':>12} {'P95(us)':>12} {'Max(us)':>12}")
        print("-" * 68)
        summary = {}

        for name, events in sorted(self.traces.items()):
            durations = [event["duration_us"] for event in events]
            mean_us = statistics.fmean(durations)
            p95_us = self.percentile(durations, 95)
            max_us = max(durations)
            print(f"{name:<20} {len(durations):>7} {mean_us:>12.1f} {p95_us:>12.1f} {max_us:>12.1f}")
            summary[name] = {
                "calls": len(durations),
                "mean_us": mean_us,
                "p95_us": p95_us,
                "max_us": max_us,
            }
        return summary

    def save_json(self, summary, path):
        path.write_text(
            json.dumps({"summary": summary, "events": self.traces}, indent=2),
            encoding="utf-8",
        )

    def plot_latency(self, path):
        functions = list(sorted(self.traces))
        fig, axes = plt.subplots(2, 2, figsize=(12, 8))
        axes = axes.ravel()

        for axis, name in zip(axes[:3], functions[:3]):
            durations = [event["duration_us"] for event in self.traces[name]]
            axis.hist(durations, bins=18, color="steelblue", edgecolor="black", alpha=0.8)
            axis.axvline(self.percentile(durations, 95), color="crimson", linestyle="--", label="P95")
            axis.set_title(f"{name}: latency distribution")
            axis.set_xlabel("Latency (us)")
            axis.set_ylabel("Count")
            axis.legend()
            axis.grid(alpha=0.25)

        for name in functions:
            durations = [event["duration_us"] for event in self.traces[name]]
            axes[3].plot(durations, label=name, linewidth=1.2)
        axes[3].set_title("Latency timeline")
        axes[3].set_xlabel("Call index")
        axes[3].set_ylabel("Latency (us)")
        axes[3].grid(alpha=0.25)
        axes[3].legend()
        fig.suptitle("Day 13 Embedded Pipeline Function Trace", fontsize=14)
        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)


tracer = FunctionTracer()
rng = random.Random(13)


@tracer.trace
def sensor_acquire():
    """Simulate I2C sensor acquisition with small communication jitter."""
    time.sleep(0.0005 + rng.random() * 0.0005)
    return [rng.uniform(-1.0, 1.0) for _ in range(256)]


@tracer.trace
def preprocess(samples):
    """Simulate normalization and feature preparation."""
    average = sum(samples) / len(samples)
    return [(sample - average) * 0.5 for sample in samples]


@tracer.trace
def inference(features):
    """Simulate a compact model inference stage with variable execution time."""
    score = sum(value * value for value in features)
    time.sleep(0.0008 + rng.random() * 0.0008)
    return score


@tracer.trace
def postprocess(score):
    """Turn the model score into a simple alarm decision."""
    time.sleep(0.00015 + rng.random() * 0.00015)
    return {"alarm": score > 45.0, "score": round(score, 3)}


def main():
    for _ in range(RUN_COUNT):
        samples = sensor_acquire()
        features = preprocess(samples)
        score = inference(features)
        postprocess(score)

    summary = tracer.report()
    json_path = OUTPUT_DIR / "day13_trace.json"
    figure_path = OUTPUT_DIR / "day13_latency.png"
    tracer.save_json(summary, json_path)
    tracer.plot_latency(figure_path)
    print(f"\nTrace data saved: {json_path.name}")
    print(f"Latency chart saved: {figure_path.name}")


if __name__ == "__main__":
    main()
