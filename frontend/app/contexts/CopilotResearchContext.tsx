// SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
// SPDX-License-Identifier: Apache-2.0

/**
 * CopilotKit Research Context
 * 
 * Provides a way for the ResearchForm to trigger the CopilotKit action
 * registered in the CopilotAgentDisplay component.
 * 
 * Supports multiple strategy selection for side-by-side comparison.
 */

"use client";

import { createContext, useContext, useState, ReactNode } from "react";
import { ResearchStrategy } from "../components/StrategySelector";
import { ReportResult } from "../components/TabbedReportDisplay";

interface ResearchParams {
  topic: string;
  report_organization: string;
  collection: string;
  search_web: boolean;
}

interface CopilotResearchContextType {
  // Research params
  triggerResearch: (params: ResearchParams) => void;
  currentParams: ResearchParams | null;
  clearParams: () => void;
  
  // Strategy selection (multi-select)
  selectedStrategies: ResearchStrategy[];
  setSelectedStrategies: (strategies: ResearchStrategy[]) => void;
  
  // Results (per-strategy)
  reportResults: ReportResult[];
  updateReportResult: (strategy: ResearchStrategy, update: Partial<ReportResult>) => void;
  clearReportResults: () => void;
  
  // Global loading state
  isResearching: boolean;
  setIsResearching: (value: boolean) => void;
}

const CopilotResearchContext = createContext<CopilotResearchContextType | null>(null);

export function CopilotResearchProvider({ children }: { children: ReactNode }) {
  const [currentParams, setCurrentParams] = useState<ResearchParams | null>(null);
  const [selectedStrategies, setSelectedStrategies] = useState<ResearchStrategy[]>(['udr']);
  const [reportResults, setReportResults] = useState<ReportResult[]>([]);
  const [isResearching, setIsResearching] = useState(false);

  const triggerResearch = (params: ResearchParams) => {
    console.log("🎯 Triggering research with params:", params);
    console.log("📊 Selected strategies:", selectedStrategies);
    setCurrentParams(params);
  };

  const clearParams = () => {
    setCurrentParams(null);
  };

  const updateReportResult = (strategy: ResearchStrategy, update: Partial<ReportResult>) => {
    setReportResults(prev => {
      const existing = prev.find(r => r.strategy === strategy);
      if (existing) {
        return prev.map(r => 
          r.strategy === strategy 
            ? { ...r, ...update }
            : r
        );
      } else {
        // Add new result
        const newResult: ReportResult = {
          strategy,
          report: '',
          isLoading: true,
          ...update,
        };
        return [...prev, newResult];
      }
    });
  };

  const clearReportResults = () => {
    setReportResults([]);
  };

  return (
    <CopilotResearchContext.Provider value={{ 
      triggerResearch, 
      currentParams, 
      clearParams,
      selectedStrategies,
      setSelectedStrategies,
      reportResults,
      updateReportResult,
      clearReportResults,
      isResearching,
      setIsResearching,
    }}>
      {children}
    </CopilotResearchContext.Provider>
  );
}

export function useCopilotResearch() {
  const context = useContext(CopilotResearchContext);
  if (!context) {
    throw new Error("useCopilotResearch must be used within CopilotResearchProvider");
  }
  return context;
}
