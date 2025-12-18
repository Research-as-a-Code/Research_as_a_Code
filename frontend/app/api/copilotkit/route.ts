import { NextRequest, NextResponse } from "next/server";

// Backend URL configuration for server-side
// In Kubernetes, INFERENCE_ORIGIN points to the backend service
// Otherwise use NEXT_PUBLIC_BACKEND_URL or default
const BACKEND_URL = 
  process.env.INFERENCE_ORIGIN || 
  process.env.NEXT_PUBLIC_BACKEND_URL || 
  "http://localhost:8000";

/**
 * CopilotKit API Route
 * 
 * This route acts as a proxy between the CopilotKit frontend and the Python backend.
 * The backend registers both "ai_q_researcher" and "default" agents.
 * 
 * Handles both:
 * - JSON responses (for "info" method)
 * - Streaming responses (for "execute" method - newline-delimited JSON events)
 */

export async function POST(req: NextRequest) {
  console.log("[CopilotKit Route] Using BACKEND_URL:", BACKEND_URL);
  
  try {
    const body = await req.json();
    const method = body.method || "unknown";
    console.log("[CopilotKit Route] Request method:", method, "body:", JSON.stringify(body).slice(0, 200));
    
    // Forward the request to the backend
    const backendResponse = await fetch(`${BACKEND_URL}/copilotkit/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

    // Check content-type to determine response handling
    const contentType = backendResponse.headers.get("content-type") || "";
    
    // For streaming responses (text/event-stream or application/x-ndjson), pass through as-is
    if (contentType.includes("text/event-stream") || 
        contentType.includes("application/x-ndjson") ||
        contentType.includes("application/stream") ||
        method === "execute") {
      console.log("[CopilotKit Route] Streaming response detected, passing through");
      
      // Pass through the streaming response
      return new Response(backendResponse.body, {
        status: backendResponse.status,
        headers: {
          "Content-Type": contentType || "text/event-stream",
          "Cache-Control": "no-cache",
          "Connection": "keep-alive",
        },
      });
    }

    // For JSON responses (info, etc.), parse and return
    const responseData = await backendResponse.json();
    console.log("[CopilotKit Route] JSON response:", JSON.stringify(responseData).slice(0, 500));

    // For info requests, log the agents
    if (method === "info" && responseData.agents) {
      console.log("[CopilotKit Route] Agents found:", responseData.agents.map((a: any) => a.name).join(", "));
    }

    return NextResponse.json(responseData, { status: backendResponse.status });
  } catch (error: any) {
    console.error("[CopilotKit Route] Error:", error.message);
    return NextResponse.json(
      { error: "Failed to connect to backend", details: error.message },
      { status: 500 }
    );
  }
}

export async function OPTIONS(req: NextRequest) {
  return new NextResponse(null, {
    status: 200,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    },
  });
}
