// SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
// SPDX-License-Identifier: Apache-2.0

/**
 * Root Layout - Stable Version
 * 
 * CopilotKit SSE temporarily disabled to resolve page load crash.
 * Uses synchronous HTTP for reliable operation.
 * TODO: Investigate SSE "[Network] No Content" error separately.
 */

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
        <div className="app-container">
          {children}
        </div>
      </body>
    </html>
  );
}

