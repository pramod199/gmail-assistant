# Gmail Assistant

A natural language Gmail assistant that reads, summarizes, and manages your emails using Google's Gemini AI.

## Features

- 📧 **Read emails** with natural language queries
- 📝 **Summarize messages** intelligently 
- ✅ **Mark emails as read** automatically
- ✍️ **Create draft replies** with AI assistance
- 🔍 **Advanced filtering** using Gmail search syntax
- 💬 **Natural language interface** - no commands to memorize

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up Gmail API:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing one
   - Enable Gmail API
   - Create credentials (OAuth 2.0 client ID)
   - Download `credentials.json` to project root

3. **Set up Gemini API:**
   - Get API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Set environment variable: `export GEMINI_API_KEY=your_api_key_here`

4. **Run the assistant:**
   ```bash
   python main.py
   ```

## Usage Examples

### Interactive Mode
```bash
python main.py
```

Then you can ask:
- "Show me my unread emails"
- "Summarize important messages from today"
- "Mark the last 3 emails as read"
- "Draft a reply to John's email"
- "What are my starred messages?"

### Single Command Mode
```bash
python main.py "summarize my unread emails"
python main.py "show me emails from boss today"
```

## Natural Language Examples

The assistant understands natural language requests:

- **Reading emails:**
  - "Show me unread emails"
  - "What emails did I get from John?"
  - "Display important messages from today"

- **Summarizing:**
  - "Summarize my important emails"
  - "Give me a brief of today's messages"
  - "What's the overview of unread emails?"

- **Managing:**
  - "Mark all unread emails as read"
  - "Mark the last 5 emails as read"

- **Drafting:**
  - "Draft a reply to the latest email"
  - "Create a response to John's message"

## Project Structure

```
gmail-assistant/
├── src/
│   ├── core/
│   │   ├── auth/              # Gmail authentication
│   │   ├── gmail_client/      # Gmail API integration
│   │   ├── filters/           # Message filtering
│   │   ├── processors/        # Message processing
│   │   └── llm/              # Gemini integration
│   ├── interface/            # Natural language processing
│   └── utils/                # Utilities
├── main.py                   # Entry point
├── requirements.txt          # Dependencies
└── README.md
```

## Configuration

Set environment variable:
```bash
export GEMINI_API_KEY=your_api_key_here
```

## Security

- Credentials are stored locally and not transmitted
- No email content is logged or stored
- Uses OAuth 2.0 for secure Gmail access
- API keys are loaded from environment variables

## Troubleshooting

**Gmail authentication fails:**
- Ensure `credentials.json` is in the project root
- Check that Gmail API is enabled in Google Cloud Console

**Gemini API errors:**
- Verify your API key is set: `echo $GEMINI_API_KEY`
- Check your Gemini API quota

**No emails found:**
- Try broader search terms
- Check your Gmail labels and filters