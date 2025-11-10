// SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
// SPDX-License-Identifier: Apache-2.0

/**
 * Root Layout with Real-Time Streaming
 * 
 * Provides AgentStreamContext for real-time SSE updates from /research/stream endpoint.
 */

"use client";

import { AgentStreamProvider } from "./contexts/AgentStreamContext";
import "./globals.css";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <title>AI-Q Research Assistant with UDF | AWS & NVIDIA Hackathon</title>
        <meta name="description" content="Enhanced NVIDIA AI-Q agent with Universal Deep Research for complex multi-domain research" />
      </head>
      <body>
        <AgentStreamProvider>
          <div className="app-container">
            {children}
          </div>
        </AgentStreamProvider>
      </body>
    </html>
  );
}
