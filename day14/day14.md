# 嵌入式硬件方向实习 · Day 14 学习笔记

## 一、今日主题

**嵌入式系统安全基础**。

Day 14 的课程内容分为两部分：上午学习 STRIDE 威胁建模和固件安全分析；下午学习 AES-GCM 加密、ECDSA 数字签名、HMAC 消息认证以及 TLS 1.3 的基本概念。

| 时间 | 课程内容 | 本次完成的实验 |
|------|----------|----------------|
| 09:00-10:30 | STRIDE 威胁建模、IoT 设备威胁分析 | 将常见固件风险映射到 STRIDE |
| 10:30-12:00 | 固件安全分析 | 静态扫描危险函数、硬编码凭据、弱加密标记与熵 |
| 13:00-15:00 | AES-GCM、ECDSA 签名 | AES-GCM 篡改检测、HMAC 完整性校验、ECDSA 固件签名验证 |
| 15:00-17:00 | TLS 1.3、证书和 PKI | 学习安全通信链路中的身份验证位置 |

本次代码只处理程序自己创建的教学样本与临时密钥，**不扫描真实设备、不修改固件、不执行攻击操作**。

---

## 二、为什么嵌入式设备也要重视安全

嵌入式系统常常直接控制传感器、电机、门锁、车辆部件或工业设备。若攻击者能够伪造设备身份、修改控制命令或替换升级固件，影响不只是“数据出错”，还可能变成错误动作。

例如，程序中的控制命令是：

```text
set_motor_limit=1200rpm
```

如果这条命令在传输途中被改成更高的转速，而系统没有做认证和完整性校验，设备可能会执行错误命令。因此安全设计的目标并不只是“把内容藏起来”，还包括确认：

```text
消息是谁发的？
内容有没有被改？
固件是不是可信发布者签发的？
设备在异常请求下能否继续正常工作？
```

---

## 三、STRIDE 威胁建模

STRIDE 是把安全风险按六个类别进行思考的方法。它不是某一种工具，而是一张检查清单：面对一个设备、一个通信接口或一个固件升级流程时，逐项询问可能发生什么问题。

| 字母 | 英文 | 中文含义 | 嵌入式场景示例 | 常见防护方式 |
|------|------|----------|----------------|--------------|
| S | Spoofing | 身份伪造 | 假装成合法设备或升级服务器 | 证书、设备密钥、ECDSA 签名 |
| T | Tampering | 数据篡改 | 修改传感器数据、控制命令或固件 | AES-GCM、HMAC、固件哈希 |
| R | Repudiation | 抵赖 | 发送方否认发过危险命令 | 审计日志、时间戳、签名 |
| I | Information Disclosure | 信息泄露 | 固件中暴露 Wi-Fi 密码、密钥或调试信息 | 安全存储、去除硬编码秘密、访问控制 |
| D | Denial of Service | 拒绝服务 | 大量无效请求使设备无法响应 | 限流、超时、看门狗、资源限制 |
| E | Elevation of Privilege | 权限提升 | 普通用户获得管理员或调试权限 | 最小权限、关闭调试接口、安全启动 |

本次实验中发现的硬编码 `password` 属于**信息泄露**；通信数据被修改属于**篡改**；伪造固件发布者属于**身份伪造**。这也是后面使用 AES-GCM、HMAC 和 ECDSA 的原因。

---

## 四、固件静态安全检查

### 1. 静态检查是什么

静态检查指不运行设备、不刷写固件，而是直接查看源码或固件字节中是否存在明显风险标记。它适合在开发阶段较早地发现问题。

本次程序统计了四类信息：

1. **SHA-256 哈希值**：固件字节的“指纹”。同一份内容应得到同一个哈希；内容改变后哈希通常会完全不同。
2. **香农熵（Shannon entropy）**：描述字节分布的均匀程度，范围通常是 `0~8 bits/byte`。高熵可能说明数据经过压缩或加密，但不是漏洞证据。
3. **危险 C 函数标记**：如 `strcpy`、`sprintf`、`gets`、`scanf`。
4. **硬编码凭据与弱密码学标记**：如 `password = "..."`、`MD5`、`RC4`。

### 2. 实验代码

文件：[day14_firmware_audit.py](day14_firmware_audit.py)

运行命令：

```bash
cd /Users/whl/gaotong/week3/day14
python3 day14_firmware_audit.py
```

程序中的样本是人为构造的，故意包含下列问题，目的是验证扫描逻辑：

```c
strcpy(dst, src);
password = "demo-only-not-a-real-secret"
legacy_integrity=MD5
network_cipher=RC4
```

### 3. 实际运行结果

```text
Size: 199 bytes
SHA-256: 4176f1c0a172d831b8d0b06632d3e13eaf0a64724630b7433fca92b799e3c61f
Shannon entropy: 5.33 bits/byte
Findings: 4

[1] HIGH - unsafe C function: strcpy
[2] CRITICAL - hard-coded credential: password = "demo-only-not-a-real-secret"
[3] MEDIUM - deprecated cryptography marker: MD5
[4] MEDIUM - deprecated cryptography marker: RC4
```

### 4. 结果解释与修改方向

| 发现 | 风险原因 | 建议 |
|------|----------|------|
| `strcpy` | 不知道目标缓冲区长度，可能写越界 | 使用带长度限制的接口，并检查返回值 |
| 硬编码密码 | 任何获得固件的人都可能看到秘密 | 每台设备独立安全配置；不要把生产密码写进源码 |
| MD5 | 已不适合用于安全性决策 | 完整性/摘要使用 SHA-256 等现代算法 |
| RC4 | 已有已知弱点 | 新设计中使用 AES-GCM 等现代方案 |

静态扫描的结论应表述为“**需要人工复核的线索**”，而不是“只要找到字符串就已经证明漏洞”。真实固件审计还需要结合源码逻辑、编译选项、配置、权限设计与实际设备测试。

---

## 五、AES-GCM：保密性与篡改检测

### 1. AES 是什么

AES 是一种对称加密算法：加密方和解密方使用同一把密钥。对称的意思是“双方共享同一个秘密”。

GCM 是 AES 的一种工作模式。它在加密内容的同时生成认证标签（authentication tag），因此不仅能隐藏内容，还能发现内容被改动。

本次使用：

```text
256 位 AES 密钥 + 12 字节 nonce + 明文 + AAD
```

其中：

| 名称 | 作用 |
|------|------|
| 密钥（key） | 加密和解密的核心秘密，不能泄露 |
| nonce | 同一密钥下每次加密必须使用不同值；它不是密码，但不能重复使用 |
| AAD | 附加认证数据；可以不加密，但也会受认证保护，例如设备 ID |
| 认证标签 | GCM 产生的校验信息；密文、AAD 或 nonce 改动后验证会失败 |

### 2. 实验结果

文件：[day14_crypto_demo.py](day14_crypto_demo.py)

运行命令：

```bash
python3 day14_crypto_demo.py
```

实际输出：

```text
Plaintext: set_motor_limit=1200rpm
Ciphertext length (includes authentication tag): 39 bytes
Correct decrypt: set_motor_limit=1200rpm
Tamper check: PASS - modified ciphertext was rejected
```

程序将密文的第一个字节做了一个很小的修改，然后尝试解密。结果被拒绝，说明 AES-GCM 的认证标签发现了篡改。

这对应 STRIDE 中的：

```text
Information Disclosure（防止旁观者读取命令）
Tampering（发现命令被修改）
```

---

## 六、HMAC-SHA256：共享密钥的消息认证

HMAC 可以理解为“带密钥的消息摘要”。发送方和接收方都拥有一把共享密钥：

```text
HMAC 标签 = HMAC(共享密钥, 消息内容)
```

接收方收到消息后，用同一密钥再算一次 HMAC；两个标签相同，则说明消息大概率来自知道该密钥的一方，并且传输后没有被修改。

本次实验输出：

```text
Original message verification: True
Changed message verification : False
```

原消息为：

```text
telemetry:temperature=25.2C
```

修改为：

```text
telemetry:temperature=99.9C
```

后，原标签无法通过校验，所以结果为 `False`。

HMAC 的局限是：双方都需要知道同一个共享密钥。若其中任何一方泄露密钥，攻击者也能生成看似正确的 HMAC。因此密钥管理很重要。

---

## 七、ECDSA：固件发布者签名

ECDSA 是椭圆曲线数字签名算法。它使用一对不同但有关联的密钥：

| 密钥 | 保存位置 | 能做什么 |
|------|----------|----------|
| 私钥 | 厂商安全环境中，绝不随固件发布 | 对固件摘要签名 |
| 公钥 | 设备中或可信证书中 | 验证签名，不能反推出私钥 |

简化的安全升级过程如下：

```text
厂商生成固件 → 计算 SHA-256 摘要 → 用私钥签名
     ↓
设备收到固件和签名 → 计算收到固件的摘要 → 用内置公钥验证
     ↓
验证成功才允许安装；验证失败则拒绝升级
```

本次实验输出：

<img width="454" height="516" alt="image" src="https://github.com/user-attachments/assets/85dcc057-f3a1-46e2-a185-98f71fe34abe" />


```text
Original firmware signature: VALID
Modified firmware signature: REJECTED
```

这说明：签名只对原始固件有效。即使攻击者拿到固件并修改一个字节，也无法在不知道厂商私钥的情况下生成能通过设备验证的新签名。

ECDSA 主要对应：

```text
Spoofing（确认发布者身份）
Tampering（拒绝被改动的固件）
```

---

## 八、TLS、证书与 PKI 的位置

TLS 1.3 用于设备与服务器之间的安全通信。可以把它理解为“网络传输层的安全通道”：它会协商密钥、加密数据、校验数据，并通过证书帮助确认服务器身份。

| 概念 | 初学者理解 |
|------|------------|
| TLS 1.3 | 浏览器访问 HTTPS 网站或设备访问云端时使用的加密通信协议 |
| 证书 | 用来声明“这个公钥属于谁”的电子证明 |
| CA | 证书颁发机构，负责为证书背书 |
| PKI | 公钥、证书、CA、吊销和验证规则组成的信任体系 |
| mbedTLS | 常用于嵌入式 C/C++ 工程的 TLS/密码学库 |

本次 Python 实验没有搭建网络 TLS 服务，但已经分别验证了 TLS 所依赖的几个核心思想：保密、完整性和身份验证。

---

## 九、关键文件

| 文件 | 作用 |
|------|------|
| `day14_firmware_audit.py` | 对教学固件样本做 SHA-256、熵、危险函数、凭据和弱算法标记检查 |
| `day14_crypto_demo.py` | 演示 AES-GCM、HMAC-SHA256、ECDSA 签名验证与篡改拒绝 |
| `day14.md` | Day 14 学习笔记 |

---

## 十、今日总结

Day 14 从“发现风险”到“实施保护”完成了一个小闭环。

首先，使用静态检查在教学固件中定位了 `strcpy`、硬编码密码、MD5 和 RC4 等风险线索；随后通过 AES-GCM 验证了密文被改动会被拒绝，通过 HMAC 验证了消息修改会导致认证失败，并通过 ECDSA 验证了被修改的固件无法通过发布者签名检查。

今后在嵌入式项目中，安全设计应尽量前置：不把秘密写死在固件里，不使用过时加密算法，对通信和升级包进行认证与完整性校验，并在设计阶段用 STRIDE 检查身份伪造、篡改、泄露、拒绝服务和权限问题。
