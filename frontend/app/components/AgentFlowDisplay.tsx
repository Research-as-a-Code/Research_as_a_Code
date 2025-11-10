// SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
// SPDX-License-Identifier: Apache-2.0

/**
 * Agent Flow Display Component
 * 
 * Displays agent execution status and logs.
 * Currently showing static "idle" state.
 * TODO: Re-implement with working SSE connection.
 */

"use client";

import { useState } from "react";

/**
 * Agent state interface - MUST match Python HackathonAgentState TypedDict
 * This is the "contract" between backend and frontend.
 */
interface AgentState {
  research_prompt: string;
  report_organization: string;
  collection: string;
  search_web: boolean;
  plan: string;
  queries: Array<{
    query: string;
    report_section: string;
    rationale: string;
  }>;
  web_research_results: string[];
  citations: string;
  running_summary: string;
  udf_strategy: string;
  udf_result: {
    success?: boolean;
    report?: string;
    sources?: Array<any>;
    error?: string;
  };
  final_report: string;
  logs: string[];
}

export function AgentFlowDisplay() {
  return (
    <div className="text-gray-400 italic">
      Agent is idle. Submit a research request to begin.
      <div className="text-xs text-gray-500 mt-2">
        (Real-time SSE streaming under investigation)
      </div>
    </div>
  );
}

