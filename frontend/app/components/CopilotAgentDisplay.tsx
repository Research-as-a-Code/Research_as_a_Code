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
import { StrategyToggle, ResearchStrategy } from "./StrategyToggle";
import { TTDDRProgressDisplay, TTDDRStage } from "./TTDDRProgressDisplay";

interface AgentState {
  currentNode?: string;
  plan?: string;
  udr_strategy?: string;  // UDR compiled strategy
  ttd_dr_stage?: TTDDRStage;  // TTD-DR current stage
  ttd_dr_iteration?: number;  // TTD-DR current iteration
  ttd_dr_convergence?: number[];  // TTD-DR convergence scores
  ttd_dr_questions?: string[];  // TTD-DR current questions
  ttd_dr_gaps?: string[];  // TTD-DR identified gaps
  ttd_dr_improvements?: string[];  // TTD-DR recent improvements
  logs: string[];
  queries: (string | { query: string; report_section?: string; rationale?: string })[];  // Can be string or object
  running_summary?: string;
  final_report?: string;
  isProcessing: boolean;
  strategy?: ResearchStrategy;  // Current strategy being used
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
    isProcessing: false,
    strategy: 'udr'  // Default to UDR
  });
  
  const { currentParams, clearParams, selectedStrategy, setSelectedStrategy } = useCopilotResearch();

  // Make agent state available to CopilotKit
  useCopilotReadable({
    description: "Current AI-Q agent execution state",
    value: agentState
  });
  
  // Expose selected strategy to parent components
  useCopilotReadable({
    description: "Currently selected research strategy",
    value: selectedStrategy
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
      {
        name: "strategy",
        type: "string",
        description: "Research strategy to use: 'udr' or 'ttd_dr'",
        required: false,
      },
    ],
    handler: async ({ topic, report_organization, collection, search_web, strategy }) => {
      const DEPLOYMENT_VERSION = "v2.1-" + Date.now();  // Unique version for this deployment
      console.log("🚀 CopilotKit action invoked via AG-UI:", { topic, collection, search_web });
      console.log("📦 Deployment version:", DEPLOYMENT_VERSION);
      
      // Prevent duplicate execution - check if already processing
      if (agentState.isProcessing) {
        console.log("⏭️ Skipping duplicate execution (already processing)");
        return "Research already in progress";
      }
      
      const activeStrategy: ResearchStrategy = (strategy as ResearchStrategy) || selectedStrategy;
      setAgentState({ 
        logs: [], 
        queries: [], 
        isProcessing: true,
        strategy: activeStrategy,
        ttd_dr_stage: activeStrategy === 'ttd_dr' ? 'planning' : undefined
      });
      onResearchStart();

      try {
        const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
        
        // Add cache-busting parameter to prevent ELB/CDN caching
        const cacheBuster = `${Date.now()}-${Math.random().toString(36).substring(7)}`;
        const requestId = `req-${cacheBuster}`;
        const endpoint = `${BACKEND_URL}/research/stream?cb=${cacheBuster}`;
        
        console.log("🔗 Backend URL:", BACKEND_URL);
        console.log("🌐 Full endpoint (with cache-buster):", endpoint);
        console.log("🆔 Request ID:", requestId, "- If you see this same ID again without submitting, responses are cached!");

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
            strategy: activeStrategy,  // Pass strategy to backend
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
        let lastDataTime = Date.now();
        const INACTIVITY_THRESHOLD = 120000; // 120 seconds (2 minutes) - extended as requested

        console.log(`🕐 Starting stream read at ${new Date().toISOString()}, inactivity threshold: ${INACTIVITY_THRESHOLD/1000}s`);

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
                    udr_strategy: data.state.udr_strategy || prev.udr_strategy,
                    // Preserve the strategy selection throughout execution
                    strategy: prev.strategy,  // Keep the initially selected strategy
                    // Backend now sends accumulated logs, just use them directly
                    logs: data.state.logs || prev.logs,
                    queries: data.state.queries || prev.queries,
                    running_summary: data.state.running_summary || prev.running_summary,
                    // TTD-DR specific state updates
                    ttd_dr_stage: data.state.ttd_dr_stage || prev.ttd_dr_stage,
                    ttd_dr_iteration: data.state.ttd_dr_iteration ?? prev.ttd_dr_iteration,
                    ttd_dr_convergence: data.state.ttd_dr_convergence || prev.ttd_dr_convergence,
                    ttd_dr_questions: data.state.ttd_dr_questions || prev.ttd_dr_questions,
                    ttd_dr_gaps: data.state.ttd_dr_gaps || prev.ttd_dr_gaps,
                    ttd_dr_improvements: data.state.ttd_dr_improvements || prev.ttd_dr_improvements,
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
      console.log("📊 Using strategy from context:", selectedStrategy);
      
      // Prevent duplicate execution - check if already processing
      if (agentState.isProcessing) {
        console.log("⏭️ Skipping useEffect execution (already processing via useCopilotAction)");
        clearParams();
        return;
      }
      
      // Use strategy from context
      const activeStrategy = (currentParams.strategy as ResearchStrategy) || selectedStrategy;
      console.log("🎯 Active strategy for this request:", activeStrategy);
      
      setAgentState({ 
        logs: [], 
        queries: [], 
        isProcessing: true,
        strategy: activeStrategy,
        ttd_dr_stage: activeStrategy === 'ttd_dr' ? 'planning' : undefined
      });
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
            strategy: activeStrategy,  // Send selected strategy to backend
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
                    udr_strategy: data.state.udr_strategy || prev.udr_strategy,
                    ttd_dr_stage: data.state.ttd_dr_stage || prev.ttd_dr_stage,
                    ttd_dr_iteration: data.state.ttd_dr_iteration || prev.ttd_dr_iteration,
                    ttd_dr_convergence: data.state.ttd_dr_convergence || prev.ttd_dr_convergence,
                    ttd_dr_questions: data.state.ttd_dr_questions || prev.ttd_dr_questions,
                    ttd_dr_gaps: data.state.ttd_dr_gaps || prev.ttd_dr_gaps,
                    ttd_dr_improvements: data.state.ttd_dr_improvements || prev.ttd_dr_improvements,
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
      {/* Strategy Selection Toggle */}
      <StrategyToggle 
        value={selectedStrategy} 
        onChange={setSelectedStrategy} 
        disabled={agentState.isProcessing}
      />
      
      {/* TTD-DR Progress Display removed - callback system not functional
          Progress is visible in Execution Logs instead */}
      
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

          {/* Strategy Path Indicator - Shows which execution path was taken */}
          {agentState.plan && (
            <div className="bg-purple-900/50 border border-purple-500 rounded-lg p-4">
              <div className="text-sm text-purple-300 mb-2">Strategy Selected</div>
              <div className="text-white">
                {agentState.strategy === 'ttd_dr' ? (
                  <span className="inline-flex items-center gap-2">
                    <span className="text-2xl">🔬</span>
                    <span className="font-semibold">Dynamic TTD-DR Strategy</span>
                  </span>
                ) : agentState.udr_strategy || agentState.strategy === 'udr' ? (
                  <span className="inline-flex items-center gap-2">
                    <span className="text-2xl">🚀</span>
                    <span className="font-semibold">Dynamic UDR Strategy</span>
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
            <div className="bg-blue-900/50 border border-blue-500 rounded-lg p-4">
              <div className="text-sm text-blue-300 mb-3 font-semibold flex items-center justify-between">
                <span>Execution Logs</span>
                <span className="text-xs text-blue-400 bg-blue-500/20 px-2 py-1 rounded">
                  {agentState.logs.length} {agentState.logs.length === 1 ? 'entry' : 'entries'}
                </span>
              </div>
              <div className="space-y-2 max-h-80 overflow-y-auto pr-2">
                {agentState.logs.map((log, idx) => (
                  <div
                    key={idx}
                    className="text-sm text-blue-100 font-mono py-2 px-3 bg-blue-950/50 rounded border border-blue-800/30 animate-fade-in"
                    style={{ animationDelay: `${Math.min(idx * 0.05, 0.5)}s` }}
                  >
                    <span className="text-blue-400 mr-2">→</span>
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
                    <span>{typeof query === 'string' ? query : query.query}</span>
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
    udf_execution: "UDR Execution",
    generate_query: "Query Generation",
    web_research: "Research",
    summarize_sources: "Synthesis",
    reflect_on_summary: "Reflection",
    finalize_summary: "Finalization",
  };
  
  return labelMap[node] || "Processing";
}

