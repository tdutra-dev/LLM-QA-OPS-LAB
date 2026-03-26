# 🤖 LLM-QA-OPS-LAB

**Production-Ready Autonomous LLM Operations Platform**

An enterprise-grade system for **autonomous incident management** powered by Large Language Models. This project demonstrates how to build **production-quality AI systems** with the same operational discipline as distributed backend services.

## 🚀 **What This System Does**

**Autonomous LLM Agent** that:
- **Perceives** incidents from multiple data streams
- **Evaluates** severity using OpenAI tool calling
- **Acts** autonomously with remediation strategies
- **Monitors** system health in real-time with interactive dashboards
- **Scales** horizontally on Kubernetes with cloud-native operations

**Production Features:**
- ✅ **Real-time Dashboard** (Dash + Plotly + Bootstrap)
- ✅ **Kubernetes Deployment** (complete K8s manifests + Helm)
- ✅ **Autonomous Agent Loop** (percezione → valutazione → azione)
- ✅ **OpenAI Tool Calling** (LLM chooses remediation tools autonomously)
- ✅ **FastAPI Backend** (auto-generated docs, async processing)
- ✅ **PostgreSQL + Redis** (persistent storage + caching layer)
- ✅ **Docker Compose** (local development environment)
- ✅ **Pandas + Polars Analytics** (time series analysis, failure rates)

## 🎯 **Key Technical Achievements**

Built through **11 implementation steps**, this project showcases:

### 🔧 **Backend Engineering**
- **FastAPI** with async/await patterns, automatic OpenAPI docs
- **PostgreSQL** with SQLAlchemy ORM, migrations, connection pooling
- **Redis** cache-aside pattern for performance optimization
- **Pydantic** models with runtime validation and type safety

### 🤖 **AI/LLM Integration** 
- **OpenAI Function Calling** for autonomous tool selection
- **Structured outputs** with JSON schema validation
- **Prompt versioning** and template management
- **Provider-agnostic adapters** (OpenAI, mock, extensible)

### 🌐 **Frontend & Visualization**
- **Interactive Dashboard** with real-time updates (Dash + Plotly)
- **Bootstrap UI** with responsive design
- **Time series charts** for trend analysis
- **Action audit trails** with filtering and search

### ☁️ **DevOps & Infrastructure**
- **Kubernetes manifests** for production deployment
- **Multi-stage Dockerfiles** optimized for size and security
- **Health checks** and **observability** (readiness/liveness probes)
- **Horizontal scaling** ready (stateless services)
- **Secret management** and **configuration as code**

## 🏗️ **System Architecture**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Dashboard     │    │  FastAPI + AI   │    │   Data Layer    │
│   (Dash 8050)   │◄───┤   (Port 8010)   ├───►│ PostgreSQL +    │
│                 │    │                 │    │ Redis Cache     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                        │                        │
         ▼                        ▼                        ▼
  📊 Real-time UI        🤖 AI Agent Loop         🗄️ Persistent Storage
  • Live metrics         • OpenAI Tool Calling    • Evaluation records  
  • Interactive charts   • Autonomous actions     • Analytics cache
  • Agent control        • Health monitoring      • Incident history
```

### **🔄 Autonomous Agent Loop**

The AI Agent autonomously:
1. **👁️ Perceives** incidents from data streams
2. **🧠 Evaluates** using OpenAI function calling (6 available tools)  
3. **⚡ Acts** with remediation strategies (monitor, retry, escalate, etc.)
4. **📈 Learns** from action outcomes for improved decision-making

```
Incident Stream → OpenAI Tool Calling → Action Selection → Execution → Logging
```

## 🛠️ **Technology Stack**

### **Backend Services**
- **FastAPI 0.104+** - High-performance async API with auto docs
- **PostgreSQL 16** - Primary data store with ACID compliance  
- **Redis 7** - High-speed cache layer for analytics
- **SQLAlchemy 2.0** - Modern async ORM with type safety
- **Pydantic V2** - Runtime validation and serialization

### **AI/LLM Integration**
- **OpenAI GPT-4** - Function calling for autonomous tool selection
- **Structured outputs** - JSON schema validation for reliability
- **Prompt engineering** - Versioned templates with deterministic generation

### **Frontend & Analytics**
- **Dash 2.16+** - Interactive Python web applications
- **Plotly 5.17+** - Real-time charting and visualization
- **Bootstrap 5** - Responsive UI components
- **Pandas 2.0** - Time series analysis and data processing
- **Polars** - High-performance DataFrame operations  

### **Infrastructure & DevOps**
- **Docker & Compose** - Containerized local development
- **Kubernetes** - Production orchestration with auto-scaling
- **nginx Ingress** - Load balancing and SSL termination
- **Multi-stage builds** - Optimized container images

## 🚀 **Quick Start**

### **Local Development (Docker Compose)**
```bash
git clone https://github.com/tdutra-dev/LLM-QA-OPS-LAB.git
cd LLM-QA-OPS-LAB

# Start complete stack
docker compose up --build -d

# Access applications
# Dashboard: http://localhost:8050  
# FastAPI:   http://localhost:8010/docs
```

### **Kubernetes Deployment** 
```bash
# Build and deploy to K8s
./scripts/k8s/build-images.sh
./scripts/k8s/deploy.sh

# Access via port forwarding
kubectl port-forward -n llmqa svc/dash-app-svc 8050:8050
```

### **Core Design Principles**

**🔒 Production-Grade Reliability:**
- Structured LLM outputs with runtime validation
- Health checks and circuit breaker patterns
- Horizontal scaling and load balancing
- Secret management and security practices

**🎯 Observable AI Systems:**
- Real-time monitoring with interactive dashboards  
- Action audit trails and decision transparency
- Performance metrics and failure analysis
- Agent behavior logging and debugging

- Container orchestration with auto-scaling
- Infrastructure as Code (K8s manifests + scripts)
- CI/CD ready architecture and deployment automation

## 📊 **Features Highlight (Latest Implementation)**

### **🎛️ Real-Time Dashboard (Step 10)**
- **Interactive monitoring** with 4 specialized tabs
- **Live metrics**: evaluations, scores, agent status, system health  
- **Time series analytics**: daily trends, 7-day rolling averages
- **Action audit trail**: filterable history with outcome tracking
- **Agent control panel**: start/stop autonomous loop with real-time status

### **☸️ Kubernetes Orchestration (Step 11)**
- **Production-ready manifests**: complete K8s deployment stack
- **Horizontal scaling**: `kubectl scale deployment/eval-py --replicas=N`
- **Service mesh**: internal DNS resolution and load balancing
- **Ingress routing**: nginx-based traffic management
- **One-command deployment**: `./scripts/k8s/deploy.sh`

### **🤖 Autonomous Agent (Steps 7-9)**
- **Incident perception**: real-time data stream processing
- **AI-driven evaluation**: OpenAI function calling with 6 available tools
- **Autonomous actions**: monitor, retry, escalate, inspect prompt/schema, check provider
- **Learning loop**: action outcome analysis for improved decision-making

## 📈 **Completed Development Roadmap**

✅ **Step 1-6**: Core infrastructure (FastAPI, PostgreSQL, Redis, analytics, Docker)  
✅ **Step 7**: ActionExecutor for autonomous incident remediation  
✅ **Step 8**: Agent Loop implementation (percezione → valutazione → azione)  
✅ **Step 9**: OpenAI Tool Calling for LLM-driven action selection  
✅ **Step 10**: Interactive Dashboard with real-time monitoring  
✅ **Step 11**: Complete Kubernetes deployment and orchestration  

🔮 **Future Steps** (Production enhancement):
- **Step 12**: Performance monitoring (Prometheus + Grafana, load testing)
- **Step 13**: Production readiness (CI/CD pipelines, security hardening, SRE)

## 🎯 **API Endpoints Overview**

The FastAPI service provides comprehensive REST APIs:

### **Core Operations**
- `POST /evaluate` - Rule-based incident evaluation  
- `POST /evaluate/tool-call` - AI-driven evaluation with tool calling
- `GET /health` - System health check
- `GET /metrics` - Real-time system metrics

### **Analytics & Monitoring**
- `GET /analytics` - Pandas/Polars processed trends and statistics
- `GET /actions` - Action execution history with filtering
- `GET /incidents` - Incident stream with severity analysis

### **Agent Control**
- `POST /agent/start` - Start autonomous agent loop
- `POST /agent/stop` - Stop autonomous agent
- `GET /agent/status` - Agent activity and performance metrics

*Interactive API documentation available at `/docs` (Swagger UI)*

## 🏆 **Professional Skills Demonstrated**

### **Backend Development**
- **API Design**: RESTful architecture with OpenAPI documentation  
- **Database Engineering**: PostgreSQL with migrations, indexing, connection pooling
- **Caching Strategies**: Redis implementation with TTL and eviction policies
- **Async Programming**: FastAPI async/await patterns for high performance

### **AI/ML Engineering**  
- **LLM Integration**: Production-grade OpenAI API integration
- **Prompt Engineering**: Structured prompts with deterministic outputs
- **Function Calling**: Advanced AI tool selection and execution
- **Validation**: Runtime schema validation for AI output reliability

### **DevOps & Infrastructure**
- **Container Orchestration**: Complete Kubernetes deployment with scaling
- **Infrastructure as Code**: K8s manifests, ConfigMaps, Secrets management  
- **Service Discovery**: Internal DNS resolution and networking
- **Monitoring**: Health checks, readiness/liveness probes, observability

### **Full-Stack Development**
- **Interactive UIs**: Real-time dashboards with Dash + Plotly
- **Data Visualization**: Time series charts, trend analysis, KPI tracking
- **Responsive Design**: Bootstrap-based professional interfaces
- **State Management**: Real-time updates with WebSocket-style functionality

### **System Architecture**
- **Microservices**: Decoupled services with clear boundaries
- **Event-Driven Design**: Autonomous agent loop with reactive patterns  
- **Scalability**: Horizontal scaling and load balancing ready
- **Security**: Secret management, container security, network isolation

---

## 🎖️ **About the Developer**

**Tendresse Dutra**  
*Senior Backend & AI Systems Engineer*

**Core Expertise:**
- **AI/LLM Systems**: Production-grade artificial intelligence integration
- **Backend Architecture**: High-performance distributed systems  
- **Cloud Infrastructure**: Kubernetes, Docker, microservices orchestration
- **Full-Stack Development**: End-to-end application development

**This project demonstrates:**
- Enterprise-level software architecture and development
- Modern DevOps practices and infrastructure as code
- AI/ML engineering with production considerations
- Full-stack capabilities from database to user interface

*Building the future of AI-powered operations.* 🚀

---

# Project Vision

LLM-QA-OPS-LAB explores how AI systems can be operated with the same discipline as distributed backend systems.

The long-term goal is to build a framework for:

- LLM reliability
- AI system observability
- operational evaluation of AI workflows

Ultimately enabling **AI-assisted operational intelligence for modern backend systems**.

---

# Author

Tendresse Dutra  
Backend & AI Systems Engineer

Focus areas:

- backend architecture
- distributed systems
- AI reliability
- LLM operational intelligence
