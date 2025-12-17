// SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
// SPDX-License-Identifier: Apache-2.0

/**
 * Main Application Page
 * 
 * Displays the research interface with:
 * - Research prompt input
 * - Multi-strategy selection for side-by-side comparison
 * - Real-time agentic flow visualization
 * - Tabbed report display for comparing results
 */

"use client";

import { useState } from "react";
import { CopilotAgentDisplay } from "./components/CopilotAgentDisplay";
import { ResearchForm } from "./components/ResearchForm";
import { TabbedReportDisplay, ReportResult } from "./components/TabbedReportDisplay";
import { ResearchStrategy } from "./components/StrategySelector";
import { useCopilotResearch } from "./contexts/CopilotResearchContext";

// Force dynamic rendering - never cache this page
export const dynamic = 'force-dynamic';

export default function Home() {
  const [isResearching, setIsResearching] = useState<boolean>(false);
  const { reportResults } = useCopilotResearch();

  const handleResearchStart = () => {
    setIsResearching(true);
  };

  const handleResearchComplete = (strategy: ResearchStrategy, report: string) => {
    console.log(`📄 [${strategy}] Report received, length:`, report.length);
  };

  const handleAllComplete = () => {
    setIsResearching(false);
  };

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
              <span className="text-green-400 font-semibold">Multi-Strategy Comparison</span>
              {' '}- Run UDR & TTD-DR side-by-side
            </p>
            <p className="text-gray-400 text-sm mt-1">
              AWS & NVIDIA Agentic AI Unleashed Hackathon
            </p>
          </div>
          <div className="text-right">
            <div className="inline-flex items-center gap-2 bg-blue-800/50 px-4 py-2 rounded-lg">
              <span className={`w-3 h-3 rounded-full ${isResearching ? 'bg-yellow-400 animate-pulse' : 'bg-green-400'}`}></span>
              <span className="text-sm">{isResearching ? 'Researching...' : 'Agent Ready'}</span>
            </div>
          </div>
        </div>
      </header>

      <div className="container mx-auto px-6 py-8 grid grid-cols-1 lg:grid-cols-2 gap-8 min-h-[calc(100vh-16rem)]">
        {/* Left Column: Research Form and Agent Flow */}
        <div className="space-y-6">
          {/* Research Form */}
          <div className="bg-gray-800/50 backdrop-blur-lg rounded-lg p-6 shadow-2xl border border-gray-700">
            <h2 className="text-2xl font-semibold mb-4 flex items-center gap-2">
              <span className="text-3xl">📝</span>
              Research Request
            </h2>
            <ResearchForm 
              onResearchStart={handleResearchStart}
              onResearchComplete={(report) => {
                // This is kept for backward compatibility but not used with multi-strategy
              }}
            />
          </div>

          {/* Agent Flow Visualization - Powered by CopilotKit AG-UI */}
          <div className="bg-gray-800/50 backdrop-blur-lg rounded-lg p-6 shadow-2xl border border-gray-700">
            <h2 className="text-2xl font-semibold mb-4 flex items-center gap-2">
              <span className="text-3xl">🤖</span>
              Strategy Selection & Progress
            </h2>
            <CopilotAgentDisplay 
              onResearchStart={handleResearchStart}
              onResearchComplete={handleResearchComplete}
              onAllComplete={handleAllComplete}
            />
          </div>
        </div>

        {/* Right Column: Tabbed Report Display */}
        <div className="bg-gray-800/50 backdrop-blur-lg rounded-lg p-6 shadow-2xl border border-gray-700 flex flex-col">
          <h2 className="text-2xl font-semibold mb-4 flex items-center gap-2">
            <span className="text-3xl">📄</span>
            Research Reports
            {reportResults.length > 1 && (
              <span className="text-sm font-normal text-purple-400 ml-2">
                (Comparison Mode)
              </span>
            )}
          </h2>
          <div className="flex-1 min-h-0">
            <TabbedReportDisplay results={reportResults} />
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="container mx-auto px-6 py-8 mt-12 border-t border-gray-700">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-sm text-gray-400">
          <div>
            <h3 className="text-white font-semibold mb-2">Architecture</h3>
            <ul className="space-y-1">
              <li>✅ NVIDIA NeMo Agent Toolkit (LangGraph)</li>
              <li>✅ Universal Deep Research (UDR)</li>
              <li>✅ Test-Time Diffusion Deep Researcher (TTD-DR)</li>
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
            <h3 className="text-white font-semibold mb-2">Features</h3>
            <ul className="space-y-1">
              <li>🔄 Parallel Strategy Execution</li>
              <li>📊 Side-by-Side Comparison</li>
              <li>⏱️ Execution Time Tracking</li>
              <li>📥 Combined Report Download</li>
            </ul>
          </div>
        </div>
      </footer>
    </main>
  );
}
