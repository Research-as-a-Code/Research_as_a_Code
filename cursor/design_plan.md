

# **A Hackathon Blueprint: Deploying a UDF-Enhanced NVIDIA AI-Q Agent on AWS EKS**

## **Executive Summary: An Integrated Blueprint for the Hackathon**

This report details a complete, integrated solution for the "Agentic AI Unleashed: AWS & NVIDIA Hackathon." The architecture synthesizes two distinct NVIDIA blueprints—the AI-Q Research Assistant and Universal Deep Research (UDF)—into a novel, two-level agentic system. This system is designed for deployment on a high-performance AWS EKS cluster, provisioned using Terraform and powered by the hackathon-mandated NVIDIA NIM microservices.

The core architectural vision involves a user interacting with a CopilotKit UI. This UI communicates with a FastAPI backend, which runs the primary AI-Q agent. This agent, built on LangGraph, orchestrates a "Deep Research" flow.1 The central innovation of this design is the integration of the NVIDIA UDF prototype 2 as a *dynamic tool* available to the AI-Q agent. This allows the agent to move beyond predefined RAG pipelines and, when a task's complexity warrants, *dynamically generate and execute a new research strategy on the fly* using UDF's "strategy-as-code" engine.3

The end-to-end flow is as follows:

1. **UI (CopilotKit):** The user submits a complex research prompt (e.g., "Generate a report on 'NIMs on EKS' and include a cost-benefit analysis").  
2. **Backend (FastAPI \+ CopilotKit SDK):** The request is received by the FastAPI backend, which is configured to stream the agent's internal state back to the UI in real-time.5  
3. **Agent (AI-Q LangGraph):** The main LangGraph agent, based on the NVIDIA NeMo Agent Toolkit 7, receives the prompt. Its "Planner" node, powered by the llama-3 1-nemotron-nano-8B-v1 NIM, recognizes this as a complex task.  
4. **Tool Invocation (UDF):** The agent formulates a natural language strategy (e.g., "1. Search web for 'NIMs on EKS'. 2\. Search internal docs for 'cost analysis'. 3\. Synthesize findings.") and calls a custom execute\_dynamic\_strategy tool.  
5. **Strategy Execution (UDF Core):** This tool, leveraging the UDF prototype's logic, compiles the natural language strategy into an executable Python code snippet.3  
6. **NIM Calls (EKS):** The generated Python code executes within the cluster, making in-network calls to:  
   * The Retrieval Embedding NIM 9 for RAG queries.  
   * The llama-3 1-nemotron-nano-8B-v1 NIM 10 for summarization, analysis, and reasoning.  
7. **Response & Visualization:** The UDF tool returns a structured result to the AI-Q agent, which formats the final report. Throughout this process, the CopilotKit UI receives live state updates (e.g., "Planning...", "Executing dynamic strategy...", "Calling Nemotron NIM..."), visualizing the agentic flow as required.11

The following table provides a "bill of materials" for the project, mapping the logical components of the application to the specific technologies and blueprints being used.

**Table 1: Architectural Component Map**

| Logical Component | Core Technology | NVIDIA Project/Blueprint | Specifics / Hackathon Mandate |
| :---- | :---- | :---- | :---- |
| **User Interface** | React / Next.js | AG-UI / CopilotKit | useCoAgentStateRender for flow visualization 11 |
| **Agent Backend** | FastAPI | NVIDIA AI-Q Blueprint | aiq-aira Python package 1 |
| **Agent Framework** | LangGraph | NVIDIA NeMo Agent Toolkit | StateGraph for stateful agent \[7, 12\] |
| **Dynamic Strategy** | Python Execution | NVIDIA UDF | "Strategy-as-Code" compiler 3 |
| **Reasoning LLM** | NVIDIA NIM | Nemotron | llama-3 1-nemotron-nano-8B-v1 \[13\] |
| **Embedding Model** | NVIDIA NIM | NeMo Retriever | text-embedding-nim 9 |
| **RAG Pipeline** | Microservices | NVIDIA RAG Blueprint | Integrated by AI-Q 1 |
| **IaaC (Path 1\)** | Terraform | AWS Blueprints | awslabs/data-on-eks 15 |
| **IaaC (Path 2\)** | AWS CDK | AWS Constructs | eks.Cluster, apprunner.Service, sagemaker.CfnEndpoint |
| **GPU Platform** | Kubernetes | AWS EKS \+ Karpenter | g5.xlarge instances provisioned on-demand 15 |

---

## **Part I: The Agentic Core: Synthesizing AI-Q and UDF**

This section details the "brain" of the application: the Python backend that fuses the production-ready AI-Q blueprint with the dynamic UDF prototype.

### **The Foundation: AI-Q Research Assistant Blueprint**

The NVIDIA AI-Q Research Assistant blueprint 1 serves as the starting point. Its architecture is already containerized, fronted by an nginx proxy, and built on a FastAPI backend (the aiq-aira package).1

Crucially, this blueprint is built on the **NVIDIA NeMo Agent Toolkit** 1, which provides the **LangGraph** framework. This directly satisfies the need for a stateful, multi-step agentic framework.12 The AI-Q agent already implements a "Deep Research" flow (plan, search, write, reflect) and a "Parallel Search" capability that consults both a RAG service and a web search (Tavily).1 This existing graph will be extended.

### **The Innovation: Integrating UDF as a Dynamic Tool**

A superficial analysis might suggest AI-Q and UDF 2 are competing research agents. However, a deeper analysis reveals a powerful symbiosis. AI-Q is a *persistent LangGraph agent* 1, while UDF is a *strategy-as-code compiler* that converts natural language plans into executable Python snippets.3 The UDF prototype UI even features a "strategy editing text area" for a human user.8 In this architecture, the AI-Q agent will replace the human, programmatically writing a strategy that UDF compiles and executes.

The implementation will involve isolating the core UDF logic (from its scan\_research.py file 2) into a Python function: def execute\_dynamic\_strategy(natural\_language\_plan: str) \-\> dict:.

This function will:

1. Use the UDF compiler to convert the natural\_language\_plan into an "actionable research orchestration code snippet".8  
2. Execute this code in an isolated environment, as UDF intends.4  
3. The executed code will then make its own calls to the NIMs (for search, summarization, etc.), which are available as internal cluster services.  
4. Finally, it will return the synthesized report or data.

This function will be registered as a Tool within the AI-Q agent's LangGraph, making it a new capability the agent can choose to invoke.

### **Defining the Unified LangGraph (Python Code Structure)**

A StateGraph from LangGraph 18 will be defined. The state object is the key to the entire system, as it is the object that will be streamed to the CopilotKit UI.

Python

from langgraph.graph import StateGraph, END  
from typing import TypedDict, List, Annotated  
import operator

\# The state object that will be streamed to the UI.  
\# This is the "handshake" between the backend and frontend.  
class AgentState(TypedDict):  
    research\_prompt: str  
    plan: str  
    dynamic\_strategy\_result: dict  
    final\_report: str  
    \# 'logs' will be updated by each node and rendered by CopilotKit  
    logs: Annotated\[List\[str\], operator.add\]

\# \--- Agent Nodes \---

def planner\_node(state: AgentState):  
    """  
    Calls the nemotron-nano-8b NIM to analyze the prompt.  
    Decides whether to use simple RAG or complex UDF strategy.  
    """  
    prompt \= state\["research\_prompt"\]  
    \#... (code to call nemotron-nano NIM)  
    plan \= "Generated plan from LLM..."   
      
    \# This is the critical update for the UI  
    new\_log \= f"Plan generated: {plan}"  
      
    return {"plan": plan, "logs": \[new\_log\]}

def dynamic\_strategy\_node(state: AgentState):  
    """  
    This node invokes the UDF "strategy-as-code" engine.  
    """  
    plan \= state\["plan"\]  
    new\_log \= f"Executing dynamic UDF strategy: {plan}"  
      
    \# Calls the wrapped UDF logic  
    result \= execute\_dynamic\_strategy(plan)   
      
    new\_log\_2 \= "UDF execution finished."  
      
    return {  
        "dynamic\_strategy\_result": result,   
        "logs": \[new\_log, new\_log\_2\]  
    }

def final\_report\_node(state: AgentState):  
    """  
    Synthesizes all findings into a final report.  
    """  
    new\_log \= "Generating final report."  
      
    \#... (code to synthesize report from state\["dynamic\_strategy\_result"\])  
    final\_report \= "This is the final generated report."  
      
    return {"final\_report": final\_report, "logs": \[new\_log\]}

\# \--- Conditional Logic \---

def should\_use\_udf(state: AgentState):  
    """  
    Inspects the plan to decide the next step.  
    """  
    if "use\_dynamic\_strategy" in state\["plan"\]:  
        return "dynamic\_strategy\_node"  
    else:  
        \# Assumes a 'simple\_rag\_node' (from AI-Q) also exists  
        return "simple\_rag\_node" 

\# \--- Build the Graph \---

def create\_agent\_graph():  
    workflow \= StateGraph(AgentState)  
      
    \# Add nodes to the graph  
    workflow.add\_node("planner", planner\_node)  
    workflow.add\_node("dynamic\_strategy", dynamic\_strategy\_node)  
    workflow.add\_node("final\_report", final\_report\_node)  
    \#... (add simple\_rag\_node, etc.)

    \# Wire the nodes together  
    workflow.set\_entry\_point("planner")  
      
    workflow.add\_conditional\_edges(  
        "planner",   
        should\_use\_udf,   
        {  
            "dynamic\_strategy\_node": "dynamic\_strategy",   
            "simple\_rag\_node": "simple\_rag" \# Placeholder for AI-Q's default RAG  
        }  
    )  
      
    workflow.add\_edge("dynamic\_strategy", "final\_report")  
    \#... (add edge from simple\_rag to final\_report)  
    workflow.add\_edge("final\_report", END)

    return workflow.compile()

This explicit state graph defines the "agentic flow" and provides the logs array for visualization.

---

## **Part II: The Interactive UI: Integrating AG-UI and CopilotKit**

This section details the frontend and the critical "glue" that connects it to the FastAPI backend, enabling real-time rendering of the logs from the AgentState.

### **The Protocol: AG-UI**

CopilotKit provides the AG-UI (Agent–User Interaction protocol) 19, which is the standard that allows the backend agent to communicate with the frontend components. It is designed for event-driven communication, state management, and streaming AI responses.6

### **The Backend Glue: copilotkit Python SDK**

The copilotkit Python SDK is natively LangGraph-aware, providing utilities for "interacting with the agent's state" 20 and explicitly designed to "integrate LangGraph workflows with CopilotKit state streaming".5

The AI-Q blueprint's main.py file, which is already a FastAPI app 1, will be modified to add the CopilotKit endpoint. This integration is remarkably straightforward.

Python

\# file: agent/main.py

import uvicorn  
from fastapi import FastAPI  
from copilotkit import CopilotKit

\# Import the graph constructor from Part I  
from.agent import create\_agent\_graph 

\# Initialize the AI-Q FastAPI app  
app \= FastAPI(  
    title="AI-Q Research Assistant Backend",  
    description="Backend service for the AI-Q agent with UDF and CopilotKit integration."  
)

\#... (all of AI-Q's existing endpoints for RAG, etc.)...

\# \--- CopilotKit Integration \---

\# 1\. Initialize the CopilotKit SDK  
copilot \= CopilotKit()

\# 2\. Wire the LangGraph agent to a new endpoint  
copilot.add\_langgraph\_endpoint(  
    app\_id="ai\_q\_researcher",      \# A unique name for this agent  
    endpoint="/copilotkit",         \# The API route the frontend will call  
    graph=create\_agent\_graph(),     \# Pass the compiled LangGraph app  
    config\_factory=lambda: {"configurable": {}}  
)

\# 3\. Include the new router in the FastAPI app  
\# This single line adds the '/copilotkit' POST endpoint  
app.include\_router(copilot.router)

\# \--- End CopilotKit Integration \---

if \_\_name\_\_ \== "\_\_main\_\_":  
    uvicorn.run(app, host="0.0.0.0", port=8000)

This code (based on 5) provides the entire backend integration. The SDK handles all the complexity of managing the WebSocket or streaming connection and synchronizing the AgentState object.

### **The Frontend Visualization: React \+ CopilotKit Hooks**

A standard Next.js/React frontend will be used.21 The application is first wrapped in the \<CopilotKit\> provider, which points to the backend API route.

TypeScript

// file: frontend/app/layout.tsx

"use client";  
import { CopilotKit } from "@copilotkit/react-core";  
import { CopilotPopup } from "@copilotkit/react-ui";  
import "@copilotkit/react-ui/styles.css";

// This component will render our agent's live logs  
import { AgentFlowDisplay } from "./components/AgentFlowDisplay"; 

export default function RootLayout({ children }: { children: React.ReactNode }) {  
  return (  
    \<html\>  
      \<body\>  
        \<CopilotKit  
          runtimeUrl\="/api/copilotkit" // A proxy to our FastAPI backend  
        \>  
          \<div className\="container"\>  
            \<h1\>Welcome to the AI-Q Research Assistant\</h1\>  
            {/\* This component renders the agentic flow \*/}  
            \<AgentFlowDisplay /\>   
              
            {/\* This provides the chat bubble UI \*/}  
            \<CopilotPopup /\>  
            {children}  
          \</div\>  
        \</CopilotKit\>  
      \</body\>  
    \</html\>  
  );  
}

The core of the visualization is achieved using the useCoAgentStateRender hook 11, which subscribes to the backend's AgentState stream.

TypeScript

// file: frontend/app/components/AgentFlowDisplay.tsx

"use client";  
import { useCoAgentStateRender } from "@copilotkit/react-core";

// This interface MUST match the Python 'AgentState' TypedDict  
interface AgentState {  
  research\_prompt: string;  
  plan: string;  
  dynamic\_strategy\_result: any;  
  final\_report: string;  
  logs: string;  
}

export function AgentFlowDisplay() {  
  // Subscribe to the state of the agent named "ai\_q\_researcher"  
  // This name must match the 'app\_id' in main.py  
  const { state } \= useCoAgentStateRender\<AgentState\>({  
    name: "ai\_q\_researcher",  
    render: ({ state }) \=\> {  
      // Don't render anything if there are no logs  
      if (\!state ||\!state.logs |

| state.logs.length \=== 0) {  
        return \<p\>Agent is idle. Ask a research question\!\</p\>;  
      }

      // This is the "agentic flow" visualization  
      return (  
        \<div className\="agent-flow"\>  
          \<h3\>Agent Status:\</h3\>  
          \<ul\>  
            {state.logs.map((log, index) \=\> (  
              \<li key\={index}\>  
                {log}  
              \</li\>  
            ))}  
          \</ul\>  
          {state.final\_report && (  
            \<div className\="report"\>  
              \<h3\>Final Report\</h3\>  
              \<pre\>{state.final\_report}\</pre\>  
            \</div\>  
          )}  
        \</div\>  
      );  
    },  
  });

  return null; // The hook itself handles the rendering  
}

This component directly renders the logs array from the AgentState, providing the exact real-time flow visualization required by the hackathon.

---

## **Part III: The Deployment Foundation: EKS vs. SageMaker**

A critical architectural decision is the choice of deployment platform, stipulated as either an "EKS Cluster or Amazon SageMaker AI endpoint." For this system, this is not a simple 1:1 choice. The application is a *system* of at least five microservices:

1. The Reasoning NIM (nemotron-nano-8b)  
2. The Embedding NIM  
3. The AI-Q FastAPI/LangGraph Agent Backend  
4. The UDF Python Executor  
5. The NVIDIA RAG services that AI-Q depends on 1

Deploying five separate SageMaker Endpoints 22 would be operationally complex and cost-prohibitive. Furthermore, the agent backend, a custom FastAPI app, is not a SageMaker model. Therefore, Amazon EKS is the superior platform, as it is designed to host all these components cohesively in a single, networked, and resource-managed environment.

### **Path 1: The Integrated EKS Architecture (Recommended)**

This architecture deploys all components—NIMs, RAG services, and the custom AI-Q/UDF Agent—as services within a single EKS cluster.

* **Service Discovery:** The agent backend (running in its pod) finds the reasoning NIM by calling its internal Kubernetes DNS name (e.g., http://nemotron-nano.nim.svc.cluster.local). This connection is secure, incurs zero network latency, and is free.  
* **GPU Provisioning:** The cluster will use **Karpenter** 15 for on-demand resource provisioning. When a NIM Deployment requests a GPU (via resources: { limits: { "nvidia.com/gpu": 1 } }), Karpenter will detect this request. It will automatically provision a new g5.2xlarge or g5.48xlarge spot instance 15, which features NVIDIA A10G Tensor Core GPUs.25 The **NVIDIA GPU Operator** 26, also installed in the cluster, will then automatically install the necessary drivers, enabling the NIM pod to be scheduled.

### **Path 2: The Serverless/Decoupled Architecture (Alternative)**

This path provides a viable alternative using SageMaker and other serverless components.

* **NIMs on SageMaker:** The nemotron-nano-8b NIM 22 and the Embedding NIM 27 are deployed as two separate **SageMaker Endpoints**. This requires packaging the NIM containers and pushing them to ECR.22  
* **Agent Backend on AWS App Runner:** The containerized FastAPI/LangGraph agent app is deployed to **AWS App Runner**.28 App Runner is a fully managed service for containerized web applications that can be deployed from ECR.30  
* **Service Discovery:** The App Runner service, using an assigned IAM role, calls the *public* SageMaker Endpoint URLs to run inference.31

### **Architectural Decision Trade-off**

The following table compares the two proposed architectures against key metrics for a hackathon.

**Table 2: Deployment Architecture Trade-offs**

| Metric | Path 1: Integrated EKS (Recommended) | Path 2: Serverless (SageMaker \+ App Runner) |
| :---- | :---- | :---- |
| **Performance** | **Very High.** Zero-latency network calls between services inside the EKS cluster. | **Medium.** All calls from the agent to the NIMs are public API calls, incurring network latency and potential cold starts.\[32\] |
| **Cost** | **Lower (at scale).** Karpenter 15 can use Spot instances. All services share pooled resources. | **Higher (at scale).** SageMaker Endpoints are billed per-hour, 24/7. App Runner is pay-per-request. |
| **Hackathon Deployment Speed** | **Fast (with IaaC).** The awslabs/data-on-eks Terraform blueprint 15 provisions 90% of the stack in one command. | **Medium.** Requires scripting the NIM-to-ECR-to-SageMaker pipeline 22 and the App Runner deployment.30 |
| **Scalability** | **Extremely High.** EKS \+ Karpenter is designed for massive, dynamic scaling.15 | **High (but decoupled).** SageMaker and App Runner scale automatically, but as two separate, uncoordinated systems. |
| **"Wow-Factor" / Complexity** | **Very High.** Demonstrates a complex, self-contained, microservice-based AI system on Kubernetes. | **High.** Demonstrates a modern, serverless AI architecture. |
| **Recommendation** | **WINNER.** This is the expert-grade solution and the awslabs blueprint provides a critical accelerator. | **Viable Alternative.** A good fallback if significant roadblocks are hit with EKS/Kubernetes. |

---

## **Part IV-A: IaaC Implementation: Terraform on EKS (Recommended)**

This section provides a step-by-step guide to deploying the recommended EKS architecture using the awslabs/data-on-eks Terraform blueprint.15

### **1\. Prerequisites**

* Install Terraform, kubectl, and the AWS CLI.  
* Obtain an **NVIDIA NGC API Key**.31 This is mandatory for pulling the NIM container images and model weights.

### **2\. Clone the data-on-eks Blueprint**

This AWS-provided blueprint is a massive accelerator. It contains pre-built Terraform modules to deploy data and AI workloads on EKS, with explicit support for NVIDIA NIMs.15

Bash

git clone https://github.com/awslabs/data-on-eks.git  
cd data-on-eks/ai-ml/nvidia-triton-server

While the directory is named nvidia-triton-server 15, the modules have been updated to deploy modern NVIDIA NIM workloads.

### **3\. Configure the Deployment**

Configure the blueprint by setting environment variables. These are read by the Terraform plan.

Bash

\# Set your target AWS Region  
export AWS\_DEFAULT\_REGION="us-west-2" 

\# 1\. Provide your NGC API Key (from Prerequisites)  
export TF\_VAR\_ngc\_api\_key="\<YOUR\_NGC\_API\_KEY\_HERE\>"

\# 2\. Enable the NVIDIA NIM deployment  
export TF\_VAR\_enable\_nvidia\_nim=true

\# 3\. Disable the standard Triton server (to avoid conflicts)  
export TF\_VAR\_enable\_nvidia\_triton\_server=false

This configuration 15 instructs Terraform to provision a full EKS cluster, install Karpenter for auto-scaling, and install the NVIDIA operators required to run GPU workloads.

### **4\. Deploy the Infrastructure**

The provided install.sh script simply wraps the terraform init and terraform apply commands.

Bash

./install.sh

This process will take approximately 20 minutes.15 On completion, a fully functional EKS cluster will be ready.

### **5\. Deploy the Hackathon-Mandated NIMs via Helm**

The Terraform blueprint sets up the cluster; Helm is used to deploy the specific models into it. First, configure kubectl to talk to the new cluster using the command output by Terraform.15

A) Deploy llama-3 1-nemotron-nano-8B-v1:  
This model 13 is deployed using the nim-llm Helm chart.10

Bash

\# Fetch the LLM NIM chart  
helm fetch https://helm.ngc.nvidia.com/nim/charts/nim-llm-\<version\>.tgz \\  
  \--username='$oauthtoken' \--password=$TF\_VAR\_ngc\_api\_key

\# Install the chart, overriding the image to use the hackathon-mandated model  
helm install nemotron-nano-nim./nim-llm-\<version\>.tgz \\  
  \--namespace nim \--create-namespace \\  
  \--set model.ngcAPIKey=$TF\_VAR\_ngc\_api\_key \\  
  \--set image.repository="nvcr.io/nim/nvidia/llama-3.1-nemotron-nano-8b-v1" \\  
  \--set image.tag="latest" \\  
  \--set resources.limits."nvidia.com/gpu"\=1 \\  
  \--set service.name="nemotron-nano-service"

B) Deploy the Retrieval Embedding NIM:  
This uses the text-embedding-nim chart.9

Bash

\# Fetch the Embedding NIM chart  
helm fetch https://helm.ngc.nvidia.com/nim/nvidia/charts/text-embedding-nim-\<version\>.tgz \\  
  \--username='$oauthtoken' \--password=$TF\_VAR\_ngc\_api\_key

\# Install the chart, selecting a specific embedding model  
helm install embedding-nim./text-embedding-nim-\<version\>.tgz \\  
  \--namespace nim \\  
  \--set image.repository="nvcr.io/nim/snowflake/arctic-embed-l" \\  
  \--set image.tag="1.0.1" \\  
  \--set persistence.enabled=true \\  
  \--set resources.limits."nvidia.com/gpu"\=1 \\  
  \--set service.name="embedding-service"

The key Helm overrides are summarized in the table below.

**Table 3: Key NVIDIA NIM Helm Chart Configurations**

| Chart | Key | Example Value | Purpose |
| :---- | :---- | :---- | :---- |
| nim-llm | image.repository | nvcr.io/nim/nvidia/llama-3.1-nemotron-nano-8b-v1 | **Selects the hackathon-mandated reasoning NIM** \[34\] |
| nim-llm | model.ngcAPIKey | "$NGC\_API\_KEY" | Authenticates to NGC to pull the model weights \[31, 36\] |
| nim-llm | resources.limits."nvidia.com/gpu" | 1 | Triggers Karpenter to provision a GPU node 15 |
| nim-llm | replicaCount | 2 | Deploys two pods for high availability (HA) 15 |
| text-embedding-nim | image.repository | nvcr.io/nim/snowflake/arctic-embed-l | Selects a specific, powerful embedding model 9 |
| text-embedding-nim | persistence.enabled | true | Persists model data across pod restarts \[14, 36\] |

### **6\. Deploy the Custom AI-Q Agent**

The final step is to deploy the custom FastAPI agent.

1. Containerize the FastAPI app from Part I using the Dockerfile in the AI-Q repo.1  
2. Push this custom image to a new AWS ECR repository.  
3. Apply a Kubernetes manifest to deploy this image into the EKS cluster.

**agent-deployment.yaml:**

YAML

apiVersion: apps/v1  
kind: Deployment  
metadata:  
  name: aiq-agent-backend  
  namespace: nim  
spec:  
  replicas: 1  
  selector:  
    matchLabels:  
      app: aiq-agent  
  template:  
    metadata:  
      labels:  
        app: aiq-agent  
    spec:  
      containers:  
      \- name: aiq-agent  
        \# Replace with your ECR image path  
        image: "\<your\_account\_id\>.dkr.ecr.us-west-2.amazonaws.com/aiq-agent:latest"  
        ports:  
        \- containerPort: 8000  
        env:  
        \# These URLs use Kubernetes DNS to find the NIM services  
        \- name: NEMOTRON\_NIM\_URL  
          value: "http://nemotron-nano-service.nim.svc.cluster.local:8000"  
        \- name: EMBEDDING\_NIM\_URL  
          value: "http://embedding-service.nim.svc.cluster.local:8000"  
\---  
apiVersion: v1  
kind: Service  
metadata:  
  name: aiq-agent-service  
  namespace: nim  
spec:  
  selector:  
    app: aiq-agent  
  ports:  
  \- port: 80  
    targetPort: 8000  
  type: LoadBalancer \# Exposes the agent to the internet for the UI

Applying this manifest (kubectl apply \-f agent-deployment.yaml) deploys the agent and connects it to the NIMs via the internal cluster network.

---

## **Part IV-B: IaaC Implementation: CDK Serverless Alternative**

This section details the alternative, decoupled architecture (Path 2\) using the AWS CDK (TypeScript).

### **1\. Project Setup**

Bash

cdk init app \--language=typescript  
npm install aws-cdk-lib @aws-cdk/aws-sagemaker-alpha @aws-cdk/aws-apprunner-alpha

This initializes a CDK project and adds the necessary libraries for SageMaker and App Runner.29

### **2\. (Manual Step) Push NIMs to ECR**

SageMaker requires custom container images to be stored in ECR.22

Bash

\# Create the ECR repository  
aws ecr create-repository \--repository-name nim-nemotron-nano

\# Pull, tag, and push the NIM container  
docker pull nvcr.io/nim/nvidia/llama-3.1-nemotron-nano-8b-v1:latest  
docker tag... \<account\_id\>.dkr.ecr.us-west-2.amazonaws.com/nim-nemotron-nano:latest  
docker push \<account\_id\>.dkr.ecr.us-west-2.amazonaws.com/nim-nemotron-nano:latest

This process must be repeated for the text-embedding-nim container.

### **3\. CDK Stack for SageMaker Endpoints (TypeScript)**

This stack creates the SageMaker Model, EndpointConfig, and Endpoint from the ECR image.38

TypeScript

// file: lib/sagemaker-stack.ts  
import \* as cdk from 'aws-cdk-lib';  
import \* as sagemaker from '@aws-cdk/aws-sagemaker-alpha'; // Using alpha module for newer features  
import \* as ecr from 'aws-cdk-lib/aws-ecr';  
import \* as iam from 'aws-cdk-lib/aws-iam';

export class SageMakerNIMStack extends cdk.Stack {  
  public readonly nemotronEndpointName: string;  
  public readonly embeddingEndpointName: string;

  constructor(scope: cdk.Construct, id: string, props?: cdk.StackProps) {  
    super(scope, id, props);

    // Assumes an IAM Role for SageMaker exists  
    const sagemakerRole \= iam.Role.fromRoleArn(this, 'SageMakerRole', 'arn:aws:iam::\<...\>:role/sagemaker-execution-role');

    // 1\. Reference the ECR image pushed in Step 2  
    const nemotronRepo \= ecr.Repository.fromRepositoryName(this, 'NemotronRepo', 'nim-nemotron-nano');  
    const nemotronImage \= sagemaker.ContainerImage.fromEcrRepository(nemotronRepo, 'latest');  
      
    // 2\. Create the SageMaker Model  
    const nemotronModel \= new sagemaker.Model(this, 'NemotronModel', {  
      modelName: 'nemotron-nano-model',  
      containers: \[{ image: nemotronImage }\],  
      role: sagemakerRole,  
    });  
      
    // 3\. Create the SageMaker Endpoint  
    const nemotronEpConfig \= new sagemaker.EndpointConfig(this, 'NemotronEpConfig', {  
      instanceProductionVariants:  
        initialInstanceCount: 1,  
      }\],  
    });  
      
    const nemotronEndpoint \= new sagemaker.Endpoint(this, 'NemotronEndpoint', {  
      endpointConfig: nemotronEpConfig,  
    });

    this.nemotronEndpointName \= nemotronEndpoint.endpointName;  
      
    //... Repeat this process for the Embedding NIM...  
    this.embeddingEndpointName \= "embedding-endpoint-name"; // Placeholder  
  }  
}

### **4\. CDK Stack for App Runner (TypeScript)**

This stack deploys the containerized FastAPI agent to App Runner 29 and injects the SageMaker endpoint names as environment variables.

TypeScript

// file: lib/app-runner-stack.ts  
import \* as cdk from 'aws-cdk-lib';  
import \* as apprunner from '@aws-cdk/aws-apprunner-alpha'; // Using alpha module  
import \* as ecr from 'aws-cdk-lib/aws-ecr';  
import \* as iam from 'aws-cdk-lib/aws-iam';

interface AppRunnerStackProps extends cdk.StackProps {  
  nemotronEndpointName: string;  
  embeddingEndpointName: string;  
}

export class AppRunnerStack extends cdk.Stack {  
  constructor(scope: cdk.Construct, id: string, props: AppRunnerStackProps) {  
    super(scope, id, props);

    // 1\. Reference the agent's ECR image (must be pushed manually)  
    const agentRepo \= ecr.Repository.fromRepositoryName(this, 'AgentRepo', 'aiq-agent');

    // 2\. Create an IAM role for App Runner to call SageMaker  
    const appRunnerRole \= new iam.Role(this, 'AppRunnerSageMakerRole', {  
      assumedBy: new iam.ServicePrincipal('tasks.apprunner.amazonaws.com'),  
    });  
    appRunnerRole.addToPolicy(new iam.PolicyStatement({  
      actions: \['sagemaker:InvokeEndpoint'\],  
      resources: \['\*'\], // Best practice: scope down to specific endpoint ARNs  
    }));  
      
    // 3\. Create the App Runner Service  
    const agentService \= new apprunner.Service(this, 'AgentService', {  
      source: apprunner.Source.fromEcr({  
        imageConfiguration: { port: 8000 }, // FastAPI port  
        repository: agentRepo,  
        tag: 'latest',  
      }),  
      instanceRole: appRunnerRole,  
      // 4\. Pass NIM Endpoint names as environment variables  
      environmentVariables: {  
        NEMOTRON\_ENDPOINT\_NAME: props.nemotronEndpointName,  
        EMBEDDING\_ENDPOINT\_NAME: props.embeddingEndpointName,  
        DEPLOYMENT\_ENV: 'sagemaker',  
      },  
    });  
      
    new cdk.CfnOutput(this, 'AgentServiceUrl', {  
      value: agentService.serviceUrl,  
    });  
  }  
}

The agent's Python code would then need logic to check the DEPLOYMENT\_ENV variable and use boto3.client('sagemaker-runtime').invoke\_endpoint(...) 31 to call the NIMs.

---

## **Part V: Conclusion and Hackathon Strategy**

### **Final Recommendation**

For the "Agentic AI Unleashed: AWS & NVIDIA Hackathon," the **Terraform EKS (Part IV-A)** architecture is the superior choice.

### **Justification**

1. **IaaC Accelerator:** The awslabs/data-on-eks Terraform blueprint 15 is a significant advantage. It solves the most complex infrastructure problems (EKS cluster creation, Karpenter integration, and NVIDIA operator installation) with a single, battle-tested script.  
2. **Performance:** In-cluster networking provides the lowest possible latency between the agent and the NIMs.15 This will result in a faster, more responsive application, which is critical for a live demo.  
3. **Holistic System:** This architecture demonstrates a sophisticated, self-contained system on EKS. It is a more impressive and powerful pattern than decoupled serverless components and better reflects a real-world, high-performance deployment.

### **Winning Hackathon Strategy**

1. **Day 1 (Infrastructure):** Immediately clone the awslabs/data-on-eks repo.15 Configure your TF\_VAR\_ngc\_api\_key and run ./install.sh. While this \~20-minute process runs, proceed to step 2\.  
2. **Day 1 (Agent Core):** Begin coding the **Agentic Core (Part I)**. Wrap the UDF logic 3, define the AgentState TypedDict, and build the LangGraph StateGraph.18  
3. **Day 1 (NIMs):** Once the cluster is up, deploy the nemotron-nano-8b 10 and text-embedding-nim 9 using the Helm charts.  
4. **Day 1 (Backend):** Implement the **Backend Glue (Part II)**. Add the copilotkit SDK 5 to the AI-Q FastAPI main.py and test the /copilotkit endpoint.  
5. **Day 2 (UI & Deployment):** Build the **Frontend Visualization (Part II)**. Create the AgentFlowDisplay component using the useCoAgentStateRender hook.11 At the same time, containerize the agent backend, push it to ECR, and deploy it to the EKS cluster using the agent-deployment.yaml manifest.  
6. **Day 2 (Test & Refine):** Test the end-to-end flow. The majority of coding time should be focused on the agent-UI loop, as the IaaC has handled the infrastructure.  
7. **Final Presentation:** Ensure the presentation clearly visualizes the agentic flow on the UI, explains the EKS \+ Karpenter \+ NIM backend, and highlights the novel synthesis of AI-Q and UDF as the project's core innovation.

#### **Works cited**

1. NVIDIA-AI-Blueprints/aiq-research-assistant \- GitHub, accessed November 4, 2025, [https://github.com/NVIDIA-AI-Blueprints/aiq-research-assistant](https://github.com/NVIDIA-AI-Blueprints/aiq-research-assistant)  
2. NVlabs/UniversalDeepResearch: Code to accompany the Universal Deep Research paper (https://arxiv.org/abs/2509.00244) \- GitHub, accessed November 4, 2025, [https://github.com/NVlabs/UniversalDeepResearch](https://github.com/NVlabs/UniversalDeepResearch)  
3. NVIDIA AI Releases Universal Deep Research (UDR): A Prototype Framework for Scalable and Auditable Deep Research Agents \- MarkTechPost, accessed November 4, 2025, [https://www.marktechpost.com/2025/09/10/nvidia-ai-releases-universal-deep-research-udr-a-prototype-framework-for-scalable-and-auditable-deep-research-agents/](https://www.marktechpost.com/2025/09/10/nvidia-ai-releases-universal-deep-research-udr-a-prototype-framework-for-scalable-and-auditable-deep-research-agents/)  
4. Universal Deep Research: Bring Your Own Model and Strategy \- arXiv, accessed November 4, 2025, [https://arxiv.org/html/2509.00244v1](https://arxiv.org/html/2509.00244v1)  
5. How To Build Full-Stack Agent Apps (Gemini, CopilotKit & LangGraph), accessed November 4, 2025, [https://www.copilotkit.ai/blog/heres-how-to-build-fullstack-agent-apps-gemini-copilotkit-langgraph](https://www.copilotkit.ai/blog/heres-how-to-build-fullstack-agent-apps-gemini-copilotkit-langgraph)  
6. What is AG-UI protocol? \- CopilotKit | The Agentic Framework for In-App AI Copilots, accessed November 4, 2025, [https://www.copilotkit.ai/blog/build-a-fullstack-stock-portfolio-agent-with-langgraph-and-ag-ui](https://www.copilotkit.ai/blog/build-a-fullstack-stock-portfolio-agent-with-langgraph-and-ag-ui)  
7. How to Scale Your LangGraph Agents in Production From A Single User to 1000 Coworkers, accessed November 4, 2025, [https://developer.nvidia.com/blog/how-to-scale-your-langgraph-agents-in-production-from-a-single-user-to-1000-coworkers/](https://developer.nvidia.com/blog/how-to-scale-your-langgraph-agents-in-production-from-a-single-user-to-1000-coworkers/)  
8. Universal Deep Research \- Research at NVIDIA, accessed November 4, 2025, [https://research.nvidia.com/labs/lpr/udr/](https://research.nvidia.com/labs/lpr/udr/)  
9. Deploy NeMo Retriever Text Embedding NIM on Kubernetes \- NVIDIA Docs Hub, accessed November 4, 2025, [https://docs.nvidia.com/nim/nemo-retriever/text-embedding/latest/deploying.html](https://docs.nvidia.com/nim/nemo-retriever/text-embedding/latest/deploying.html)  
10. Deploying with Helm — NVIDIA NIM for Large Language Models (LLMs), accessed November 4, 2025, [https://docs.nvidia.com/nim/large-language-models/1.4.0/deploy-helm.html](https://docs.nvidia.com/nim/large-language-models/1.4.0/deploy-helm.html)  
11. Easily Build a UI for Your AI Agent in Minutes (LangGraph \+ CopilotKit), accessed November 4, 2025, [https://webflow.copilotkit.ai/blog/easily-build-a-ui-for-your-ai-agent-in-minutes-langgraph-copilotkit](https://webflow.copilotkit.ai/blog/easily-build-a-ui-for-your-ai-agent-in-minutes-langgraph-copilotkit)  
12. LangGraph Integration — NVIDIA NeMo Guardrails, accessed November 4, 2025, [https://docs.nvidia.com/nemo/guardrails/latest/user-guides/langchain/langgraph-integration.html](https://docs.nvidia.com/nemo/guardrails/latest/user-guides/langchain/langgraph-integration.html)  
13. nvidia/Llama-3.1-Nemotron-Nano-8B-v1 \- Hugging Face, accessed November 4, 2025, [https://huggingface.co/nvidia/Llama-3.1-Nemotron-Nano-8B-v1](https://huggingface.co/nvidia/Llama-3.1-Nemotron-Nano-8B-v1)  
14. Helm Chart for NeMo Retriever Text Embedding NIM \- NGC Catalog \- NVIDIA, accessed November 4, 2025, [https://catalog.ngc.nvidia.com/orgs/nim/teams/snowflake/helm-charts/text-embedding-nim](https://catalog.ngc.nvidia.com/orgs/nim/teams/snowflake/helm-charts/text-embedding-nim)  
15. Scaling a Large Language Model with NVIDIA NIM on Amazon EKS with Karpenter, accessed November 4, 2025, [https://aws.amazon.com/blogs/containers/scaling-a-large-language-model-with-nvidia-nim-on-amazon-eks-with-karpenter/](https://aws.amazon.com/blogs/containers/scaling-a-large-language-model-with-nvidia-nim-on-amazon-eks-with-karpenter/)  
16. NVIDIA NeMo Agent Toolkit \- NVIDIA Developer, accessed November 4, 2025, [https://developer.nvidia.com/nemo-agent-toolkit](https://developer.nvidia.com/nemo-agent-toolkit)  
17. Improve AI Code Generation Using NVIDIA NeMo Agent Toolkit | NVIDIA Technical Blog, accessed November 4, 2025, [https://developer.nvidia.com/blog/improve-ai-code-generation-using-nvidia-nemo-agent-toolkit/](https://developer.nvidia.com/blog/improve-ai-code-generation-using-nvidia-nemo-agent-toolkit/)  
18. LangGraph overview \- Docs by LangChain, accessed November 4, 2025, [https://docs.langchain.com/oss/python/langgraph/overview](https://docs.langchain.com/oss/python/langgraph/overview)  
19. Mastra, The TypeScript Agent Framework \- CopilotKit, accessed November 4, 2025, [https://www.copilotkit.ai/blog/how-copilotkit-mastra-enable-real-time-agent-interaction](https://www.copilotkit.ai/blog/how-copilotkit-mastra-enable-real-time-agent-interaction)  
20. Streaming and Tool Calls \- CopilotKit, accessed November 4, 2025, [https://docs.copilotkit.ai/langgraph/concepts/copilotkit-config](https://docs.copilotkit.ai/langgraph/concepts/copilotkit-config)  
21. Agents 101: How to build your first AI Agent in 30 minutes\!⚡️ \- DEV Community, accessed November 4, 2025, [https://dev.to/copilotkit/agents-101-how-to-build-your-first-ai-agent-in-30-minutes-1042/?ref=anmolbaranwal.com](https://dev.to/copilotkit/agents-101-how-to-build-your-first-ai-agent-in-30-minutes-1042/?ref=anmolbaranwal.com)  
22. Deploy LLMs in Minutes using NVIDIA NIM on Amazon SageMaker | by Jeevitha M | Medium, accessed November 4, 2025, [https://medium.com/@jeevitha.m/deploy-llms-in-minutes-using-nvidia-nim-on-amazon-sagemaker-616a606d1529](https://medium.com/@jeevitha.m/deploy-llms-in-minutes-using-nvidia-nim-on-amazon-sagemaker-616a606d1529)  
23. CDK construct for installing and configuring Karpenter on EKS clusters \- GitHub, accessed November 4, 2025, [https://github.com/aws-samples/cdk-eks-karpenter](https://github.com/aws-samples/cdk-eks-karpenter)  
24. Amazon EKS- implementing and using GPU nodes with NVIDIA drivers | by Marcin Cuber, accessed November 4, 2025, [https://marcincuber.medium.com/amazon-eks-implementing-and-using-gpu-nodes-with-nvidia-drivers-08d50fd637fe](https://marcincuber.medium.com/amazon-eks-implementing-and-using-gpu-nodes-with-nvidia-drivers-08d50fd637fe)  
25. Amazon EC2 G5 Instances, accessed November 4, 2025, [https://aws.amazon.com/ec2/instance-types/g5/](https://aws.amazon.com/ec2/instance-types/g5/)  
26. NVIDIA GPU Operator with Amazon EKS, accessed November 4, 2025, [https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/amazon-eks.html](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/amazon-eks.html)  
27. Hosting NVIDIA speech NIM models on Amazon SageMaker AI: Parakeet ASR, accessed November 4, 2025, [https://aws.amazon.com/blogs/machine-learning/hosting-nvidia-speech-nim-models-on-amazon-sagemaker-ai-parakeet-asr/](https://aws.amazon.com/blogs/machine-learning/hosting-nvidia-speech-nim-models-on-amazon-sagemaker-ai-parakeet-asr/)  
28. Deploy application containers to AWS App Runner with AWS App2Container, accessed November 4, 2025, [https://docs.aws.amazon.com/app2container/latest/UserGuide/a2c-integrations-apprunner.html](https://docs.aws.amazon.com/app2container/latest/UserGuide/a2c-integrations-apprunner.html)  
29. AppRunner Construct Library — AWS Cloud Development Kit 2.220.0 documentation, accessed November 4, 2025, [https://docs.aws.amazon.com/cdk/api/v2/python/aws\_cdk.aws\_apprunner\_alpha/README.html](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_apprunner_alpha/README.html)  
30. aws-samples/cdk-apprunner-ecr \- GitHub, accessed November 4, 2025, [https://github.com/aws-samples/cdk-apprunner-ecr](https://github.com/aws-samples/cdk-apprunner-ecr)  
31. Accelerate Generative AI Inference with NVIDIA NIM Microservices on Amazon SageMaker, accessed November 4, 2025, [https://aws.amazon.com/blogs/machine-learning/get-started-with-nvidia-nim-inference-microservices-on-amazon-sagemaker/](https://aws.amazon.com/blogs/machine-learning/get-started-with-nvidia-nim-inference-microservices-on-amazon-sagemaker/)  
32. AWS re:Invent 2024 \- High-performance generative AI on Amazon EKS, accessed November 4, 2025, [https://repost.aws/articles/AR1\_KslUIETuOMLGGJNPOEHA/aws-re-invent-2024-high-performance-generative-ai-on-amazon-eks](https://repost.aws/articles/AR1_KslUIETuOMLGGJNPOEHA/aws-re-invent-2024-high-performance-generative-ai-on-amazon-eks)  
33. Llama-3.1-Nemotron-Nano-8B-v1 \- NGC Catalog \- NVIDIA, accessed November 4, 2025, [https://catalog.ngc.nvidia.com/orgs/nim/teams/nvidia/containers/llama-3.1-nemotron-nano-8b-v1](https://catalog.ngc.nvidia.com/orgs/nim/teams/nvidia/containers/llama-3.1-nemotron-nano-8b-v1)  
34. Deploy with Helm for NVIDIA NIM for LLMs, accessed November 4, 2025, [https://docs.nvidia.com/nim/large-language-models/latest/deploy-helm.html](https://docs.nvidia.com/nim/large-language-models/latest/deploy-helm.html)  
35. aws/aws-cdk: The AWS Cloud Development Kit is a framework for defining cloud infrastructure in code \- GitHub, accessed November 4, 2025, [https://github.com/aws/aws-cdk](https://github.com/aws/aws-cdk)  
36. Deploy generative AI models from Amazon SageMaker JumpStart using the AWS CDK, accessed November 4, 2025, [https://aws.amazon.com/blogs/machine-learning/deploy-generative-ai-models-from-amazon-sagemaker-jumpstart-using-the-aws-cdk/](https://aws.amazon.com/blogs/machine-learning/deploy-generative-ai-models-from-amazon-sagemaker-jumpstart-using-the-aws-cdk/)  
37. Create a SageMaker inference endpoint with custom model & extended container, accessed November 4, 2025, [https://aws.amazon.com/blogs/machine-learning/create-a-sagemaker-inference-endpoint-with-custom-model-extended-container/](https://aws.amazon.com/blogs/machine-learning/create-a-sagemaker-inference-endpoint-with-custom-model-extended-container/)  
38. Deploying SageMaker Pipelines Using AWS CDK \- Luminis, accessed November 4, 2025, [https://www.luminis.eu/blog/deploying-sagemaker-pipelines-using-aws-cdk/](https://www.luminis.eu/blog/deploying-sagemaker-pipelines-using-aws-cdk/)