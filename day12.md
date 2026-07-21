# 嵌入式硬件方向实习 · Day 12 学习笔记

## 一、今日主题

ARM NEON 向量化。

根据课程计划，Day 12 学习 NEON 架构和 NEON C Intrinsics：理解 128 位向量寄存器、`int8x16_t` / `float32x4_t` / `float64x2_t` 等数据类型，并使用加载、存储、加法、乘法与融合乘加指令实现向量化点积和 ReLU。

| 时间 | 内容 |
|------|------|
| 09:00-10:30 | NEON 架构：向量寄存器、数据类型与关键指令 |
| 10:30-12:00 | NEON C Intrinsics：点积、ReLU 与性能对比 |

本机为 Apple Silicon `arm64`，可原生运行 ARM NEON。课程中的 Linux 编译参数 `gcc -O3 -march=armv8-a+simd` 在 macOS 上等价调整为：

```bash
clang -O3 -Wall -Wextra -arch arm64 day12_neon.c -o day12_neon
```

---

## 二、NEON 架构要点

ARMv8-A NEON 提供 32 个 128 位向量寄存器（`v0` 到 `v31`）。同一个寄存器可以按不同数据宽度解释：

| 数据类型 | 单个 128 位寄存器中的元素数 | 用途示例 |
|----------|--------------------------:|----------|
| `int8x16_t` | 16 个 8 位整数 | 图像像素、量化神经网络 |
| `float32x4_t` | 4 个 32 位浮点数 | 卷积、点积、传感器向量计算 |
| `float64x2_t` | 2 个 64 位浮点数 | 高精度数值计算 |

本实验使用 `float32x4_t`，即每次在一个 128 位寄存器中并行处理 4 个 `float`。

---

## 三、核心 NEON C Intrinsics

| Intrinsic | 作用 | 本实验中的含义 |
|-----------|------|----------------|
| `vdupq_n_f32(0.0f)` | 将标量复制到 4 个通道 | 创建四路零累加器 |
| `vld1q_f32(ptr)` | 从内存加载 4 个 `float` | 读取 4 个向量元素 |
| `vfmaq_f32(acc, a, b)` | 四路融合乘加 | `acc += a * b` |
| `vaddvq_f32(v)` | 四路水平求和 | 将向量累加器变为标量结果 |
| `vmaxq_f32(v, zero)` | 四路逐元素取最大值 | 实现 ReLU：`max(v, 0)` |
| `vst1q_f32(ptr, v)` | 将 4 个 `float` 写回内存 | 保存 ReLU 结果 |

点积的向量化核心：

```c
float32x4_t va = vld1q_f32(a + i);
float32x4_t vb = vld1q_f32(b + i);
vector_sum = vfmaq_f32(vector_sum, va, vb);
```

循环每次前进 4 个元素，末尾不足 4 个元素时再由标量循环处理，保证任意长度输入都可正确计算。

---

## 四、实验设计

程序对两个长度为 `1,048,576` 的 `float` 数组进行点积，并重复 300 次以稳定测量执行时间。

### 1. 标量版本

```c
for (int i = 0; i < n; ++i) {
    sum += a[i] * b[i];
}
```

标量版本通过 `#pragma clang loop vectorize(disable)` 禁止编译器自动向量化，因此可作为 NEON Intrinsics 的对照基线。

### 2. NEON 版本

```c
for (; i <= n - 4; i += 4) {
    float32x4_t va = vld1q_f32(a + i);
    float32x4_t vb = vld1q_f32(b + i);
    vector_sum = vfmaq_f32(vector_sum, va, vb);
}
```

每轮计时后都会轻微修改一个输入元素，并在两组测试前重新初始化输入，防止 `-O3` 编译器将重复点积的结果提升到循环外，避免出现失真的 `0 ms` 测试结果。

---

## 五、点积结果

实际运行结果：

```text
Scalar dot: 168.98 ms
NEON dot  : 62.44 ms
Speedup   : 2.71x
```

| 指标 | 标量 | NEON | 结论 |
|------|-----:|-----:|------|
| 点积耗时 | 168.98 ms | 62.44 ms | NEON 约快 2.71 倍 |
| 点积结果 | -5.7280 | -5.7306 | 差值仅 0.002656 |

`float32x4_t` 理论上能同时处理 4 个单精度数，但实际加速低于 4 倍，因为仍存在内存加载、循环控制、向量结果水平求和与尾部标量处理等开销。

两种结果存在微小差异是正常的浮点行为：标量版本从左到右逐个累加，而 NEON 先分 4 路累加、再做水平求和；浮点加法不满足严格结合律，因此舍入顺序不同会带来很小误差。

---

## 六、ReLU 结果与内存带宽

ReLU 定义为：

```text
ReLU(x) = max(x, 0)
```

NEON 实现：

```c
float32x4_t value = vld1q_f32(data + i);
vst1q_f32(data + i, vmaxq_f32(value, zero));
```

实际运行结果：

```text
Scalar ReLU: 18.86 ms
NEON ReLU  : 19.21 ms
ReLU speedup: 0.98x
```

ReLU 没有获得明显加速，原因不是 NEON 失效，而是 ReLU 每个元素只进行一次比较，却必须从内存读取并写回数据。此时性能主要受内存读写带宽和缓存行为限制，计算单元的并行能力无法成为决定因素。

这说明：是否使用 SIMD 不应只看理论并行度，还要判断任务是计算密集型还是内存访问密集型。点积包含大量乘加，属于更适合 SIMD 的计算密集型操作；ReLU 更接近内存带宽受限操作。

---

## 七、运行方法

```bash
cd /Users/whl/gaotong/week3
clang -O3 -Wall -Wextra -arch arm64 day12_neon.c -o day12_neon
./day12_neon
```

---

## 八、关键文件

| 文件 | 用途 |
|------|------|
| `week3/day12_neon.c` | 标量/NEON 点积与 ReLU、计时及结果校验 |
| `week3/day12_neon` | 本机编译生成的可执行文件 |
| `week3/day12.md` | Day 12 实验记录与分析 |

---

## 九、今日总结

Day 12 完成了 ARM NEON 的基础实践。通过 `float32x4_t` 和 `vld1q_f32`、`vfmaq_f32`、`vaddvq_f32` 等 Intrinsics，实现了四路单精度浮点点积，并取得 2.71 倍加速。

同时，ReLU 测试表明 SIMD 并非对所有算法都能产生同等加速。当任务主要受内存读写限制时，向量化计算只能带来很小收益。性能优化必须结合实际测量、算法特点、缓存和内存带宽综合判断。
