一、ARMSOC架构笔记（核心知识点）
1. 什么是 ARM SoC
SoC（System on Chip） = 把整个系统放到一颗芯片里。不同于你 STM32（MCU，微控制器），ARM SoC 通常指 应用处理器级别的芯片（如手机里的骁龙、树莓派的 BCM2837、全志 H3 等）。
表格
对比项	  STM32（MCU）	       ARM SoC（如 Cortex-A 系列）
核心	    Cortex-M 系列	     Cortex-A 系列
主频	    几十~几百 MHz	     几百 MHz ~ 几 GHz
内存	    片上 SRAM（KB~MB级）外挂 DDR（GB级）
存储	    Flash 直接执行	     需从 eMMC/SD/NAND 加载到 DDR
操作系统	裸机/RTOS	         Linux/Android
启动方式	上电即跑	           Bootloader → Kernel → Rootfs
2. ARM SoC 典型架构组成
plain
┌─────────────────────────────────────┐
│         Application Processor       │
│    (Cortex-A72/A53/A76 等 ARM 核)    │
├─────────────────────────────────────┤
│  NEON/VFP (浮点/ SIMD)  │  L1/L2 Cache │
├─────────────────────────────────────┤
│           CoreSight (调试)           │
├─────────────────────────────────────┤
│  GIC (通用中断控制器)  │  Timer (定时器) │
├─────────────────────────────────────┤
│         AMBA 总线 (AXI/AHB/APB)      │
├─────────────────────────────────────┤
│  GPU │ VPU │ ISP │ USB │ DDR Ctrl   │
│  SDIO│ UART│ SPI │ I2C│ GMAC 等     │
└─────────────────────────────────────┘
3. 关键组件详解
（1）处理器核心
Cortex-A 系列：按性能分大核（A7x）+ 小核（A5x），组成 big.LITTLE 架构，平衡性能与功耗
ARMv8/ARMv9 架构：64位执行状态（AArch64），支持虚拟化、安全扩展（TrustZone）
（2）AMBA 总线
AXI：高速总线，连接 DDR、GPU 等
AHB：中速，连接 DMA、USB 等
APB：低速，连接 UART、SPI、I2C、GPIO 等外设
（3）内存架构
L1 Cache：每个核独立（I-Cache + D-Cache）
L2 Cache：多核共享
L3 Cache：部分高端 SoC 有
DDR 控制器：接外部 DDR3/DDR4/LPDDR4，SoC 必须有的部件
（4）启动流程（Boot Sequence）
plain
上电 → BootROM (固化在芯片内)
  → 从 SD/eMMC/SPI-NOR 加载 SPL/FSBL (第一阶段)
  → 加载 U-Boot (第二阶段 Bootloader)
  → U-Boot 加载 Linux Kernel + Device Tree
  → Kernel 挂载 Rootfs → 进入用户空间
（5）时钟与电源管理
PLL（锁相环）：从外部晶振生成各模块所需时钟
PMU：电源域划分，支持 DVFS（动态调频调压）
（6）TrustZone 安全扩展
世界分为 Secure World 和 Normal World
安全启动（Secure Boot）：从 BootROM 开始链式校验签名
4. 与嵌入式开发的关联
设备树（Device Tree）：ARM SoC 跑 Linux 时，用 .dts 文件描述硬件，解决"同内核不同板子"的问题
驱动模型：Linux 的 platform_driver 对接 SoC 上的各种控制器
交叉编译：在 x86 电脑上编译 ARM 可执行文件（aarch64-linux-gnu-gcc）
