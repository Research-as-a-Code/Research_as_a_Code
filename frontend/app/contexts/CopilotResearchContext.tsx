// SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
// SPDX-License-Identifier: Apache-2.0

/**
 * CopilotKit Research Context
 * 
 * Provides a way for the ResearchForm to trigger the CopilotKit action
 * registered in the CopilotAgentDisplay component.
 */

"use client";

import { createContext, useContext, useState, ReactNode } from "react";

interface ResearchParams {
  topic: string;
  report_organization: string;
  collection: string;
  search_web: boolean;
}

interface CopilotResearchContextType {
  triggerResearch: (params: ResearchParams) => void;
  currentParams: ResearchParams | null;
  clearParams: () => void;
}

const CopilotResearchContext = createContext<CopilotResearchContextType | null>(null);

export function CopilotResearchProvider({ children }: { children: ReactNode }) {
  const [currentParams, setCurrentParams] = useState<ResearchParams | null>(null);

  const triggerResearch = (params: ResearchParams) => {
    console.log("🎯 Triggering CopilotKit research action:", params);
    setCurrentParams(params);
  };

  const clearParams = () => {
    setCurrentParams(null);
  };

  return (
    <CopilotResearchContext.Provider value={{ triggerResearch, currentParams, clearParams }}>
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

