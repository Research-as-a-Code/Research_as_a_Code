// SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
// SPDX-License-Identifier: Apache-2.0

/**
 * Root Layout with CopilotKit Provider
 * 
 * This component wraps the entire application with CopilotKit,
 * enabling real-time agent state streaming from the FastAPI backend.
 */

"use client";

import { CopilotKit } from "@copilotkit/react-core";
import { CopilotPopup } from "@copilotkit/react-ui";
import "@copilotkit/react-ui/styles.css";
import "./globals.css";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Backend URL - change this based on your deployment
  const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

  return (
    <html lang="en">
      <head>
        <title>AI-Q Research Assistant with UDF | AWS & NVIDIA Hackathon</title>
        <meta name="description" content="Enhanced NVIDIA AI-Q agent with Universal Deep Research for complex multi-domain research" />
      </head>
      <body>
        <CopilotKit
          runtimeUrl={`${BACKEND_URL}/copilotkit`}
          agent="ai_q_researcher"
        >
          <div className="app-container">
            {children}
          </div>
          {/* CopilotPopup provides the chat bubble UI */}
          <CopilotPopup />
        </CopilotKit>
      </body>
    </html>
  );
}

