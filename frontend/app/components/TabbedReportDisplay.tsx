// SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
// SPDX-License-Identifier: Apache-2.0

/**
 * Tabbed Report Display Component
 * 
 * Displays multiple research reports in a tabbed interface for side-by-side comparison.
 */

"use client";

import React, { useState, useEffect } from 'react';
import ReactMarkdown from "react-markdown";
import { Loader2, CheckCircle2, XCircle, Clock, Download } from 'lucide-react';
import { ResearchStrategy, STRATEGY_CONFIG } from './StrategySelector';

export interface ReportResult {
  strategy: ResearchStrategy;
  report: string;
  isLoading: boolean;
  error?: string;
  startTime?: number;
  endTime?: number;
}

interface TabbedReportDisplayProps {
  results: ReportResult[];
}

export function TabbedReportDisplay({ results }: TabbedReportDisplayProps) {
  const [activeTab, setActiveTab] = useState<ResearchStrategy | null>(null);
  
  // Auto-select first tab when results change
  useEffect(() => {
    if (results.length > 0 && !activeTab) {
      setActiveTab(results[0].strategy);
    }
  }, [results, activeTab]);

  // Auto-switch to completed tab when it finishes
  useEffect(() => {
    const completedResult = results.find(r => !r.isLoading && r.report && !r.error);
    if (completedResult && results.some(r => r.isLoading)) {
      // If one completed and others are still loading, optionally switch to completed one
      // For now, keep current tab - user can switch manually
    }
  }, [results]);

  const activeResult = results.find(r => r.strategy === activeTab);

  const formatDuration = (result: ReportResult): string => {
    if (!result.startTime) return '';
    const end = result.endTime || Date.now();
    const seconds = Math.round((end - result.startTime) / 1000);
    return `${seconds}s`;
  };

  const downloadReport = (result: ReportResult) => {
    const blob = new Blob([result.report], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `research-report-${result.strategy}-${Date.now()}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const downloadAllReports = () => {
    const completedResults = results.filter(r => r.report && !r.error);
    if (completedResults.length === 0) return;

    const combinedReport = completedResults.map(r => {
      const config = STRATEGY_CONFIG[r.strategy];
      const duration = r.startTime && r.endTime 
        ? `(completed in ${Math.round((r.endTime - r.startTime) / 1000)}s)`
        : '';
      return `# ${config.name} Report ${duration}\n\n${r.report}`;
    }).join('\n\n---\n\n');

    const blob = new Blob([combinedReport], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `research-comparison-${Date.now()}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Empty state
  if (results.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-gray-400">
        <div className="text-6xl mb-4">📝</div>
        <div className="text-lg font-semibold">No report generated yet</div>
        <div className="text-sm mt-2">Select strategies and submit a research request</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Tab Headers */}
      <div className="flex items-center justify-between border-b border-gray-700 mb-4">
        <div className="flex gap-1">
          {results.map((result) => {
            const config = STRATEGY_CONFIG[result.strategy];
            const isActive = activeTab === result.strategy;
            const Icon = config.icon;
            
            return (
              <button
                key={result.strategy}
                onClick={() => setActiveTab(result.strategy)}
                className={`
                  relative px-4 py-3 flex items-center gap-2 transition-all border-b-2 -mb-[2px]
                  ${isActive 
                    ? `${config.borderColor} ${config.color} bg-gray-800/50` 
                    : 'border-transparent text-gray-400 hover:text-gray-200 hover:bg-gray-800/30'}
                `}
              >
                <Icon className="w-4 h-4" />
                <span className="font-medium text-sm">{config.name}</span>
                
                {/* Status indicator */}
                <span className="ml-1">
                  {result.isLoading ? (
                    <Loader2 className="w-4 h-4 animate-spin text-yellow-500" />
                  ) : result.error ? (
                    <XCircle className="w-4 h-4 text-red-500" />
                  ) : result.report ? (
                    <CheckCircle2 className="w-4 h-4 text-green-500" />
                  ) : null}
                </span>
                
                {/* Duration badge */}
                {result.startTime && (
                  <span className="text-[10px] text-gray-500 flex items-center gap-0.5">
                    <Clock className="w-3 h-3" />
                    {formatDuration(result)}
                  </span>
                )}
              </button>
            );
          })}
        </div>
        
        {/* Download buttons */}
        <div className="flex gap-2">
          {results.length > 1 && results.some(r => r.report && !r.error) && (
            <button
              onClick={downloadAllReports}
              className="text-xs px-3 py-1.5 bg-purple-600 hover:bg-purple-700 text-white rounded-lg flex items-center gap-1.5 transition"
            >
              <Download className="w-3.5 h-3.5" />
              Download All
            </button>
          )}
        </div>
      </div>

      {/* Tab Content */}
      <div className="flex-1 min-h-0">
        {activeResult ? (
          <TabContent result={activeResult} onDownload={downloadReport} />
        ) : (
          <div className="flex items-center justify-center h-full text-gray-400">
            Select a tab to view results
          </div>
        )}
      </div>
    </div>
  );
}

interface TabContentProps {
  result: ReportResult;
  onDownload: (result: ReportResult) => void;
}

function TabContent({ result, onDownload }: TabContentProps) {
  const config = STRATEGY_CONFIG[result.strategy];
  
  // Loading state
  if (result.isLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-gray-400">
        <Loader2 className={`w-12 h-12 mb-4 animate-spin ${config.color}`} />
        <div className="text-lg font-semibold">Generating {config.name} report...</div>
        <div className="text-sm mt-2">
          {result.startTime && (
            <span className="flex items-center gap-1">
              <Clock className="w-4 h-4" />
              Running for {Math.round((Date.now() - result.startTime) / 1000)}s
            </span>
          )}
        </div>
      </div>
    );
  }

  // Error state
  if (result.error) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-red-400">
        <XCircle className="w-12 h-12 mb-4" />
        <div className="text-lg font-semibold">{config.name} Failed</div>
        <div className="text-sm mt-2 text-gray-400 max-w-md text-center">
          {result.error}
        </div>
      </div>
    );
  }

  // Empty state
  if (!result.report || result.report.trim().length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-gray-400">
        <div className="text-6xl mb-4">📝</div>
        <div className="text-lg font-semibold">Waiting for {config.name} results</div>
      </div>
    );
  }

  // Report content
  return (
    <div className="flex flex-col h-full space-y-4">
      {/* Header with download */}
      <div className="flex justify-between items-center flex-shrink-0">
        <div className="flex items-center gap-2">
          <span className={`text-sm font-medium ${config.color}`}>
            {config.name} Report
          </span>
          {result.startTime && result.endTime && (
            <span className="text-xs text-gray-500">
              Completed in {Math.round((result.endTime - result.startTime) / 1000)}s
            </span>
          )}
        </div>
        <button
          onClick={() => onDownload(result)}
          className="bg-green-600 hover:bg-green-700 text-white px-3 py-1.5 rounded-lg flex items-center gap-1.5 text-sm transition"
        >
          <Download className="w-4 h-4" />
          Download
        </button>
      </div>

      {/* Report Content */}
      <div className="flex-1 prose prose-invert prose-blue max-w-none bg-gray-900/50 rounded-lg p-6 overflow-y-auto min-h-0">
        <ReactMarkdown
          components={{
            h1: ({ node, ...props }) => <h1 className="text-3xl font-bold text-white mb-4" {...props} />,
            h2: ({ node, ...props }) => <h2 className="text-2xl font-bold text-blue-300 mt-6 mb-3" {...props} />,
            h3: ({ node, ...props }) => <h3 className="text-xl font-semibold text-blue-200 mt-4 mb-2" {...props} />,
            p: ({ node, ...props }) => <p className="text-gray-300 leading-relaxed mb-4" {...props} />,
            ul: ({ node, ...props }) => <ul className="list-disc list-inside text-gray-300 mb-4 space-y-1" {...props} />,
            ol: ({ node, ...props }) => <ol className="list-decimal list-inside text-gray-300 mb-4 space-y-1" {...props} />,
            li: ({ node, ...props }) => <li className="text-gray-300" {...props} />,
            a: ({ node, ...props }) => <a className="text-blue-400 hover:text-blue-300 underline" {...props} />,
            code: ({ node, inline, ...props }: any) =>
              inline ? (
                <code className="bg-gray-800 text-blue-300 px-1 py-0.5 rounded text-sm" {...props} />
              ) : (
                <code className="block bg-gray-800 text-gray-300 p-4 rounded-lg overflow-x-auto text-sm" {...props} />
              ),
            blockquote: ({ node, ...props }) => (
              <blockquote className="border-l-4 border-blue-500 pl-4 italic text-gray-400 my-4" {...props} />
            ),
          }}
        >
          {result.report}
        </ReactMarkdown>
      </div>
    </div>
  );
}

