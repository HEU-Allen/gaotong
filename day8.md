# 嵌入式硬件方向实习 · Day 8 学习笔记

## 一、今日主题

FreeRTOS 内存管理、栈余量监控、中断服务程序（ISR）设计，以及固定优先级实时调度分析。

今天的主要任务是在前一天的传感器、控制和监控任务基础上，增加堆和任务栈监控；使用 Tick Hook 模拟周期性中断，并通过 `xQueueSendFromISR()` 将事件交给普通任务处理；最后使用 Python 建立固定优先级抢占调度模型，分析 CPU 利用率和控制任务的调度抖动。

---

## 二、FreeRTOS 内存与栈配置

首先检查 `FreeRTOSConfig.h` 中与本实验相关的配置：

```c
#define configTOTAL_HEAP_SIZE             ( ( size_t ) ( 100 * 1024 ) )
#define configUSE_TRACE_FACILITY          1
#define configCHECK_FOR_STACK_OVERFLOW    2
#define configUSE_TICK_HOOK               1
```

| 配置项 | 作用 |
|------|------|
| `configTOTAL_HEAP_SIZE` | FreeRTOS 动态内存堆大小，本工程为 100 KB |
| `configUSE_TRACE_FACILITY` | 启用任务状态查询接口，例如 `uxTaskGetSystemState()` |
| `configCHECK_FOR_STACK_OVERFLOW = 2` | 使用更严格的栈溢出检测方式 |
| `configUSE_TICK_HOOK` | 允许每次系统 Tick 中断调用 `vApplicationTickHook()` |

FreeRTOS 中，任务控制块、任务栈、队列和互斥锁等对象通常从 RTOS 堆中动态分配。仅观察当前剩余堆空间并不充分，还需要观察历史最低剩余值和分配次数，才能判断系统是否存在持续泄漏风险。

---

## 三、堆与栈监控任务

在 `main_day8_isr.c` 中创建 `Mem` 任务，每 5 秒输出一次堆统计和任务状态。

核心接口如下：

```c
vPortGetHeapStats( &xHeapStats );
uxTaskCount = uxTaskGetSystemState( xTaskStatus, DAY8_MAX_TASKS, NULL );
```

其中：

| 字段 / 接口 | 含义 |
|------|------|
| `xAvailableHeapSpaceInBytes` | 当前可用堆空间 |
| `xMinimumEverFreeBytesRemaining` | 系统运行以来最小的剩余堆空间 |
| `xNumberOfSuccessfulAllocations` | 成功动态分配次数 |
| `xNumberOfSuccessfulFrees` | 成功释放次数 |
| `usStackHighWaterMark` | 任务运行历史中最小剩余栈空间，单位为 word |

QEMU 运行结果：

```text
heap_free=97488 heap_min=97488 alloc=12 free=0
task=Mem priority=1 stack_free_words=132
task=IDLE priority=0 stack_free_words=102
task=Ctrl priority=4 stack_free_words=86
task=Sensor priority=3 stack_free_words=84
task=Monitor priority=1 stack_free_words=212
task=Tmr Svc priority=5 stack_free_words=221
task=ISRWork priority=2 stack_free_words=216
```

实验分析：

1. 堆总大小为 102400 bytes，当前可用空间为 97488 bytes，说明已分配约 4912 bytes。
2. 多次输出中 `heap_free`、`heap_min`、`alloc` 和 `free` 均保持不变，说明初始化结束后没有持续动态分配，也没有观察到内存泄漏迹象。
3. `free=0` 在本实验中是正常现象：任务、互斥锁和队列均在启动阶段创建，并在系统运行期间长期存在。
4. 所有任务的 `stack_free_words` 都为正。最小值为 `Sensor` 任务的 84 words；在 Cortex-M3 上每个 word 为 4 bytes，因此约保留 336 bytes 栈余量。
5. `usStackHighWaterMark` 是历史最小剩余栈空间，而不是当前瞬时空闲空间。因此它适合用于评估任务栈大小是否安全。

---

## 四、ISR 延后处理实验

### 1. 设计原则

中断服务程序运行时会打断当前任务，因此应尽可能短小。ISR 中不应执行以下操作：

- `printf()` 等耗时 IO；
- `vTaskDelay()` 等阻塞 API；
- 普通互斥锁操作；
- 可能长时间循环或等待的处理逻辑。

正确的模式是：ISR 只记录事件或通知任务，普通任务在任务上下文中完成打印、计算或通信等耗时工作。这种模式称为延后中断处理。

```text
SysTick 中断
    ↓
vApplicationTickHook()
    ↓
vDemoTickHook()
    ↓ xQueueSendFromISR()
ISRWork 任务解除阻塞
    ↓
打印和后续业务处理
```

### 2. Tick Hook 与 ISR 安全 API

工程在 `main.c` 的 `vApplicationTickHook()` 中调用 `vDemoTickHook()`。每次 Tick 到来时，`vDemoTickHook()` 仅计数；当计数达到 `configTICK_RATE_HZ` 时，代表过去约 1 秒，向队列发送一个事件。

核心代码如下：

```c
( void ) xQueueSendFromISR( xIsrEventQueue,
                            &ulEventValue,
                            &xHigherPriorityTaskWoken );

if( xHigherPriorityTaskWoken != pdFALSE )
{
    portYIELD_FROM_ISR( xHigherPriorityTaskWoken );
}
```

`xQueueSendFromISR()` 是专用于中断上下文的 FreeRTOS API。若它唤醒了更高优先级任务，`portYIELD_FROM_ISR()` 可以让调度器尽快切换到该任务。

### 3. QEMU 验证结果

终端中持续出现：

```text
deferred_tick_event=1
```

该输出约每秒一次，且任务列表中出现：

```text
task=ISRWork priority=2 stack_free_words=216
```

这说明事件由 Tick Hook 成功发送，`ISRWork` 任务成功接收并处理。新增 ISR 队列和任务后，堆可用空间由此前的 `98744 bytes` 变为 `97488 bytes`，成功分配次数由 9 增至 12；随后数值稳定。

---

## 五、固定优先级实时调度分析

编写 `day8_realtime.py`，用固定优先级抢占式调度模拟控制系统的周期任务。任务配置如下：

| 任务 | 周期 T | 最坏执行时间 WCET | 优先级 |
|------|-------:|------------------:|-------:|
| Control | 1 ms | 0.3 ms | 4 |
| Sensor | 10 ms | 0.5 ms | 3 |
| Comm | 100 ms | 2.0 ms | 2 |
| Monitor | 1000 ms | 5.0 ms | 1 |

优先级越高，任务越可以抢占低优先级任务。该配置中 `Control` 任务周期最短、优先级最高，符合电机控制任务需要快速响应的实际需求。

### 1. CPU 利用率

总利用率公式为：

```text
U = sum( Ci / Ti )
```

本实验计算为：

```text
U = 0.3 / 1 + 0.5 / 10 + 2 / 100 + 5 / 1000
  = 0.375
```

对于 4 个任务，Liu-Layland RMS 充分可调度上界为：

```text
U_bound = n * ( 2^(1/n) - 1 )
        = 4 * ( 2^(1/4) - 1 )
        ≈ 0.757
```

由于：

```text
0.375 < 0.757
```

因此该任务集合满足 RMS 的充分可调度条件。脚本对前 20 ms 的离散调度仿真结果也未发现截止时间错过。

### 2. 调度与抖动图

生成文件：

```text
day8_realtime.png
```

图的上半部分显示：

1. `Control` 任务以 1 ms 周期反复抢占其他任务。
2. `Sensor`、`Comm` 和 `Monitor` 在被抢占后继续执行，而不是重新开始。
3. 大约 11 ms 后出现较多 `Idle` 时间片，说明 CPU 存在余量。

图的下半部分使用固定随机种子生成 50 个控制任务释放抖动样本，标准差设为 50 us。抖动大多数在 `+/- 50 us` 附近，样本范围约为 `-98 us` 到 `+107 us`。

需要注意：这里的抖动是 Python 人为生成的模拟数据，用于理解调度抖动的分析方式；它不是从 QEMU 或真实硬件测得的实际中断延迟。

---

## 六、今日遇到的问题与解决方法

| 问题 | 原因 | 解决方法 |
|------|------|----------|
| 初始 QEMU 工程没有内存状态输出 | 默认示例未创建监控任务 | 使用 `vPortGetHeapStats()` 和 `uxTaskGetSystemState()` 新建 `Mem` 任务 |
| ISR 中不能直接进行打印 | `printf()` 耗时且 ISR 不应阻塞 | ISR 使用 `xQueueSendFromISR()`，由 `ISRWork` 任务打印 |
| 需要区分普通 API 与 ISR API | 普通队列接口可能进入阻塞或临界区处理 | 在 ISR 中使用带 `FromISR` 后缀的 API |
| 任务栈是否安全难以直接判断 | 仅看配置栈大小无法了解真实使用情况 | 读取 `usStackHighWaterMark`，检查历史最小剩余值 |
| 初始调度图文字重叠 | 20 ms 内时间片过于密集 | 去掉色块内文本，改为使用颜色图例 |

---

## 七、今日关键文件

| 文件 | 功能 |
|------|------|
| `FreeRTOS/.../main_day8_isr.c` | Day 8 专用任务、堆栈监控和 ISR 延后处理实现 |
| `FreeRTOS/.../main.c` | 调用 Tick Hook 中的 `vDemoTickHook()` |
| `FreeRTOS/.../build/gcc/Makefile` | 将构建源文件切换为 `main_day8_isr.c` |
| `day8_realtime.py` | 固定优先级调度和模拟抖动分析脚本 |
| `day8_realtime.png` | 调度时间线和抖动曲线 |

---

## 八、今日总结

今天完成了 FreeRTOS 中内存、栈和中断处理的基础实践。

通过 `vPortGetHeapStats()` 可以持续观察堆使用情况，通过 `uxTaskGetSystemState()` 和 `usStackHighWaterMark` 可以评估各任务的栈余量。实际 QEMU 结果表明，新增内存监控和 ISR 任务后，堆统计值稳定、所有任务仍有正的栈余量，当前配置可以正常运行。

中断实验进一步说明：ISR 的职责是快速确认事件并通知任务，而不是完成复杂业务。使用 `xQueueSendFromISR()` 和 `portYIELD_FROM_ISR()` 将处理延后到 `ISRWork` 任务后，系统能够每秒稳定处理 Tick 事件，同时避免在中断上下文中执行耗时打印。

实时调度分析表明，本次任务集利用率为 37.5%，低于 4 任务 RMS 的 75.7% 充分可调度上界。控制任务获得最高优先级，可以优先满足 1 ms 周期要求；同时系统仍保留空闲时间，为未来增加通信、诊断或更复杂控制算法提供余量。

---

## 九、后续优化方向

1. 使用 GPIO 翻转或 ARM DWT 周期计数器测量真实的中断响应时间和任务抖动。
2. 为队列发送失败添加计数器，验证高频 ISR 场景下是否发生事件丢失。
3. 对每个任务进行响应时间分析，补充 RMS 利用率判定之外的最坏情况验证。
4. 根据实际业务负载继续调整任务栈大小，避免过度分配或栈余量不足。
