# 🚀 Quick Start Guide

## AI-Q + UDF Research Assistant - Get Running in 30 Minutes

This guide gets you up and running as quickly as possible. For detailed documentation, see [DEPLOYMENT.md](DEPLOYMENT.md).

---

## Prerequisites Checklist

- [ ] AWS Account configured (`aws configure`)
- [ ] Tools installed: `terraform`, `kubectl`, `helm`, `docker`
- [ ] NVIDIA NGC API Key ([Get it here](https://ngc.nvidia.com/setup/api-key))
- [ ] Tavily API Key (optional, [get here](https://tavily.com/))

---

## 3-Step Deployment

### Step 1: Setup Environment (2 minutes)

```bash
cd ~/repos/AIML/Research_as_a_Code

# Set your API keys
export TF_VAR_ngc_api_key="nvapi-YOUR_KEY_HERE"
export NGC_API_KEY="nvapi-YOUR_KEY_HERE"
export TAVILY_API_KEY="tvly-YOUR_KEY_HERE"  # Optional
export AWS_DEFAULT_REGION="us-west-2"

# Verify
echo $NGC_API_KEY
aws sts get-caller-identity
```

### Step 2: Deploy Infrastructure (~20 minutes)

```bash
cd infrastructure/terraform
./install.sh

# Configure kubectl (command will be shown at end of install)
aws eks update-kubeconfig --region us-west-2 --name ai-q-udf-hackathon
```

### Step 3: Deploy Application (~40 minutes)

```bash
cd ../kubernetes

# Deploy NIMs (30 minutes)
./deploy-nims.sh

# Deploy Agent (10 minutes)
./deploy-agent.sh
```

---

## Access Your Application

```bash
# Get the URL
kubectl get svc aiq-agent-frontend -n aiq-agent

# Look for EXTERNAL-IP column (e.g., xxx.us-west-2.elb.amazonaws.com)
# Open in browser: http://<EXTERNAL-IP>
```

---

## Test It Works

1. Open the application URL in your browser
2. Enter query: `"What is Amazon EKS?"`
3. Watch the "Agentic Flow" panel show real-time execution
4. See the generated report in the right panel

**Advanced test:**

Enter: `"Generate a report on NIMs on EKS with cost-benefit analysis"`

Watch as the agent:
- Recognizes complexity → Selects UDF strategy
- Compiles multi-step research plan
- Executes dynamic code
- Synthesizes comprehensive report

---

## Troubleshooting One-Liners

```bash
# Check if everything is running
kubectl get nodes && kubectl get pods -n nim && kubectl get pods -n aiq-agent

# Watch NIMs start
kubectl get pods -n nim --watch

# View agent logs
kubectl logs -n aiq-agent -l component=backend -f

# Restart a stuck NIM
kubectl delete pod <pod-name> -n nim
```

---

## Cleanup

```bash
# Delete agent only
kubectl delete namespace aiq-agent

# Delete NIMs
kubectl delete namespace nim

# Delete infrastructure (stops all costs)
cd infrastructure/terraform
terraform destroy
```

---

## Estimated Timeline

| Task | Time |
|------|------|
| Prerequisites setup | 5 min |
| Terraform (EKS + Karpenter) | 20 min |
| NIMs deployment | 30 min |
| Agent deployment | 10 min |
| **Total** | **~65 min** |

---

## Costs

**With Spot instances**: ~$4-5/hour  
**With On-Demand**: ~$15-20/hour

**Remember to `terraform destroy` when done!**

---

## Next Steps

- Read [README.md](README.md) for architecture details
- See [DEPLOYMENT.md](DEPLOYMENT.md) for troubleshooting
- Explore [cursor/design_plan.md](cursor/design_plan.md) for design rationale
- Customize [backend/main.py](backend/main.py) for your needs

---

## Key Features to Demo

1. **Simple RAG**: Ask "What is Kubernetes?"
2. **UDF Strategy**: Ask "Compare EKS vs GKE with cost analysis"
3. **Real-Time Flow**: Watch the left panel stream agent decisions
4. **Report Quality**: Download and review the generated markdown

---

## Common Issues

| Issue | Solution |
|-------|----------|
| "Permission denied" on scripts | `chmod +x infrastructure/**/*.sh` |
| NIMs stuck in Pending | Wait 10min for Karpenter to provision GPU nodes |
| ImagePullBackOff | Check NGC_API_KEY is correct |
| Can't access frontend | Wait 5min for LoadBalancer DNS to propagate |

---

## Support

- **GitHub Issues**: [Create an issue](https://github.com/yourusername/Research_as_a_Code/issues)
- **Documentation**: See [README.md](README.md) and [DEPLOYMENT.md](DEPLOYMENT.md)
- **Architecture**: See [cursor/design_plan.md](cursor/design_plan.md)

**Happy Hacking!** 🎉

Built for AWS & NVIDIA Agentic AI Unleashed Hackathon 2025

