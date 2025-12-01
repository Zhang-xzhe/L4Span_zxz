# DL Scheduler Trace-Based Simulation

## 概述

此功能允许使用真实采集的下行调度trace（包含MCS、TBS、重传信息）来驱动调度器，实现基于真实信道条件的仿真。

## 功能特性

- ✅ **MCS 替换**：使用 trace 中的 MCS 值替代 CQI 计算的 MCS
- ✅ **TBS 替换**：直接使用 trace 中的 TBS（传输块大小）
- ✅ **重传控制**：根据 trace 决定是否需要重传及重传次数
- ✅ **HARQ 管理**：可指定 HARQ 进程 ID
- ✅ **循环播放**：trace 自动循环，支持长时间仿真

## Trace 文件格式

### CSV 格式
```csv
# slot_index, mcs, tbs_bytes, needs_retx, retx_count, harq_id
0, 16, 5376, 0, 0, 0
1, 16, 5376, 0, 0, 1
2, 12, 3752, 0, 0, 2
3, 12, 3752, 1, 1, 0
4, 10, 2856, 1, 2, 0
```

### 字段说明

| 字段 | 类型 | 范围 | 说明 |
|------|------|------|------|
| `slot_index` | uint | 0-10239 | 时隙索引（SFN内） |
| `mcs` | uint | 0-28 | MCS索引 (PDSCH) |
| `tbs_bytes` | uint | >0 | 传输块大小（字节） |
| `needs_retx` | bool | 0/1 | 是否需要重传 |
| `retx_count` | uint | 0-4 | 重传次数 (0=首次传输) |
| `harq_id` | uint | 0-15 | HARQ进程ID (可选) |

## 使用方法

### 1. 生成 Trace 文件

#### 方法 A: 使用脚本生成模拟 trace

```bash
cd /home/zxz/1Code/L4Span_zxz

# 生成所有类型的 trace
python3 scripts/generate_dl_sched_trace.py --type all

# 生成固定 MCS/TBS 的 trace
python3 scripts/generate_dl_sched_trace.py --type constant \
    --mcs 20 --tbs 14112 --retx-prob 0.03 --slots 2000

# 生成变化的 MCS trace (模拟信道变化)
python3 scripts/generate_dl_sched_trace.py --type varying --slots 5000

# 生成移动场景 trace (模拟切换)
python3 scripts/generate_dl_sched_trace.py --type mobility --slots 3000
```

#### 方法 B: 从真实测量转换

如果你有真实的日志数据，修改脚本中的 `parse_real_trace()` 函数：

```python
def parse_real_trace(input_file, output_file):
    with open(input_file, 'r') as fin, open(output_file, 'w') as fout:
        writer = csv.writer(fout)
        writer.writerow(['# slot_index', 'mcs', 'tbs_bytes', 'needs_retx', 'retx_count', 'harq_id'])
        
        for line in fin:
            # 解析你的日志格式
            # 提取: slot, mcs, tbs, crc_result, harq_id, retx_count
            # 写入 trace 文件
            pass
```

### 2. 配置调度器使用 Trace

#### 修改 gNB 配置文件

在你的 gNB YAML 配置中添加：

```yaml
# configs/l4span/gnb_with_trace.yml
cell_cfg:
  # ... 其他配置 ...

expert_execution:
  scheduler:
    # 启用 trace-based 调度
    dl_scheduler_trace_file: "configs/l4span/dl_sched_varying_trace.csv"
```

#### 或通过代码配置

```cpp
scheduler_expert_config sched_cfg;
// ... 其他配置 ...
sched_cfg.dl_scheduler_trace_file = "configs/l4span/dl_sched_varying_trace.csv";
```

### 3. 运行和验证

启动 gNB：

```bash
./build/apps/gnb/gnb -c configs/l4span/gnb_with_trace.yml
```

查看日志输出：

```
[INFO] [SCHED] Loaded 1000 scheduler trace samples from 'configs/l4span/dl_sched_varying_trace.csv'
[DEBUG] [SCHED] ue=1 Using trace MCS=16 TBS=5376 (slot=0)
[DEBUG] [SCHED] ue=1 Using trace MCS=20 TBS=14112 (slot=50)
[INFO] [SCHED] ue=1 HARQ retransmission triggered by trace (retx_count=1)
```

## Trace 类型说明

### 1. 固定 Trace (Constant)
- **用途**：基准测试，验证系统吞吐量
- **特点**：固定 MCS 和 TBS，可配置重传概率
- **文件**：`dl_sched_constant_trace.csv`

### 2. 变化 Trace (Varying)
- **用途**：模拟信道质量周期性变化
- **特点**：MCS 随模拟 SNR 变化 (0-28)
- **文件**：`dl_sched_varying_trace.csv`

### 3. 移动 Trace (Mobility)
- **用途**：模拟用户移动和切换场景
- **特点**：包含多个阶段 (好信号→劣化→切换→恢复)
- **文件**：`dl_sched_mobility_trace.csv`

## 工作原理

### Trace 替换流程

```
正常调度流程:
CQI报告 → 计算MCS → 计算PRB数 → 计算TBS → 分配资源

Trace-based调度流程:
读取Trace → 使用Trace MCS → 使用Trace TBS → 分配资源
           ↓
       跳过CQI计算
```

### 代码集成点

1. **Trace 加载**：`dl_scheduler_trace_manager` 在初始化时加载
2. **MCS 替换**：在 `ue_cell::required_dl_prbs()` 中应用
3. **TBS 替换**：在 `ue_cell_grid_allocator::allocate_dl_grant()` 中应用
4. **重传控制**：在 HARQ 反馈处理中应用

## MCS 到 TBS 映射参考

| MCS | 调制 | 码率 | TBS (100PRB,14符号) |
|-----|------|------|---------------------|
| 0   | QPSK | 0.12 | ~712 bytes          |
| 5   | QPSK | 0.37 | ~2280 bytes         |
| 10  | 16QAM| 0.48 | ~4584 bytes         |
| 15  | 16QAM| 0.66 | ~7992 bytes         |
| 20  | 64QAM| 0.74 | ~14112 bytes        |
| 25  | 64QAM| 0.89 | ~21384 bytes        |
| 28  | 64QAM| 0.93 | ~25456 bytes        |

*注：实际 TBS 还取决于 PRB 数量和符号数*

## 高级用法

### 1. 提取真实测量 Trace

从 srsRAN 日志中提取：

```bash
# 提取调度信息
grep "PDSCH.*ue=" gnb.log | \
  awk '{print $slot, $mcs, $tbs}' > measurements.txt

# 转换为 trace 格式
python3 scripts/generate_dl_sched_trace.py --type real \
    --input measurements.txt \
    --output configs/l4span/my_real_trace.csv
```

### 2. 多UE Trace

目前实现针对单个 UE，如需多UE支持，可以：

- 在 trace 文件中添加 `ue_id` 列
- 修改 `dl_scheduler_trace_manager` 支持多UE索引
- 每个 UE 使用独立的 trace 文件

### 3. 动态切换 Trace

```cpp
// 在运行时切换 trace (需要添加接口)
scheduler->set_dl_trace_file("configs/l4span/new_trace.csv");
```

## 调试技巧

### 启用详细日志

```cpp
// 在调度器代码中
logger.set_level(srslog::basic_levels::debug);
```

### 验证 Trace 应用

检查日志中的 MCS/TBS 值是否与 trace 文件一致：

```bash
# 查看调度日志
grep "Using trace MCS" gnb.log

# 对比 trace 文件
head -n 10 configs/l4span/dl_sched_varying_trace.csv
```

### 性能分析

```bash
# 统计平均 TBS
awk -F',' 'NR>1 {sum+=$3; count++} END {print "Avg TBS:", sum/count}' trace.csv

# 统计重传率
awk -F',' 'NR>1 {total++; if($4==1) retx++} END {print "Retx rate:", retx/total*100"%"}' trace.csv
```

## 故障排除

### 问题 1：Trace 文件加载失败

**症状**：日志显示 "Failed to open scheduler trace file"

**解决**：
- 检查文件路径是否正确（相对于运行目录）
- 确认文件权限
- 验证 CSV 格式（逗号分隔，无多余空格）

### 问题 2：MCS/TBS 未被替换

**症状**：调度仍使用 CQI 计算的 MCS

**解决**：
- 确认 trace 已加载（查看 INFO 日志）
- 检查 `is_enabled()` 返回 true
- 验证 slot 索引匹配

### 问题 3：系统性能下降

**症状**：吞吐量低于预期

**解决**：
- 检查 trace 中的 MCS/TBS 是否合理
- 验证重传率不要过高（<10%）
- 确认 TBS 值适合当前 PRB 配置

## 参考

- 3GPP TS 38.214: Physical layer procedures for data
- 3GPP TS 38.321: MAC protocol specification
- srsRAN Scheduler Documentation

## 示例场景

### 场景 1：固定信道质量测试

```bash
python3 scripts/generate_dl_sched_trace.py --type constant \
    --mcs 20 --tbs 14112 --retx-prob 0.01 --slots 10000
```

用途：测试系统在稳定高质量信道下的最大吞吐量

### 场景 2：信道衰落测试

```bash
python3 scripts/generate_dl_sched_trace.py --type varying --slots 5000
```

用途：测试链路自适应算法在时变信道下的性能

### 场景 3：切换场景测试

```bash
python3 scripts/generate_dl_sched_trace.py --type mobility --slots 3000
```

用途：测试系统在用户移动和切换时的鲁棒性
