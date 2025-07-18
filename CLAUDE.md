# Gmail Assistant - Technical Plan

## Project Overview
Building a modular Gmail assistant that processes natural language requests to read, summarize, and manage Gmail messages using Gemini LLM.

## Architecture Design

### Modular Structure
```
gmail-assistant/
├── src/
│   ├── core/
│   │   ├── auth/              # Gmail authentication & credentials
│   │   ├── gmail_client/      # Gmail API integration
│   │   ├── filters/           # Message filtering system
│   │   ├── processors/        # Message processing & analysis
│   │   └── llm/              # Gemini LLM integration
│   ├── interface/            # Natural language processing
│   ├── utils/                # Utilities & helpers
│   └── config/               # Configuration management
├── tests/                    # Unit & integration tests
├── requirements.txt          # Dependencies
└── main.py                  # Entry point
```

## Core Components

### 1. Authentication Layer (`src/core/auth/`)
- **gmail_auth.py**: OAuth2 credential management
- **token_manager.py**: Token refresh & storage
- **scopes_config.py**: Gmail API scopes configuration

### 2. Gmail API Client (`src/core/gmail_client/`)
- **gmail_service.py**: Gmail API service wrapper
- **message_reader.py**: Message retrieval operations
- **message_modifier.py**: Mark read, draft creation
- **error_handler.py**: API error handling

### 3. Message Filtering (`src/core/filters/`)
- **filter_engine.py**: Main filtering logic
- **filter_types.py**: Unread, important, starred filters
- **query_builder.py**: Gmail query string construction
- **custom_filters.py**: User-defined filter support

### 4. Message Processing (`src/core/processors/`)
- **message_parser.py**: Extract content, headers, metadata
- **content_extractor.py**: Clean & format message content
- **attachment_handler.py**: Handle attachments safely

### 5. LLM Integration (`src/core/llm/`)
- **gemini_client.py**: Gemini API integration
- **prompt_templates.py**: Summarization & response prompts
- **response_generator.py**: Draft generation logic

### 6. Natural Language Interface (`src/interface/`)
- **nlp_processor.py**: Natural language intent recognition
- **intent_classifier.py**: Classify user requests (read, summarize, draft, mark-read)
- **parameter_extractor.py**: Extract filters, limits, recipients from text
- **conversation_handler.py**: Manage interactive sessions

## Natural Language Processing

### User Input Examples
Users can express requests naturally:
- "Show me my unread emails"
- "Summarize important messages from today"
- "Mark the last 3 emails as read"
- "Draft a reply to John's email about the meeting"
- "What are my starred messages?"
- "Read emails from my boss"

### Intent Classification
- **READ**: "show", "read", "get", "fetch", "list", "what are"
- **SUMMARIZE**: "summarize", "summary", "brief", "overview"
- **MARK_READ**: "mark read", "mark as read", "archive"
- **DRAFT**: "reply", "draft", "compose", "write back"

### Parameter Extraction
- **Filters**: "unread", "important", "starred", "from:sender"
- **Limits**: "last 5", "recent", "today", "this week"
- **Recipients**: email addresses, names in contacts

## Technical Implementation

### Gemini Integration for NLP
- **Intent Recognition**: Use Gemini to classify user intent from natural language
- **Parameter Extraction**: Extract filters, limits, and targets from user requests
- **Context Understanding**: Maintain conversation context for follow-up questions

### Gmail API Integration
- **Authentication**: OAuth2 flow with credential caching
- **Scopes**: `gmail.modify` for read/mark operations, `gmail.compose` for drafts
- **Rate Limiting**: Implement request throttling & retry logic
- **Error Handling**: Graceful handling of quota limits & network issues

### Message Processing Pipeline
1. **User Input**: Natural language request
2. **Intent Analysis**: Gemini classifies intent and extracts parameters
3. **Gmail Query**: Build appropriate Gmail API query
4. **Message Retrieval**: Fetch matching messages
5. **Content Processing**: Extract and format message content
6. **LLM Processing**: Summarize or generate responses as needed
7. **User Response**: Present results in natural language

## Dependencies & Requirements
- `google-auth==2.3.3`
- `google-api-python-client==2.31.0`
- `google-generativeai` (Gemini SDK)
- `pydantic` (Data validation)
- `python-dotenv` (Environment management)

## Development Phases
1. **Phase 1**: Core authentication & Gmail API integration
2. **Phase 2**: Basic message reading with simple filters
3. **Phase 3**: Gemini integration for intent recognition
4. **Phase 4**: Natural language parameter extraction
5. **Phase 5**: Summarization & draft generation
6. **Phase 6**: Interactive conversation handling
7. **Phase 7**: Testing & optimization

## Security & Configuration
- **Credential Security**: Secure token storage, no hardcoded secrets
- **Input Validation**: Sanitize user inputs & email content
- **Privacy**: No logging of email content or personal data
- **Rate Limiting**: Respect Gmail API quotas
- **Error Handling**: Graceful degradation for API failures