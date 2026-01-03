# Voice Agent - AI-Powered Voice Assistant

A production-ready AI voice agent system built with **Deepgram Voice Agent**, **Twilio**, and **Convex RAG**. This system enables businesses to deploy intelligent voice assistants that can handle customer calls, answer questions from a knowledge base, and perform actions like taking orders or booking appointments.

## 🌟 Features

- **Real-time Voice Conversations** - Powered by Deepgram's Voice Agent API
- **Multi-tenant Architecture** - Support multiple organizations with isolated knowledge bases
- **RAG-based Knowledge Base** - Semantic search using Convex vector database
- **Document Ingestion** - Parse PDFs, images, and documents using LlamaParse
- **Dynamic Function Calling** - LLM can search menus, lookup business info, place orders
- **Twilio Integration** - Handle inbound/outbound phone calls
- **WebSocket Server** - Real-time audio streaming between Twilio and Deepgram
- **Configurable Agents** - Custom system prompts, functions, and voices per phone number

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Phone Call    │────▶│     Twilio      │────▶│  WebSocket      │
│   (Customer)    │     │   (Voice SIP)   │     │   Server        │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Convex DB     │◀───▶│   FastAPI       │◀───▶│   Deepgram      │
│  (RAG + Data)   │     │   (REST API)    │     │  Voice Agent    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                         │
                                                         ▼
                                                ┌─────────────────┐
                                                │  LLM (Groq)     │
                                                │  Function Calls │
                                                └─────────────────┘
```

## 📁 Project Structure

```
├── app/
│   ├── api/v1/           # REST API endpoints
│   │   ├── agents.py     # Agent management
│   │   ├── calls.py      # Call handling
│   │   ├── health.py     # Health checks
│   │   ├── knowledge_base.py  # KB management
│   │   ├── phone_configs.py   # Phone configuration
│   │   ├── tenants.py    # Multi-tenant management
│   │   └── twilio_webhooks.py # Twilio webhooks
│   ├── core/
│   │   ├── config.py     # Application settings
│   │   ├── convex_client.py   # Convex DB client
│   │   ├── logging.py    # Structured logging
│   │   └── exceptions.py # Custom exceptions
│   ├── functions/
│   │   └── dynamic_functions.py  # LLM function implementations
│   ├── services/
│   │   ├── voice_knowledge_service.py  # RAG search service
│   │   ├── chunking_service.py    # Document chunking
│   │   ├── config_service.py      # Phone config service
│   │   └── session_service.py     # Session management
│   └── schemas/          # Pydantic models
├── websocket_server/
│   ├── server.py         # WebSocket server for Twilio↔Deepgram
│   ├── connection_manager.py  # Connection handling
│   └── handlers/         # Message handlers
├── convex/               # Convex backend
│   ├── schema.ts         # Database schema
│   ├── rag.ts            # Vector search functions
│   ├── phoneConfigs.ts   # Phone config mutations
│   ├── organizations.ts  # Tenant management
│   └── agents.ts         # Agent configurations
├── scripts/
│   ├── setup_phone.py    # Configure phone agent
│   ├── ingest_file.py    # Ingest documents to KB
│   └── deploy_convex.py  # Deploy Convex backend
├── knowledge_data/       # Document files for ingestion
├── server.py             # FastAPI main entry point
├── start.py              # Application starter
└── make_call.py          # Outbound call utility
```

## 🚀 Quick Start

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Convex account
- Deepgram API key
- Twilio account
- Ngrok (for local development)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/SrinathS-21/Voice-Agent.git
   cd Voice-Agent
   ```

2. **Install dependencies**
   ```bash
   uv sync
   # or
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

4. **Deploy Convex backend**
   ```bash
   npx convex dev
   ```

5. **Start the server**
   ```bash
   # Terminal 1: Start ngrok
   ngrok http 5000

   # Terminal 2: Update WEBSOCKET_URL in .env with ngrok URL, then:
   uv run python start.py
   ```

### Setting Up a Phone Agent

1. **Configure phone number with agent settings**
   ```bash
   uv run python scripts/setup_phone.py
   ```

2. **Ingest knowledge base documents**
   ```bash
   uv run python scripts/ingest_file.py knowledge_data/your_document.pdf --org-id YOUR_ORG_ID
   ```

3. **Make a test call**
   ```bash
   uv run python make_call.py +1234567890
   ```

## ⚙️ Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `DEEPGRAM_API_KEY` | Deepgram API key for voice agent (required) |
| `TWILIO_ACCOUNT_SID` | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | Twilio auth token |
| `TWILIO_PHONE_NUMBER` | Your Twilio phone number |
| `WEBSOCKET_URL` | WebSocket server URL (ngrok in dev) |
| `CONVEX_URL` | Convex deployment URL (required) |
| `CONVEX_DEPLOY_KEY` | Convex deployment key |
| `OPENAI_API_KEY` | OpenAI API key for embeddings (required by Convex RAG) |
| `GROQ_API_KEY` | Groq API key for LLM (powers voice agent responses) |
| `LLAMA_CLOUD_API_KEY` | LlamaParse API key for document parsing |

### Agent Configuration

Agents are configured per phone number with:
- **System Prompt** - Instructions for the LLM
- **Greeting** - Initial message when call connects
- **Functions** - Available actions (search menu, lookup info, etc.)
- **Voice Settings** - TTS voice configuration

## 📚 API Endpoints

### Health & Status
- `GET /health` - Health check
- `GET /api/v1/health/ready` - Readiness probe

### Phone Configuration
- `GET /api/v1/phone-configs` - List phone configs
- `POST /api/v1/phone-configs` - Create phone config
- `GET /api/v1/phone-configs/{phone}` - Get config by phone

### Knowledge Base
- `POST /api/v1/knowledge-base/ingest` - Ingest document
- `POST /api/v1/knowledge-base/search` - Search knowledge base
- `DELETE /api/v1/knowledge-base/clear` - Clear namespace

### Calls
- `POST /api/v1/calls/outbound` - Initiate outbound call
- `GET /api/v1/calls/{call_id}` - Get call status

### Twilio Webhooks
- `POST /api/v1/twilio/voice` - Incoming call webhook
- `POST /api/v1/twilio/status` - Call status webhook

## 🔧 Development

### Running Tests
```bash
uv run pytest tests/
```

### Postman Collection
Import `VoiceAgent.postman_collection.json` for API testing.

### Debugging
- Check WebSocket logs for real-time conversation flow
- Use `scripts/debug_*.py` scripts for troubleshooting
- Enable verbose logging in `.env`

## 🏢 Multi-Tenant Setup

Each organization has:
- Isolated knowledge base namespace
- Custom agent configuration
- Separate phone number(s)
- Independent analytics

Create a new tenant:
```bash
uv run python scripts/create_tenant_simple.py
```

## 📖 Knowledge Base

### Supported Document Types
- PDF files
- Images (with OCR)
- Text files

### Ingestion Process
1. Document parsed by LlamaParse
2. Text cleaned and chunked (400 tokens, 150 overlap)
3. Embeddings generated via OpenAI text-embedding-3-small (1536 dimensions)
4. Stored in Convex vector database with semantic search

### Search
- Semantic search with cosine similarity
- Configurable result limits and score thresholds
- Caching for voice conversation performance

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

This project is proprietary software.

## 🙏 Acknowledgments

- [Deepgram](https://deepgram.com/) - Voice AI & Agent platform
- [Twilio](https://twilio.com/) - Cloud telephony
- [Convex](https://convex.dev/) - Backend database & RAG
- [OpenAI](https://openai.com/) - Embeddings for semantic search
- [LlamaParse](https://www.llamaindex.ai/) - Document parsing
