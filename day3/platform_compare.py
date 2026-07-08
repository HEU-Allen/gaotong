"""多平台推理性能对比可视化"""

import matplotlib.pyplot as plt
import numpy as np

# ========== Mac 中文字体修复 ==========
plt.rcParams['font.sans-serif'] = ['PingFang SC', 'Heiti SC', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
# =======================================

# 数据：你的实测 + 计划书预期
data = {
    'Mac CPU\n(FP32)':     {'lat': 50,   'fps': 20.0,  'eff': 1.0},
    'Colab CPU\n(FP32)':   {'lat': 154,  'fps': 6.5,   'eff': 0.3},
    'Colab GPU\n(FP32)':   {'lat': 12,   'fps': 83.2,  'eff': 8.3},
    'Jetson Orin\n(FP16)': {'lat': 8,    'fps': 125,   'eff': 12.5},
    'RK3588 NPU\n(INT8)':  {'lat': 5,    'fps': 200,   'eff': 20.0},
}

platforms = list(data.keys())
colors = ['#2196F3', '#FF9800', '#4CAF50', '#9C27B0', '#F44336']

fig, axes = plt.subplots(1, 3, figsize=(15, 5))

for ax, key, title, unit in zip(axes,
    ['lat', 'fps', 'eff'],
    ['推理延迟 (ms)', '吞吐量 (FPS)', '能效比 (FPS/W)'],
    ['ms', 'FPS', 'FPS/W']):
    
    vals = [data[p][key] for p in platforms]
    bars = ax.barh(platforms, vals, color=colors)
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xlabel(unit)
    
    # 在柱状图上标注数值
    for bar, val in zip(bars, vals):
        ax.text(val + max(vals)*0.02, bar.get_y() + bar.get_height()/2,
                f'{val:.1f}', va='center', fontsize=10)

plt.suptitle('YOLOv10-N 多平台推理性能对比', fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig('platform_benchmark.png', dpi=150, bbox_inches='tight')
print("✅ 性能对比图已保存：platform_benchmark.png")
plt.show()