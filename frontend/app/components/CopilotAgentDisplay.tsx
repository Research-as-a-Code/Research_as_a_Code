// SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
// SPDX-License-Identifier: Apache-2.0

/**
 * CopilotKit AG-UI Agent State Display
 * 
 * Uses CopilotKit's useCopilotAction to invoke the AI-Q agent via AG-UI protocol.
 * Renders real-time agent state updates from CopilotKit.
 * 
 * Supports parallel execution of multiple strategies for side-by-side comparison.
 */

"use client";

import { useCopilotAction, useCopilotReadable } from "@copilotkit/react-core";
import { useState, useEffect, useRef, useCallback } from "react";
import { useCopilotResearch } from "../contexts/CopilotResearchContext";
import { StrategySelector, ResearchStrategy, STRATEGY_CONFIG } from "./StrategySelector";
import { TTDDRStage } from "./TTDDRProgressDisplay";
import { getBackendUrl } from "../utils/backendUrl";

interface PerStrategyState {
  currentNode?: string;
  plan?: string;
  udr_strategy?: string;
  ttd_dr_stage?: TTDDRStage;
  ttd_dr_iteration?: number;
  ttd_dr_convergence?: number[];
  ttd_dr_questions?: string[];
  ttd_dr_gaps?: string[];
  ttd_dr_improvements?: string[];
  logs: string[];
  queries: (string | { query: string; report_section?: string; rationale?: string })[];
  running_summary?: string;
  final_report?: string;
  isLoading: boolean;
  error?: string;
  startTime?: number;
  endTime?: number;
}

interface CopilotAgentDisplayProps {
  onResearchStart: () => void;
  onResearchComplete: (strategy: ResearchStrategy, report: string) => void;
  onAllComplete: () => void;
}

export function CopilotAgentDisplay({ 
  onResearchStart, 
  onResearchComplete,
  onAllComplete
}: CopilotAgentDisplayProps) {
  const [strategyStates, setStrategyStates] = useState<Map<ResearchStrategy, PerStrategyState>>(new Map());
  const [isProcessing, setIsProcessing] = useState(false);
  const abortControllersRef = useRef<Map<ResearchStrategy, AbortController>>(new Map());
  
  const { 
    currentParams, 
    clearParams, 
    selectedStrategies, 
    setSelectedStrategies,
    updateReportResult,
    clearReportResults,
    setIsResearching
  } = useCopilotResearch();

  // Make agent state available to CopilotKit
  useCopilotReadable({
    description: "Current AI-Q agent execution state for all strategies",
    value: Object.fromEntries(strategyStates)
  });
  
  useCopilotReadable({
    description: "Currently selected research strategies",
    value: selectedStrategies
  });

  // Helper to update a specific strategy's state
  const updateStrategyState = useCallback((
    strategy: ResearchStrategy, 
    update: Partial<PerStrategyState> | ((prev: PerStrategyState) => PerStrategyState)
  ) => {
    setStrategyStates(prev => {
      const newMap = new Map(prev);
      const existing = newMap.get(strategy) || {
        logs: [],
        queries: [],
        isLoading: false,
      };
      
      const updated = typeof update === 'function' 
        ? update(existing)
        : { ...existing, ...update };
      
      newMap.set(strategy, updated);
      return newMap;
    });
  }, []);

  // Execute research for a single strategy (returns a promise)
  const executeStrategyResearch = useCallback(async (
    strategy: ResearchStrategy,
    params: {
      topic: string;
      report_organization: string;
      collection: string;
      search_web: boolean;
    }
  ): Promise<string> => {
    const startTime = Date.now();
    const controller = new AbortController();
    abortControllersRef.current.set(strategy, controller);

    // Initialize state for this strategy
    updateStrategyState(strategy, {
      logs: [],
      queries: [],
      isLoading: true,
      startTime,
      endTime: undefined,
      final_report: undefined,
      error: undefined,
      ttd_dr_stage: strategy === 'ttd_dr' ? 'planning' : undefined,
    });

    // Update report results for tabbed display
    updateReportResult(strategy, {
      isLoading: true,
      report: '',
      error: undefined,
      startTime,
      endTime: undefined,
    });

    try {
      const BACKEND_URL = getBackendUrl();
      const cacheBuster = `${Date.now()}-${Math.random().toString(36).substring(7)}`;
      const endpoint = `${BACKEND_URL}/research/stream?cb=${cacheBuster}&strategy=${strategy}`;
      
      console.log(`🔗 [${strategy}] Starting stream to:`, endpoint);

      const response = await fetch(endpoint, {
        method: "POST",
        cache: 'no-store',
        headers: { 
          "Content-Type": "application/json",
          "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
          "X-Request-ID": `${strategy}-${cacheBuster}`,
        },
        body: JSON.stringify({
          topic: params.topic,
          report_organization: params.report_organization,
          collection: params.collection,
          search_web: params.search_web,
          strategy: strategy,
        }),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";
      let finalReport = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line || line.startsWith(":")) continue;
          
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.substring(6));

              if (data.type === "update") {
                console.log(`📦 [${strategy}] State update from node:`, data.node);
                
                updateStrategyState(strategy, prev => ({
                  ...prev,
                  currentNode: data.node,
                  plan: data.state.plan || prev.plan,
                  udr_strategy: data.state.udr_strategy || prev.udr_strategy,
                  logs: data.state.logs || prev.logs,
                  queries: data.state.queries || prev.queries,
                  running_summary: data.state.running_summary || prev.running_summary,
                  ttd_dr_stage: data.state.ttd_dr_stage || prev.ttd_dr_stage,
                  ttd_dr_iteration: data.state.ttd_dr_iteration ?? prev.ttd_dr_iteration,
                  ttd_dr_convergence: data.state.ttd_dr_convergence || prev.ttd_dr_convergence,
                  ttd_dr_questions: data.state.ttd_dr_questions || prev.ttd_dr_questions,
                  ttd_dr_gaps: data.state.ttd_dr_gaps || prev.ttd_dr_gaps,
                  ttd_dr_improvements: data.state.ttd_dr_improvements || prev.ttd_dr_improvements,
                }));
                
                if (data.state.final_report) {
                  finalReport = data.state.final_report;
                }
              } else if (data.type === "complete") {
                console.log(`✅ [${strategy}] Stream complete`);
              } else if (data.type === "error") {
                throw new Error(data.message);
              }
            } catch (e) {
              if (e instanceof SyntaxError) {
                console.error(`[${strategy}] Error parsing SSE:`, e, "Line:", line);
              } else {
                throw e;
              }
            }
          }
        }
      }

      const endTime = Date.now();
      
      updateStrategyState(strategy, {
        isLoading: false,
        final_report: finalReport,
        endTime,
      });

      updateReportResult(strategy, {
        isLoading: false,
        report: finalReport,
        endTime,
      });

      if (finalReport) {
        onResearchComplete(strategy, finalReport);
      }

      return finalReport;

    } catch (error: any) {
      const endTime = Date.now();
      const errorMessage = error.name === 'AbortError' 
        ? 'Request was cancelled'
        : error.message || 'Unknown error';
      
      console.error(`❌ [${strategy}] Research failed:`, errorMessage);
      
      updateStrategyState(strategy, {
        isLoading: false,
        error: errorMessage,
        endTime,
      });

      updateReportResult(strategy, {
        isLoading: false,
        error: errorMessage,
        endTime,
      });

      throw error;
    } finally {
      abortControllersRef.current.delete(strategy);
    }
  }, [updateStrategyState, updateReportResult, onResearchComplete]);

  // Watch for form submissions and trigger parallel research
  useEffect(() => {
    const executeAllStrategies = async () => {
      if (!currentParams || isProcessing) return;

      console.log("🚀 Starting parallel research for strategies:", selectedStrategies);
      
      setIsProcessing(true);
      setIsResearching(true);
      clearReportResults();
      setStrategyStates(new Map());
      onResearchStart();

      // Initialize all strategy states
      for (const strategy of selectedStrategies) {
        updateReportResult(strategy, {
          isLoading: true,
          report: '',
          startTime: Date.now(),
        });
      }

      // Execute all strategies in parallel
      const promises = selectedStrategies.map(strategy =>
        executeStrategyResearch(strategy, currentParams)
          .catch(err => {
            console.error(`[${strategy}] Failed:`, err);
            return null; // Don't let one failure stop others
          })
      );

      await Promise.allSettled(promises);

      console.log("✅ All strategies completed");
      setIsProcessing(false);
      setIsResearching(false);
      onAllComplete();
      clearParams();
    };

    executeAllStrategies();
  }, [currentParams]); // eslint-disable-line react-hooks/exhaustive-deps

  // CopilotKit action registration
  useCopilotAction({
    name: "generate_research",
    description: "Generate research reports using multiple strategies for comparison",
    parameters: [
      { name: "topic", type: "string", description: "The research topic", required: true },
      { name: "report_organization", type: "string", description: "How to organize the report", required: false },
      { name: "collection", type: "string", description: "RAG collection name", required: false },
      { name: "search_web", type: "boolean", description: "Whether to search the web", required: false },
    ],
    handler: async ({ topic, report_organization, collection, search_web }) => {
      console.log("🚀 CopilotKit action invoked:", { topic, selectedStrategies });
      
      if (isProcessing) {
        return "Research already in progress";
      }
      
      // This will trigger the useEffect above via context
      return `Starting research with ${selectedStrategies.length} strategy(ies)`;
    },
    render: "Researching...",
  });

  // Aggregate stats across all strategies
  const allLogs = Array.from(strategyStates.values()).flatMap(s => s.logs);
  const anyLoading = Array.from(strategyStates.values()).some(s => s.isLoading);

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Strategy Selection */}
      <StrategySelector 
        selectedStrategies={selectedStrategies} 
        onChange={setSelectedStrategies} 
        disabled={isProcessing}
      />
      
      {!isProcessing && strategyStates.size === 0 ? (
        <div className="text-gray-400 italic">
          Agent is idle. Select strategies and submit a research request.
          <div className="text-xs text-gray-500 mt-2">
            ✨ Powered by CopilotKit AG-UI Protocol
          </div>
        </div>
      ) : (
        <>
          {/* Per-Strategy Progress */}
          {selectedStrategies.map(strategy => {
            const state = strategyStates.get(strategy);
            if (!state) return null;
            
            const config = STRATEGY_CONFIG[strategy];
            const Icon = config.icon;
            
            return (
              <div 
                key={strategy}
                className={`bg-gray-900/50 border rounded-lg p-4 ${
                  state.isLoading ? config.borderColor : 'border-gray-700'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Icon className={`w-5 h-5 ${config.color}`} />
                    <span className={`font-semibold ${config.color}`}>{config.name}</span>
                    {state.isLoading && (
                      <span className="inline-block animate-pulse text-yellow-400">●</span>
                    )}
                    {!state.isLoading && state.final_report && (
                      <span className="text-green-400">✓</span>
                    )}
                    {!state.isLoading && state.error && (
                      <span className="text-red-400">✗</span>
                    )}
                  </div>
                  {state.currentNode && (
                    <span className="text-xs text-gray-500">
                      Node: {state.currentNode}
                    </span>
                  )}
                </div>
                
                {/* Compact log display */}
                {state.logs.length > 0 && (
                  <div className="text-xs text-gray-400 max-h-24 overflow-y-auto space-y-0.5">
                    {state.logs.slice(-5).map((log, idx) => (
                      <div key={idx} className="truncate">
                        <span className="text-gray-600 mr-1">→</span>
                        {log}
                      </div>
                    ))}
                  </div>
                )}
                
                {state.error && (
                  <div className="text-xs text-red-400 mt-2">
                    Error: {state.error}
                  </div>
                )}
              </div>
            );
          })}

          {/* Combined Queries Display */}
          {Array.from(strategyStates.values()).some(s => s.queries.length > 0) && (
            <div className="bg-green-900/50 border border-green-500 rounded-lg p-4">
              <div className="text-sm text-green-300 mb-2 font-semibold">
                Generated Queries
              </div>
              <ul className="space-y-1 max-h-32 overflow-y-auto">
                {Array.from(strategyStates.entries()).flatMap(([strategy, state]) =>
                  state.queries.slice(0, 3).map((query, idx) => (
                    <li key={`${strategy}-${idx}`} className="text-sm text-green-200 flex items-start gap-2">
                      <span className={STRATEGY_CONFIG[strategy].color}>
                        [{STRATEGY_CONFIG[strategy].name}]
                      </span>
                      <span>{typeof query === 'string' ? query : query.query}</span>
                    </li>
                  ))
                )}
              </ul>
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
