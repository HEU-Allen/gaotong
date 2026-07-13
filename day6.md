# Day 6：FreeRTOS 架构与 QEMU 仿真

## 一、今日目标

1. 搭建 ARM Cortex-M3 的 FreeRTOS 交叉编译与 QEMU 仿真环境。
2. 理解任务、调度器、Tick、上下文切换和任务状态。
3. 运行队列与软件定时器示例，验证周期调度。
4. 实现传感器采集、控制、监控三个任务，并用互斥锁保护共享状态。

## 二、开发环境

- 主机：macOS，Apple Silicon（arm64）
- 工作目录：`/Users/whl/gaotong/week2`
- 仿真器：QEMU 11.0.2
- 交叉编译器：Arm GNU Toolchain 15.2.1
- RTOS：FreeRTOS，目标平台为 MPS2 AN385 / Cortex-M3

## 三、FreeRTOS 核心知识点

### 1. 任务与调度器

FreeRTOS 将每个独立执行单元称为任务（Task）。调度器从处于 Ready 状态的任务中选择优先级最高的任务运行。

任务常见状态：

- Running：正在占用 CPU 执行。
- Ready：具备运行条件，等待调度器分配 CPU。
- Blocked：等待延时、队列、信号量或其他事件，不占用 CPU。
- Suspended：被显式挂起，不能被调度。

### 2. Tick 与周期任务

Tick 是系统周期性时钟。`pdMS_TO_TICKS()` 用于把毫秒转换为 Tick 数。

`vTaskDelayUntil()` 适合周期任务：它以固定的唤醒时刻为基准，避免 `vTaskDelay()` 因任务执行时间而逐步漂移。

### 3. 队列与软件定时器

队列用于任务间传递数据。接收任务可在 `xQueueReceive(..., portMAX_DELAY)` 中进入 Blocked 状态，数据到达后再被唤醒。

软件定时器由 FreeRTOS 的 Timer/Daemon Task 执行回调。回调函数不能阻塞，因此队列发送等待时间设为 0。

### 4. 互斥锁与共享状态

多个任务读写同一份控制状态时，需要互斥锁保证一次读取或更新的完整性。

本次使用 `xSemaphoreCreateMutex()` 创建互斥锁，并通过 `xSemaphoreTake()` / `xSemaphoreGive()` 保护共享的传感器值、目标值和控制输出。

## 四、实践记录

### 1. 编译与仿真环境

FreeRTOS 示例目录：

```text
FreeRTOS/FreeRTOS/Demo/CORTEX_MPS2_QEMU_IAR_GCC/build/gcc
```

编译命令：

```zsh
make
```

生成文件：

```text
output/RTOSDemo.out
```

QEMU 运行命令：

```zsh
qemu-system-arm -machine mps2-an385 -cpu cortex-m3 -kernel output/RTOSDemo.out -nographic
```

退出 QEMU：按 `Control + A`，松开后按 `x`。

### 2. 队列与软件定时器实验

原示例包含：

- 发送任务：每 200 ms 向队列发送数值 100。
- 接收任务：收到 100 后打印 `Message received from task`。
- 自动重载软件定时器：每 2 s 向队列发送数值 200。
- 接收任务：收到 200 后打印 `Message received from software timer`。

将任务周期修改为 500 ms，软件定时器周期修改为 3 s 后，仿真输出表现为每约 3 秒出现 6 条任务消息和 1 条定时器消息，验证了周期调度与软件定时器正常工作。

### 3. 三任务控制系统

在 `main_blinky.c` 中实现了共享状态：

```c
typedef struct
{
    uint32_t sensorValue;
    uint32_t setpoint;
    int32_t controlOutput;
} ControlState_t;
```

任务划分：

| 任务 | 优先级 | 周期 | 功能 |
| --- | ---: | ---: | --- |
| Ctrl | 4 | 1 ms | 读取传感器值，计算控制输出 |
| Sensor | 3 | 10 ms | 模拟传感器采样，数值在 0 到 100 间循环 |
| Monitor | 1 | 1000 ms | 读取并打印系统状态 |

控制规律为：

```text
controlOutput = 2 * (setpoint - sensorValue)
```

目标值固定为 50。运行结果示例：

```text
sensor=7 setpoint=50 output=100
sensor=0 setpoint=50 output=-88
sensor=94 setpoint=50 output=-74
sensor=87 setpoint=50 output=-60
```

监控值与控制输出偶尔相差一次采样周期：高优先级控制任务可能先按旧传感器值完成计算，随后传感器任务才更新共享状态。这是任务周期、优先级和调度顺序带来的正常现象。

## 五、遇到的问题与处理

| 问题 | 原因 | 处理方式 |
| --- | --- | --- |
| Homebrew 下载中断 | GitHub Container Registry 的 HTTP/2 连接临时中断 | 使用 `caffeinate` 保持设备唤醒并重试下载 |
| FreeRTOS 下载过大 | `--recurse-submodules` 会递归下载大量不需要的 AWS、网络和加密子模块 | 停止递归下载，仅初始化 `FreeRTOS/Source` 内核子模块 |
| 编译提示找不到 `stdlib.h` | Homebrew 的 `arm-none-eabi-gcc` 不包含完整的 newlib 头文件与库 | 安装 `gcc-arm-embedded`，使用 Arm 官方完整工具链 |
| 监控输出显示 `u`、`d` | 项目自带的轻量版 `printf` 不支持 `%lu`、`%ld` | 增加简单的有符号/无符号整数输出函数，分段打印数值 |

## 六、本次修改文件

- `FreeRTOS/FreeRTOS/Demo/CORTEX_MPS2_QEMU_IAR_GCC/main_blinky.c`
  - 调整任务和定时器周期。
  - 新增互斥锁、共享控制状态和三个周期任务。
  - 新增轻量数字打印函数。
- `FreeRTOS/FreeRTOS/Demo/CORTEX_MPS2_QEMU_IAR_GCC/main_blinky_queue_demo.c`
  - 保留原队列与软件定时器示例的备份。

## 七、今日收获

1. 完成了从 ARM 交叉编译到 QEMU 运行 FreeRTOS 程序的完整流程。
2. 理解了 `vTaskDelayUntil()`、队列、软件定时器和互斥锁的基本用法。
3. 能够依据任务周期和优先级解释调度结果与一次采样延迟。
4. 完成了一个可运行的传感器采集、控制、监控三任务仿真框架。

## 八、下一步

Day 7 将学习 PID 控制理论，并用 Python 完成 PID 控制器仿真与参数调节。
