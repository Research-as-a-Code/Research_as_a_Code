// SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
// SPDX-License-Identifier: Apache-2.0

/**
 * Research Form Component
 * 
 * Allows users to input research parameters and submit requests.
 */

"use client";

import { useState } from "react";

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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!topic.trim()) {
      alert("Please enter a research topic");
      return;
    }

    setIsSubmitting(true);
    onResearchStart();

    const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

    try {
      // Use synchronous research endpoint
      const response = await fetch(`${BACKEND_URL}/research`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          topic: topic,
          report_organization: reportOrg,
          collection: collection,
          search_web: searchWeb
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const result = await response.json();
      onResearchComplete(result.final_report || "");
    } catch (error) {
      console.error("Research request failed:", error);
      alert(`Research failed: ${error}`);
      onResearchComplete("");
    } finally {
      setIsSubmitting(false);
    }
  };

  // Example topics - US Customs Tariff queries
  const exampleTopics = [
    "What is the tariff for replacement batteries for a Raritan remote management card?",
    "What's the tariff of Reese's Pieces?",
    "Tariff of a replacement Roomba vacuum motherboard, used",
  ];

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Topic Input */}
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-2">
          Research Topic *
        </label>
        <textarea
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          className="w-full px-4 py-3 bg-gray-900/50 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/50 transition"
          rows={3}
          placeholder="Enter your research question or topic..."
          disabled={isSubmitting}
        />
        
        {/* Example Topics */}
        <div className="mt-2">
          <div className="text-xs text-gray-400 mb-1">Quick examples:</div>
          <div className="flex flex-wrap gap-2">
            {exampleTopics.map((example, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => setTopic(example)}
                className="text-xs bg-blue-900/30 hover:bg-blue-800/50 text-blue-300 px-3 py-1 rounded-full transition"
                disabled={isSubmitting}
              >
                {example.slice(0, 40)}...
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Report Organization */}
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-2">
          Report Organization
        </label>
        <input
          type="text"
          value={reportOrg}
          onChange={(e) => setReportOrg(e.target.value)}
          className="w-full px-4 py-2 bg-gray-900/50 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/50 transition"
          placeholder="Describe the desired report structure..."
          disabled={isSubmitting}
        />
      </div>

      {/* Collection (Optional) */}
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-2">
          RAG Collection (Optional)
        </label>
        <input
          type="text"
          value={collection}
          onChange={(e) => setCollection(e.target.value)}
          className="w-full px-4 py-2 bg-gray-900/50 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/50 transition"
          placeholder="Enter 'us_tariffs' for tariff queries, or leave empty for web-only research"
          disabled={isSubmitting}
        />
      </div>

      {/* Search Web Checkbox */}
      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          id="searchWeb"
          checked={searchWeb}
          onChange={(e) => setSearchWeb(e.target.checked)}
          className="w-4 h-4 text-blue-500 bg-gray-900 border-gray-600 rounded focus:ring-2 focus:ring-blue-500"
          disabled={isSubmitting}
        />
        <label htmlFor="searchWeb" className="text-sm text-gray-300">
          Include web search (Tavily)
        </label>
      </div>

      {/* Submit Button */}
      <button
        type="submit"
        disabled={isSubmitting || !topic.trim()}
        className={`w-full py-3 px-6 rounded-lg font-semibold text-white transition-all ${
          isSubmitting || !topic.trim()
            ? "bg-gray-700 cursor-not-allowed"
            : "bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5"
        }`}
      >
        {isSubmitting ? (
          <span className="flex items-center justify-center gap-2">
            <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            Researching...
          </span>
        ) : (
          <span className="flex items-center justify-center gap-2">
            <span className="text-xl">🚀</span>
            Start Research
          </span>
        )}
      </button>
    </form>
  );
}

