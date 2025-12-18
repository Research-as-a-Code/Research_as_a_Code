// Runtime configuration for AI-Q Frontend
// This file can be mounted via Kubernetes ConfigMap for true runtime configuration
// without requiring a Docker image rebuild.
//
// Usage in Kubernetes:
// 1. Create a ConfigMap with this file
// 2. Mount it to /app/public/config.js in the frontend container
// 3. The frontend will load it before React initializes
//
// To update the backend URL:
// - Edit the ConfigMap and restart the frontend pods
// - No image rebuild required!

window.__RUNTIME_CONFIG__ = {
  // Backend API URL - update this when the backend ELB changes
  BACKEND_URL: "http://af3615e06391145bc88022ac024a36ca-bd296660cda3522f.elb.us-west-2.amazonaws.com"
};

