#!/usr/bin/env python3
"""
Parse srsRAN PDSCH logs and generate downlink scheduler trace file.

This script parses actual srsRAN log files and extracts PDSCH TBS information
to create a trace file for trace-based scheduling.

Trace format (CSV):
slot_index, mcs, tbs_bytes, needs_retx, retx_count, harq_id

Expected log format patterns:
- MAC PDSCH allocation logs
- PHY PDSCH transmission logs
- HARQ retransmission logs
"""

import argparse
import csv
import re
import os
from datetime import datetime
from collections import defaultdict


class PDSCHTraceParser:
    def __init__(self):
        # Regular expressions for different log patterns
        self.patterns = {
            # MAC scheduler PDSCH allocation
            'mac_pdsch': re.compile(
                r'.*MAC.*PDSCH.*slot=(\d+).*ue=(\w+).*mcs=(\d+).*tbs=(\d+).*'
            ),
            
            # PHY PDSCH transmission
            'phy_pdsch': re.compile(
                r'.*PHY.*PDSCH.*slot=(\d+).*ue=(\w+).*mcs=(\d+).*tbs=(\d+).*harq_id=(\d+).*'
            ),
            
            # HARQ acknowledgment/retransmission
            'harq_ack': re.compile(
                r'.*HARQ.*slot=(\d+).*ue=(\w+).*harq_id=(\d+).*ack=(0|1).*'
            ),
            
            # Alternative MAC format with different field order
            'mac_alt': re.compile(
                r'.*scheduler.*dl.*slot=(\d+).*rnti=(\w+).*mcs=(\d+).*tbs_bytes=(\d+).*harq=(\d+).*'
            ),
            
            # Generic PDSCH pattern - more flexible
            'generic_pdsch': re.compile(
                r'.*slot[=:\s]+(\d+).*(?:ue|rnti|UE)[=:\s]+(\w+).*mcs[=:\s]+(\d+).*tbs[=:\s_]*(\d+)(?:.*harq[=:\s_]*(\d+))?'
            )
        }
        
        self.slot_data = defaultdict(lambda: {
            'mcs': None,
            'tbs': None,
            'harq_id': None,
            'ue_id': None,
            'retx_count': 0,
            'ack_received': None
        })
        
        self.parsed_count = 0
        
    def parse_line(self, line):
        """Parse a single log line and extract PDSCH information."""
        line = line.strip()
        if not line or line.startswith('#'):
            return None
            
        # Try each pattern
        for pattern_name, pattern in self.patterns.items():
            match = pattern.search(line)
            if match:
                return self._extract_data(match, pattern_name, line)
        
        return None
    
    def _extract_data(self, match, pattern_name, line):
        """Extract data based on the matched pattern."""
        try:
            if pattern_name == 'mac_pdsch':
                slot, ue_id, mcs, tbs = match.groups()
                return {
                    'slot': int(slot),
                    'ue_id': ue_id,
                    'mcs': int(mcs),
                    'tbs': int(tbs),
                    'harq_id': None,
                    'type': 'pdsch'
                }
                
            elif pattern_name == 'phy_pdsch':
                slot, ue_id, mcs, tbs, harq_id = match.groups()
                return {
                    'slot': int(slot),
                    'ue_id': ue_id,
                    'mcs': int(mcs),
                    'tbs': int(tbs),
                    'harq_id': int(harq_id),
                    'type': 'pdsch'
                }
                
            elif pattern_name == 'harq_ack':
                slot, ue_id, harq_id, ack = match.groups()
                return {
                    'slot': int(slot),
                    'ue_id': ue_id,
                    'harq_id': int(harq_id),
                    'ack': int(ack),
                    'type': 'harq'
                }
                
            elif pattern_name == 'mac_alt':
                slot, rnti, mcs, tbs, harq_id = match.groups()
                return {
                    'slot': int(slot),
                    'ue_id': rnti,
                    'mcs': int(mcs),
                    'tbs': int(tbs),
                    'harq_id': int(harq_id),
                    'type': 'pdsch'
                }
                
            elif pattern_name == 'generic_pdsch':
                groups = match.groups()
                slot = int(groups[0])
                ue_id = groups[1]
                mcs = int(groups[2])
                tbs = int(groups[3])
                harq_id = int(groups[4]) if groups[4] else None
                
                return {
                    'slot': slot,
                    'ue_id': ue_id,
                    'mcs': mcs,
                    'tbs': tbs,
                    'harq_id': harq_id,
                    'type': 'pdsch'
                }
                
        except (ValueError, IndexError) as e:
            print(f"Warning: Failed to parse line: {line[:100]}... Error: {e}")
            return None
            
        return None
    
    def process_file(self, input_file):
        """Process the entire log file."""
        print(f"Processing log file: {input_file}")
        
        line_count = 0
        with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line_count += 1
                if line_count % 10000 == 0:
                    print(f"Processed {line_count} lines, found {self.parsed_count} PDSCH entries")
                
                data = self.parse_line(line)
                if data:
                    self.parsed_count += 1
                    slot = data['slot']
                    
                    if data['type'] == 'pdsch':
                        # Store PDSCH transmission data
                        self.slot_data[slot].update({
                            'mcs': data['mcs'],
                            'tbs': data['tbs'],
                            'harq_id': data.get('harq_id', slot % 8),  # Default HARQ ID
                            'ue_id': data['ue_id']
                        })
                        
                    elif data['type'] == 'harq':
                        # Process HARQ feedback
                        if data['ack'] == 0:  # NACK - retransmission needed
                            self.slot_data[slot]['retx_count'] += 1
                        self.slot_data[slot]['ack_received'] = data['ack']
        
        print(f"Finished processing {line_count} lines")
        print(f"Found {self.parsed_count} PDSCH-related entries")
        print(f"Unique slots with data: {len(self.slot_data)}")
        
    def generate_trace(self, output_file, min_slot=None, max_slot=None):
        """Generate the trace file from parsed data."""
        if not self.slot_data:
            print("No PDSCH data found in logs!")
            return
            
        # Determine slot range
        all_slots = sorted(self.slot_data.keys())
        start_slot = min_slot if min_slot is not None else all_slots[0]
        end_slot = max_slot if max_slot is not None else all_slots[-1]
        
        print(f"Generating trace for slots {start_slot} to {end_slot}")
        
        with open(output_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['# slot_index', 'mcs', 'tbs_bytes', 'needs_retx', 'retx_count', 'harq_id'])
            
            trace_entries = 0
            default_entries = 0
            
            for slot in range(start_slot, end_slot + 1):
                data = self.slot_data.get(slot)
                
                if data and data['mcs'] is not None and data['tbs'] is not None:
                    # Real data from logs
                    mcs = data['mcs']
                    tbs = data['tbs']
                    harq_id = data['harq_id'] if data['harq_id'] is not None else slot % 8
                    retx_count = data['retx_count']
                    needs_retx = 1 if retx_count > 0 else 0
                    
                    writer.writerow([slot, mcs, tbs, needs_retx, retx_count, harq_id])
                    trace_entries += 1
                    
                else:
                    # Fill missing slots with default values
                    # Use reasonable defaults or interpolate from nearby slots
                    mcs = self._get_default_mcs(slot)
                    tbs = self._get_default_tbs(mcs)
                    harq_id = slot % 8
                    
                    writer.writerow([slot, mcs, tbs, 0, 0, harq_id])
                    default_entries += 1
        
        total_slots = end_slot - start_slot + 1
        print(f"✓ Generated trace file: {output_file}")
        print(f"  Real data entries: {trace_entries}")
        print(f"  Default entries: {default_entries}")
        print(f"  Total slots: {total_slots}")
        print(f"  Coverage: {trace_entries/total_slots*100:.1f}%")
    
    def _get_default_mcs(self, slot):
        """Get a reasonable default MCS for missing slots."""
        # Look for nearby slots with data
        for offset in range(1, 100):
            for direction in [-1, 1]:
                check_slot = slot + direction * offset
                data = self.slot_data.get(check_slot)
                if data and data['mcs'] is not None:
                    return data['mcs']
        
        # If no nearby data found, use a moderate MCS
        return 16
    
    def _get_default_tbs(self, mcs):
        """Get default TBS for a given MCS."""
        # Approximate TBS values for different MCS (assuming ~100 PRBs)
        mcs_to_tbs = {
            0: 712, 1: 1480, 2: 1736, 3: 2280, 4: 2856,
            5: 3496, 6: 4584, 7: 5352, 8: 5992, 9: 6712,
            10: 7992, 11: 8760, 12: 9912, 13: 11064, 14: 12216,
            15: 14112, 16: 15840, 17: 17568, 18: 19848, 19: 22152,
            20: 25456, 21: 27376, 22: 28336, 23: 30576, 24: 32616,
            25: 34656, 26: 36696, 27: 38984, 28: 42368
        }
        
        return mcs_to_tbs.get(mcs, 5376)  # Default to 5376 if MCS not in table
    
    def print_stats(self):
        """Print parsing statistics."""
        if not self.slot_data:
            print("No data to analyze")
            return
            
        mcs_values = [data['mcs'] for data in self.slot_data.values() if data['mcs'] is not None]
        tbs_values = [data['tbs'] for data in self.slot_data.values() if data['tbs'] is not None]
        
        print(f"\n--- Parsing Statistics ---")
        print(f"Total slots with data: {len(self.slot_data)}")
        print(f"MCS range: {min(mcs_values)} - {max(mcs_values)}" if mcs_values else "No MCS data")
        print(f"TBS range: {min(tbs_values)} - {max(tbs_values)} bytes" if tbs_values else "No TBS data")
        
        if mcs_values:
            import statistics
            print(f"Average MCS: {statistics.mean(mcs_values):.1f}")
            print(f"Average TBS: {statistics.mean(tbs_values):.0f} bytes")
        
        retx_slots = [slot for slot, data in self.slot_data.items() if data['retx_count'] > 0]
        print(f"Slots with retransmissions: {len(retx_slots)}")


def main():
    parser = argparse.ArgumentParser(
        description='Parse srsRAN logs and generate PDSCH trace files'
    )
    parser.add_argument('input_log', 
                       help='Input log file from srsRAN')
    parser.add_argument('-o', '--output', 
                       default='pdsch_trace.csv',
                       help='Output trace file (default: pdsch_trace.csv)')
    parser.add_argument('--min-slot', type=int,
                       help='Minimum slot index to include')
    parser.add_argument('--max-slot', type=int,
                       help='Maximum slot index to include')
    parser.add_argument('--stats', action='store_true',
                       help='Show detailed parsing statistics')
    parser.add_argument('--output-dir', default='configs/l4span',
                       help='Output directory')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input_log):
        print(f"Error: Input log file not found: {args.input_log}")
        return 1
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    output_path = os.path.join(args.output_dir, args.output)
    
    # Parse the log file
    parser = PDSCHTraceParser()
    parser.process_file(args.input_log)
    
    # Show statistics if requested
    if args.stats:
        parser.print_stats()
    
    # Generate trace file
    parser.generate_trace(output_path, args.min_slot, args.max_slot)
    
    print(f"\n✓ Trace file generated successfully!")
    print(f"✓ Output: {output_path}")
    print(f"\nTo use this trace, add to your configuration:")
    print(f"  dl_scheduler_trace_file: \"{output_path}\"")
    print(f"\nExample usage:")
    print(f"  ./gnb -c configs/gnb_config.yml")
    
    return 0


if __name__ == "__main__":
    exit(main())