# 嵌入式硬件方向实习 · Day 11 学习笔记

## 一、今日主题

Python 性能分析与火焰图。

课程计划中 Day 11 的工具包括 `cProfile`、`timeit`、`snakeviz`、`pyinstrument` 和 `Scalene`。本次在 macOS 上完成与课程目标等价的 `cProfile + timeit + SnakeViz` 实验：定位传感器数据处理热点，完成算法优化，并通过火焰图验证优化效果。

| 时间 | 内容 |
|------|------|
| 09:00-10:30 | Python 性能分析工具：`cProfile`、`timeit`、SnakeViz |
| 10:30-12:00 | 性能分析实践：定位热点、优化滑动平均算法、对比结果 |

> 课程计划标注 Windows 环境；`cProfile`、`timeit` 与 SnakeViz 也支持 macOS，因此实验知识点和分析流程保持一致。

---

## 二、实验目标

1. 使用 `cProfile` 分析 Python 函数的调用次数和累计耗时；
2. 使用 `timeit` 对比优化前后的平均运行时间；
3. 使用 SnakeViz 打开 `.prof` 文件并查看 Icicle 火焰图；
4. 将传感器滑动平均由重复求和优化为维护窗口累计和。

---

## 三、实验对象：传感器滑动平均

程序生成 80,000 个模拟温度样本，使用窗口大小 `80` 计算滑动平均值。

### 1. 基线实现

基线版本在每个输出位置都重新对窗口内元素求和：

```python
for index in range(len(samples) - window + 1):
    result.append(sum(samples[index:index + window]) / window)
```

该方式会重复计算相邻窗口共有的 79 个样本，时间复杂度约为 `O(n * w)`。

### 2. 优化实现

优化版本只在开始时计算一次窗口和，随后每移动一个样本，就加上新样本并减去移出窗口的旧样本：

```python
window_sum += samples[index]
window_sum -= samples[index - window]
result.append(window_sum / window)
```

该方式将主要计算量降为一次线性遍历，时间复杂度约为 `O(n)`。

---

## 四、运行命令

在 `week3` 目录、已激活虚拟环境的前提下运行：

```bash
python day11_profile.py
```

程序会生成：

```text
day11_slow.prof
day11_fast.prof
```

安装并打开 SnakeViz：

```bash
pip install snakeviz
snakeviz day11_slow.prof
```

终端按 `Ctrl + C` 停止当前服务后，可查看优化版本：

```bash
snakeviz day11_fast.prof
```

---

## 五、cProfile 结果

本机实际运行结果如下：

| 版本 | 函数调用次数 | 主函数累计耗时 | 关键热点 |
|------|------------:|--------------:|----------|
| 基线版本 | 159,845 | 0.038 s | `sum()` 调用 79,921 次 |
| 优化版本 | 79,925 | 0.008 s | 只有一次初始化 `sum()` |

基线版本的关键输出：

```text
moving_average_slow  cumulative: 0.038 s
builtins.sum         ncalls: 79921, cumulative: 0.017 s
```

优化版本中，`sum()` 不再是主要热点：

```text
moving_average_fast  cumulative: 0.008 s
builtins.sum         ncalls: 1
```

两版程序均输出 `79,921` 个滑动平均结果，最后一个温度值均为约 `24.888 C`，说明优化改变了计算过程，但没有改变计算结果。

---

## 六、timeit 对比

`timeit.repeat()` 对每个版本执行 3 次并取平均值。

| 版本 | 平均耗时 | 加速效果 |
|------|---------:|----------|
| 基线版本 | 29.71 ms | 基准 |
| 优化版本 | 5.76 ms | 约 5.2 倍 |

结论：减少重复计算后，平均耗时从 `29.71 ms` 降至 `5.76 ms`。实际加速倍率低于窗口大小 80，是因为循环、列表追加、Python 解释器执行等固定开销仍然存在。

---

## 七、SnakeViz 火焰图分析

SnakeViz 的 Icicle 图中，矩形宽度代表函数占用的时间。

### 1. 基线版本

根节点为 `moving_average_slow`，总耗时约 `0.0364 s`。其下 `builtins.sum` 占约 `0.0171 s`，是图中最明显的子块。这证明重复窗口求和是性能热点。

### 2. 优化版本

根节点为 `moving_average_fast`，总耗时约 `0.00823 s`。图中没有大面积的 `sum()` 子块，只保留滑动窗口的加减更新逻辑。

火焰图与终端的 `cProfile`、`timeit` 结果相互验证：热点被定位为重复 `sum()`，优化后热点被消除，运行时间显著降低。

---

## 八、pyinstrument 采样分析

首次直接分析 `day11_profile.py` 时，单次工作负载只有几十毫秒，采样点主要落在 `generate_sensor_samples()` 的 `Random.uniform()` 中，未能稳定捕捉短暂的 `sum()` 调用。

因此新增 `day11_pyinstrument_demo.py`，让慢版和优化版各重复执行 40 次，将总分析时间延长到约 1.86 秒。实际调用时间线如下：

| 调用路径 | 采样时间 | 结论 |
|----------|---------:|------|
| `run_workload` | 1.860 s | 完整重复工作负载 |
| `moving_average_slow` | 1.440 s | 主要性能瓶颈 |
| `moving_average_slow → sum` | 0.677 s | 重复窗口求和的直接耗时 |
| `moving_average_fast` | 0.389 s | 优化后的线性滑动更新 |
| `generate_sensor_samples` | 0.015 s | 数据生成不是主要瓶颈 |

这说明两类性能工具的角色不同：`cProfile` 适合精确统计短函数的调用次数和累计耗时；`pyinstrument` 是采样分析器，更适合持续时间足够长的真实工作负载、调用时间线和长任务分析。

运行命令：

```bash
pyinstrument -r html -o day11_pyinstrument.html day11_pyinstrument_demo.py
open day11_pyinstrument.html
```

---

## 九、关键文件

| 文件 | 用途 |
|------|------|
| `week3/day11_profile.py` | 基线/优化滑动平均、`cProfile`、`timeit` 测试代码 |
| `week3/day11_slow.prof` | 基线版本的性能分析数据 |
| `week3/day11_fast.prof` | 优化版本的性能分析数据 |
| `week3/day11_pyinstrument_demo.py` | 用于 pyinstrument 采样的重复工作负载 |
| `week3/day11.md` | Day 11 实验记录与结论 |

---

## 十、今日总结

Day 11 完成了 Python 性能分析的完整基本流程：先用 `cProfile` 获取调用次数和累计耗时，再用 SnakeViz 将调用关系可视化为火焰图，通过 `timeit` 用平均运行时间量化优化效果，最后使用 `pyinstrument` 分析持续工作负载的调用时间线。

本实验说明，性能优化不应先凭感觉修改代码，而应先用数据定位热点。对于滑动窗口类传感器数据处理，维护状态并复用相邻窗口的计算结果，可以减少重复工作，同时保持输出结果不变。
