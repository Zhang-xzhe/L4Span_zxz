#!/usr/bin/env python3
"""
RLC Queue Visualization Script

This script parses RLC log files and visualizes the queued_bytes over time.
It looks for lines like:
"2025-12-02T03:33:52.195474 [RLC     ] [D] du=0 ue=0 DRB1 DL: Reading SDU from sdu_queue. queued_sdus=941 queued_bytes=1320223"

Usage:
    python visualize_rlc_queue.py <log_file> [options]
    
Example:
    python visualize_rlc_queue.py gnb.log
    python visualize_rlc_queue.py gnb.log --drb DRB1 --direction DL
    python visualize_rlc_queue.py gnb.log --output queue_plot.png
"""

import re
import argparse
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from collections import defaultdict

def parse_rlc_log_line(line):
    """
    Parse a single RLC log line and extract relevant information.
    
    Returns:
        dict with keys: timestamp, du, ue, drb, direction, queued_sdus, queued_bytes
        or None if line doesn't match the pattern
    """
    # Pattern to match the log format
    pattern = r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+)\s+\[RLC\s+\]\s+\[.\]\s+du=(\d+)\s+ue=(\d+)\s+(\w+)\s+(DL|UL):\s+Reading SDU from sdu_queue\.\s+queued_sdus=(\d+)\s+queued_bytes=(\d+)'
    
    match = re.search(pattern, line)
    if match:
        timestamp_str, du, ue, drb, direction, queued_sdus, queued_bytes = match.groups()
        
        # Parse timestamp
        timestamp = datetime.fromisoformat(timestamp_str)
        
        return {
            'timestamp': timestamp,
            'du': int(du),
            'ue': int(ue),
            'drb': drb,
            'direction': direction,
            'queued_sdus': int(queued_sdus),
            'queued_bytes': int(queued_bytes)
        }
    return None

def parse_log_file(filename, du_filter=None, ue_filter=None, drb_filter=None, direction_filter=None):
    """
    Parse the entire log file and extract RLC queue information.
    
    Args:
        filename: Path to the log file
        du_filter: Filter by DU ID (None = all)
        ue_filter: Filter by UE ID (None = all)
        drb_filter: Filter by DRB name (None = all)
        direction_filter: Filter by direction 'DL' or 'UL' (None = all)
    
    Returns:
        dict mapping (du, ue, drb, direction) -> list of (timestamp, queued_bytes) tuples
    """
    data = defaultdict(list)
    total_lines = 0
    matched_lines = 0
    
    print(f"Parsing log file: {filename}")
    
    try:
        with open(filename, 'r') as f:
            for line in f:
                total_lines += 1
                parsed = parse_rlc_log_line(line)
                
                if parsed:
                    # Apply filters
                    if du_filter is not None and parsed['du'] != du_filter:
                        continue
                    if ue_filter is not None and parsed['ue'] != ue_filter:
                        continue
                    if drb_filter is not None and parsed['drb'] != drb_filter:
                        continue
                    if direction_filter is not None and parsed['direction'] != direction_filter:
                        continue
                    
                    # Create key for grouping
                    key = (parsed['du'], parsed['ue'], parsed['drb'], parsed['direction'])
                    data[key].append((parsed['timestamp'], parsed['queued_bytes'], parsed['queued_sdus']))
                    matched_lines += 1
                
                # Progress indicator
                if total_lines % 10000 == 0:
                    print(f"  Processed {total_lines} lines, matched {matched_lines} entries...")
    
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found!")
        return None
    except Exception as e:
        print(f"Error reading file: {e}")
        return None
    
    print(f"Parsing complete: {total_lines} lines processed, {matched_lines} RLC entries matched")
    print(f"Found {len(data)} unique DRB streams")
    
    return data

def plot_queue_data(data, output_file=None, show_sdus=False):
    """
    Create visualization of queue data over time.
    
    Args:
        data: Dictionary from parse_log_file
        output_file: If provided, save plot to this file
        show_sdus: If True, also plot queued_sdus
    """
    if not data:
        print("No data to plot!")
        return
    
    # Create figure with subplots
    num_streams = len(data)
    
    if show_sdus:
        fig, axes = plt.subplots(num_streams, 2, figsize=(16, 4 * num_streams))
        if num_streams == 1:
            axes = axes.reshape(1, -1)
    else:
        fig, axes = plt.subplots(num_streams, 1, figsize=(14, 4 * num_streams))
        if num_streams == 1:
            axes = [axes]
    
    fig.suptitle('RLC Queue Evolution Over Time', fontsize=16, fontweight='bold')
    
    for idx, (key, values) in enumerate(sorted(data.items())):
        du, ue, drb, direction = key
        timestamps = [v[0] for v in values]
        queued_bytes = [v[1] for v in values]
        queued_sdus = [v[2] for v in values]
        
        title = f"DU={du} UE={ue} {drb} {direction}"
        
        # Plot queued_bytes
        if show_sdus:
            ax_bytes = axes[idx, 0]
            ax_sdus = axes[idx, 1]
        else:
            ax_bytes = axes[idx]
        
        # Bytes plot
        ax_bytes.plot(timestamps, queued_bytes, linewidth=1, color='blue', alpha=0.7)
        ax_bytes.set_xlabel('Time')
        ax_bytes.set_ylabel('Queued Bytes', color='blue')
        ax_bytes.tick_params(axis='y', labelcolor='blue')
        ax_bytes.set_title(f'{title} - Queued Bytes')
        ax_bytes.grid(True, alpha=0.3)
        ax_bytes.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        plt.setp(ax_bytes.xaxis.get_majorticklabels(), rotation=45)
        
        # Add statistics
        avg_bytes = sum(queued_bytes) / len(queued_bytes)
        max_bytes = max(queued_bytes)
        min_bytes = min(queued_bytes)
        ax_bytes.axhline(y=avg_bytes, color='red', linestyle='--', alpha=0.5, label=f'Avg: {avg_bytes:.0f}')
        ax_bytes.legend(loc='upper right')
        
        stats_text = f'Min: {min_bytes:,}\nMax: {max_bytes:,}\nAvg: {avg_bytes:,.0f}\nSamples: {len(queued_bytes)}'
        ax_bytes.text(0.02, 0.98, stats_text, transform=ax_bytes.transAxes,
                     verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
                     fontsize=9)
        
        # SDUs plot (if requested)
        if show_sdus:
            ax_sdus.plot(timestamps, queued_sdus, linewidth=1, color='green', alpha=0.7)
            ax_sdus.set_xlabel('Time')
            ax_sdus.set_ylabel('Queued SDUs', color='green')
            ax_sdus.tick_params(axis='y', labelcolor='green')
            ax_sdus.set_title(f'{title} - Queued SDUs')
            ax_sdus.grid(True, alpha=0.3)
            ax_sdus.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
            plt.setp(ax_sdus.xaxis.get_majorticklabels(), rotation=45)
            
            avg_sdus = sum(queued_sdus) / len(queued_sdus)
            ax_sdus.axhline(y=avg_sdus, color='red', linestyle='--', alpha=0.5, label=f'Avg: {avg_sdus:.0f}')
            ax_sdus.legend(loc='upper right')
    
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f"Plot saved to: {output_file}")
    else:
        plt.show()

def print_summary(data):
    """Print summary statistics for each stream."""
    print("\n" + "="*80)
    print("SUMMARY STATISTICS")
    print("="*80)
    
    for key, values in sorted(data.items()):
        du, ue, drb, direction = key
        queued_bytes = [v[1] for v in values]
        queued_sdus = [v[2] for v in values]
        
        print(f"\nDU={du} UE={ue} {drb} {direction}:")
        print(f"  Samples: {len(values)}")
        print(f"  Time range: {values[0][0]} to {values[-1][0]}")
        print(f"  Duration: {values[-1][0] - values[0][0]}")
        print(f"  Queued Bytes - Min: {min(queued_bytes):,}, Max: {max(queued_bytes):,}, Avg: {sum(queued_bytes)/len(queued_bytes):,.0f}")
        print(f"  Queued SDUs  - Min: {min(queued_sdus):,}, Max: {max(queued_sdus):,}, Avg: {sum(queued_sdus)/len(queued_sdus):,.0f}")

def main():
    parser = argparse.ArgumentParser(
        description='Visualize RLC queue evolution from log files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Basic usage - parse all RLC queues
  %(prog)s gnb.log
  
  # Filter by specific DRB and direction
  %(prog)s gnb.log --drb DRB1 --direction DL
  
  # Filter by UE and save to file
  %(prog)s gnb.log --ue 0 --output rlc_queue.png
  
  # Show both bytes and SDUs
  %(prog)s gnb.log --show-sdus
  
  # Only print summary statistics
  %(prog)s gnb.log --summary-only
        ''')
    
    parser.add_argument('logfile', help='Path to the log file')
    parser.add_argument('--du', type=int, help='Filter by DU ID')
    parser.add_argument('--ue', type=int, help='Filter by UE ID')
    parser.add_argument('--drb', help='Filter by DRB name (e.g., DRB1)')
    parser.add_argument('--direction', choices=['DL', 'UL'], help='Filter by direction (DL or UL)')
    parser.add_argument('--output', '-o', help='Save plot to file instead of displaying')
    parser.add_argument('--show-sdus', action='store_true', help='Also plot queued_sdus')
    parser.add_argument('--summary-only', action='store_true', help='Only print summary, do not plot')
    
    args = parser.parse_args()
    
    # Parse log file
    data = parse_log_file(
        args.logfile,
        du_filter=args.du,
        ue_filter=args.ue,
        drb_filter=args.drb,
        direction_filter=args.direction
    )
    
    if data is None or len(data) == 0:
        print("No matching data found!")
        return
    
    # Print summary
    print_summary(data)
    
    # Plot data (unless summary-only)
    if not args.summary_only:
        plot_queue_data(data, output_file=args.output, show_sdus=args.show_sdus)

if __name__ == '__main__':
    main()
