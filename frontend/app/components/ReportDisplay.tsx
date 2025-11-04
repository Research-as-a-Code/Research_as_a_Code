// SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
// SPDX-License-Identifier: Apache-2.0

/**
 * Report Display Component
 * 
 * Displays the final research report with markdown rendering.
 */

"use client";

import ReactMarkdown from "react-markdown";

interface ReportDisplayProps {
  report: string;
  isLoading: boolean;
}

export function ReportDisplay({ report, isLoading }: ReportDisplayProps) {
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-gray-400">
        <svg className="animate-spin h-12 w-12 mb-4 text-blue-500" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
        <div className="text-lg font-semibold">Generating report...</div>
        <div className="text-sm mt-2">Watch the agentic flow in the left panel</div>
      </div>
    );
  }

  if (!report || report.trim().length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-gray-400">
        <div className="text-6xl mb-4">📝</div>
        <div className="text-lg font-semibold">No report generated yet</div>
        <div className="text-sm mt-2">Submit a research request to begin</div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Download Button */}
      <div className="flex justify-end">
        <button
          onClick={() => {
            const blob = new Blob([report], { type: "text/markdown" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `research-report-${Date.now()}.md`;
            a.click();
            URL.revokeObjectURL(url);
          }}
          className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg flex items-center gap-2 transition"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          Download Report
        </button>
      </div>

      {/* Report Content with Markdown Rendering */}
      <div className="prose prose-invert prose-blue max-w-none bg-gray-900/50 rounded-lg p-6 overflow-y-auto max-h-[70vh]">
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
          {report}
        </ReactMarkdown>
      </div>
    </div>
  );
}

