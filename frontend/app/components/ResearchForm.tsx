// SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
// SPDX-License-Identifier: Apache-2.0

/**
 * Research Form Component with CopilotKit AG-UI Integration
 * 
 * Uses CopilotKit actions to invoke the AI-Q researcher agent.
 * Real-time updates appear through AG-UI protocol streaming.
 */

"use client";

import { useState } from "react";
import { useCopilotResearch } from "../contexts/CopilotResearchContext";

interface ResearchFormProps {
  onResearchStart: () => void;
  onResearchComplete: (report: string) => void;
}

export function ResearchForm({ onResearchStart, onResearchComplete }: ResearchFormProps) {
  const [topic, setTopic] = useState("");
  const [reportOrg, setReportOrg] = useState(
    "Create a comprehensive report with introduction, detailed analysis, and conclusion."
  );
  const [collection, setCollection] = useState("");
  const [searchWeb, setSearchWeb] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const { triggerResearch } = useCopilotResearch();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!topic.trim()) {
      alert("Please enter a research topic");
      return;
    }

    setIsSubmitting(true);
    
    // Trigger the CopilotKit action via context
    // This will be picked up by CopilotAgentDisplay's useEffect
    triggerResearch({
      topic,
      report_organization: reportOrg,
      collection,
      search_web: searchWeb,
    });
    
    // Reset after a delay (action will handle actual execution)
    setTimeout(() => setIsSubmitting(false), 1000);
  };

  // Example topics - US Customs Tariff queries
  const exampleTopics = [
    "What is the tariff for replacement batteries for a Raritan remote management card?",
    "What's the tariff of Reese's Pieces?",
    "Tariff of a replacement Roomba vacuum motherboard, used",
    "What are typical import duties for electronics from China?",
    "What tariff codes apply to semiconductors?"
  ];

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Research Topic */}
      <div>
        <label htmlFor="topic" className="block text-sm font-medium text-gray-200 mb-2">
          Research Topic *
        </label>
        <textarea
          id="topic"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="Enter your research topic..."
          className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
          rows={3}
          required
        />
        
        {/* Example Topics */}
        <div className="mt-2 text-xs text-gray-400">
          <span className="font-semibold">Examples:</span>
          <div className="mt-1 space-y-1">
            {exampleTopics.map((example, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => setTopic(example)}
                className="block text-blue-400 hover:text-blue-300 hover:underline text-left"
              >
                • {example}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Report Organization */}
      <div>
        <label htmlFor="reportOrg" className="block text-sm font-medium text-gray-200 mb-2">
          Report Organization
        </label>
        <textarea
          id="reportOrg"
          value={reportOrg}
          onChange={(e) => setReportOrg(e.target.value)}
          className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
          rows={2}
        />
      </div>

      {/* Collection Name */}
      <div>
        <label htmlFor="collection" className="block text-sm font-medium text-gray-200 mb-2">
          RAG Collection Name
        </label>
        <input
          type="text"
          id="collection"
          value={collection}
          onChange={(e) => setCollection(e.target.value)}
          placeholder="us_tariffs"
          className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
        <p className="mt-2 text-xs text-gray-400">
          Leave empty for web search only. Use <span className="font-mono bg-gray-700 px-1 rounded">us_tariffs</span> for tariff documents.
        </p>
      </div>

      {/* Search Web Checkbox */}
      <div className="flex items-center">
        <input
          type="checkbox"
          id="searchWeb"
          checked={searchWeb}
          onChange={(e) => setSearchWeb(e.target.checked)}
          className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500 focus:ring-2"
        />
        <label htmlFor="searchWeb" className="ml-2 text-sm font-medium text-gray-200">
          Search the Web (Tavily API)
        </label>
      </div>

      {/* Submit Button */}
      <button
        type="submit"
        disabled={isSubmitting}
        className={`w-full py-3 px-6 rounded-lg font-semibold text-white transition-all ${
          isSubmitting
            ? "bg-gray-600 cursor-not-allowed"
            : "bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 shadow-lg hover:shadow-xl"
        }`}
      >
        {isSubmitting ? (
          <span className="flex items-center justify-center gap-2">
            <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
                fill="none"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            Processing...
          </span>
        ) : (
          "Start Research"
        )}
      </button>

      {/* Status Note */}
      {isSubmitting && (
        <div className="text-sm text-blue-400 text-center animate-pulse">
          🔄 CopilotKit AG-UI: Watch real-time updates below!
        </div>
      )}
    </form>
  );
}
