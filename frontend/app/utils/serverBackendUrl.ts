// SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
// SPDX-License-Identifier: Apache-2.0

/**
 * Server-side Backend URL Detection Utility
 * 
 * This is the server-side equivalent of backendUrl.ts for use in Next.js API routes.
 * 
 * Priority order:
 * 1. INFERENCE_ORIGIN env var (Kubernetes internal service URL)
 * 2. NEXT_PUBLIC_BACKEND_URL env var (if set to non-default)
 * 3. Fallback to hardcoded AWS backend ELB (for AWS deployments without env vars)
 * 4. Fallback to localhost:8000 (local development)
 * 
 * IMPORTANT: This must match the fallback logic in backendUrl.ts (client-side)
 * to ensure consistent routing between direct browser calls and API proxy calls.
 */

// Hardcoded AWS backend ELB - must match the value in backendUrl.ts
const AWS_BACKEND_ELB = "http://af3615e06391145bc88022ac024a36ca-bd296660cda3522f.elb.us-west-2.amazonaws.com";

/**
 * Get the backend URL for server-side API routes.
 * 
 * This function should be called at request time (not module load) to support
 * dynamic configuration, but for simplicity we compute it once at startup.
 */
export function getServerBackendUrl(): string {
  // 1. Kubernetes internal service URL (highest priority in deployed environments)
  if (process.env.INFERENCE_ORIGIN) {
    console.log("[ServerBackendUrl] Using INFERENCE_ORIGIN:", process.env.INFERENCE_ORIGIN);
    return process.env.INFERENCE_ORIGIN;
  }
  
  // 2. Explicit backend URL (if set to non-default)
  if (process.env.NEXT_PUBLIC_BACKEND_URL && 
      process.env.NEXT_PUBLIC_BACKEND_URL !== "http://localhost:8000") {
    console.log("[ServerBackendUrl] Using NEXT_PUBLIC_BACKEND_URL:", process.env.NEXT_PUBLIC_BACKEND_URL);
    return process.env.NEXT_PUBLIC_BACKEND_URL;
  }
  
  // 3. Check if we're likely in an AWS deployment
  // In Vercel/AWS, VERCEL_URL or similar might be set, or we can check for AWS-specific env vars
  // Since we can't detect hostname on server-side like client-side, we use a heuristic:
  // If NODE_ENV is production and no explicit URL is set, assume AWS deployment
  if (process.env.NODE_ENV === 'production') {
    console.log("[ServerBackendUrl] Production mode without explicit URL, using AWS backend ELB");
    return AWS_BACKEND_ELB;
  }
  
  // 4. Fallback to localhost for local development
  console.log("[ServerBackendUrl] Using localhost fallback");
  return "http://localhost:8000";
}

// Export a constant for use in route files (computed once at module load)
export const BACKEND_URL = getServerBackendUrl();

