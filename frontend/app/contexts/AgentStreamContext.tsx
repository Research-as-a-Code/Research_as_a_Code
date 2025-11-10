// SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
// SPDX-License-Identifier: Apache-2.0

/**
 * Agent Stream Context
 * 
 * Manages real-time SSE streaming of agent state from /research/stream endpoint.
 * Provides current node, logs, queries, and other state updates to components.
 */

"use client";

import React, { createContext, useContext, useState, useCallback } from "react";

interface AgentState {
  currentNode: string;
  logs: string[];
  queries: Array<{ query: string }>;
  plan: string;
  final_report: string;
  citations: string;
  sources: string[];
  udf_strategy?: string;
  udf_result?: any;
  isProcessing: boolean;
  error?: string;
}

interface AgentStreamContextType {
  state: AgentState;
  startStream: (params: {
    topic: string;
    report_organization: string;
    collection: string;
    search_web: boolean;
  }) => void;
  reset: () => void;
}

const AgentStreamContext = createContext<AgentStreamContextType | undefined>(undefined);

const initialState: AgentState = {
  currentNode: "",
  logs: [],
  queries: [],
  plan: "",
  final_report: "",
  citations: "",
  sources: [],
  isProcessing: false,
};

export function AgentStreamProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AgentState>(initialState);

  const reset = useCallback(() => {
    setState(initialState);
  }, []);

  const startStream = useCallback(async (params: {
    topic: string;
    report_organization: string;
    collection: string;
    search_web: boolean;
  }) => {
    // Reset state
    setState({ ...initialState, isProcessing: true });

    const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

    try {
      // Use fetch with streaming for POST support
      const response = await fetch(`${BACKEND_URL}/research/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          topic: params.topic,
          report_organization: params.report_organization,
          collection: params.collection,
          search_web: params.search_web,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      // Read the stream
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error("No response body");
      }

      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        // Decode chunk and add to buffer
        buffer += decoder.decode(value, { stream: true });

        // Process complete SSE messages (lines starting with "data: ")
        const lines = buffer.split("\n");
        buffer = lines.pop() || ""; // Keep incomplete line in buffer

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.substring(6));

              if (data.type === "update") {
                // Update state with new node data
                setState((prev) => ({
                  ...prev,
                  currentNode: data.node,
                  logs: data.state.logs || prev.logs,
                  queries: data.state.queries || prev.queries,
                  plan: data.state.plan || prev.plan,
                  final_report: data.state.final_report || prev.final_report,
                  citations: data.state.citations || prev.citations,
                  sources: data.state.sources || prev.sources,
                  udf_strategy: data.state.udf_strategy || prev.udf_strategy,
                  udf_result: data.state.udf_result || prev.udf_result,
                }));
              } else if (data.type === "complete") {
                setState((prev) => ({ ...prev, isProcessing: false }));
              } else if (data.type === "error") {
                setState((prev) => ({
                  ...prev,
                  isProcessing: false,
                  error: data.message,
                }));
              }
            } catch (e) {
              console.error("Error parsing SSE event:", e);
            }
          }
        }
      }
    } catch (error) {
      console.error("Stream error:", error);
      setState((prev) => ({
        ...prev,
        isProcessing: false,
        error: error instanceof Error ? error.message : "Stream error",
      }));
    }
  }, []);

  return (
    <AgentStreamContext.Provider value={{ state, startStream, reset }}>
      {children}
    </AgentStreamContext.Provider>
  );
}

export function useAgentStream() {
  const context = useContext(AgentStreamContext);
  if (!context) {
    throw new Error("useAgentStream must be used within AgentStreamProvider");
  }
  return context;
}

