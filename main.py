#!/usr/bin/env python3

import os
import re
import sys
import readline

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.core.auth.gmail_auth import GmailAuth
from src.core.gmail_client.gmail_service import GmailService
from src.core.llm.gemini_client import GeminiClient
from src.interface.nlp_processor import NLPProcessor


class GmailAssistant:
    def __init__(self):
        print("🚀 Starting Gmail Assistant...")
        
        # Initialize components
        self.gmail_auth = GmailAuth()
        self.gmail_service = GmailService(self.gmail_auth)
        self.gemini_client = GeminiClient()
        self.nlp_processor = NLPProcessor(self.gmail_service, self.gemini_client)
        
        # Test connections
        # self._verify_connections()
    
    def _verify_connections(self):
        print("Authenticating with Gmail...")
        if not self.gmail_service.test_connection():
            print("Gmail authentication failed!")
            sys.exit(1)
        print("Gmail connection successful!")
        
        print("Testing Gemini connection...")
        try:
            test_result = self.gemini_client.classify_intent("test")
            print("Gemini connection successful!")
        except Exception as e:
            print(f"Gemini connection failed: {e}")
            print("Make sure GEMINI_API_KEY is set in your environment")
            sys.exit(1)
    
    def run_interactive(self):
        print("\n Gmail Assistant ready!")
        print("Ask me anything in natural language:")
        print("  • 'Show me my first unread email'")
        print("  • 'Read the last 3 emails in full'")
        print("  • 'Summarize my important messages'")
        print("  • 'Mark my unread emails as read'")
        print("  • 'Draft a reply to the latest email'")
        print("  • Type 'quit' to exit\n")
        
        while True:
            try:
                user_input = input("💬 Ask me: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'bye']:
                    print("👋 Goodbye!")
                    break
                
                if not user_input:
                    continue
                
                print("Processing your request...")
                result = self.nlp_processor.process_user_request(user_input, "me")
                
                print("\n" + "="*50)
                # print(f"full response {result}")
                print("\n result" + "="*50)
                print(result.get("response", "No response generated"))
                print("="*50 + "\n")
                
            except KeyboardInterrupt:
                print("\n Goodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")


def main():
    assistant = GmailAssistant()
    assistant.run_interactive()


if __name__ == "__main__":
    main()