/*
 *
 * Copyright 2021-2024 Software Radio Systems Limited
 *
 * This file is part of srsRAN.
 *
 * srsRAN is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as
 * published by the Free Software Foundation, either version 3 of
 * the License, or (at your option) any later version.
 *
 * srsRAN is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * A copy of the GNU Affero General Public License can be found in
 * the LICENSE file in the top-level directory of this distribution
 * and at http://www.gnu.org/licenses/.
 *
 */

#include "srsran/scheduler/scheduler_trace.h"
#include "srsran/srslog/srslog.h"
#include "srsran/ran/slot_point.h"
#include <fstream>
#include <sstream>

using namespace srsran;

dl_scheduler_trace_manager::dl_scheduler_trace_manager(const std::string& trace_file)
{
  if (!trace_file.empty()) {
    load_trace_file(trace_file);
  }
}

void dl_scheduler_trace_manager::load_trace_file(const std::string& filename)
{
  auto& logger = srslog::fetch_basic_logger("SCHED");

  std::ifstream file(filename);
  
  if (!file.is_open()) {
    logger.warning("Failed to open scheduler trace file '{}'. Trace-based scheduling disabled.", filename);
    enabled_ = false;
    return;
  }

  std::string line;
  size_t      line_num = 0;
  size_t      valid_samples = 0;

  while (std::getline(file, line)) {
    line_num++;

    // Skip empty lines and comments
    if (line.empty() || line[0] == '#') {
      continue;
    }

    dl_scheduler_trace_sample sample;
    if (parse_trace_line(line, sample)) {
      // Store sample
      trace_samples_.push_back(sample);
      
      // Build slot index map
      slot_to_index_[sample.slot_index] = trace_samples_.size() - 1;
      
      valid_samples++;
    } else {
      logger.warning("Failed to parse trace line {} in file '{}'", line_num, filename);
    }
  }

  if (trace_samples_.empty()) {
    logger.warning("No valid samples in trace file '{}'. Trace-based scheduling disabled.", filename);
    enabled_ = false;
  } else {
    logger.info("Loaded {} scheduler trace samples from '{}' ({} lines processed)", 
                valid_samples, filename, line_num);
    enabled_ = true;
  }
}

bool dl_scheduler_trace_manager::parse_trace_line(const std::string& line, dl_scheduler_trace_sample& sample)
{
  std::istringstream iss(line);
  char               comma;
  int                needs_retx_int;
  int                harq_id_int = -1;

  // Try to detect format by counting commas
  std::string line_copy = line;
  size_t comma_count = std::count(line_copy.begin(), line_copy.end(), ',');
  
  if (comma_count == 1) {
    // TBS-only format: slot_index,tbs_bytes
    iss >> sample.slot_index >> comma >> sample.tbs;
    
    if (iss.fail()) {
      return false;
    }
    
    // Set default values for missing fields
    sample.mcs = sch_mcs_index{0}; // Will be calculated dynamically
    sample.needs_retx = false;
    sample.retx_count = 0;
    sample.harq_id = std::nullopt;
    
  } else {
    // Full format: slot_index, mcs, tbs, needs_retx, retx_count[, harq_id]
    unsigned mcs_val;
    iss >> sample.slot_index >> comma 
        >> mcs_val >> comma 
        >> sample.tbs >> comma 
        >> needs_retx_int >> comma 
        >> sample.retx_count;
    sample.mcs = sch_mcs_index{static_cast<uint8_t>(mcs_val)};

    if (iss.fail()) {
      return false;
    }

    // Optional HARQ ID
    if (iss >> comma >> harq_id_int) {
      if (harq_id_int >= 0) {
        sample.harq_id = to_harq_id(harq_id_int);
      }
    }

    sample.needs_retx = (needs_retx_int != 0);
    
    // Validate MCS only for full format
    if (sample.mcs > 28) { // Max MCS for PDSCH
      return false;
    }
  }

  if (sample.tbs == 0) {
    return false;
  }

  if (sample.retx_count > 4) { // Reasonable limit
    return false;
  }

  return true;
}

std::optional<dl_scheduler_trace_sample> 
dl_scheduler_trace_manager::get_trace_sample(slot_point slot) const
{
  if (!enabled_ || trace_samples_.empty()) {
    return std::nullopt;
  }

  // Don't apply trace until UE access is complete (configurable delay)
  if (slot.to_uint() < start_slot_) {
    return std::nullopt;
  }

  // Return the next sample in sequence and advance the index
  dl_scheduler_trace_sample sample = trace_samples_[current_index_];
  
  // Advance to next sample, wrapping around to beginning if at end
  current_index_ = (current_index_ + 1) % trace_samples_.size();
  
  return sample;
}

std::optional<dl_scheduler_trace_sample> 
dl_scheduler_trace_manager::get_sample_by_index(size_t index) const
{
  if (!enabled_ || trace_samples_.empty() || index >= trace_samples_.size()) {
    return std::nullopt;
  }

  return trace_samples_[index];
}
