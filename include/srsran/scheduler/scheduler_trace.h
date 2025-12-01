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

#pragma once

#include "srsran/ran/sch/sch_mcs.h"
#include "srsran/scheduler/harq_id.h"
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

namespace srsran {

/// Trace sample for a single slot
struct dl_scheduler_trace_sample {
  unsigned         slot_index;      ///< Slot index in the trace
  sch_mcs_index    mcs;              ///< MCS index to use
  unsigned         tbs;              ///< Transport Block Size in bytes
  bool             needs_retx;       ///< Whether this transmission is a retransmission
  unsigned         retx_count;       ///< Retransmission count (0 = first transmission)
  std::optional<harq_id_t> harq_id; ///< HARQ process ID (optional)

  dl_scheduler_trace_sample() : 
    slot_index(0), 
    mcs(0), 
    tbs(0), 
    needs_retx(false), 
    retx_count(0) {}
};

/// Manager for downlink scheduler trace
class dl_scheduler_trace_manager {
public:
  /// Constructor
  explicit dl_scheduler_trace_manager(const std::string& trace_file);

  /// Get trace sample for a specific slot
  /// \param slot Slot point
  /// \return Trace sample if available, nullopt otherwise
  std::optional<dl_scheduler_trace_sample> get_trace_sample(slot_point slot) const;

  /// Check if trace is valid and loaded
  bool is_valid() const { return !trace_samples_.empty(); }

  /// Get total number of samples in trace
  size_t size() const { return trace_samples_.size(); }

  /// Enable/disable trace override
  void set_enabled(bool enable) { enabled_ = enable; }
  
  /// Check if trace override is enabled
  bool is_enabled() const { return enabled_; }

  /// Get trace sample by index (for sequential access)
  std::optional<dl_scheduler_trace_sample> get_sample_by_index(size_t index) const;

private:
  /// Load trace file
  void load_trace_file(const std::string& filename);

  /// Parse a single line from trace file
  bool parse_trace_line(const std::string& line, dl_scheduler_trace_sample& sample);

  std::vector<dl_scheduler_trace_sample> trace_samples_;
  std::unordered_map<unsigned, size_t> slot_to_index_; ///< Map slot index to trace sample index
  bool enabled_ = true;
  size_t current_index_ = 0; ///< For sequential access
};

} // namespace srsran
