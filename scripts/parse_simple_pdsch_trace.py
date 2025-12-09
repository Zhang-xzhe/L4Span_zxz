#!/usr/bin/env python3
"""
简化的PDSCH日志解析脚本 - 从srsRAN日志中提取TBS信息生成trace文件

使用方法:
python parse_simple_pdsch_trace.py gnb_log.txt -o pdsch_trace.csv

支持的日志格式:
- MAC scheduler日志
- PHY PDSCH传输日志
- 通用格式日志
"""

import argparse
import csv
import re
import os
from collections import defaultdict


def parse_srsran_log(log_file, output_file):
    """解析srsRAN日志文件并生成PDSCH trace"""
    
    # 常用的日志模式 - 适配不同的srsRAN版本
    patterns = [
        # 模式1: MAC scheduler格式
        r'.*slot[=:\s]*(\d+).*mcs[=:\s]*(\d+).*tbs[=:\s]*(\d+)',
        
        # 模式2: PHY格式  
        r'.*PDSCH.*slot[=:\s]*(\d+).*mcs[=:\s]*(\d+).*tbs[=:\s]*(\d+)',
        
        # 模式3: 带RNTI格式
        r'.*rnti[=:\s]*\w+.*slot[=:\s]*(\d+).*mcs[=:\s]*(\d+).*tbs[=:\s]*(\d+)',
        
        # 模式4: 调度器格式
        r'.*scheduler.*slot[=:\s]*(\d+).*mcs[=:\s]*(\d+).*tbs[=:\s]*(\d+)',
        
        # 模式5: 通用格式 - 匹配包含slot, mcs, tbs的行
        r'.*slot[=:\s]*(\d+).*(?:mcs|MCS)[=:\s]*(\d+).*(?:tbs|TBS)[=:\s]*(\d+)',
    ]
    
    compiled_patterns = [re.compile(p, re.IGNORECASE) for p in patterns]
    
    slot_data = {}
    parsed_lines = 0
    total_lines = 0
    
    print(f"开始解析日志文件: {log_file}")
    
    try:
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                total_lines += 1
                
                if line_num % 10000 == 0:
                    print(f"已处理 {line_num} 行, 找到 {parsed_lines} 个PDSCH条目")
                
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # 尝试匹配各种模式
                for pattern in compiled_patterns:
                    match = pattern.search(line)
                    if match:
                        try:
                            slot = int(match.group(1))
                            mcs = int(match.group(2))
                            tbs = int(match.group(3))
                            
                            # 保存数据
                            slot_data[slot] = {
                                'mcs': mcs,
                                'tbs': tbs,
                                'harq_id': slot % 8,  # 默认HARQ ID
                                'needs_retx': 0,      # 默认不需要重传
                                'retx_count': 0       # 重传次数
                            }
                            parsed_lines += 1
                            break  # 找到匹配就跳出循环
                            
                        except (ValueError, IndexError):
                            continue
    
    except Exception as e:
        print(f"读取文件出错: {e}")
        return False
    
    if not slot_data:
        print("警告: 没有找到任何PDSCH数据!")
        print("请检查日志格式是否包含 slot、mcs、tbs 信息")
        return False
    
    print(f"解析完成:")
    print(f"  总行数: {total_lines}")
    print(f"  解析的PDSCH条目: {parsed_lines}")
    print(f"  唯一时隙: {len(slot_data)}")
    
    # 生成trace文件
    print(f"生成trace文件: {output_file}")
    
    slots = sorted(slot_data.keys())
    start_slot = slots[0]
    end_slot = slots[-1]
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['# slot_index', 'mcs', 'tbs_bytes', 'needs_retx', 'retx_count', 'harq_id'])
        
        # 填充连续的时隙
        for slot in range(start_slot, end_slot + 1):
            if slot in slot_data:
                data = slot_data[slot]
                writer.writerow([
                    slot,
                    data['mcs'],
                    data['tbs'],
                    data['needs_retx'],
                    data['retx_count'],
                    data['harq_id']
                ])
            else:
                # 对于缺失的时隙，使用前一个有效值或默认值
                default_mcs = 16
                default_tbs = 5376
                
                # 尝试找前面最近的有效值
                for prev_slot in range(slot-1, max(start_slot-1, slot-100), -1):
                    if prev_slot in slot_data:
                        default_mcs = slot_data[prev_slot]['mcs']
                        default_tbs = slot_data[prev_slot]['tbs']
                        break
                
                writer.writerow([slot, default_mcs, default_tbs, 0, 0, slot % 8])
    
    # 显示统计信息
    mcs_values = [data['mcs'] for data in slot_data.values()]
    tbs_values = [data['tbs'] for data in slot_data.values()]
    
    print(f"统计信息:")
    print(f"  时隙范围: {start_slot} - {end_slot}")
    print(f"  MCS范围: {min(mcs_values)} - {max(mcs_values)}")
    print(f"  TBS范围: {min(tbs_values)} - {max(tbs_values)} bytes")
    print(f"  平均MCS: {sum(mcs_values)/len(mcs_values):.1f}")
    print(f"  平均TBS: {sum(tbs_values)/len(tbs_values):.0f} bytes")
    
    return True


def main():
    parser = argparse.ArgumentParser(description='从srsRAN日志生成PDSCH trace文件')
    parser.add_argument('input_log', help='输入的srsRAN日志文件')
    parser.add_argument('-o', '--output', default='pdsch_trace.csv', 
                       help='输出的trace文件名 (默认: pdsch_trace.csv)')
    parser.add_argument('--output-dir', default='configs/l4span',
                       help='输出目录 (默认: configs/l4span)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input_log):
        print(f"错误: 找不到输入文件 {args.input_log}")
        return 1
    
    # 创建输出目录
    os.makedirs(args.output_dir, exist_ok=True)
    output_path = os.path.join(args.output_dir, args.output)
    
    # 解析日志
    success = parse_srsran_log(args.input_log, output_path)
    
    if success:
        print(f"\n✓ trace文件生成成功!")
        print(f"✓ 输出文件: {output_path}")
        print(f"\n使用方法:")
        print(f"在配置文件中添加:")
        print(f'  dl_scheduler_trace_file: "{output_path}"')
        return 0
    else:
        print("生成trace文件失败")
        return 1


if __name__ == "__main__":
    exit(main())