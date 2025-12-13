#!/usr/bin/env python3
"""
测试PDSCH trace解析脚本的示例
"""

import os
import tempfile

def create_sample_log():
    """创建一个示例srsRAN日志文件用于测试"""
    
    sample_log = """
# Sample srsRAN log file
[INFO] Starting gNB...
[DEBUG] Cell configuration loaded
[INFO] 2024-12-09T10:00:01.123 [MAC ] slot=0 ue=4601 mcs=16 tbs=5376 nof_prb=25
[INFO] 2024-12-09T10:00:01.124 [MAC ] slot=1 ue=4601 mcs=18 tbs=6200 nof_prb=25  
[INFO] 2024-12-09T10:00:01.125 [MAC ] slot=2 ue=4601 mcs=20 tbs=7400 nof_prb=28
[DEBUG] Some other log entry
[INFO] 2024-12-09T10:00:01.126 [MAC ] slot=3 ue=4601 mcs=15 tbs=4800 nof_prb=22
[INFO] 2024-12-09T10:00:01.127 [PHY ] PDSCH transmission slot=4 ue=4601 mcs=17 tbs=5900 harq_id=0
[INFO] 2024-12-09T10:00:01.128 [MAC ] DL scheduler slot=5 rnti=4601 mcs=19 tbs=6800 prb_start=0
[INFO] 2024-12-09T10:00:01.129 [MAC ] slot=6 ue=4601 mcs=22 tbs=8200 nof_prb=30
[ERROR] Some error message  
[INFO] 2024-12-09T10:00:01.130 [MAC ] slot=7 ue=4601 mcs=14 tbs=4200 nof_prb=20
[INFO] 2024-12-09T10:00:01.131 [PHY ] PDSCH slot=8 mcs=21 tbs=7800 ue_id=4601
[INFO] 2024-12-09T10:00:01.132 [MAC ] slot=9 ue=4601 mcs=16 tbs=5376 nof_prb=25
[INFO] 2024-12-09T10:00:01.133 [MAC ] slot=10 ue=4601 mcs=18 tbs=6200 nof_prb=25
"""
    
    # 创建临时文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
        f.write(sample_log)
        return f.name


def test_parsing():
    """测试解析功能"""
    print("=== PDSCH Trace 解析工具测试 ===\n")
    
    # 创建示例日志
    log_file = create_sample_log()
    print(f"创建示例日志文件: {log_file}")
    
    # 测试简化解析器
    print("\n1. 测试简化解析器:")
    print("python parse_simple_pdsch_trace.py sample.log -o test_trace.csv")
    
    try:
        import subprocess
        import sys
        
        # 运行简化解析器
        result = subprocess.run([
            sys.executable, 'parse_simple_pdsch_trace.py', 
            log_file, '-o', 'test_trace.csv'
        ], capture_output=True, text=True, cwd='.')
        
        print("输出:")
        print(result.stdout)
        if result.stderr:
            print("错误:")
            print(result.stderr)
            
    except Exception as e:
        print(f"运行测试失败: {e}")
    
    # 清理
    try:
        os.unlink(log_file)
        print(f"清理临时文件: {log_file}")
    except:
        pass
    
    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    test_parsing()