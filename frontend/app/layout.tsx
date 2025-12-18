// SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
// SPDX-License-Identifier: Apache-2.0

/**
 * Root Layout with CopilotKit AG-UI Integration
 * 
 * Integrates CopilotKit provider with AG-UI protocol support.
 * The backend runs LangGraphAGUIAgent serving at /copilotkit/ endpoint.
 * Includes CopilotSidebar for direct agent interaction via chat interface.
 * 
 * Backend URL configuration priority:
 * 1. Runtime config from /config.js (window.__RUNTIME_CONFIG__.BACKEND_URL)
 * 2. Build-time NEXT_PUBLIC_BACKEND_URL env var
 * 3. Hostname-based detection (AWS ELB)
 * 4. Fallback to localhost:8000
 * 
 * For runtime updates without rebuild, mount a ConfigMap to /app/public/config.js
 */

"use client";

import { CopilotKit } from "@copilotkit/react-core";
import { CopilotResearchProvider } from "./contexts/CopilotResearchContext";
import Script from "next/script";
import "./globals.css";
import { useMemo } from "react";
import { getBackendUrl } from "./utils/backendUrl";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const backendUrl = useMemo(() => getBackendUrl(), []);

  return (
    <html lang="en">
      <head>
        <title>AI-Q Research Assistant with AG-UI | AWS & NVIDIA Hackathon</title>
        <meta name="description" content="Enhanced NVIDIA AI-Q agent with Universal Deep Research and CopilotKit AG-UI integration" />
        {/* Runtime config - can be overridden via ConfigMap mount */}
        <Script src="/config.js" strategy="beforeInteractive" />
      </head>
      <body>
        <CopilotKit
          runtimeUrl={`${backendUrl}/copilotkit/`}
          agent="ai_q_researcher"
          showDevConsole={false}
        >
          <CopilotResearchProvider>
            <div className="app-container">
              {children}
            </div>
          </CopilotResearchProvider>
        </CopilotKit>
      </body>
    </html>
  );
}
