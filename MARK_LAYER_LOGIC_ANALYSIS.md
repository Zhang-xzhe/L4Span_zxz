# MARK 层逻辑分析报告

## 执行模式总结

### ✅ 完全是数据驱动的架构

**结论：MARK 层的所有函数都是数据驱动的，没有定时触发的函数。**

---

## 主要触发机制

### 1. **数据包驱动（Packet-Driven）**

所有核心逻辑都是由数据包的到达触发的：

#### TX 路径（下行发送）
```cpp
void handle_sdu(byte_buffer sdu, qos_flow_id_t qos_flow_id)
```
- **触发时机**：当有下行数据包从上层（SDAP/5GC）到达时
- **执行内容**：
  - 解析 IP/TCP/UDP 头部
  - ECN 标记决策（基于队列状态）
  - TCP 包追踪（加入 in-flight 队列）
  - 流状态更新
  - DRB 队列管理

#### RX 路径（上行接收）
```cpp
void handle_pdu(byte_buffer pdu, qos_flow_id_t qfi)
```
- **触发时机**：当有上行数据包从下层（RLC/MAC）到达时
- **执行内容**：
  - 处理 TCP ACK（从 in-flight 队列移除已确认包）
  - 计算 RTT
  - 修改 TCP 窗口大小（RWND 调整）
  - AccECN 选项字段更新

### 2. **反馈驱动（Feedback-Driven）**

```cpp
void handle_feedback(mark_utils::delivery_status_feedback feedback, drb_id_t drb_id)
```
- **触发时机**：当从 NR-U 接口收到传输反馈时
- **触发来源**：由另一个 executor（执行器）异步调用
- **执行内容**：
  - 更新队列出队速率（dequeue rate）
  - 预测排队延迟
  - **重新计算标记概率**（make_mark_decision）

**注释原文：**
```cpp
// Handle the feedback from the NR-U interface, it's called by another executor,
// so it won't affect the downlink or uplink traffic performance.
```

---

## 内部函数调用链

### 标记决策更新流程

```
handle_feedback()
    ↓
make_mark_decision()
    ↓
├─ predict_dequeue_rate()      // 预测出队速率
└─ predict_queuing_delay()     // 预测排队延迟
```

这些都是**同步调用**，在 `handle_feedback()` 被触发时执行。

---

## 关键函数分类

### 数据包处理函数（实时路径）
| 函数 | 触发方式 | 执行频率 |
|------|---------|---------|
| `handle_sdu()` | 下行包到达 | 每个下行包 |
| `handle_pdu()` | 上行包到达 | 每个上行包 |
| `drb_queue_update()` | 被 `handle_sdu()` 调用 | 每个下行包 |
| `update_drb_flow_state_tcp()` | 被 `handle_sdu()` 调用 | 每个 TCP 下行包 |

### 反馈处理函数（异步路径）
| 函数 | 触发方式 | 执行频率 |
|------|---------|---------|
| `handle_feedback()` | RLC/MAC 层反馈 | 周期性（由下层决定） |
| `make_mark_decision()` | 被 `handle_feedback()` 调用 | 每次反馈 |
| `predict_dequeue_rate()` | 被 `make_mark_decision()` 调用 | 每次反馈 |
| `predict_queuing_delay()` | 被 `make_mark_decision()` 调用 | 每次反馈 |

### 配置函数（初始化时）
| 函数 | 触发方式 | 执行频率 |
|------|---------|---------|
| `create_tx()` | 初始化 | 一次 |
| `create_rx()` | 初始化 | 一次 |
| `add_drb()` | DRB 建立 | 每个 DRB 一次 |
| `add_mapping()` | QFI 映射 | 每个 QoS 流一次 |
| `set_pdcp_sn_size()` | PDCP 配置 | 每个 DRB 一次 |

---

## 定时器使用情况

### 头文件包含分析
```cpp
#include "srsran/support/timers.h"  // ← 包含了但未使用
```

**搜索结果：**
- ❌ 没有定时器对象实例化
- ❌ 没有周期性任务调度
- ❌ 没有 `timer.run()`、`timer.set()` 等调用

**结论：** `timers.h` 被包含但**未实际使用**，可能是历史遗留或预留接口。

---

## 异步执行模型

### Executor 使用

```cpp
// Handle the feedback from the NR-U interface, it's called by another executor,
// so it won't affect the downlink or uplink traffic performance.
```

**关键点：**
- `handle_feedback()` 由**另一个 executor** 调用
- 这样设计是为了**避免阻塞数据路径**
- 计算密集型的标记决策更新不会影响实时包处理

### 线程安全考虑

**潜在的并发访问：**
1. `handle_sdu()` / `handle_pdu()` - 数据平面线程
2. `handle_feedback()` - 反馈处理线程

**共享数据结构：**
- `drb_flow_state` - 流状态（标记概率等）
- `drb_pdcp_sn_ts` - 队列状态向量
- `tcp_flow_tracking` - TCP 在途包队列

**注意：** 代码中**没有显式的互斥锁**，依赖于 srsRAN 的 executor 模型保证线程安全。

---

## 时间使用方式

### 时间戳获取（非定时触发）

```cpp
auto now = std::chrono::system_clock::now();
auto duration = now.time_since_epoch();
auto ts = std::chrono::duration_cast<std::chrono::microseconds>(duration);
```

**用途：**
- 记录包发送时间（TX timestamp）
- 记录包接收时间（RX timestamp）
- 计算 RTT（`rtt_us = rx_ts - tx_ts`）
- 计算队列延迟

**特点：** 这些都是**被动测量**，不是主动定时触发。

---

## 流活跃性检查（唯一的"时间间隔"逻辑）

```cpp
// flow liveness check
if ((now - rx.get()->drb_flow_state[drb_id].l4s_last_see).count() > 1000000) 
  rx.get()->drb_flow_state[drb_id].have_l4s = false;

if ((now - rx.get()->drb_flow_state[drb_id].classic_last_see).count() > 1000000) 
  rx.get()->drb_flow_state[drb_id].have_classic = false;
```

**说明：**
- **阈值：** 1,000,000 微秒 = 1 秒
- **检查时机：** 每次收到包时检查（不是定时检查）
- **目的：** 如果流超过 1 秒没有新包，标记为不活跃

**这仍然是数据驱动的！** 不是独立的定时任务。

---

## 架构优势

### ✅ 纯数据驱动的好处

1. **低延迟**：
   - 没有轮询开销
   - 没有定时器唤醒延迟
   - 包到达立即处理

2. **资源高效**：
   - CPU 不需要周期性唤醒
   - 没有包时，MARK 层完全空闲
   - 按需计算，避免浪费

3. **可扩展性**：
   - 多流并行处理
   - 反馈处理在独立 executor
   - 数据平面和控制平面解耦

4. **简单清晰**：
   - 函数调用链直观
   - 没有复杂的定时器管理
   - 易于调试和追踪

---

## 与其他层的交互

### 上行数据流（Uplink）
```
SDAP/5GC
    ↓ (SDU)
MARK TX (handle_sdu)
    ↓ (PDU)
PDCP → RLC → MAC
```

### 下行数据流（Downlink）
```
MAC → RLC → PDCP
    ↓ (PDU)
MARK RX (handle_pdu)
    ↓ (SDU)
SDAP/5GC
```

### 反馈流
```
MAC/RLC
    ↓ (Feedback)
MARK (handle_feedback)
    ↓ (Update marking probabilities)
```

---

## 总结

### 回答你的问题：

1. **是否所有函数都是数据驱动的？**
   - ✅ **是的**，所有核心逻辑都由以下事件触发：
     - 数据包到达（TX/RX）
     - 反馈消息到达
     - 配置更新

2. **有没有每间隔多久运行一次的函数？**
   - ❌ **没有**，MARK 层没有定时触发的函数
   - `handle_feedback()` 的调用频率由下层（RLC/MAC）决定，但不是由 MARK 层自己的定时器触发

3. **时间的使用方式：**
   - 仅用于**时间戳记录**和**延迟测量**
   - 流活跃性检查基于"上次见到包的时间"，仍是数据驱动

### 架构特点

- **事件驱动架构**（Event-Driven）
- **零轮询开销**（Zero Polling Overhead）
- **按需计算**（On-Demand Computation）
- **异步反馈处理**（Asynchronous Feedback）

这种设计非常适合高性能网络协议栈，避免了定时器带来的开销和延迟。
