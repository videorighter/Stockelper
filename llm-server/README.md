# Stockelper LLM Server

A multi-agent LangGraph-based system for comprehensive stock analysis and trading decisions, powered by AI agents specializing in different aspects of financial analysis.

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- API keys for external services (see Configuration section)

### One-Command Deployment

1. Clone the repository:
```bash
git clone <repository-url>
cd Stockelper/llm-server
```

2. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

3. Start the services:
```bash
docker-compose up -d
```

4. Access the API:
- Server: http://localhost:8000
- Health check: http://localhost:8000/health
- API documentation: http://localhost:8000/docs

## 🏗️ Architecture

### Multi-Agent System

The Stockelper LLM server implements a sophisticated multi-agent architecture using LangGraph:

#### Core Agents

1. **SupervisorAgent**: Central orchestrator that routes tasks and manages agent execution
2. **MarketAnalysisAgent**: Analyzes market trends, news, and sentiment
3. **FundamentalAnalysisAgent**: Performs fundamental analysis of companies
4. **TechnicalAnalysisAgent**: Conducts technical analysis of stock charts
5. **RiskManagementAgent**: Assesses and manages investment risks
6. **TradingAgent**: Executes trading decisions based on analysis

#### Agent Tools

Each agent has specialized tools:
- **News Search**: Real-time financial news retrieval
- **Report Search**: Company report analysis
- **Sentiment Analysis**: Market sentiment evaluation
- **Graph QA**: Knowledge graph querying
- **Technical Indicators**: Chart pattern analysis
- **Risk Metrics**: Risk assessment calculations

### System Components

- **FastAPI Server**: RESTful API interface
- **PostgreSQL**: User data and checkpoint storage
- **Neo4j**: Knowledge graph for relationships
- **MongoDB**: Document storage for reports and news
- **Langfuse**: AI observability and tracing (cloud)

## 🔧 Configuration

### Required API Keys

Create a `.env` file based on `.env.example` and configure:

#### AI Services
- `YOUR_OPENAI_API_KEY`: OpenAI GPT models
- `YOUR_ANTHROPIC_API_KEY`: Claude models
- `YOUR_TAVILY_API_KEY`: Web search capabilities

#### Observability
- `YOUR_LANGFUSE_CLOUD_HOST`: Langfuse cloud instance
- `YOUR_LANGFUSE_PUBLIC_KEY`: Langfuse public key
- `YOUR_LANGFUSE_SECRET_KEY`: Langfuse secret key

#### Data Services
- `YOUR_NEO4J_URI`: Neo4j graph database
- `YOUR_NEO4J_USERNAME`: Neo4j username
- `YOUR_NEO4J_PASSWORD`: Neo4j password
- `YOUR_MONGODB_URI`: MongoDB connection string

#### Trading API (Optional)
- `YOUR_KIS_APP_KEY`: Korean Investment & Securities API
- `YOUR_KIS_APP_SECRET`: KIS API secret
- `YOUR_KIS_ACCESS_TOKEN`: KIS access token

#### Database
- `DB_PASSWORD`: PostgreSQL password

### Service Configuration

The system uses cloud-based Langfuse for observability, eliminating the need for local setup. All sensitive information is externalized through environment variables.

## 📊 API Usage

### Basic Analysis Request

```bash
curl -X POST "http://localhost:8000/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Analyze AAPL stock for investment decision",
    "analysis_type": "comprehensive"
  }'
```

### Streaming Analysis

```bash
curl -X POST "http://localhost:8000/analyze/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the current market sentiment for Tesla?",
    "stream": true
  }'
```

### Agent-Specific Analysis

```bash
curl -X POST "http://localhost:8000/agent/market-analysis" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Latest news impact on semiconductor stocks",
    "symbols": ["NVDA", "AMD", "INTC"]
  }'
```

## 🛠️ Development

### Local Development Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
export DATABASE_URL="postgresql://stockelper:password@localhost:5432/stockelper"
export OPENAI_API_KEY="your-key"
# ... other environment variables
```

3. Run the development server:
```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Project Structure

```
llm-server/
├── src/
│   ├── multi_agent/           # LangGraph agents
│   │   ├── supervisor_agent/  # Central orchestrator
│   │   ├── market_analysis_agent/
│   │   ├── fundamental_analysis_agent/
│   │   ├── technical_analysis_agent/
│   │   ├── risk_management_agent/
│   │   └── base/             # Base agent classes
│   ├── routers/              # FastAPI routers
│   ├── models/               # Data models
│   ├── services/             # Business logic
│   └── main.py               # FastAPI application
├── database/
│   └── init-db.sql          # Database initialization
├── docker-compose.yml       # Container orchestration
├── Dockerfile              # Container definition
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## 🔒 Security

### Environment Variables

- All sensitive data is externalized through environment variables
- Use strong passwords for database access
- Rotate API keys regularly
- Use HTTPS in production

### Database Security

- PostgreSQL runs in an isolated Docker network
- Database initialization scripts create proper user permissions
- Checkpoint data is encrypted at rest

## 📈 Monitoring

### Langfuse Integration

The system integrates with Langfuse cloud for:
- Request tracing and monitoring
- Performance analytics
- Cost tracking
- Error monitoring

Access your Langfuse dashboard to monitor system performance and usage.

### Health Checks

- Server health: `GET /health`
- Database connectivity: Automatic health checks in Docker
- Service dependencies: Built-in dependency validation

## 🚀 Deployment

### Production Deployment

1. Use environment-specific configuration:
```bash
# Production environment variables
export ENVIRONMENT=production
export DEBUG=false
export DATABASE_URL="your-production-db-url"
```

2. Scale services as needed:
```bash
docker-compose up -d --scale stockelper-llm-server=3
```

3. Set up reverse proxy (nginx/traefik) for load balancing

### Cloud Deployment

The system is designed for cloud deployment with:
- Stateless application design
- External service dependencies
- Container-based architecture
- Environment-based configuration

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:
1. Check the API documentation at `/docs`
2. Review logs in Docker containers
3. Verify environment variable configuration
4. Check external service connectivity

## 🔄 Updates

The system supports hot reloading in development mode. For production updates:
1. Build new container images
2. Update environment variables if needed
3. Perform rolling deployment
4. Verify system health

---

**Note**: This is an open-source version with sensitive information redacted. Ensure you have valid API keys and proper configuration before deployment.
