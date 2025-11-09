// SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
// SPDX-License-Identifier: Apache-2.0

/**
 * Agent Flow Display Component
 * 
 * This is the CORE visualization component for the hackathon.
 * It uses CopilotKit's useCoAgentStateRender hook to subscribe to
 * the backend agent's state and render it in real-time.
 * 
 * As described in the design plan (Part II), this provides the
 * "agentic flow" visualization required by the hackathon.
 */

"use client";

import { useCoAgentStateRender } from "@copilotkit/react-core";
import { useState, useEffect } from "react";

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

interface AgentFlowDisplayProps {
  logs?: string[];
  executionPath?: string;
}

export function AgentFlowDisplay({ logs: propLogs, executionPath: propExecutionPath }: AgentFlowDisplayProps) {
  const [flowHistory, setFlowHistory] = useState<string[]>([]);
  const [currentPhase, setCurrentPhase] = useState<string>("Idle");

  // Subscribe to agent state with useCoAgentStateRender
  // The name "ai_q_researcher" MUST match the app_id in backend main.py
  useCoAgentStateRender<AgentState>({
    name: "ai_q_researcher",
    render: ({ state }) => {
      // This render function is called every time the agent state updates
      
      // Fallback to props if CopilotKit state is not available
      const logs = state?.logs && state.logs.length > 0 ? state.logs : (propLogs || []);
      const udfStrategy = state?.udf_strategy || (propExecutionPath === "UDF" ? "Dynamic UDF" : "");
      
      if (logs.length === 0) {
        return (
          <div className="text-gray-400 italic">
            Agent is idle. Submit a research request to begin.
          </div>
        );
      }

      // Determine current phase from logs
      const latestLog = logs[logs.length - 1] || "";
      
      let phase = "Processing";
      if (latestLog.includes("Analyzing research complexity")) {
        phase = "🤔 Planning";
      } else if (latestLog.includes("Executing dynamic UDF strategy")) {
        phase = "🚀 UDF Execution";
      } else if (latestLog.includes("Generating research queries")) {
        phase = "📋 Query Generation";
      } else if (latestLog.includes("Conducting research")) {
        phase = "🔍 Research";
      } else if (latestLog.includes("Synthesizing report")) {
        phase = "📝 Synthesis";
      } else if (latestLog.includes("Finalizing report")) {
        phase = "📄 Finalization";
      } else if (latestLog.includes("complete")) {
        phase = "✅ Complete";
      }

      // Update flow history
      setFlowHistory(logs);
      setCurrentPhase(phase);

      return (
        <div className="space-y-4">
          {/* Current Phase Indicator */}
          <div className="bg-blue-900/50 border border-blue-500 rounded-lg p-4">
            <div className="text-sm text-blue-300 mb-1">Current Phase</div>
            <div className="text-xl font-semibold text-white">{phase}</div>
          </div>

          {/* Strategy Path Indicator */}
          {(state?.plan || propExecutionPath) && (
            <div className="bg-purple-900/50 border border-purple-500 rounded-lg p-4">
              <div className="text-sm text-purple-300 mb-2">Strategy Selected</div>
              <div className="text-white">
                {udfStrategy || propExecutionPath === "UDF" ? (
                  <span className="inline-flex items-center gap-2">
                    <span className="text-2xl">🚀</span>
                    <span className="font-semibold">Dynamic UDF Strategy</span>
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-2">
                    <span className="text-2xl">📚</span>
                    <span className="font-semibold">Simple RAG Pipeline</span>
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Logs Display */}
          <div className="bg-gray-900/80 rounded-lg p-4 max-h-96 overflow-y-auto">
            <div className="text-sm text-gray-300 mb-3 font-semibold">
              Execution Log
            </div>
            <div className="space-y-2 font-mono text-sm">
              {logs.map((log, index) => (
                <div
                  key={index}
                  className="text-gray-300 leading-relaxed animate-fade-in"
                  style={{ animationDelay: `${index * 0.05}s` }}
                >
                  <span className="text-blue-400">→</span> {log}
                </div>
              ))}
            </div>
          </div>

          {/* Queries Display (if available) */}
          {state?.queries && state.queries.length > 0 && (
            <div className="bg-green-900/30 border border-green-500 rounded-lg p-4">
              <div className="text-sm text-green-300 mb-2 font-semibold">
                Generated Queries ({state.queries.length})
              </div>
              <ul className="space-y-2 text-sm">
                {state.queries.map((q, idx) => (
                  <li key={idx} className="text-gray-300">
                    <span className="text-green-400 font-bold">{idx + 1}.</span> {q.query}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* UDF Result Display (if available) */}
          {state?.udf_result && state.udf_result.success && (
            <div className="bg-yellow-900/30 border border-yellow-500 rounded-lg p-4">
              <div className="text-sm text-yellow-300 mb-2 font-semibold">
                UDF Execution Result
              </div>
              <div className="text-gray-300 text-sm">
                ✅ Strategy executed successfully
                {state.udf_result.sources && (
                  <div className="mt-2">
                    📚 Retrieved {state.udf_result.sources.length} sources
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Final Report Ready Indicator */}
          {state?.final_report && state.final_report.length > 0 && (
            <div className="bg-emerald-900/50 border border-emerald-500 rounded-lg p-4">
              <div className="text-emerald-300 font-semibold flex items-center gap-2">
                <span className="text-2xl">🎉</span>
                <span>Research Complete! Report ready in right panel.</span>
              </div>
            </div>
          )}
        </div>
      );
    },
  });

  return null; // The hook itself handles rendering via the render callback
}

