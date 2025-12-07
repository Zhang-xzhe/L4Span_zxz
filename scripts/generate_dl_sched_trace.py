#!/usr/bin/env python3
"""
Generate downlink scheduler trace file from real measurements.

Trace format (CSV):
slot_index, mcs, tbs_bytes, needs_retx, retx_count[, harq_id]

Example:
0, 16, 5376, 0, 0
1, 16, 5376, 0, 0
2, 12, 3752, 0, 0
3, 12, 3752, 1, 1, 0
"""

import argparse
import csv
import numpy as np


def generate_constant_trace(num_slots=1000, mcs=16, tbs=5376, retx_prob=0.05, output_file="dl_sched_trace.csv"):
    """Generate a constant MCS/TBS trace with occasional retransmissions."""
    
    print(f"Generating constant trace: MCS={mcs}, TBS={tbs} bytes, RetxProb={retx_prob}")
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['# slot_index', 'mcs', 'tbs_bytes', 'needs_retx', 'retx_count', 'harq_id'])
        
        harq_id = 0
        for slot_idx in range(num_slots):
            needs_retx = 1 if np.random.random() < retx_prob else 0
            retx_count = np.random.randint(1, 4) if needs_retx else 0
            
            writer.writerow([slot_idx, mcs, tbs, needs_retx, retx_count, harq_id % 8])
            harq_id += 1
    
    print(f"✓ Generated {num_slots} slots to {output_file}")


def generate_varying_mcs_trace(num_slots=1000, output_file="dl_sched_varying_trace.csv"):
    """Generate trace with varying MCS based on simulated channel quality."""
    
    print(f"Generating varying MCS trace...")
    
    # MCS to TBS mapping (approximate, for 100 PRBs, 14 symbols)
    mcs_to_tbs = {
        0: 712,    # QPSK, very low code rate
        5: 2280,   # QPSK
        10: 4584,  # 16QAM
        15: 7992,  # 16QAM
        20: 14112, # 64QAM
        25: 21384, # 64QAM
        28: 25456, # 64QAM max
    }
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['# slot_index', 'mcs', 'tbs_bytes', 'needs_retx', 'retx_count', 'harq_id'])
        
        harq_id = 0
        for slot_idx in range(num_slots):
            # Simulate channel variation (sinusoidal + noise)
            phase = 2 * np.pi * slot_idx / 100
            snr_var = 10 * np.sin(phase) + np.random.normal(0, 2)
            
            # Map SNR to MCS (simplified)
            base_snr = 15  # dB
            snr = base_snr + snr_var
            
            if snr < 5:
                mcs = 0
            elif snr < 10:
                mcs = 5
            elif snr < 15:
                mcs = 10
            elif snr < 20:
                mcs = 15
            elif snr < 25:
                mcs = 20
            elif snr < 28:
                mcs = 25
            else:
                mcs = 28
            
            tbs = mcs_to_tbs.get(mcs, 5376)
            
            # Retransmission more likely at low SNR
            retx_prob = max(0.01, min(0.3, (25 - snr) / 50))
            needs_retx = 1 if np.random.random() < retx_prob else 0
            retx_count = np.random.randint(1, 4) if needs_retx else 0
            
            writer.writerow([slot_idx, mcs, tbs, needs_retx, retx_count, harq_id % 8])
            harq_id += 1
    
    print(f"✓ Generated {num_slots} slots to {output_file}")


def generate_mobility_trace(num_slots=2000, output_file="dl_sched_mobility_trace.csv"):
    """Generate trace simulating user mobility (handover scenario)."""
    
    print(f"Generating mobility trace (handover simulation)...")
    
    mcs_to_tbs = {
        0: 712, 5: 2280, 10: 4584, 15: 7992, 20: 14112, 25: 21384, 28: 25456
    }
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['# slot_index', 'mcs', 'tbs_bytes', 'needs_retx', 'retx_count', 'harq_id'])
        
        harq_id = 0
        phase = 0  # Good signal
        
        for slot_idx in range(num_slots):
            # Simulate mobility phases
            if slot_idx < 500:
                # Good signal (cell center)
                mcs = np.random.choice([20, 25, 28], p=[0.3, 0.5, 0.2])
                retx_prob = 0.02
            elif slot_idx < 700:
                # Moving away (degrading)
                mcs = np.random.choice([15, 20, 25], p=[0.3, 0.4, 0.3])
                retx_prob = 0.05
            elif slot_idx < 900:
                # Cell edge (poor signal)
                mcs = np.random.choice([0, 5, 10], p=[0.2, 0.5, 0.3])
                retx_prob = 0.15
            elif slot_idx < 1100:
                # Handover (very poor)
                mcs = np.random.choice([0, 5], p=[0.7, 0.3])
                retx_prob = 0.25
            else:
                # New cell (recovering)
                progress = (slot_idx - 1100) / 900
                if progress < 0.3:
                    mcs = np.random.choice([5, 10, 15], p=[0.4, 0.4, 0.2])
                    retx_prob = 0.10
                else:
                    mcs = np.random.choice([15, 20, 25], p=[0.2, 0.5, 0.3])
                    retx_prob = 0.03
            
            tbs = mcs_to_tbs.get(mcs, 5376)
            needs_retx = 1 if np.random.random() < retx_prob else 0
            retx_count = np.random.randint(1, 4) if needs_retx else 0
            
            writer.writerow([slot_idx, mcs, tbs, needs_retx, retx_count, harq_id % 8])
            harq_id += 1
    
    print(f"✓ Generated {num_slots} slots to {output_file}")


def parse_real_trace(input_file, output_file):
    """Parse real measurement trace and convert to scheduler trace format."""
    
    print(f"Parsing real trace from {input_file}...")
    
    # This is a placeholder - adapt to your actual log format
    # Expected input format: timestamp, ue_id, mcs, tbs, crc_ok, harq_id, retx_count
    
    with open(input_file, 'r') as fin, open(output_file, 'w', newline='') as fout:
        writer = csv.writer(fout)
        writer.writerow(['# slot_index', 'mcs', 'tbs_bytes', 'needs_retx', 'retx_count', 'harq_id'])
        
        slot_idx = 0
        for line in fin:
            if line.startswith('#') or not line.strip():
                continue
            
            # Parse your log format here
            # Example: parts = line.strip().split(',')
            # mcs = int(parts[2])
            # tbs = int(parts[3])
            # ... etc
            
            # writer.writerow([slot_idx, mcs, tbs, needs_retx, retx_count, harq_id])
            slot_idx += 1
    
    print(f"✓ Converted to {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Generate downlink scheduler trace files for L4Span simulation'
    )
    parser.add_argument('--type', 
                       choices=['constant', 'varying', 'mobility', 'real', 'all'],
                       default='all',
                       help='Type of trace to generate')
    parser.add_argument('--slots', type=int, default=1000,
                       help='Number of slots to generate')
    parser.add_argument('--mcs', type=int, default=16,
                       help='MCS index for constant trace (0-28)')
    parser.add_argument('--tbs', type=int, default=5376,
                       help='TBS in bytes for constant trace')
    parser.add_argument('--retx-prob', type=float, default=0.05,
                       help='Retransmission probability (0.0-1.0)')
    parser.add_argument('--input', type=str,
                       help='Input file for real trace parsing')
    parser.add_argument('--output-dir', default='configs/l4span',
                       help='Output directory')
    
    args = parser.parse_args()
    
    import os
    os.makedirs(args.output_dir, exist_ok=True)
    
    if args.type in ['constant', 'all']:
        generate_constant_trace(
            args.slots, args.mcs, args.tbs, args.retx_prob,
            f"{args.output_dir}/dl_sched_constant_trace.csv"
        )
    
    if args.type in ['varying', 'all']:
        generate_varying_mcs_trace(
            args.slots,
            f"{args.output_dir}/dl_sched_varying_trace.csv"
        )
    
    if args.type in ['mobility', 'all']:
        generate_mobility_trace(
            args.slots * 2,
            f"{args.output_dir}/dl_sched_mobility_trace.csv"
        )
    
    if args.type == 'real' and args.input:
        parse_real_trace(
            args.input,
            f"{args.output_dir}/dl_sched_real_trace.csv"
        )
    
    print("\n✓ All trace files generated successfully!")
    print(f"\nTo use these traces, add to your configuration:")
    print(f"  dl_scheduler_trace_file: \"{args.output_dir}/dl_sched_varying_trace.csv\"")
    print(f"\nTrace format:")
    print(f"  slot_index, mcs, tbs_bytes, needs_retx, retx_count, harq_id")


if __name__ == "__main__":
    main()
