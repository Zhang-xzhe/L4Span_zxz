# MARK 层定时触发机制实现方案

## 需求分析

需要实现一个每毫秒触发一次的定时器，用于：
1. 检查当前 RLC 队列长度和发送速率
2. 生成已收到 TCP 包的 ACK 并递交给上层

## 设计方案

### 1. 定时器集成

由于 MARK 层当前是纯数据驱动的，添加定时器需要：

#### 选项 A：使用 srsRAN 的 timer_manager（推荐）
- 优点：与现有框架集成
- 缺点：需要 timer_manager 实例和 executor

#### 选项 B：使用独立线程
- 优点：独立运行，不依赖其他组件
- 缺点：增加线程开销，需要线程同步

### 2. 实现架构

```
┌─────────────────────────────────────────┐
│      mark_entity_impl                   │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │  Periodic Timer (1ms)            │  │
│  │  - check_rlc_queue_and_rate()    │  │
│  │  - generate_tcp_acks()           │  │
│  └──────────────────────────────────┘  │
│                                         │
│  Data-driven path (existing):           │
│  - handle_sdu() for TX                  │
│  - handle_pdu() for RX                  │
│  - handle_feedback()                    │
└─────────────────────────────────────────┘
```

### 3. 关键功能实现

#### 3.1 检查 RLC 队列长度和发送速率

需要添加接口到 RLC 层获取：
- 当前队列中的包数量
- 当前队列大小（字节）
- 发送速率（bytes/sec 或 packets/sec）

#### 3.2 生成 TCP ACK

需要实现：
- 根据收到的 TCP 包生成 ACK
- 构造正确的 TCP/IP 头部
- 通过上层接口发送 ACK

## 代码实现

### 方案 1：基于 timer_manager（与 srsRAN 集成）

需要修改的文件：
1. `mark_entity_impl.h` - 添加定时器成员和回调
2. `mark.h` - 更新接口以接收 timer_manager
3. `mark_factory.cpp` - 传递 timer_manager 实例

### 方案 2：基于独立线程（简单快速）

只需修改：
1. `mark_entity_impl.h` - 添加线程和周期性任务

## 推荐实现

考虑到以下因素：
- 需要快速实现
- 最小化对现有架构的影响
- 易于调试和维护

**建议使用方案 2（独立线程）**，原因：
1. 不需要修改 mark_entity 的创建流程
2. 线程可以在构造函数中启动，析构函数中停止
3. 可以独立控制周期（1ms）
4. 与数据路径完全解耦

## 注意事项

### 线程安全
由于会有多个线程访问共享数据：
- 定时器线程
- 数据包处理线程（TX/RX）
- 反馈处理线程

需要添加互斥锁保护：
- `tcp_flow_tracking`
- `five_tuple_to_drb`
- `drb_flow_state`

### 性能影响

1ms 定时器会带来一定开销：
- CPU 唤醒频率：1000 Hz
- 每次检查需要遍历流状态

优化建议：
- 如果没有活跃流，跳过处理
- 使用条件变量而非忙等待
- 可配置的周期（1ms 可能太频繁）

### RLC 接口

需要确认 RLC 层是否提供：
```cpp
struct rlc_queue_status {
  size_t queue_bytes;
  size_t queue_packets;
  double tx_rate_bps;
  double tx_rate_pps;
};

virtual rlc_queue_status get_queue_status(drb_id_t drb_id) = 0;
```

如果没有，需要添加这个接口。
