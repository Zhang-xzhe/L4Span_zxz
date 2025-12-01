# DL Scheduler Trace-Based Simulation - Quick Start Guide

## 快速开始

### 1. 生成 Trace 文件

```bash
cd /home/zxz/1Code/L4Span_zxz

# 生成所有类型的trace
python3 scripts/generate_dl_sched_trace.py --type all --slots 2000

# 或者只生成特定类型
python3 scripts/generate_dl_sched_trace.py --type varying --slots 1000
```

### 2. 配置调度器

编辑你的配置文件，添加 trace 文件路径。

**方法 A: 使用提供的示例配置**
```bash
# 直接使用示例配置
./build/apps/gnb/gnb -c configs/l4span/gnb_with_dl_trace.yml
```

**方法 B: 修改现有配置**

在你的 YAML 配置文件中添加：

```yaml
expert_execution:
  scheduler:
    dl_scheduler_trace_file: "configs/l4span/dl_sched_varying_trace.csv"
```

### 3. 编译项目

```bash
cd /home/zxz/1Code/L4Span_zxz

# 重新编译
cmake --build build -j$(nproc)
```

### 4. 运行验证

```bash
# 启动 gNB（使用trace模式）
./build/apps/gnb/gnb -c configs/l4span/gnb_with_dl_trace.yml

# 在日志中查找trace应用信息
grep "Using trace MCS" /tmp/gnb_trace.log
grep "Loaded.*scheduler trace" /tmp/gnb_trace.log
```

## 预期输出

启动时应该看到：

```
[INFO] [SCHED] Loaded 1000 scheduler trace samples from 'configs/l4span/dl_sched_varying_trace.csv' (1001 lines processed)
[INFO] [SCHED] DL scheduler trace-based mode enabled with 1000 samples
```

运行时应该看到（如果启用了 DEBUG 日志）：

```
[DEBUG] [SCHED] ue=1 rnti=0x4601: Using trace MCS=16 TBS=5376 (slot=0)
[DEBUG] [SCHED] ue=1 rnti=0x4601: Using trace MCS=20 TBS=14112 (slot=50)
```

## Trace 文件类型

### 1. 固定 Trace (Constant)
- **文件**: `dl_sched_constant_trace.csv`
- **用途**: 基准测试，固定 MCS 和 TBS
- **场景**: 验证系统吞吐量上限

### 2. 变化 Trace (Varying)
- **文件**: `dl_sched_varying_trace.csv`
- **用途**: 模拟信道质量变化
- **场景**: 测试链路自适应性能

### 3. 移动 Trace (Mobility)
- **文件**: `dl_sched_mobility_trace.csv`
- **用途**: 模拟用户移动和切换
- **场景**: 测试系统鲁棒性

## 验证 Trace 工作

### 检查 MCS 分布

```bash
# 统计trace中的MCS分布
awk -F',' 'NR>1 {mcs[$2]++} END {for (m in mcs) print "MCS", m":", mcs[m]}' \
    configs/l4span/dl_sched_varying_trace.csv | sort -n
```

### 查看 TBS 统计

```bash
# 计算平均TBS
awk -F',' 'NR>1 {sum+=$3; count++} END {print "Average TBS:", sum/count, "bytes"}' \
    configs/l4span/dl_sched_varying_trace.csv
```

### 重传率统计

```bash
# 统计重传率
awk -F',' 'NR>1 {total++; if($4==1) retx++} END {print "Retransmission rate:", (retx/total)*100"%"}' \
    configs/l4span/dl_sched_varying_trace.csv
```

## 故障排除

### 问题 1: Trace 文件未加载

**症状**: 日志中没有 "Loaded.*scheduler trace" 消息

**解决**:
1. 检查配置文件路径是否正确
2. 确认trace文件存在且可读
3. 验证YAML语法正确（缩进）

### 问题 2: MCS/TBS 未被替换

**症状**: 日志中没有 "Using trace MCS" 消息

**解决**:
1. 启用DEBUG日志: `sched_level: debug`
2. 检查trace文件格式是否正确
3. 确认有数据流量（需要UE连接）

### 问题 3: 编译错误

**症状**: 找不到 scheduler_trace.h

**解决**:
```bash
# 确认文件存在
ls include/srsran/scheduler/scheduler_trace.h
ls lib/scheduler/scheduler_trace.cpp

# 清理后重新编译
rm -rf build
cmake -B build
cmake --build build -j$(nproc)
```

## 高级用法

### 自定义 Trace 生成

修改 `scripts/generate_dl_sched_trace.py` 中的参数：

```python
# 修改MCS范围
if snr < 10:
    mcs = 5  # 低SNR使用低MCS
elif snr < 20:
    mcs = 15  # 中等SNR
else:
    mcs = 25  # 高SNR使用高MCS

# 修改重传概率
retx_prob = max(0.01, min(0.3, (25 - snr) / 50))
```

### 多UE场景（未来扩展）

目前实现是单UE，如需多UE支持：

1. 在trace文件中添加 `ue_id` 列
2. 修改 `dl_scheduler_trace_manager` 支持UE索引
3. 每个UE使用独立的trace文件

### 从真实日志提取 Trace

```python
# 示例: 从srsRAN日志提取
def parse_srsran_log(log_file):
    with open(log_file, 'r') as f:
        for line in f:
            if 'PDSCH' in line and 'mcs=' in line:
                # 提取 slot, mcs, tbs
                # 写入trace文件
                pass
```

## 性能影响

- **CPU开销**: 每slot增加约 <1μs（trace查找）
- **内存开销**: ~1KB per 1000 samples
- **延迟**: 无额外延迟（trace预加载）

## 相关文件

- **头文件**: `include/srsran/scheduler/scheduler_trace.h`
- **实现**: `lib/scheduler/scheduler_trace.cpp`
- **集成点**: `lib/scheduler/ue_scheduling/ue_cell_grid_allocator.cpp`
- **生成工具**: `scripts/generate_dl_sched_trace.py`
- **文档**: `configs/l4span/DL_SCHEDULER_TRACE_README.md`

## 联系与支持

如有问题，请检查：
1. 详细文档: `configs/l4span/DL_SCHEDULER_TRACE_README.md`
2. srsRAN官方文档
3. 代码注释
