# PDSCH Trace 生成工具

这个目录包含了从srsRAN日志文件中提取PDSCH TBS信息并生成trace文件的工具。

## 工具说明

### 1. parse_simple_pdsch_trace.py
简化的PDSCH日志解析脚本，专门用于从srsRAN日志中提取TBS信息。

**特点:**
- 支持多种srsRAN日志格式
- 自动填充缺失的时隙
- 生成标准的scheduler trace格式

**使用方法:**
```bash
python parse_simple_pdsch_trace.py gnb_log.txt -o pdsch_trace.csv
```

**参数:**
- `input_log`: 输入的srsRAN日志文件
- `-o, --output`: 输出的trace文件名 (默认: pdsch_trace.csv)
- `--output-dir`: 输出目录 (默认: configs/l4span)

### 2. parse_pdsch_trace.py
完整的PDSCH日志解析脚本，支持更多高级功能。

**特点:**
- 支持HARQ重传检测
- 详细的统计信息
- 灵活的时隙范围选择
- 多种日志模式识别

**使用方法:**
```bash
python parse_pdsch_trace.py gnb_log.txt -o detailed_trace.csv --stats
```

**参数:**
- `input_log`: 输入的srsRAN日志文件
- `-o, --output`: 输出trace文件
- `--min-slot`: 最小时隙索引
- `--max-slot`: 最大时隙索引
- `--stats`: 显示详细统计信息
- `--output-dir`: 输出目录

### 3. generate_dl_sched_trace.py
原有的trace生成工具，用于生成模拟数据。

**使用方法:**
```bash
python generate_dl_sched_trace.py --type all --slots 1000
```

### 4. test_trace_parser.py
测试脚本，用于验证解析器功能。

## 支持的日志格式

脚本能够识别以下srsRAN日志格式:

1. **MAC调度器格式:**
   ```
   [MAC] slot=123 ue=4601 mcs=16 tbs=5376 nof_prb=25
   ```

2. **PHY传输格式:**
   ```
   [PHY] PDSCH transmission slot=123 ue=4601 mcs=16 tbs=5376 harq_id=0
   ```

3. **调度器格式:**
   ```
   [SCHED] DL scheduler slot=123 rnti=4601 mcs=16 tbs_bytes=5376
   ```

4. **通用格式:**
   - 任何包含 slot、mcs、tbs 字段的日志行

## Trace文件格式

生成的trace文件采用CSV格式:

```csv
# slot_index, mcs, tbs_bytes, needs_retx, retx_count, harq_id
0, 16, 5376, 0, 0, 0
1, 18, 6200, 0, 0, 1
2, 20, 7400, 0, 0, 2
...
```

字段说明:
- `slot_index`: 时隙索引
- `mcs`: 调制编码方案索引
- `tbs_bytes`: 传输块大小(字节)
- `needs_retx`: 是否需要重传 (0/1)
- `retx_count`: 重传次数
- `harq_id`: HARQ进程ID

## 在L4Span中使用trace

1. **生成trace文件:**
   ```bash
   python parse_simple_pdsch_trace.py your_gnb.log -o my_trace.csv
   ```

2. **修改配置文件:**
   在gNB配置文件中添加:
   ```yaml
   expert_execution:
     dl_scheduler_trace_file: "configs/l4span/my_trace.csv"
   ```

3. **运行仿真:**
   ```bash
   ./gnb -c configs/gnb_config.yml
   ```

## 示例工作流程

```bash
# 1. 运行srsRAN收集日志
./gnb -c configs/gnb_rf_b200_tdd_n78_20mhz.yml > gnb_output.log

# 2. 解析日志生成trace
cd scripts
python parse_simple_pdsch_trace.py ../gnb_output.log -o real_trace.csv

# 3. 在新的仿真中使用trace
# 编辑配置文件添加: dl_scheduler_trace_file: "configs/l4span/real_trace.csv"
./gnb -c configs/gnb_with_trace.yml

# 4. 查看统计信息
python parse_pdsch_trace.py ../gnb_output.log --stats
```

## 故障排除

**如果没有找到PDSCH数据:**
1. 检查日志文件是否包含MAC或PHY相关信息
2. 确认日志级别包含INFO或DEBUG
3. 验证日志格式是否包含slot、mcs、tbs字段

**如果trace数据不连续:**
- 脚本会自动填充缺失的时隙
- 使用最近有效的MCS/TBS值或默认值

**性能优化:**
- 对于大型日志文件，考虑使用 `--min-slot` 和 `--max-slot` 参数
- 使用简化解析器处理基本需求