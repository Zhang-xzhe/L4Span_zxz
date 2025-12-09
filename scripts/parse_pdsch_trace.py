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
            # srsRAN UE PDSCH format: "- UE PDSCH: ue=0 c-rnti=0x4601 h_id=0 rb=[...] tbs=309 mcs=7 rv=0 nrtx=0"
            'srsran_ue_pdsch': re.compile(
                r'- UE PDSCH: ue=(\d+) c-rnti=(0x[\da-fA-F]+) h_id=(\d+).*?tbs=(\d+) mcs=(\d+) rv=(\d+) nrtx=(\d+)'
            ),
            
            # srsRAN PHY PDSCH format: "PDSCH: rnti=0x4601 h_id=0 k1=4 prb=[...] tbs=309"
            'srsran_phy_pdsch': re.compile(
                r'\[PHY\s+\].*PDSCH: rnti=(0x[\da-fA-F]+) h_id=(\d+).*?tbs=(\d+)'
            ),
            
            # RAR PDSCH format: "- RAR PDSCH: ra-rnti=0x10b rb=[...] tbs=9 mcs=0"
            'srsran_rar_pdsch': re.compile(
                r'- RAR PDSCH: ra-rnti=(0x[\da-fA-F]+).*?tbs=(\d+) mcs=(\d+)'
            ),
            
            # Slot extraction from timestamp or slot indicators
            'slot_indicator': re.compile(
                r'\[\s*(\d+)\.(\d+)\]'  # [slot.subframe] format
            ),
            
            # Alternative slot format in srsRAN
            'srsran_slot': re.compile(
                r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+).*?\[\s*(\d+)\.(\d+)\]'
            ),
            
            # Generic PDSCH pattern - more flexible
            'generic_pdsch': re.compile(
                r'.*(?:ue|UE)[=:\s]+(\d+).*?(?:rnti|RNTI)[=:\s]+(0x[\da-fA-F]+).*?(?:tbs|TBS)[=:\s]+(\d+).*?(?:mcs|MCS)[=:\s]+(\d+)'
            )
        }
        
        self.slot_data = defaultdict(lambda: {
            'mcs': None,
            'tbs': None,
            'harq_id': None,
            'ue_id': None,
            'rnti': None,
            'retx_count': 0,
            'ack_received': None
        })
        
        self.parsed_count = 0
        self.current_slot = 0
        
    def extract_slot_from_line(self, line):
        """Extract slot number from srsRAN log line."""
        # Try to find slot in format [slot.subframe]
        match = self.patterns['slot_indicator'].search(line)
        if match:
            slot = int(match.group(1))
            subframe = int(match.group(2))
            # Convert to absolute slot (10 slots per frame, assuming 10ms frame)
            return slot
        
        # Try timestamp + slot format
        match = self.patterns['srsran_slot'].search(line)
        if match:
            slot = int(match.group(2))
            return slot
            
        return self.current_slot  # Use last known slot
        
    def parse_line(self, line):
        """Parse a single log line and extract PDSCH information."""
        line = line.strip()
        if not line or line.startswith('#'):
            return None
        
        # Update current slot from line
        slot = self.extract_slot_from_line(line)
        if slot != self.current_slot:
            self.current_slot = slot
            
        # Try each pattern
        for pattern_name, pattern in self.patterns.items():
            if pattern_name in ['slot_indicator', 'srsran_slot']:
                continue  # Skip slot extraction patterns
                
            match = pattern.search(line)
            if match:
                return self._extract_data(match, pattern_name, line)
        
        return None
    
    def _extract_data(self, match, pattern_name, line):
        """Extract data based on the matched pattern."""
        try:
            if pattern_name == 'srsran_ue_pdsch':
                # "- UE PDSCH: ue=0 c-rnti=0x4601 h_id=0 rb=[...] tbs=309 mcs=7 rv=0 nrtx=0"
                ue_id, rnti, harq_id, tbs, mcs, rv, nrtx = match.groups()
                return {
                    'slot': self.current_slot,
                    'ue_id': int(ue_id),
                    'rnti': rnti,
                    'mcs': int(mcs),
                    'tbs': int(tbs),
                    'harq_id': int(harq_id),
                    'rv': int(rv),
                    'nrtx': int(nrtx),
                    'type': 'pdsch'
                }
                
            elif pattern_name == 'srsran_phy_pdsch':
                # "[PHY] PDSCH: rnti=0x4601 h_id=0 k1=4 prb=[...] tbs=309"
                rnti, harq_id, tbs = match.groups()
                return {
                    'slot': self.current_slot,
                    'rnti': rnti,
                    'tbs': int(tbs),
                    'harq_id': int(harq_id),
                    'type': 'phy_pdsch'
                }
                
            elif pattern_name == 'srsran_rar_pdsch':
                # "- RAR PDSCH: ra-rnti=0x10b rb=[...] tbs=9 mcs=0"
                rnti, tbs, mcs = match.groups()
                return {
                    'slot': self.current_slot,
                    'rnti': rnti,
                    'tbs': int(tbs),
                    'mcs': int(mcs),
                    'type': 'rar_pdsch'
                }
                
            elif pattern_name == 'generic_pdsch':
                # Generic pattern fallback
                groups = match.groups()
                if len(groups) >= 4:
                    ue_id = int(groups[0])
                    rnti = groups[1]
                    tbs = int(groups[2])
                    mcs = int(groups[3])
                    
                    return {
                        'slot': self.current_slot,
                        'ue_id': ue_id,
                        'rnti': rnti,
                        'mcs': mcs,
                        'tbs': tbs,
                        'harq_id': None,
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
                        # Store PDSCH transmission data from UE PDSCH logs
                        self.slot_data[slot].update({
                            'mcs': data.get('mcs'),
                            'tbs': data.get('tbs'),
                            'harq_id': data.get('harq_id', slot % 8),  # Default HARQ ID
                            'ue_id': data.get('ue_id'),
                            'rnti': data.get('rnti'),
                            'nrtx': data.get('nrtx', 0)  # Number of retransmissions
                        })
                        
                    elif data['type'] == 'rar_pdsch':
                        # Store RAR PDSCH data (usually for initial access)
                        self.slot_data[slot].update({
                            'mcs': data.get('mcs'),
                            'tbs': data.get('tbs'),
                            'harq_id': 0,  # RAR typically uses HARQ ID 0
                            'rnti': data.get('rnti'),
                            'nrtx': 0,
                            'type': 'rar'
                        })
                        
                    elif data['type'] == 'phy_pdsch':
                        # PHY layer confirmation - can be used to validate MAC layer data
                        if slot in self.slot_data and not self.slot_data[slot]['tbs']:
                            self.slot_data[slot]['tbs'] = data.get('tbs')
                        
                    elif data['type'] == 'harq':
                        # Process HARQ feedback (if present)
                        if data.get('ack') == 0:  # NACK - retransmission needed
                            self.slot_data[slot]['retx_count'] += 1
                        self.slot_data[slot]['ack_received'] = data.get('ack')
        
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
                    
                    # Use nrtx if available, otherwise retx_count
                    retx_count = data.get('nrtx', data.get('retx_count', 0))
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

    def debug_parse_sample(self, input_file, num_lines=100):
        """Debug function to show parsing results for first few lines."""
        print(f"=== DEBUG MODE: Analyzing first {num_lines} lines ===")
        
        line_count = 0
        found_patterns = {}
        
        with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line_count += 1
                if line_count > num_lines:
                    break
                    
                # Check each pattern
                for pattern_name, pattern in self.patterns.items():
                    if pattern_name in ['slot_indicator', 'srsran_slot']:
                        continue
                    
                    if pattern.search(line):
                        if pattern_name not in found_patterns:
                            found_patterns[pattern_name] = []
                        found_patterns[pattern_name].append((line_count, line.strip()[:200]))
                        
                # Show slot extraction
                slot = self.extract_slot_from_line(line)
                if slot != self.current_slot:
                    print(f"Line {line_count}: Slot changed to {slot}")
                    self.current_slot = slot
                    
                # Show PDSCH matches
                data = self.parse_line(line)
                if data:
                    print(f"Line {line_count}: FOUND {data['type']} -> {data}")
        
        print(f"\n=== Pattern Matches in first {num_lines} lines ===")
        for pattern_name, matches in found_patterns.items():
            print(f"{pattern_name}: {len(matches)} matches")
            for line_num, line_text in matches[:3]:  # Show first 3 matches
                print(f"  Line {line_num}: {line_text}")
            if len(matches) > 3:
                print(f"  ... and {len(matches) - 3} more matches")
        
        if not found_patterns:
            print("No pattern matches found! Checking for common log patterns...")
            # Show sample lines that might contain relevant data
            with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
                for i, line in enumerate(f):
                    if i > num_lines:
                        break
                    if any(keyword in line.lower() for keyword in ['pdsch', 'tbs', 'mcs', 'ue']):
                        print(f"Line {i+1}: {line.strip()[:200]}")


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
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug mode (analyze first 100 lines)')
    parser.add_argument('--debug-lines', type=int, default=100,
                       help='Number of lines to analyze in debug mode')
    parser.add_argument('--output-dir', default='configs/l4span',
                       help='Output directory')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input_log):
        print(f"Error: Input file '{args.input_log}' not found!")
        return 1
    
    # Ensure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Create parser instance
    trace_parser = PDSCHTraceParser()
    
    if args.debug:
        # Debug mode - analyze sample of the file
        trace_parser.debug_parse_sample(args.input_log, args.debug_lines)
        return 0
    
    # Normal processing
    trace_parser.process_file(args.input_log)
    
    if args.stats:
        trace_parser.print_stats()
    
    # Generate trace file
    output_path = os.path.join(args.output_dir, args.output)
    trace_parser.generate_trace(output_path, args.min_slot, args.max_slot)
    
    print(f"\n✓ Trace file generated: {output_path}")
    print(f"\nTo use this trace in L4Span, add to your configuration:")
    print(f"  dl_scheduler_trace_file: \"{output_path}\"")
    
    return 0
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug mode for detailed parsing output')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input_log):
        print(f"Error: Input log file not found: {args.input_log}")
        return 1
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    output_path = os.path.join(args.output_dir, args.output)
if __name__ == "__main__":
    exit(main())