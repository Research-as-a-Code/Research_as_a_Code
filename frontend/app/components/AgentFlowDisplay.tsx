// SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
// SPDX-License-Identifier: Apache-2.0

/**
 * Agent Flow Display Component with Real-Time Streaming
 * 
 * Displays live agent execution state from AgentStreamContext.
 * Shows current phase, logs, queries, and progress in real-time.
 */

"use client";

import { useAgentStream } from "../contexts/AgentStreamContext";

export function AgentFlowDisplay() {
  const { state } = useAgentStream();

  // Show idle state when no agent is running
  if (!state.isProcessing && state.logs.length === 0) {
    return (
      <div className="text-gray-400 italic">
        Agent is idle. Submit a research request to begin.
        <div className="text-xs text-gray-500 mt-2">
          ✨ Real-time streaming via Server-Sent Events
        </div>
      </div>
    );
  }

  // Determine current phase from node name
  let phase = "Processing";
  let phaseEmoji = "⚙️";
  
  if (state.isProcessing) {
    const node = state.currentNode;
    if (node === "planner") {
      phase = "🤔 Planning Strategy";
    } else if (node === "udf_execution") {
      phase = "🚀 UDF Execution";
    } else if (node === "generate_query") {
      phase = "📋 Query Generation";
    } else if (node === "web_research") {
      phase = "🔍 Research";
    } else if (node === "summarize_sources") {
      phase = "📝 Synthesis";
    } else if (node === "reflect_on_summary") {
      phase = "🔄 Reflection";
    } else if (node === "finalize_summary") {
      phase = "📄 Finalization";
    }
  } else {
    phase = "✅ Complete";
    phaseEmoji = "✅";
  }

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Current Phase Indicator */}
      <div className="bg-blue-900/50 border border-blue-500 rounded-lg p-4">
        <div className="text-sm text-blue-300 mb-1">Current Phase</div>
        <div className="text-xl font-semibold text-white flex items-center gap-2">
          <span>{phaseEmoji}</span>
          <span>{phase}</span>
          {state.isProcessing && (
            <span className="inline-block animate-pulse text-blue-400">●</span>
          )}
        </div>
        {state.currentNode && (
          <div className="text-xs text-blue-400 mt-1">Node: {state.currentNode}</div>
        )}
      </div>

      {/* Strategy Path Indicator */}
      {state.plan && (
        <div className="bg-purple-900/50 border border-purple-500 rounded-lg p-4">
          <div className="text-sm text-purple-300 mb-2">Strategy Selected</div>
          <div className="text-white">
            {state.udf_strategy ? (
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
          {state.plan && (
            <div className="text-sm text-purple-200 mt-2 opacity-75">
              {state.plan.substring(0, 150)}...
            </div>
          )}
        </div>
      )}

      {/* Execution Logs */}
      {state.logs.length > 0 && (
        <div className="bg-gray-900/80 rounded-lg p-4 max-h-96 overflow-y-auto">
          <div className="text-sm text-gray-300 mb-3 font-semibold flex items-center justify-between">
            <span>Execution Log</span>
            <span className="text-xs text-gray-500">{state.logs.length} entries</span>
          </div>
          <div className="space-y-2 font-mono text-sm">
            {state.logs.map((log, index) => (
              <div
                key={index}
                className="text-gray-300 leading-relaxed animate-fade-in"
                style={{ animationDelay: `${Math.min(index * 0.05, 1)}s` }}
              >
                <span className="text-blue-400">→</span> {log}
              </div>
            ))}
            {state.isProcessing && (
              <div className="text-blue-400 animate-pulse">
                <span className="text-blue-400">→</span> Processing...
              </div>
            )}
          </div>
        </div>
      )}

      {/* Generated Queries */}
      {state.queries.length > 0 && (
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

      {/* UDF Execution Result */}
      {state.udf_result && state.udf_result.success && (
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

      {/* Sources/Citations Preview */}
      {state.sources.length > 0 && (
        <div className="bg-indigo-900/30 border border-indigo-500 rounded-lg p-4">
          <div className="text-sm text-indigo-300 mb-2 font-semibold">
            Sources Retrieved
          </div>
          <div className="text-gray-300 text-sm">
            📚 {state.sources.length} sources collected
          </div>
        </div>
      )}

      {/* Completion Indicator */}
      {state.final_report && state.final_report.length > 100 && (
        <div className="bg-emerald-900/50 border border-emerald-500 rounded-lg p-4">
          <div className="text-emerald-300 font-semibold flex items-center gap-2">
            <span className="text-2xl">🎉</span>
            <span>Research Complete! Report ready ({(state.final_report.length / 1000).toFixed(1)}k chars)</span>
          </div>
        </div>
      )}

      {/* Error Display */}
      {state.error && (
        <div className="bg-red-900/50 border border-red-500 rounded-lg p-4">
          <div className="text-red-300 font-semibold flex items-center gap-2">
            <span className="text-2xl">❌</span>
            <span>Error: {state.error}</span>
          </div>
        </div>
      )}
    </div>
  );
}
