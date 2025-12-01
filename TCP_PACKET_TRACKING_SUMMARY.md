# TCP 完整包追踪功能实现总结

## 功能概述
在 MARK 层实现了 TCP 数据包的完整副本保存和追踪功能，用于监控在途（in-flight）数据包，直到收到 ACK 确认。

## 修改的文件

### 1. `include/srsran/mark/ip_utils.h`
**新增数据结构：**

```cpp
/// TCP packet information for tracking in flight packets
struct tcp_packet_info {
  uint32_t seq_num;              ///< TCP 序列号
  uint32_t end_seq_num;          ///< 结束序列号 (seq + payload_len)
  uint16_t payload_len;          ///< TCP 载荷长度（字节）
  uint16_t ip_total_len;         ///< IP 包总长度
  int64_t  tx_timestamp_us;      ///< 发送时间戳（微秒）
  uint8_t  ecn_mark;             ///< ECN 标记
  bool     is_retransmission;    ///< 是否为重传包
  
  std::vector<uint8_t> packet_data;  ///< 完整 IP 包副本
};

/// Per-flow TCP tracking state
struct tcp_flow_tracking {
  std::deque<tcp_packet_info> in_flight_packets;  ///< 未确认包队列
  uint32_t last_ack_received;                      ///< 最后收到的 ACK 号
  uint32_t next_expected_seq;                      ///< 下一个期望序列号
  size_t   total_packets_sent;                     ///< 发送包总数
  size_t   total_packets_acked;                    ///< 已确认包总数
  size_t   total_retransmissions;                  ///< 重传总数
  int64_t  last_tx_timestamp_us;                   ///< 最后发送时间戳
  int64_t  last_ack_timestamp_us;                  ///< 最后 ACK 时间戳
};
```

### 2. `include/srsran/mark/mark.h`
**添加追踪映射表：**
```cpp
class mark_rx_pdu_handler {
  // ...existing members...
  
  /// @brief: TCP packet tracking for in-flight packets per flow
  std::unordered_map<ip::five_tuple, ip::tcp_flow_tracking> tcp_flow_tracking;
};
```

### 3. `lib/mark/mark_entity_impl.h` (TX 发送端)
**追踪逻辑：**
- 检测 TCP 数据包（有载荷的数据包，排除 SYN/RST/纯 ACK）
- **复制完整 IP 包数据**到 `packet_data` 向量
- 检测重传（通过序列号匹配）
- 加入在途队列
- 记录统计信息

**关键代码：**
```cpp
// 创建包信息结构
ip::tcp_packet_info pkt_info(tcp_hdr->seq, tcp_payload_len, ipv4_hdr->tot_len, ts.count(), ect);

// 复制完整 IP 包数据
pkt_info.packet_data.resize(ipv4_hdr->tot_len);
memcpy(pkt_info.packet_data.data(), (*sdu_it).data(), ipv4_hdr->tot_len);

// 加入队列
flow_track.in_flight_packets.push_back(std::move(pkt_info));
```

### 4. `lib/mark/mark_entity_rx_impl.h` (RX 接收端)
**ACK 处理逻辑：**
- 检测 ACK 包
- 使用累积 ACK 机制移除已确认的包
- 计算 RTT（往返时延）
- 更新流统计信息

**关键代码：**
```cpp
// 处理累积 ACK
while (!flow_track.in_flight_packets.empty()) {
  auto& front_pkt = flow_track.in_flight_packets.front();
  if (front_pkt.end_seq_num <= ack_num) {
    // 计算 RTT
    int64_t rtt_us = ts_us - front_pkt.tx_timestamp_us;
    
    // 移除已确认的包
    flow_track.in_flight_packets.pop_front();
    flow_track.total_packets_acked++;
  } else {
    break;
  }
}
```

## 功能特性

### ✅ 已实现功能
1. **完整包保存**：保存整个 IP 包的副本（包括 IP 头部、TCP 头部、TCP 载荷）
2. **重传检测**：通过序列号检测重传包
3. **RTT 计算**：基于发送和 ACK 时间戳计算往返时延
4. **流级别追踪**：每个 TCP 流独立追踪
5. **统计信息**：发送包数、确认包数、重传数等

### 📊 数据结构优势
- **内存管理**：使用 `std::vector` 自动管理内存
- **高效查找**：使用 `std::deque` 支持快速队首/队尾操作
- **移动语义**：使用 `std::move` 避免不必要的拷贝

### 💡 使用场景
1. **深度包检测**：可以访问完整包内容进行分析
2. **包级别分析**：查看特定包的 ECN 标记、时延等
3. **重传分析**：追踪哪些包被重传
4. **RTT 监控**：实时监控网络往返时延
5. **调试**：可以导出包数据进行离线分析

## 内存考虑

**每个在途包的内存占用：**
- 元数据：约 40 字节
- 包数据：约 1500 字节（典型 MTU）
- **总计**：约 1540 字节/包

**建议：**
- 监控在途包队列大小
- 对于高速流，考虑设置队列大小上限
- 定期清理长时间未确认的包（超时机制）

## 编译和测试

**编译命令：**
```bash
cd /home/zxz/1Code/L4Span_zxz
cmake --build build -j$(nproc)
```

**调试日志：**
- TX 端：`logger.log_debug("TX TCP packet tracked: seq={}, len={}, pkt_size={}, in_flight={}, flow={}")`
- RX 端：`logger.log_debug("TCP ACK received: seq={}, ack={}, payload_len={}, RTT={} us, ECN={}, flow={}")`

## 后续可能的扩展

1. **超时清理机制**：自动移除长时间未确认的包
2. **包数据压缩**：对于只需要部分数据的场景，可以只保存 TCP 载荷
3. **选择性保存**：根据配置决定是否保存包数据
4. **包数据导出**：将包数据导出为 PCAP 格式用于 Wireshark 分析
5. **流量回放**：使用保存的包数据进行流量重放测试

## 注意事项

⚠️ **重要提示：**
- 这会显著增加内存使用（每个在途包 ~1.5KB）
- 高吞吐场景下需要监控内存使用
- 建议在生产环境中添加包队列大小限制
- 考虑添加配置选项来启用/禁用完整包保存功能
