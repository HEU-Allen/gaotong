## 嵌入式硬件方向实习 · Day 3 学习笔记

### 一、今日主题
**推理后端优化**：TensorRT 加速（NVIDIA GPU）+ RKNN Toolkit2 部署（Rockchip NPU）+ 多平台性能对比可视化

---

### 二、上午：TensorRT 优化

**1. TensorRT 四大核心技术**
- **层融合（Layer Fusion）**：将 Conv+BN+ReLU 等多个算子融合为单个 CUDA 核，减少 kernel launch 开销与内存读写。
- **FP16/INT8 精度校准**：利用低精度运算提升吞吐量，同时通过校准最小化精度损失。
- **内核自动调优（Kernel Auto-Tuning）**：针对目标 GPU 架构自动选择最优 CUDA kernel 实现。
- **动态形状（Dynamic Shapes）**：支持运行时变化的输入尺寸，提升部署灵活性。

**2. Colab GPU 实践**
- 环境：Google Colab（Tesla T4，CUDA 13.0）。
- 测试方法：基于 PyTorch YOLOv10-N FP32 推理，对比 CPU 与 GPU 后端性能。
测试结果如下：
<img width="942" height="330" alt="3ef50a7063de61682d9e0a0d5397bdb9" src="https://github.com/user-attachments/assets/03c45cac-0586-4920-b0b1-ccdfbfa303b5" />

| 后端 | 延迟 | FPS | 加速比 |
|------|------|-----|--------|
| CPU（Colab） | 154.20 ms | 6.5 | 1x |
| GPU（Tesla T4） | 12.02 ms | 83.2 | **12.82x** |


- **结果分析**：GPU 相比 CPU 实现 **12.8 倍**加速。若进一步使用 TensorRT FP16/INT8 优化，预期可压缩至 **8 ms/125 FPS**（FP16）或 **5 ms/200 FPS**（INT8），接近 Jetson Orin NX 与 RK3588 NPU 的理论性能。

---

### 三、下午：RKNN Toolkit2 与性能分析

**1. RKNN 模型转换**
- 目标：将 ONNX 模型转换为 RK3588 NPU 可运行的 `.rknn` 格式。
- 标准工作流：
  ```
  rknn.config() → rknn.load_onnx() → rknn.build(do_quantization=True) → rknn.export_rknn()
  ```
- 转换结果：成功生成 `yolov10n_rk3566.rknn`（INT8 量化）。

**2. 遇到的问题与解决**

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| RKNN Toolkit2 安装失败 | Colab 默认 Python 3.12 与 RKNN Toolkit2 2.3.0 存在兼容性冲突 | 使用 Miniconda 创建 Python 3.9 独立环境，隔离依赖后成功安装 |
| 模拟器无法运行 | RKNN Toolkit2 2.3.0 的 `init_runtime(target='simulator')` 已移除平台配置支持 | 记录该限制；这是可以直接在 RK3588 真机上部署 `.rknn` 文件验证 |

**3. 多平台性能对比可视化**
- 在 Mac 本地运行 `platform_compare.py`，生成 `platform_benchmark.png`。
- 对比维度：推理延迟（ms）、吞吐量（FPS）、能效比（FPS/W）。
- 数据汇总（实测 + 计划书预期）：

| 平台                | 延迟     | FPS  | 能效比  | 备注        |
| ----------------- | ------ | ---- | ---- | --------- |
| Mac CPU（FP32）     | 50 ms  | 20.0 | 1.0  | 实测        |
| Colab CPU（FP32）   | 154 ms | 6.5  | 0.3  | 实测        |
| Colab GPU（FP32）   | 12 ms  | 83.2 | 8.3  | 实测        |
| Jetson Orin（FP16） | 8 ms   | 125  | 12.5 | **计划书预期** |
| RK3588 NPU（INT8）  | 5 ms   | 200  | 20.0 | **计划书预期** |

<img width="1470" height="500" alt="Figure_2" src="https://github.com/user-attachments/assets/560abd83-a879-4450-9457-3e17f4b4cf72" />

- **结论**：不同硬件平台需匹配最优推理后端——TensorRT 用于 NVIDIA 生态，RKNN 用于 Rockchip NPU，CoreML 用于 Apple Silicon。RK3588 NPU 在 INT8 量化下能效比最高，适合边缘低功耗部署。

---

### 四、今日关键结论

| 优化方向 | 核心技术 | 适用平台 | 预期收益 |
|----------|----------|----------|----------|
| TensorRT 加速 | 层融合 + FP16/INT8 校准 + 自动调优 | NVIDIA GPU / Jetson | 延迟从 12 ms → 8 ms（FP16） |
| RKNN 部署 | ONNX → RKNN 转换 + INT8 量化 | RK3588 / RK3566 等 NPU | 延迟 5 ms，FPS 200，能效比 20 FPS/W |
| 多平台可视化 | Matplotlib 横向对比 | 全平台 | 直观呈现延迟/FPS/能效三维指标 |

- **核心认知**：模型压缩（Day 2）解决"模型能不能放得下"，推理后端优化（Day 3）解决"模型能不能跑得快"。两者结合，才能实现从"可用"到"好用"的嵌入式部署。

---

### 五、遇到的问题与解决

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| `platform_compare.py` 中文乱码 | Matplotlib 默认无中文字体，Mac 系统中文渲染失败 | 在代码开头配置 `plt.rcParams['font.sans-serif'] = ['PingFang SC', 'Heiti SC']` 并关闭 Unicode 负号 |
| RKNN 模拟器不可用 | RKNN Toolkit2 2.3.0 移除 simulator 平台配置 | 如有RKNN可改用真机部署验证；可以用 RK3588 板子直接烧录测试 |
| Colab Python 3.12 冲突 | RKNN 官方 wheel 未适配 Python 3.12 | Miniconda 创建 Python 3.9 环境，完全隔离依赖 |

---

### 六、今日关键代码清单

| 文件 | 功能 |
|------|------|
| `platform_compare.py` | 多平台推理性能对比可视化（Matplotlib 三图横向对比） |
| `rknn_convert2.py` | ONNX → RKNN 模型转换（含 INT8 量化配置） |
| Colab 笔记本 | PyTorch GPU 基准测试（Tesla T4 FP32 推理） |
| `yolov10n_rk3566.rknn` | 转换产物，待 RK3588 真机部署验证 |

---


