import { NextRequest, NextResponse } from "next/server";
import { BACKEND_URL } from "../../../utils/serverBackendUrl";

/**
 * CopilotKit Info Route
 * 
 * Returns runtime info including available agents.
 * This endpoint is called by CopilotKit to discover available agents.
 * 
 * The /info endpoint always returns JSON (not streaming), so we can safely
 * use response.json() here.
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
      console.error("[CopilotKit Info Route] Backend GET returned:", backendResponse.status);
      // Fall back to POST method if GET isn't supported
      return await fetchInfoViaPost();
    }

    // Try to parse as JSON
    const text = await backendResponse.text();
    try {
      const data = JSON.parse(text);
      console.log("[CopilotKit Info Route] Response:", JSON.stringify(data));
      return NextResponse.json(data);
    } catch (parseError) {
      console.error("[CopilotKit Info Route] Failed to parse JSON:", text.slice(0, 200));
      // Fall back to POST method
      return await fetchInfoViaPost();
    }
  } catch (error: any) {
    console.error("[CopilotKit Info Route] GET Error:", error.message);
    // Try POST as fallback
    try {
      return await fetchInfoViaPost();
    } catch (postError: any) {
      console.error("[CopilotKit Info Route] POST fallback also failed:", postError.message);
      return NextResponse.json(
        { error: "Failed to get runtime info", details: error.message },
        { status: 500 }
      );
    }
  }
}

async function fetchInfoViaPost(): Promise<NextResponse> {
  console.log("[CopilotKit Info Route] Using POST fallback");
  
  const postResponse = await fetch(`${BACKEND_URL}/copilotkit/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ method: "info" }),
  });
  
  const text = await postResponse.text();
  try {
    const data = JSON.parse(text);
    console.log("[CopilotKit Info Route] POST fallback response:", JSON.stringify(data));
    return NextResponse.json(data);
  } catch (parseError) {
    console.error("[CopilotKit Info Route] POST response not JSON:", text.slice(0, 200));
    throw new Error("Backend returned non-JSON response");
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

    const text = await backendResponse.text();
    try {
      const data = JSON.parse(text);
      console.log("[CopilotKit Info Route] Response:", JSON.stringify(data));
      return NextResponse.json(data);
    } catch (parseError) {
      console.error("[CopilotKit Info Route] Response not JSON:", text.slice(0, 200));
      return NextResponse.json(
        { error: "Backend returned non-JSON response", details: text.slice(0, 200) },
        { status: 500 }
      );
    }
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
