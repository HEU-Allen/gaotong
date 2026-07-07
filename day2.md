## 嵌入式硬件方向实习 · Day 2 学习笔记

### 一、今日主题
**嵌入式模型优化三件套**：INT8 动态量化 + 知识蒸馏 + 模型剪枝

### 二、上午：INT8 动态量化实践

**1. 量化操作**
- 使用 `onnxruntime.quantization.quantize_dynamic` 对 YOLOv10-N 进行 INT8 动态量化。
- 模型大小变化：FP32 为 9.5MB → INT8 为 2.7MB，压缩比约 **3.5x**。

**2. 跨平台推理测试**
- **Mac 本地测试**：ONNX Runtime CPUExecutionProvider 未实现 ConvInteger 算子，INT8 模型无法加载，测试失败。
<img width="1126" height="788" alt="image" src="https://github.com/user-attachments/assets/01bf2ba9-cbc6-4061-aa6e-16265ad02e3c" />
- **Google Colab（Linux CPU）测试**：INT8 模型可正常运行，测试结果如下：
<img width="752" height="288" alt="image" src="https://github.com/user-attachments/assets/3807097e-49fb-43e1-aade-e84117521e8a" />
| 指标 | FP32 | INT8 | 变化 |
|------|------|------|------|
| 模型大小 | 9.50 MB | 2.71 MB | 压缩 3.5x |
| 平均延迟 | ~90 ms | ~650 ms | - |
| 理论 FPS | ~11 | ~1.5 | - |

- 结果分析：Colab 服务器 CPU 缺少 VNNI/AMX 加速指令集，INT8 推理速度反而下降。

**3. 结论**
- INT8 量化的模型压缩效果明确（9.5MB → 2.7MB，约 3.5x），但推理加速高度依赖硬件指令集支持。
- 在通用 CPU 上无法体现速度优势；在支持 VNNI 的 Intel 11代+ CPU 或专用 NPU（RK3588、Jetson）上，INT8 可实现 3-4 倍加速。

---

### 三、下午：知识蒸馏与模型剪枝

**1. 知识蒸馏（YOLOv10-S → YOLOv10-N）**
- 加载教师模型 YOLOv10-S（22.2M 参数）与学生模型 YOLOv10-N（2.3M 参数）。
- 蒸馏损失函数：L = α·L_task + (1-α)·T²·KL(σ(z_s/T) || σ(z_t/T))，其中温度 T=4，α=0.5。
- 在随机输入下验证损失计算框架正确性，输出硬损失、软损失与总损失。
- 运行结果如下：
<img width="760" height="542" alt="image" src="https://github.com/user-attachments/assets/984d6498-f6cb-464a-b855-007ee008b7c9" />
- 损失值偏大的原因说明：
  - 输入为随机噪声（`torch.randn`），非真实图片。
  - 输出包含边界框坐标（xywh，数值范围 0-640）、置信度、类别概率，量纲不统一。
  - 仅为单次前向传播计算损失，非训练后的收敛值。
- 实际部署时，需在 COCO 数据集上进行多轮训练，硬损失应使用真实标注（Ground Truth）。

**2. 模型剪枝**

*（1）L1 非结构化剪枝*
- 使用 `torch.nn.utils.prune.global_unstructured`，在所有 Conv2d 层中统一按 L1 范数排序剪枝。
- 遇到的问题与解决：YOLOv10 的卷积层封装在自定义模块（C2f、Conv 等）中，直接遍历 `named_modules()` 无法正确匹配 Conv2d，改用 `modules()` 递归遍历所有子模块解决。
- 统计验证：通过 `module.weight`（property）读取应用 mask 后的参数，而非 `p.data`，正确统计非零参数。
- 剪枝结果：
<img width="570" height="361" alt="image" src="https://github.com/user-attachments/assets/b8ff2fc1-ef5b-4128-b3d3-1be47ca0f085" />
| 指标 | 数值 |
|------|------|
| 原始参数量 | 2,775,520 (2.78M) |
| 非零参数量 | 1,927,766 (1.93M) |
| 稀疏度 | **30.5%** |
| 理论压缩率 | **1.44x** |

*（2）通道剪枝分析*
- 基于卷积核 L1 范数，对 model.0.conv（16 通道）建议剪除 1 个通道（10%）。

---

### 四、今日关键结论

| 优化手段 | 核心效果 | 适用场景 |
|----------|----------|----------|
| INT8 动态量化 | 模型压缩 3.5x，加速需硬件支持 | 嵌入式 NPU（RK3588、Jetson） |
| 知识蒸馏 | 小模型模仿大模型行为，提升精度 | 精度敏感场景 |
| 非结构化剪枝 | 稀疏度 30.5%，需稀疏计算硬件 | NVIDIA Sparse Tensor Core |
| 通道剪枝 | 直接删卷积核，通用硬件友好 | 需配合 Fine-tuning 恢复精度 |

- **非结构化剪枝**：随机位置置零，需要稀疏计算硬件支持（如 NVIDIA Sparse Tensor Core）。
- **通道剪枝**：直接删除整个卷积核，对通用硬件更友好，但需配合重训练（Fine-tuning）恢复精度。
- **实际部署时，通道剪枝 + 重训练是更稳定的方案。**

### 五、今日关键代码清单

| 文件 | 功能 |
|------|------|
| `quantize.py` | ONNX INT8 动态量化 + FP32/INT8 对比测试 |
| `distill.py` | 知识蒸馏损失计算（YOLOv10-S → YOLOv10-N） |
| `prune.py` | L1 非结构化剪枝 + 通道剪枝分析 |
