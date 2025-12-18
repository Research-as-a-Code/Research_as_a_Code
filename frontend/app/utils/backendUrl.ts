// SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
// SPDX-License-Identifier: Apache-2.0

/**
 * Backend URL Detection Utility
 * 
 * Priority order for determining the backend URL:
 * 1. Runtime window global: window.__RUNTIME_CONFIG__?.BACKEND_URL (true runtime config)
 * 2. Build-time env var: NEXT_PUBLIC_BACKEND_URL (if set to non-default)
 * 3. Hostname-based detection for AWS ELB deployments
 * 4. Fallback to localhost:8000
 * 
 * For Kubernetes deployments, inject runtime config via:
 * - A ConfigMap-mounted /config.js file that sets window.__RUNTIME_CONFIG__
 * - Or pass --build-arg NEXT_PUBLIC_BACKEND_URL during Docker build
 */

// Extend Window interface for TypeScript
declare global {
  interface Window {
    __RUNTIME_CONFIG__?: {
      BACKEND_URL?: string;
    };
  }
}

/**
 * Get the backend URL based on the current environment.
 * This runs on the client side and supports both build-time and runtime configuration.
 */
export function getBackendUrl(): string {
  // 1. Check for runtime config (true runtime override - highest priority)
  // This can be injected via a script tag or ConfigMap-mounted file
  if (typeof window !== 'undefined' && window.__RUNTIME_CONFIG__?.BACKEND_URL) {
    return window.__RUNTIME_CONFIG__.BACKEND_URL;
  }
  
  // 2. Check for build-time environment variable (if explicitly set to non-default)
  if (process.env.NEXT_PUBLIC_BACKEND_URL && 
      process.env.NEXT_PUBLIC_BACKEND_URL !== "http://localhost:8000") {
    return process.env.NEXT_PUBLIC_BACKEND_URL;
  }
  
  // 3. Runtime hostname-based detection for browser
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    
    // Local development
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      return "http://localhost:8000";
    }
    
    // AWS ELB deployment - derive backend URL from frontend hostname pattern
    // Frontend: af2f4f77d44fb4b41bc00856345951e2-974749261.us-west-2.elb.amazonaws.com
    // Backend: af3615e06391145bc88022ac024a36ca-bd296660cda3522f.elb.us-west-2.amazonaws.com
    // Note: This is a fallback - prefer setting BACKEND_URL via runtime config or build arg
    if (hostname.includes('.elb.') || hostname.includes('.amazonaws.com')) {
      // Default AWS backend ELB - update via runtime config if this changes
      return "http://af3615e06391145bc88022ac024a36ca-bd296660cda3522f.elb.us-west-2.amazonaws.com";
    }
  }
  
  // 4. Fallback to localhost for SSR or unknown environments
  return "http://localhost:8000";
}

