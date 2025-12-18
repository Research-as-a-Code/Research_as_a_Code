# AI-Q Research Assistant Frontend

Next.js frontend for the AI-Q Research Assistant with CopilotKit AG-UI integration.

## Features

- Real-time agent flow visualization via CopilotKit
- Multiple research strategy comparison (UDR, TTD-DR, Simple RAG)
- Side-by-side tabbed report display
- Streaming progress updates

## Quick Start

```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Open http://localhost:3000
```

## Backend URL Configuration

The frontend supports **runtime configuration** without requiring a Docker image rebuild.

### Priority Order

1. **Runtime Config** (`window.__RUNTIME_CONFIG__.BACKEND_URL`)
   - Loaded from `/config.js` before React initializes
   - Highest priority - overrides all other settings
   - **No rebuild required** - just update and restart pods

2. **Build-time Environment Variable** (`NEXT_PUBLIC_BACKEND_URL`)
   - Set during `docker build` or `npm run build`
   - Baked into the JavaScript bundle
   - Requires rebuild to change

3. **Automatic Detection**
   - `localhost` → `http://localhost:8000`
   - AWS ELB hostname → Configured backend ELB URL

### Local Development

The frontend automatically detects `localhost` and connects to `http://localhost:8000`:

```bash
npm run dev
# Automatically uses http://localhost:8000 as backend
```

### Production (Kubernetes)

**Option A: Via Helm Values (Recommended)**

```yaml
# values.yaml
frontend:
  runtimeConfig:
    backendUrl: "http://your-backend-elb.amazonaws.com"
```

```bash
helm upgrade <release> ./deploy/helm/aiq-aira
# Pods restart automatically when ConfigMap changes
```

**Option B: Edit ConfigMap Directly**

```bash
kubectl edit configmap <release>-frontend-config -n <namespace>
```

Update the `config.js` content:
```javascript
window.__RUNTIME_CONFIG__ = {
  BACKEND_URL: "http://new-backend-url.amazonaws.com"
};
```

Then restart pods:
```bash
kubectl rollout restart deployment/<release>-aira-frontend -n <namespace>
```

**Option C: Build-time Configuration**

```bash
docker build \
  --build-arg NEXT_PUBLIC_BACKEND_URL="http://backend:8000" \
  -f frontend/Dockerfile .
```

### Config File Location

| Environment | Config File Path |
|-------------|-----------------|
| Development | `frontend/public/config.js` |
| Docker/K8s | `/app/public/config.js` (mounted via ConfigMap) |

## Project Structure

```
frontend/
├── app/
│   ├── components/
│   │   ├── CopilotAgentDisplay.tsx  # Main agent display with strategy execution
│   │   ├── StrategySelector.tsx     # Multi-strategy selection UI
│   │   ├── TabbedReportDisplay.tsx  # Side-by-side report comparison
│   │   ├── ResearchForm.tsx         # Research input form
│   │   └── ReportDisplay.tsx        # Single report display
│   ├── contexts/
│   │   ├── CopilotResearchContext.tsx  # Research state management
│   │   └── AgentStreamContext.tsx      # SSE streaming context
│   ├── utils/
│   │   └── backendUrl.ts            # Runtime backend URL detection
│   ├── layout.tsx                   # Root layout with CopilotKit provider
│   ├── page.tsx                     # Main page
│   └── globals.css                  # Global styles
├── public/
│   └── config.js                    # Runtime configuration (mountable)
├── Dockerfile
└── package.json
```

## Environment Variables

| Variable | Type | Description |
|----------|------|-------------|
| `NEXT_PUBLIC_BACKEND_URL` | Build-time | Backend API URL (default: `http://localhost:8000`) |

> **Note**: `NEXT_PUBLIC_*` variables in Next.js are replaced at build time, not runtime. For dynamic configuration, use the runtime config approach described above.

## Troubleshooting

### "ERR_CONNECTION_REFUSED" or "Agent not found"

The frontend is trying to connect to the wrong backend URL.

1. Check browser console for the URL it's trying to reach
2. Update the runtime config (see Configuration section above)
3. Restart frontend pods if using Kubernetes

### Changes not taking effect

1. Clear browser cache (Ctrl+Shift+R)
2. For Kubernetes: ensure pods restarted after ConfigMap update
3. For Docker: rebuild the image if using build-time config

## Building for Production

```bash
# Build static assets
npm run build

# Build Docker image
docker build -f Dockerfile -t aiq-frontend:latest ..

# With custom backend URL
docker build \
  --build-arg NEXT_PUBLIC_BACKEND_URL="http://backend:8000" \
  -f Dockerfile -t aiq-frontend:latest ..
```

