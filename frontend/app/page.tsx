// SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
// SPDX-License-Identifier: Apache-2.0

/**
 * Main Application Page
 * 
 * Displays the research interface with:
 * - Research prompt input
 * - Real-time agentic flow visualization
 * - Final report display
 */

"use client";

import { useState } from "react";
import { AgentFlowDisplay } from "./components/AgentFlowDisplay";
import { ResearchForm } from "./components/ResearchForm";
import { ReportDisplay } from "./components/ReportDisplay";

interface ResearchResult {
  final_report: string;
  logs: string[];
  execution_path: string;
  citations: string;
}

export default function Home() {
  const [currentReport, setCurrentReport] = useState<string>("");
  const [currentLogs, setCurrentLogs] = useState<string[]>([]);
  const [executionPath, setExecutionPath] = useState<string>("");
  const [isResearching, setIsResearching] = useState<boolean>(false);

  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-900 via-blue-900 to-purple-900 text-white">
      {/* Header */}
      <header className="container mx-auto px-6 py-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-4xl font-bold mb-2">
              🔬 AI-Q Research Assistant
            </h1>
            <p className="text-blue-300 text-lg">
              Enhanced with <span className="text-green-400 font-semibold">Universal Deep Research</span>
            </p>
            <p className="text-gray-400 text-sm mt-1">
              AWS & NVIDIA Agentic AI Unleashed Hackathon
            </p>
          </div>
          <div className="text-right">
            <div className="inline-flex items-center gap-2 bg-blue-800/50 px-4 py-2 rounded-lg">
              <span className="w-3 h-3 bg-green-400 rounded-full animate-pulse"></span>
              <span className="text-sm">Agent Ready</span>
            </div>
          </div>
        </div>
      </header>

      <div className="container mx-auto px-6 py-8 grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Left Column: Research Form and Agent Flow */}
        <div className="space-y-6">
          {/* Research Form */}
          <div className="bg-gray-800/50 backdrop-blur-lg rounded-lg p-6 shadow-2xl border border-gray-700">
            <h2 className="text-2xl font-semibold mb-4 flex items-center gap-2">
              <span className="text-3xl">📝</span>
              Research Request
            </h2>
            <ResearchForm 
              onResearchStart={() => {
                setIsResearching(true);
                setCurrentLogs([]);
                setExecutionPath("");
              }}
              onResearchComplete={(result) => {
                setCurrentReport(result.final_report);
                setCurrentLogs(result.logs);
                setExecutionPath(result.execution_path);
                setIsResearching(false);
              }}
            />
          </div>

          {/* Agent Flow Visualization */}
          <div className="bg-gray-800/50 backdrop-blur-lg rounded-lg p-6 shadow-2xl border border-gray-700">
            <h2 className="text-2xl font-semibold mb-4 flex items-center gap-2">
              <span className="text-3xl">🤖</span>
              Agentic Flow
            </h2>
            <AgentFlowDisplay logs={currentLogs} executionPath={executionPath} />
          </div>
        </div>

        {/* Right Column: Report Display */}
        <div className="bg-gray-800/50 backdrop-blur-lg rounded-lg p-6 shadow-2xl border border-gray-700">
          <h2 className="text-2xl font-semibold mb-4 flex items-center gap-2">
            <span className="text-3xl">📄</span>
            Research Report
          </h2>
          <ReportDisplay report={currentReport} isLoading={isResearching} />
        </div>
      </div>

      {/* Footer */}
      <footer className="container mx-auto px-6 py-8 mt-12 border-t border-gray-700">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-sm text-gray-400">
          <div>
            <h3 className="text-white font-semibold mb-2">Architecture</h3>
            <ul className="space-y-1">
              <li>✅ NVIDIA NeMo Agent Toolkit (LangGraph)</li>
              <li>✅ Universal Deep Research (UDF)</li>
              <li>✅ CopilotKit (AG-UI Protocol)</li>
            </ul>
          </div>
          <div>
            <h3 className="text-white font-semibold mb-2">NVIDIA NIMs</h3>
            <ul className="space-y-1">
              <li>🧠 Llama-3.1-Nemotron-Nano-8B (Reasoning)</li>
              <li>✍️ Llama-3.1-Nemotron-Nano-8B (Instruct)</li>
              <li>🔍 NeMo Retriever (Embeddings)</li>
            </ul>
          </div>
          <div>
            <h3 className="text-white font-semibold mb-2">Deployment</h3>
            <ul className="space-y-1">
              <li>☸️ Amazon EKS with Karpenter</li>
              <li>🚀 NVIDIA NIM Microservices</li>
              <li>📦 Docker + Helm + Terraform</li>
            </ul>
          </div>
        </div>
      </footer>
    </main>
  );
}

