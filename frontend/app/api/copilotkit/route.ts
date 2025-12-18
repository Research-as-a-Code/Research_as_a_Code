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
 */

export async function POST(req: NextRequest) {
  console.log("[CopilotKit Route] Using BACKEND_URL:", BACKEND_URL);
  
  try {
    const body = await req.json();
    console.log("[CopilotKit Route] Request:", JSON.stringify(body).slice(0, 200));
    
    // Forward the request to the backend
    const backendResponse = await fetch(`${BACKEND_URL}/copilotkit/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

    // Get the response
    const responseData = await backendResponse.json();
    console.log("[CopilotKit Route] Backend response:", JSON.stringify(responseData));

    // For info requests, ensure we log the agents
    if (body.method === "info" && responseData.agents) {
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
