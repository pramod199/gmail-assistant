import os
import json
from typing import Optional, List, Dict, Any
import google.generativeai as genai
from config.settings import GEMINI_MODEL, GEMINI_TEMPERATURE, GEMINI_MAX_TOKENS, DEFAULT_EMAIL_LIMIT, DEFAULT_QUERY


class GeminiClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("Gemini API key not found. Set GEMINI_API_KEY environment variable.")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(GEMINI_MODEL)
    
    def summarize_emails(self, messages: List[Dict[str, Any]]) -> str:
        if not messages:
            return "No messages to summarize."
        
        email_text = self._format_messages_for_summary(messages)
        
        prompt = f"""
        Create a clear, readable summary of these emails for the user. Include all important information from the actual email content.

        {email_text}

        Write a natural summary that captures everything important from each email. Include all specific details like amounts, dates, account information, transaction details, deadlines, offers, etc. 

        Make it easy to read and understand. Focus on what the user needs to know from each email.

        Only use information that is actually in the email content.
        """
        
        try:
            print(f"[summarize_emails], Request model: {GEMINI_MODEL}")
            print("Request prompt:", prompt[:300] + "..." if len(prompt) > 300 else prompt)
            
            response = self.model.generate_content(prompt)
            print("[summarize_emails], Response raw: ", response.text)
            
            return response.text
        except Exception as e:
            print(f"ERROR GEMINI API: {str(e)}")
            return f"Error generating summary: {str(e)}"
    
    def classify_intent(self, user_input: str) -> Dict[str, Any]:
        prompt = f"""
        Analyze this user request: "{user_input}"

        Extract:
        1. INTENT: READ, SUMMARIZE, MARK_READ, or DRAFT
        2. EMAIL COUNT: How many emails (number or {DEFAULT_EMAIL_LIMIT} if not specified)
        3. DISPLAY FORMAT: FULL or PREVIEW (default: PREVIEW)
        4. GMAIL QUERY: Convert to Gmail search syntax, some query example: in:inbox is:unread, in:important is:read , is:starred , is:important (default: {DEFAULT_QUERY})
        5. NAVIGATION: Simple navigation detection
           - "next" for "next message", "next email"
           - "previous" for "previous message", "prev email"
           - "none" for everything else
        6. TOKEN: Extract pageToken if user provides one
           - Look for "with token", "token:", "page token" followed by alphanumeric string
           - Examples: "next with token abc123", "token: xyz456"
           - If no token found, return null

        Navigation examples:
        - "read my next message" → navigation: "next", token: null
        - "next with token abc123" → navigation: "next", token: "abc123"
        - "show me previous email" → navigation: "previous", token: null
        - "read my emails" → navigation: "none", token: null

        Respond exactly as a valid JSON object:
        {{
        "intent": "[intent]",
        "limit": [number],
        "display": "[format]",
        "gmail_query": "[gmail search query]",
        "navigation": "[next|previous|none]",
        "token": "[extracted_token_or_null]"
        }}

        """
        
        try:
            print(f"[classify_intent], Request model: {GEMINI_MODEL}, Request user input: '{user_input}'")
            
            response = self.model.generate_content(prompt)
            
            print("[classify_intent], Response raw: ", response.text)
            
            parsed = self._parse_intent_response(response.text)
            print("[classify_intent] Response parsed: ", parsed)
            
            return parsed
        except Exception as e:
            print(f"[classify_intent] ERROR GEMINI API: {str(e)}")
            return {
                "intent": "READ",
                "gmail_query": DEFAULT_QUERY,
                "limit": DEFAULT_EMAIL_LIMIT,
                "display": "PREVIEW",
                "error": str(e)
            }
    
    def generate_draft_reply(self, original_message: Dict[str, Any], user_instruction: str = "") -> str:
        original_subject = original_message.get("subject", "")
        original_body = original_message.get("body", "")
        original_sender = original_message.get("sender", "")
        
        prompt = f"""
        Generate a professional email reply based on:

        Original email:
        From: {original_sender}
        Subject: {original_subject}
        Body: {original_body[:500]}...

        User instruction: {user_instruction or "Generate an appropriate reply"}

        Generate a professional, concise reply. Include only the email body text, no headers.
        """
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error generating reply: {str(e)}"
    
    def _format_messages_for_summary(self, messages: List[Dict[str, Any]]) -> str:
        formatted = []
        for i, msg in enumerate(messages[:10], 1):  # Limit to 10 messages
            sender = msg.get("sender", "Unknown")
            subject = msg.get("subject", "No subject")
            
            # Use full body content for summary, fallback to snippet if body is empty
            body = msg.get("body", "")
            content = body if body and len(body.strip()) > 10 else msg.get("snippet", "")
            
            formatted.append(f"{i}. From: {sender}\n   Subject: {subject}\n   Content: {content}\n")
        
        return "\n".join(formatted)
    
    def _parse_intent_response(self, response_text: str) -> Dict[str, Any]:
        default_result = {
            "intent": "READ",
            "gmail_query": DEFAULT_QUERY,
            "limit": DEFAULT_EMAIL_LIMIT,
            "display": "PREVIEW",
            "navigation": "none",
            "token": None
        }
        
        try:
            # Try to extract JSON from the response
            response_text = response_text.strip()
            
            # Find JSON content between curly braces
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}')
            
            if start_idx != -1 and end_idx != -1:
                json_str = response_text[start_idx:end_idx + 1]
                parsed = json.loads(json_str)
                
                # Validate and clean the parsed result
                result = default_result.copy()
                
                if "intent" in parsed and parsed["intent"] in ["READ", "SUMMARIZE", "MARK_READ", "DRAFT"]:
                    result["intent"] = parsed["intent"]
                
                if "gmail_query" in parsed and parsed["gmail_query"]:
                    result["gmail_query"] = parsed["gmail_query"]
                
                if "limit" in parsed:
                    if isinstance(parsed["limit"], int):
                        result["limit"] = parsed["limit"]
                    elif isinstance(parsed["limit"], str) and parsed["limit"].isdigit():
                        result["limit"] = int(parsed["limit"])
                
                if "display" in parsed and parsed["display"] in ["FULL", "PREVIEW"]:
                    result["display"] = parsed["display"]
                
                if "navigation" in parsed and parsed["navigation"] in ["next", "previous", "none"]:
                    result["navigation"] = parsed["navigation"]
                
                if "token" in parsed and parsed["token"]:
                    result["token"] = parsed["token"]
                
                return result
                
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"[_parse_intent_response] JSON parsing failed: {e}")
            print(f"[_parse_intent_response] Raw response: {response_text}")
        
        return default_result