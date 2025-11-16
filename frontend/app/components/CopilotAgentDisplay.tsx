// SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
// SPDX-License-Identifier: Apache-2.0

/**
 * CopilotKit AG-UI Agent State Display
 * 
 * Uses CopilotKit's useCopilotAction to invoke the AI-Q agent via AG-UI protocol.
 * Renders real-time agent state updates from CopilotKit.
 */

"use client";

import { useCopilotAction, useCopilotReadable } from "@copilotkit/react-core";
import { useState, useEffect } from "react";
import { useCopilotResearch } from "../contexts/CopilotResearchContext";

interface AgentState {
  currentNode?: string;
  plan?: string;
  udf_strategy?: string;
  logs: string[];
  queries: string[];
  running_summary?: string;
  final_report?: string;
  isProcessing: boolean;
}

interface CopilotAgentDisplayProps {
  onResearchStart: () => void;
  onResearchComplete: (report: string) => void;
  onActionRegistered?: (executeAction: (params: any) => Promise<void>) => void;
}

export function CopilotAgentDisplay({ 
  onResearchStart, 
  onResearchComplete,
  onActionRegistered
}: CopilotAgentDisplayProps) {
  const [agentState, setAgentState] = useState<AgentState>({
    logs: [],
    queries: [],
    isProcessing: false
  });
  
  const { currentParams, clearParams } = useCopilotResearch();

  // Make agent state available to CopilotKit
  useCopilotReadable({
    description: "Current AI-Q agent execution state",
    value: agentState
  });

  // Register CopilotKit action for research generation (for AG-UI protocol)
  useCopilotAction({
    name: "generate_research",
    description: "Generate a comprehensive research report using the AI-Q agent with RAG and web search",
    parameters: [
      {
        name: "topic",
        type: "string",
        description: "The research topic or question",
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
        description: "Whether to search the web",
        required: false,
      },
    ],
    handler: async ({ topic, report_organization, collection, search_web }) => {
      console.log("🚀 CopilotKit action invoked via AG-UI:", { topic, collection, search_web });
      
      // Prevent duplicate execution - check if already processing
      if (agentState.isProcessing) {
        console.log("⏭️ Skipping duplicate execution (already processing)");
        return "Research already in progress";
      }
      
      setAgentState({ logs: [], queries: [], isProcessing: true });
      onResearchStart();

      try {
        const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
        
        // Add cache-busting parameter to prevent ELB/CDN caching
        const cacheBuster = `cb=${Date.now()}-${Math.random().toString(36).substring(7)}`;
        const endpoint = `${BACKEND_URL}/research/stream?${cacheBuster}`;
        
        console.log("🔗 Backend URL:", BACKEND_URL);
        console.log("🌐 Full endpoint (with cache-buster):", endpoint);

        // Call the streaming endpoint
        console.log("📡 Initiating fetch to /research/stream...");
        const response = await fetch(endpoint, {
          method: "POST",
          cache: 'no-store' as RequestCache,  // Force fetch to bypass ALL browser cache
          headers: { 
            "Content-Type": "application/json",
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Request-ID": cacheBuster  // Additional uniqueness marker
          },
          body: JSON.stringify({
            topic: topic || "",
            report_organization: report_organization || "Create a comprehensive report",
            collection: collection || "",
            search_web: search_web !== false,
          }),
        });

        console.log("📨 Response received:", response.status, response.statusText);
        console.log("📊 Response headers:", Object.fromEntries(response.headers.entries()));

        if (!response.ok) {
          console.error("❌ Response not OK:", response.status);
          throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body?.getReader();
        console.log("📖 Reader obtained:", !!reader);
        const decoder = new TextDecoder();
        if (!reader) throw new Error("No response body");

        let buffer = "";
        let finalReport = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            // Skip empty lines and SSE comments (keepalive)
            if (!line || line.startsWith(":")) {
              continue;
            }
            
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.substring(6));

                if (data.type === "update") {
                  console.log("📦 State update from node:", data.node, "Keys:", Object.keys(data.state));
                  
                  setAgentState(prev => ({
                    ...prev,
                    currentNode: data.node,
                    plan: data.state.plan || prev.plan,
                    udf_strategy: data.state.udf_strategy || prev.udf_strategy,
                    logs: data.state.logs || prev.logs,
                    queries: data.state.queries || prev.queries,
                    running_summary: data.state.running_summary || prev.running_summary,
                  }));
                  
                  if (data.state.final_report) {
                    console.log("📄 Final report received in state, length:", data.state.final_report.length);
                    finalReport = data.state.final_report;
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
                console.error("Error parsing SSE event:", e, "Line:", line);
              }
            }
          }
        }

        console.log("✅ Stream processing complete!");
        
        // Ensure we mark processing as complete and trigger callback
        setAgentState(prev => ({ ...prev, isProcessing: false }));
        if (finalReport) {
          console.log("📄 Final report received, length:", finalReport.length);
          onResearchComplete(finalReport);
        } else {
          console.warn("⚠️ Stream completed but no final report was received");
        }
        
        return `✅ Research completed! Generated ${finalReport.length} characters.`;
      } catch (error: any) {
        console.error("❌ Research failed in handler:");
        console.error("Error name:", error.name);
        console.error("Error message:", error.message);
        console.error("Error stack:", error.stack);
        console.error("Full error object:", error);
        
        setAgentState(prev => ({ ...prev, isProcessing: false }));
        
        // Handle specific streaming errors
        if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
          const betterError = new Error("Connection lost during research. Please try again.");
          console.error("Throwing better error:", betterError);
          throw betterError;
        } else if (error.message?.includes('ERR_INCOMPLETE_CHUNKED_ENCODING')) {
          const betterError = new Error("Stream was interrupted. The backend may have timed out. Try a simpler query.");
          console.error("Throwing better error:", betterError);
          throw betterError;
        }
        
        console.error("Re-throwing original error");
        throw error;
      }
    },
    render: "Researching...",
  });

  // Watch for form submissions and trigger the CopilotKit action
  // This avoids duplicate execution - we only execute via useCopilotAction handler
  useEffect(() => {
    const executeResearch = async () => {
      if (!currentParams) return;

      console.log("🔥 Form submitted with params:", currentParams);
      
      // Prevent duplicate execution - check if already processing
      if (agentState.isProcessing) {
        console.log("⏭️ Skipping useEffect execution (already processing via useCopilotAction)");
        clearParams();
        return;
      }
      
      setAgentState({ logs: [], queries: [], isProcessing: true });
      onResearchStart();

      try {
        const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
        
        // Add cache-busting parameter to prevent ELB/CDN caching
        const cacheBuster = `cb=${Date.now()}-${Math.random().toString(36).substring(7)}`;
        const endpoint = `${BACKEND_URL}/research/stream?${cacheBuster}`;
        
        console.log("🔗 Backend URL:", BACKEND_URL);
        console.log("🌐 Full endpoint:", endpoint);

        // Create AbortController with 10 minute timeout for long-running research
        const controller = new AbortController();
        const timeoutId = setTimeout(() => {
          console.warn("⏱️ Request timeout after 10 minutes");
          controller.abort();
        }, 10 * 60 * 1000);

        const response = await fetch(endpoint, {
          method: "POST",
          cache: 'no-store' as RequestCache,  // Force fetch to bypass ALL browser cache
          headers: { 
            "Content-Type": "application/json",
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Request-ID": cacheBuster  // Additional uniqueness marker
          },
          body: JSON.stringify({
            topic: currentParams.topic || "",
            report_organization: currentParams.report_organization || "Create a comprehensive report",
            collection: currentParams.collection || "",
            search_web: currentParams.search_web !== false,
          }),
          signal: controller.signal,
        });
        
        clearTimeout(timeoutId);

        console.log("📨 Response received:", response.status, response.statusText);

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();
        if (!reader) throw new Error("No response body");

        let buffer = "";
        let finalReport = "";
        let lastDataTime = Date.now();
        const INACTIVITY_THRESHOLD = 30000; // 30 seconds without data = warning

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          // Update last data time
          const now = Date.now();
          const timeSinceLastData = now - lastDataTime;
          lastDataTime = now;
          
          // Warn if we haven't received data in a while (but stream is still open)
          if (timeSinceLastData > INACTIVITY_THRESHOLD) {
            console.warn(`⚠️ Stream inactive for ${(timeSinceLastData / 1000).toFixed(1)}s`);
          }

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (!line || line.startsWith(":")) {
              continue;
            }

            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.substring(6));

                if (data.type === "update") {
                  console.log("📦 State update from node:", data.node, "Keys:", Object.keys(data.state));
                  
                  setAgentState((prev) => ({
                    ...prev,
                    currentNode: data.node,
                    plan: data.state.plan || prev.plan,
                    udf_strategy: data.state.udf_strategy || prev.udf_strategy,
                    logs: data.state.logs || prev.logs,
                    queries: data.state.queries || prev.queries,
                    running_summary: data.state.running_summary || prev.running_summary,
                  }));

                  if (data.state.final_report) {
                    console.log("📄 Final report received in state, length:", data.state.final_report.length);
                    finalReport = data.state.final_report;
                  }
                } else if (data.type === "complete") {
                  setAgentState((prev) => ({ ...prev, isProcessing: false }));
                  if (finalReport) {
                    onResearchComplete(finalReport);
                  }
                } else if (data.type === "error") {
                  throw new Error(data.message);
                }
              } catch (e) {
                console.error("Error parsing SSE event:", e, "Line:", line);
              }
            }
          }
        }

        console.log("✅ Research completed!");
        
        // Ensure we mark processing as complete and trigger callback
        setAgentState((prev) => ({ ...prev, isProcessing: false }));
        if (finalReport) {
          console.log("📄 Final report received, length:", finalReport.length);
          onResearchComplete(finalReport);
        } else {
          console.warn("⚠️ Stream completed but no final report was received");
        }
        
        clearParams();
      } catch (error: any) {
        console.error("❌ Research failed:");
        console.error("Error:", error.message);
        console.error("Error type:", error.name);
        
        // Add helpful error message to logs
        const errorMessage = error.message?.includes("network error") || error.name === "TypeError"
          ? "⚠️ Network connection lost. The research may still be processing on the server."
          : `❌ Error: ${error.message}`;
        
        setAgentState((prev) => ({
          ...prev,
          isProcessing: false,
          logs: [...prev.logs, errorMessage]
        }));
        
        clearParams();
      }
    };

    executeResearch();
  }, [currentParams, clearParams, onResearchStart, onResearchComplete]);

  return (
    <div className="space-y-4 animate-fade-in">
      {!agentState.isProcessing && agentState.logs.length === 0 ? (
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
          {agentState.logs.length > 0 && (
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
          {agentState.queries.length > 0 && (
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

