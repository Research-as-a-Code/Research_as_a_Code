import { NextRequest, NextResponse } from "next/server";

// Backend URL configuration for server-side
const BACKEND_URL = 
  process.env.INFERENCE_ORIGIN || 
  process.env.NEXT_PUBLIC_BACKEND_URL || 
  "http://localhost:8000";

/**
 * CopilotKit Info Route
 * 
 * Returns runtime info including available agents.
 * This endpoint is called by CopilotKit to discover available agents.
 */

export async function GET(req: NextRequest) {
  console.log("[CopilotKit Info Route] GET request, backend:", BACKEND_URL);
  
  try {
    // Call the backend's info endpoint
    const backendResponse = await fetch(`${BACKEND_URL}/copilotkit/info`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!backendResponse.ok) {
      console.error("[CopilotKit Info Route] Backend returned:", backendResponse.status);
      // Fall back to POST method if GET isn't supported
      const postResponse = await fetch(`${BACKEND_URL}/copilotkit/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ method: "info" }),
      });
      
      const postData = await postResponse.json();
      console.log("[CopilotKit Info Route] POST fallback response:", JSON.stringify(postData));
      return NextResponse.json(postData);
    }

    const data = await backendResponse.json();
    console.log("[CopilotKit Info Route] Response:", JSON.stringify(data));

    return NextResponse.json(data);
  } catch (error: any) {
    console.error("[CopilotKit Info Route] Error:", error.message);
    return NextResponse.json(
      { error: "Failed to get runtime info", details: error.message },
      { status: 500 }
    );
  }
}

export async function POST(req: NextRequest) {
  console.log("[CopilotKit Info Route] POST request");
  
  try {
    const backendResponse = await fetch(`${BACKEND_URL}/copilotkit/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ method: "info" }),
    });

    const data = await backendResponse.json();
    console.log("[CopilotKit Info Route] Response:", JSON.stringify(data));

    return NextResponse.json(data);
  } catch (error: any) {
    console.error("[CopilotKit Info Route] Error:", error.message);
    return NextResponse.json(
      { error: "Failed to get runtime info", details: error.message },
      { status: 500 }
    );
  }
}

export async function OPTIONS(req: NextRequest) {
  return new NextResponse(null, {
    status: 200,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    },
  });
}

