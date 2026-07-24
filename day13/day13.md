# 嵌入式硬件方向实习 · Day 13 学习笔记

## 一、今日主题

Windows 嵌入式性能追踪与调优。

课程计划列出的 Windows 工具包括 Windows Performance Analyzer（WPA）、ETW、SEGGER SystemView、STM32CubeMonitor 和 Ozone。由于本次使用 macOS，无法直接运行这些 Windows GUI 工具；但课程后续提供的 Python 轻量函数追踪框架可以跨平台运行，因此本次以该框架完成同样的核心流程：记录函数延迟、统计均值/P95/最大值、定位瓶颈并实施内存分配优化。

| 时间 | 内容 |
|------|------|
| 09:00-10:30 | 性能追踪工具体系：WPA、ETW、SystemView、CubeMonitor、Ozone |
| 10:30-12:00 | Python 轻量性能追踪实践 |
| 13:00-15:00 | NumPy 向量化与 Python 内存分配优化 |

---

## 二、性能追踪中的关键指标

### 1. 延迟

延迟是一次函数调用从开始到结束花费的时间。本实验使用 `time.perf_counter_ns()` 读取高精度计时器，并转换为微秒：

```python
latency_us = (time.perf_counter_ns() - start_ns) / 1000.0
```

```text
1 ms = 1000 us
```

### 2. 平均值、P95 与最大值

| 指标 | 含义 | 用途 |
|------|------|------|
| 平均值 | 所有调用延迟的平均水平 | 判断总体性能 |
| P95 | 95% 的调用不超过此延迟 | 判断大多数情况下的实时表现 |
| 最大值 | 所有调用中最慢的一次 | 发现极端尖峰、调度干扰或异常分配 |

实时系统不能只看平均值。例如平均延迟很低，但偶尔出现很大的尖峰，仍可能导致任务错过截止时间。

---

## 三、课程对齐的函数追踪实验

课程示例追踪三类嵌入式常见工作：

```text
YOLOv10 图像预处理 → PID 控制计算 → 卡尔曼滤波更新
```

本次的 `FunctionTracer` 使用装饰器包裹目标函数：

```python
@tracer.trace
def pid_compute(...):
    ...
```

装饰器在函数调用前记录开始时间、调用后计算耗时，并按函数名保存每一次延迟。它相当于一个轻量、跨平台的函数级追踪器。

### 1. 被追踪的三个函数

| 函数 | 模拟内容 |
|------|----------|
| `yolov10_preprocess` | 图像填充、归一化、HWC 转 CHW，模拟 YOLO 输入预处理 |
| `pid_compute` | 计算误差、积分项、微分项和控制输出 |
| `kalman_update` | 计算增益并更新状态估计和协方差 |

运行命令：

```bash
cd /Users/whl/gaotong/week3/day13
python day13_course_trace.py
open day13_course_latency.png
```

---

## 四、课程对齐版追踪结果

本次运行 1000 次，结果如下：


| 函数 | 调用次数 | 平均延迟 | P95 | 最大延迟 | 判断 |
|------|---------:|---------:|----:|---------:|------|
| `yolov10_preprocess` | 1000 | 1258.9 us | 1574.0 us | 4266.3 us | 主要瓶颈 |
| `kalman_update` | 1000 | 13.0 us | 18.1 us | 853.9 us | 平均很快，存在偶发尖峰 |
| `pid_compute` | 1000 | 4.5 us | 6.6 us | 20.2 us | 非瓶颈 |

<img width="1800" height="1200" alt="day13_course_latency" src="https://github.com/user-attachments/assets/f47cb900-b4ab-4913-b8d7-b8c35d5c7c71" />


延迟时间线显示，YOLO 预处理的绿色曲线远高于 PID 和卡尔曼滤波。原因是预处理需要处理约 `640 × 640 × 3` 的图像数据，并且原始实现每帧都会创建新的大尺寸浮点数组。

因此，优化顺序应为：

```text
先优化 YOLO 预处理
再评估是否需要优化卡尔曼滤波
PID 当前不需要优化
```

> 卡尔曼滤波的最大值出现单次较大尖峰，并不说明其平均计算很慢。Python 进程调度、内存分配、垃圾回收和操作系统后台活动都可能造成偶发尖峰；这正是同时查看 P95 和最大值的原因。

---

## 五、内存分配优化

### 1. 原始方式：每帧分配

原始预处理每次调用都会创建新的 `640 × 640 × 3` 浮点数组：

```python
resized = np.zeros((640, 640, 3), dtype=np.float32)
```

这会带来：

1. 反复向系统申请大块内存；
2. 初始化新内存为零；
3. 后续由 Python 和系统回收旧数组；
4. 延迟产生更明显的长尾和尖峰。

### 2. 优化方式：预分配工作缓冲区

优化后只在初始化时申请一次：

```python
self.buffer = np.empty((640, 640, 3), dtype=np.float32)
```

每帧重复使用该缓冲区：

```python
self.buffer.fill(0.0)
np.multiply(frame, 1.0 / 255.0, out=self.buffer[:height, :width], casting="unsafe")
```

这是一种对象池/工作缓冲区思想：不反复创建和销毁同类型大对象，而是让对象长期存在并被重复使用。

运行命令：

```bash
python day13_preprocess_optimization.py
open day13_preprocess_optimization.png
```

---

## 六、优化结果

| 方案 | 平均延迟 | P95 | 最大延迟 |
|------|---------:|----:|---------:|
| 每帧新建数组 | 902.3 us | 1213.6 us | 3179.6 us |
| 复用工作缓冲区 | 650.5 us | 763.4 us | 1088.0 us |

平均延迟加速比：

```text
902.3 / 650.5 = 1.39x
```

<img width="1800" height="675" alt="day13_preprocess_optimization" src="https://github.com/user-attachments/assets/ea56a4fb-f293-4e7e-8d41-4bc95cf18ee5" />


优化不仅让平均延迟降低约 28%，还显著减小了长尾：最大延迟从约 `3.18 ms` 降到约 `1.09 ms`。这对实时任务更重要，因为长尾延迟更容易造成周期任务抖动或错过截止时间。

---

## 七、与 Windows/RTOS 追踪工具的对应关系

| 课程工具 | 典型用途 | 本次 Python 实验中的对应概念 |
|----------|----------|------------------------------|
| WPA / ETW | 系统级事件与 CPU 时间线 | 函数调用时间线、延迟分布 |
| SystemView | RTOS 任务切换、中断延迟 | 任务/函数执行时间、P95、最大值 |
| STM32CubeMonitor | STM32 实时变量监控 | 保存 JSON 追踪数据和延迟统计 |
| Ozone | 调试与 RTOS 感知 | 按函数定位性能瓶颈 |

本次并没有替代 Windows 工具本身，而是用可在 macOS 运行的 Python 实验掌握相同的分析逻辑：先记录事件，再量化延迟，最后根据数据选择优化对象。

---

## 八、补充验证：通用嵌入式流水线

在课程对齐实验之前，还完成了一个通用的“传感器采集 - 预处理 - 推理 - 后处理”函数追踪练习，用于先验证追踪器、直方图与时间线输出是否正常。该部分是辅助验证，不替代第四节中的课程对齐实验。

<img width="1800" height="1200" alt="day13_latency" src="https://github.com/user-attachments/assets/655eb594-7549-462f-a564-648cfb00aa8e" />


该辅助实验中，`inference` 的平均延迟约 1469.6 us，为通用流水线的主要耗时阶段；这与课程对齐实验中“图像预处理属于主要瓶颈”的方法论一致：先测量，再确定优化优先级。

---

## 九、关键文件

| 文件 | 用途 |
|------|------|
| `day13_course_trace.py` | 课程对齐：YOLO 预处理、PID、卡尔曼滤波的函数追踪 |
| `day13_course_trace.json` | 1000 次调用的函数延迟数据与统计摘要 |
| `day13_course_latency.png` | 课程对齐版的延迟直方图与时间线 |
| `day13_preprocess_optimization.py` | 预分配工作缓冲区的内存优化对比 |
| `day13_preprocess_optimization.json` | 优化前后平均值、P95、最大值和加速比 |
| `day13_preprocess_optimization.png` | 预处理延迟分布和均值对比图 |
| `day13.md` | Day 13 学习笔记 |

---

## 十、今日总结

Day 13 完成了从“记录性能数据”到“依据数据优化”的闭环。

首先用函数追踪器统计 YOLO 预处理、PID 和卡尔曼滤波的平均值、P95 与最大值，定位到图像预处理是主要瓶颈；随后通过预分配并复用工作缓冲区，避免每帧重复创建大尺寸数组，使平均预处理延迟从 902.3 us 降至 650.5 us，并显著降低最大延迟。

本实验说明：实时系统的性能优化不能只看平均速度。应同时关注 P95、最大延迟和时间线中的尖峰；找到瓶颈后，应优先优化真正耗时最多、波动最大的阶段。
