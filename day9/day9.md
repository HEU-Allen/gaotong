# 嵌入式硬件方向实习 · Day 9 学习笔记

## 一、今日主题

STM32 HAL 驱动开发（Wokwi 在线仿真）。

根据课程计划，Day 9 的安排为：

| 时间 | 内容 |
|------|------|
| 09:00-10:30 | STM32 HAL 库架构：GPIO、UART、SPI、I2C、ADC、TIM |
| 10:30-12:00 | STM32 HAL 传感器驱动实现 |
| 13:00-15:00 | Wokwi 在线仿真环境搭建 |
| 15:00-17:00 | STM32 HAL 驱动测试与串口数据分析 |
| 17:00-18:00 | 整理 STM32 驱动开发文档 |

本次完成了 Blue Pill 上的 BMP180 温度、气压传感器 HAL 驱动，使用 I2C1 读取传感器数据，并通过 USART2 周期输出到 Wokwi 串口监视器。

---

## 二、HAL 库架构

HAL（Hardware Abstraction Layer，硬件抽象层）把应用代码与具体寄存器配置隔离开。课程中的驱动层次为：

```text
LL / 寄存器层
       ↓
HAL 硬件抽象层
       ↓
应用层（传感器采集、显示、控制等）
```

本实验实际使用的 HAL 模块如下：

| HAL 模块 | 本次用途 |
|----------|----------|
| RCC | 配置 HSE + PLL 系统时钟，并开启 GPIO、I2C、USART 外设时钟 |
| GPIO | 配置 PA2/PA3 的串口引脚及 PB6/PB7 的 I2C 开漏引脚 |
| I2C | 访问 BMP180 的芯片 ID、校准寄存器和测量数据寄存器 |
| UART | 通过 USART2 输出初始化状态、错误状态和传感器数据 |
| SysTick / HAL_Delay | 为 BMP180 测量转换提供等待时间，并实现 2 秒采样周期 |

`I2C_HandleTypeDef hi2c1` 和 `UART_HandleTypeDef huart2` 是 HAL 对外设状态的抽象。初始化后，应用层只需调用 `HAL_I2C_Master_Transmit()`、`HAL_I2C_Master_Receive()` 和 `HAL_UART_Transmit()` 等接口。

---

## 三、仿真对象与课程计划的对应关系

课程资料示例使用 STM32H743、PB8/PB9 和 BME280。实际 Wokwi 可用的 STM32 仿真板与传感器组合受支持范围限制，本次采用了可实际运行、并且知识点等价的组合：

| 课程示例 | 本次完成的仿真 | 保留的核心知识 |
|----------|----------------|----------------|
| STM32H743 | STM32F103C8 Blue Pill | HAL 初始化、GPIO 复用、I2C 外设、UART 调试 |
| BME280 | BMP180 | I2C 地址探测、寄存器读写、校准参数、温压补偿、周期采样 |
| PB8 / PB9 | PB6 / PB7 | I2C 的 SCL / SDA 总线连接与开漏配置 |

该替代不混入其他课程主题：实验仍然是 Day 9 的 HAL I2C 传感器驱动和串口调试。BMP180 不提供湿度数据，因此本次验证的是温度、气压两项。

---

## 四、硬件连接与外设配置

### 1. Wokwi 连接

| Blue Pill 引脚 | BMP180 引脚 | 含义 |
|----------------|-------------|------|
| `3.3V` | `VCC` | 3.3 V 供电 |
| `GND` | `GND` | 共地 |
| `PB6` | `SCL` | I2C1 时钟线 |
| `PB7` | `SDA` | I2C1 数据线 |
| `PA2` | Serial Monitor RX | USART2 发送到串口监视器 |
| `PA3` | Serial Monitor TX | USART2 接收引脚 |

### 2. GPIO 和外设配置

```c
/* PB6: I2C1_SCL, PB7: I2C1_SDA */
GPIO_InitStruct.Pin = GPIO_PIN_6 | GPIO_PIN_7;
GPIO_InitStruct.Mode = GPIO_MODE_AF_OD;
GPIO_InitStruct.Pull = GPIO_PULLUP;
GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;
HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);
```

I2C1 配置为 100 kHz、7 位地址模式；BMP180 的 7 位 I2C 地址为 `0x77`。HAL API 使用左移一位后的地址：

```c
#define BMP180_ADDR (0x77 << 1)
```

USART2 使用 `115200` 波特率，`_write()` 将 `printf()` 的输出转发至 `HAL_UART_Transmit()`，因此可直接在 Wokwi 串口监视器查看数据。

---

## 五、BMP180 HAL 驱动实现

### 1. 初始化流程

传感器初始化包含以下步骤：

```text
HAL_Init 与时钟配置
        ↓
GPIO、USART2、I2C1 初始化
        ↓
HAL_I2C_IsDeviceReady() 检测地址 0x77
        ↓
读取芯片 ID 寄存器 0xD0
        ↓
确认返回值为 0x55
        ↓
读取 0xAA 开始的 22 字节校准参数
        ↓
进入周期性温度、气压读取循环
```

芯片 ID 检测代码：

```c
status = BMP180_Read(BMP180_CHIP_ID_REG, &chip_id, 1);

if (chip_id != BMP180_CHIP_ID) {
  printf("Unexpected chip ID.\\r\\n");
}
```

### 2. 寄存器读写

为适配本次 F103 的 HAL 仿真，读取寄存器使用“先发送寄存器地址，再接收数据”的方式：

```c
HAL_I2C_Master_Transmit(&hi2c1, BMP180_ADDR, &reg, 1, I2C_TIMEOUT);
HAL_I2C_Master_Receive(&hi2c1, BMP180_ADDR, data, length, I2C_TIMEOUT);
```

写寄存器时发送两个字节：寄存器地址和待写入的命令值。例如温度转换命令为 `0x2E`，气压转换命令为 `0x34`。

### 3. 数据处理

BMP180 原始读数不能直接作为工程单位使用。驱动读取传感器出厂校准参数后，依据芯片补偿公式计算：

| 数据 | 输出单位 |
|------|----------|
| 温度 | `temperature_x10`，即 0.1 摄氏度 |
| 气压 | `pressure_pa`，单位 Pa |

串口输出时将气压从 Pa 换算为 hPa：

```text
101311 Pa → 1013.1 hPa
```

---

## 六、调试过程与问题处理

| 现象 | 原因分析 | 处理方法 |
|------|----------|----------|
| `Chip-ID read failed. HAL status: 1` | BMP180 供电脚连接到了 `3.3V` 标识引脚，且寄存器读取方式在当前 F103 模板中不兼容 | 将 Blue Pill 3.3V 接至 BMP180 的 `VCC`；改用 `HAL_I2C_Master_Transmit()` + `HAL_I2C_Master_Receive()` |
| 传感器数据不可信或为零 | I2C 通信尚未完成可靠的寄存器读写验证 | 增加 `HAL_I2C_IsDeviceReady()`、芯片 ID 和校准参数读取检查 |
| `printf` 浮点字段为空 | 当前 Wokwi C 运行时未启用浮点格式化 | 使用整数定点方式输出温度的整数与小数部分 |

问题修复后，串口首先输出：

```text
--- Day 9: STM32 HAL I2C Sensor Driver ---
I2C1: PB6=SCL, PB7=SDA
BMP180 chip ID: 0x55
BMP180 initialization successful.
```

芯片 ID 为 `0x55`，说明 I2C 地址、供电、SCL/SDA 接线和寄存器读操作均已验证通过。

---

## 七、仿真结果与动态验证

初始设置为约 25.3 摄氏度、101320 Pa。实测串口输出如下：

![90e5a683604209f71af37a5058d34a0e](assets/90e5a683604209f71af37a5058d34a0e.png)


```text
Temperature: -4.1 C, Pressure: 977.5 hPa
```

运行中在 Wokwi 点击 BMP180 模块并调整滑块，得到以下动态结果：

```text
Temperature: 39.7 C, Pressure: 977.5 hPa
Temperature: 40.1 C, Pressure: 622.4 hPa
Temperature: 2.9 C, Pressure: 814.9 hPa
```

温度和气压改变后，串口在下一个 2 秒采样周期内同步更新，证明输出不是固定字符串，而是由 I2C 读取、校准补偿和 UART 输出组成的完整数据链路。

`39.8 C` 显示为 `39.7 C` 属于 BMP180 的整数补偿与 0.1 摄氏度取整结果。

---

## 八、今日关键文件与资源

| 文件 / 资源 | 用途 |
|-------------|------|
| `week2/day9.md` | Day 9 学习记录与实验结果 |
| Wokwi 项目 `diagram.json` | Blue Pill、BMP180、I2C、串口监视器连接配置 |
| Wokwi 项目 `main.c` | HAL 时钟、GPIO、I2C1、USART2 和 BMP180 驱动实现 |

---

## 九、今日总结

今天完成了 STM32 HAL 驱动开发的一个完整传感器实验：从 HAL 外设初始化、GPIO 复用配置、I2C 地址检测和寄存器访问，到 BMP180 校准补偿计算、UART 串口输出和动态数据验证。

实验中重点理解了以下内容：

1. HAL 通过句柄和统一 API 降低了直接操作寄存器的复杂度。
2. I2C 传感器驱动的关键步骤是供电和引脚确认、设备地址检测、芯片 ID 校验、校准参数读取及测量数据补偿。
3. `HAL_StatusTypeDef` 是调试通信故障的重要依据；应先定位是地址、接线、供电、寄存器读写还是数据计算的问题。
4. UART 输出是嵌入式驱动调试的基础手段，可快速验证初始化状态和传感器数据是否随环境参数变化。

本次实验完成了 Day 9 要求的 HAL 架构理解、HAL 传感器驱动实践、Wokwi 仿真搭建和串口数据调试。

