// SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
// SPDX-License-Identifier: Apache-2.0

/**
 * Root Layout with CopilotKit AG-UI Integration
 * 
 * Integrates CopilotKit provider with AG-UI protocol support.
 * The backend runs LangGraphAGUIAgent serving at /copilotkit/ endpoint.
 * Includes CopilotSidebar for direct agent interaction via chat interface.
 */

"use client";

import { CopilotKit } from "@copilotkit/react-core";
import { CopilotSidebar } from "@copilotkit/react-ui";
import { AgentStreamProvider } from "./contexts/AgentStreamContext";
import "./globals.css";
import "@copilotkit/react-ui/styles.css";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

  return (
    <html lang="en">
      <head>
        <title>AI-Q Research Assistant with AG-UI | AWS & NVIDIA Hackathon</title>
        <meta name="description" content="Enhanced NVIDIA AI-Q agent with Universal Deep Research and CopilotKit AG-UI integration" />
      </head>
      <body>
        <CopilotKit
          runtimeUrl={`${BACKEND_URL}/copilotkit`}
          agent="ai_q_researcher"
          showDevConsole={false}
        >
          <CopilotSidebar
            defaultOpen={false}
            clickOutsideToClose={true}
            labels={{
              title: "AI-Q Research Assistant",
              initial: "Ask me to research any topic! I can search the web and RAG collections.",
            }}
          >
            <div className="app-container">
              {children}
            </div>
          </CopilotSidebar>
        </CopilotKit>
      </body>
    </html>
  );
}
