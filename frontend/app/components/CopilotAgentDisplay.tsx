// SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
// SPDX-License-Identifier: Apache-2.0

/**
 * CopilotKit AG-UI Agent State Display
 * 
 * Replaces custom AgentFlowDisplay with CopilotKit's native AG-UI visualization.
 * Renders real-time agent state updates from the AG-UI protocol.
 */

"use client";

import { useCopilotAction, useCopilotReadable } from "@copilotkit/react-core";
import { useState, useEffect } from "react";

interface AgentState {
  currentNode?: string;
  plan?: string;
  udf_strategy?: string;
  logs?: string[];
  queries?: string[];
  running_summary?: string;
  final_report?: string;
  isProcessing?: boolean;
}

interface CopilotAgentDisplayProps {
  onResearchStart: () => void;
  onResearchComplete: (report: string) => void;
}

export function CopilotAgentDisplay({ 
  onResearchStart, 
  onResearchComplete 
}: CopilotAgentDisplayProps) {
  const [agentState, setAgentState] = useState<AgentState>({
    isProcessing: false,
    logs: [],
    queries: []
  });

  // Make agent state available to CopilotKit
  useCopilotReadable({
    description: "Current agent execution state",
    value: agentState
  });

  // Register research action with CopilotKit
  useCopilotAction({
    name: "generate_research",
    description: "Generate a comprehensive research report using AI-Q agent with RAG and web search capabilities",
    parameters: [
      {
        name: "topic",
        type: "string",
        description: "The research topic or question to investigate",
        required: true,
      },
      {
        name: "report_organization",
        type: "string",
        description: "How to organize the report",
        required: false,
      },
      {
        name: "collection",
        type: "string",
        description: "RAG collection name (e.g., 'us_tariffs')",
        required: false,
      },
      {
        name: "search_web",
        type: "boolean",
        description: "Whether to search the web using Tavily API",
        required: false,
      },
    ],
    handler: async ({ topic, report_organization, collection, search_web }) => {
      console.log("🚀 CopilotKit action invoked:", { topic, collection, search_web });
      
      setAgentState(prev => ({ ...prev, isProcessing: true, logs: [] }));
      onResearchStart();

      try {
        const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

        // Use the custom streaming endpoint for now
        // In future, this could use CopilotKit's agent invocation
        const response = await fetch(`${BACKEND_URL}/research/stream`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            topic: topic || "",
            report_organization: report_organization || "Create a comprehensive report",
            collection: collection || "",
            search_web: search_web !== false,
          }),
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();

        if (!reader) {
          throw new Error("No response body");
        }

        let buffer = "";
        let finalReport = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.substring(6));

                if (data.type === "update") {
                  const state = data.state;
                  setAgentState(prev => ({
                    ...prev,
                    currentNode: data.node,
                    plan: state.plan || prev.plan,
                    udf_strategy: state.udf_strategy || prev.udf_strategy,
                    logs: state.logs || prev.logs,
                    queries: state.queries || prev.queries,
                    running_summary: state.running_summary || prev.running_summary,
                  }));
                  
                  if (state.final_report) {
                    finalReport = state.final_report;
                  }
                } else if (data.type === "complete") {
                  setAgentState(prev => ({ ...prev, isProcessing: false }));
                  if (finalReport) {
                    onResearchComplete(finalReport);
                  }
                } else if (data.type === "error") {
                  throw new Error(data.message);
                }
              } catch (e) {
                console.error("Error parsing SSE event:", e);
              }
            }
          }
        }

        return `Research completed successfully! Report generated with ${finalReport.length} characters.`;
      } catch (error) {
        console.error("Research failed:", error);
        setAgentState(prev => ({ ...prev, isProcessing: false }));
        throw error;
      }
    },
  });

  // Render the agent state visualization
  return (
    <div className="space-y-4 animate-fade-in">
      {/* Show idle state when no agent is running */}
      {!agentState.isProcessing && agentState.logs && agentState.logs.length === 0 ? (
        <div className="text-gray-400 italic">
          Agent is idle. Submit a research request to begin.
          <div className="text-xs text-gray-500 mt-2">
            ✨ Powered by CopilotKit AG-UI Protocol
          </div>
        </div>
      ) : (
        <>
          {/* Current Phase Indicator */}
          <div className="bg-blue-900/50 border border-blue-500 rounded-lg p-4">
            <div className="text-sm text-blue-300 mb-1">Current Phase</div>
            <div className="text-xl font-semibold text-white flex items-center gap-2">
              <span>{getPhaseEmoji(agentState.currentNode)}</span>
              <span>{getPhaseLabel(agentState.currentNode)}</span>
              {agentState.isProcessing && (
                <span className="inline-block animate-pulse text-blue-400">●</span>
              )}
            </div>
            {agentState.currentNode && (
              <div className="text-xs text-blue-400 mt-1">Node: {agentState.currentNode}</div>
            )}
          </div>

          {/* Strategy Path Indicator */}
          {agentState.plan && (
            <div className="bg-purple-900/50 border border-purple-500 rounded-lg p-4">
              <div className="text-sm text-purple-300 mb-2">Strategy Selected</div>
              <div className="text-white">
                {agentState.udf_strategy ? (
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
              {agentState.plan && (
                <div className="text-sm text-purple-200 mt-2 opacity-75">
                  {agentState.plan.substring(0, 150)}...
                </div>
              )}
            </div>
          )}

          {/* Execution Logs */}
          {agentState.logs && agentState.logs.length > 0 && (
            <div className="bg-gray-900/50 border border-gray-600 rounded-lg p-4">
              <div className="text-sm text-gray-300 mb-2 font-semibold">Execution Logs</div>
              <div className="space-y-1 max-h-60 overflow-y-auto">
                {agentState.logs.map((log, idx) => (
                  <div
                    key={idx}
                    className="text-xs text-gray-400 font-mono py-1 px-2 bg-gray-800/50 rounded"
                  >
                    {log}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Generated Queries */}
          {agentState.queries && agentState.queries.length > 0 && (
            <div className="bg-green-900/50 border border-green-500 rounded-lg p-4">
              <div className="text-sm text-green-300 mb-2 font-semibold">
                Generated Queries ({agentState.queries.length})
              </div>
              <ul className="space-y-1">
                {agentState.queries.map((query, idx) => (
                  <li key={idx} className="text-sm text-green-200 flex items-start gap-2">
                    <span className="text-green-400">•</span>
                    <span>{query}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Running Summary */}
          {agentState.running_summary && (
            <div className="bg-yellow-900/50 border border-yellow-500 rounded-lg p-4">
              <div className="text-sm text-yellow-300 mb-2 font-semibold">Running Summary</div>
              <div className="text-sm text-yellow-100 max-h-40 overflow-y-auto">
                {agentState.running_summary}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// Helper functions
function getPhaseEmoji(node?: string): string {
  if (!node) return "⚙️";
  
  const emojiMap: Record<string, string> = {
    planner: "🤔",
    udf_execution: "🚀",
    generate_query: "📋",
    web_research: "🔍",
    summarize_sources: "📝",
    reflect_on_summary: "🔄",
    finalize_summary: "📄",
  };
  
  return emojiMap[node] || "⚙️";
}

function getPhaseLabel(node?: string): string {
  if (!node) return "Processing";
  
  const labelMap: Record<string, string> = {
    planner: "Planning Strategy",
    udf_execution: "UDF Execution",
    generate_query: "Query Generation",
    web_research: "Research",
    summarize_sources: "Synthesis",
    reflect_on_summary: "Reflection",
    finalize_summary: "Finalization",
  };
  
  return labelMap[node] || "Processing";
}

