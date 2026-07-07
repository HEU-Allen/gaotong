## 嵌入式硬件方向实习 · Day 1 学习笔记

### 一、今日主题
**嵌入式 AI 推理系统**：YOLOv10-N ONNX 导出 + 基准测试

### 二、上午：理论学习（09:00-12:00）

**1. ARM 异构 SoC 架构**
- 精读 ARM DynamIQ 技术白皮书，理解 big.LITTLE 架构设计。
- 对比 Cortex-A76（大核）与 Cortex-A55（小核）的微架构差异：
  - A76 流水线深度 13 级，支持乱序执行（128 条指令窗口），L1 Cache 为 64KB+64KB。
  - A55 流水线深度 8 级，顺序执行，L1 Cache 为 32KB+32KB。
- 以 RK3588 SoC 为例：4×A76@2.4GHz + 4×A55@1.8GHz + Mali-G610 GPU + 6TOPS NPU。

**2. NPU 架构与 Roofline 模型**
- 理解脉动阵列（Systolic Array）的工作原理：数据在 PE 阵列中流动，减少内存访问。
- Roofline 模型：分析计算密度（Operational Intensity）与内存带宽瓶颈的关系。
- 对比主流嵌入式 NPU：RK3588（6 TOPS）、Jetson Orin NX（100 TOPS）、Apple M4 Neural Engine。

---

### 三、下午：实践操作（13:00-18:00）

**1. 环境搭建**
- 创建 Python 虚拟环境，避免污染系统环境。
- 安装核心依赖：`onnxruntime`、`numpy`、`opencv-python`、`matplotlib`、`psutil`、`ultralytics`、`onnx`、`onnxsim`。
- 遇到的问题与解决：
  - `nump` 拼写错误，修正为 `numpy`。
  - `onnxslm` 拼写错误，修正为 `onnxsim`。
  - `onnxruntime-tools` 在 Python 3.9 下存在依赖冲突，跳过安装（YOLOv10 推理不需要）。
<img width="1128" height="742" alt="5b52a0d6b8e50dbcfb5d5af9a9308338" src="https://github.com/user-attachments/assets/2868dea6-2f64-4bf3-a5b7-9f5aa3818796" />
**2. YOLOv10-N ONNX 导出**
- 使用 Ultralytics 框架加载预训练权重 `yolov10n.pt`，导出为 ONNX 格式。
- 导出参数说明：
  - `format='onnx'`：目标格式为 ONNX。
  - `imgsz=640`：输入分辨率固定为 640×640。
  - `simplify=True`：使用 ONNX Simplifier 去除冗余节点。
  - `opset=17`：ONNX 算子集版本，保证兼容性。
- 导出结果：`yolov10n.onnx`（约 9.5MB），模型结构简化成功。

**3. ONNX Runtime 基准测试**
- 测试环境：MacBook（Apple Silicon），CPU 推理。
- 测试方法：预热 10 次后，正式计时 100 次，计算平均延迟与 P95 延迟。
<img width="776" height="464" alt="7353fd84bf00cd6de38a7ffba4ac63ca" src="https://github.com/user-attachments/assets/4393e0d2-f75a-4c68-905d-ee0cfc3c3ff9" />
- 测试结果：

| 指标 | 数值 |
|------|------|
| 测试平台 | Mac CPU |
| 平均延迟 | **49.95 ms** |
| P95 延迟 | **53.21 ms** |
| 理论 FPS | **20.0** |

- 结果分析：YOLOv10-N 作为轻量模型，在纯 CPU 环境下可达到约 20 FPS，满足部分实时检测场景需求。若部署到带 NPU 的嵌入式板（如 RK3588），预期可提升至 30-60 FPS。

---

### 四、今日遇到的问题与解决

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| `ModuleNotFoundError: No module named 'onnxruntime'` | 终端未激活虚拟环境 | 执行 `source venv/bin/activate` |
| `pip install nump` 报错 | 拼写错误 | 修正为 `numpy` |
| `pip install onnxslm` 报错 | 拼写错误 | 修正为 `onnxsim` |
| `onnxruntime-tools` 安装失败 | Python 3.9 兼容性问题 | 跳过该包，不影响核心功能 |

### 五、关键代码清单

| 文件 | 功能 |
|------|------|
| `export.py` | YOLOv10-N 导出 ONNX |
| `benchmark.py` | ONNX Runtime 基准测试（预热 + 100 次计时 + FPS 计算） |
