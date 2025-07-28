from typing import Dict, Any, List, Optional
from ..core.llm.gemini_client import GeminiClient
from ..core.filters.filter_engine import FilterEngine
from ..core.gmail_client.gmail_service import GmailService
from ..core.navigation.navigation_manager import NavigationManager
from config.settings import DEFAULT_EMAIL_LIMIT, MAX_EMAIL_LIMIT


class NLPProcessor:
    def __init__(self, gmail_service: GmailService, gemini_client: GeminiClient):
        self.gmail_service = gmail_service
        self.gemini_client = gemini_client
        self.filter_engine = FilterEngine()
        self.navigation_managers = {}  # user_id -> NavigationManager
    
    def get_navigation_manager(self, user_id: str = "default") -> NavigationManager:
        """Get or create NavigationManager for specific user"""
        if user_id not in self.navigation_managers:
            self.navigation_managers[user_id] = NavigationManager(user_id=user_id)
        return self.navigation_managers[user_id]
    
    def process_user_request(self, user_input: str, user_id: str = "default") -> Dict[str, Any]:
        print("Analyzing request with Gemini...")
        intent_data = self.gemini_client.classify_intent(user_input)
        print(f"Intent data from gemini: {intent_data}")
        
        intent = intent_data.get("intent", "READ")
        
        if intent == "READ":
            return self._handle_read_request(intent_data, user_id)
        elif intent == "SUMMARIZE":
            return self._handle_summarize_request(user_input, intent_data, user_id)
        elif intent == "MARK_READ":
            return self._handle_mark_read_request(user_input, intent_data, user_id)
        elif intent == "DRAFT":
            return self._handle_draft_request(user_input, intent_data, user_id)
        else:
            print("intent is not clear so falling back to default read intent")
            return self._handle_read_request(intent_data, user_id)  # Default fallback
    
    def _handle_read_request(self, intent_data: Dict[str, Any], user_id: str = "default") -> Dict[str, Any]:
        query = intent_data.get("gmail_query", "is:unread")
        limit = intent_data.get("limit", DEFAULT_EMAIL_LIMIT)
        display_format = intent_data.get("display", "PREVIEW")
        navigation = intent_data.get("navigation", "none")
        
        navigation_manager = self.get_navigation_manager(user_id)
        print(f"[DEBUG] User {user_id} - Navigation command: '{navigation}', Navigation state: {navigation_manager.get_navigation_info()}")
        
        # Handle navigation commands
        if navigation == "next":
            page_token = navigation_manager.navigate_next()
            if page_token is None:
                return {
                    "action": "read",
                    "messages": [],
                    "count": 0,
                    "response": "No next page available. Please start a new search first."
                }
        elif navigation == "previous":
            page_token = navigation_manager.navigate_previous()
            print(f"[DEBUG] User {user_id} - Previous navigation returned token: {page_token}")
            if page_token is None:
                return {
                    "action": "read",
                    "messages": [],
                    "count": 0,
                    "response": "Already at the first page."
                }
        else:
            # Check if this is actually a new search (different query) or just a parsing issue
            current_state = navigation_manager._get_state()
            current_query = current_state.get('current_query', '')
            if query != current_query:
                # Truly new search - reset navigation
                navigation_manager.start_new_search(query, limit)
                page_token = None
            else:
                # Same query, might be navigation that wasn't parsed correctly
                # Keep existing navigation state and use current page token
                page_token = navigation_manager.get_current_page_token()
        
        print(f"Searching Gmail with query: '{query}', limit: {limit}, token: {page_token}")
        result = self.gmail_service.search_messages(query, limit, page_token)
        messages = result["messages"]
        print(f"Found {len(messages)} messages")
        
        if not messages:
            return {
                "action": "read",
                "messages": [],
                "count": 0,
                "response": "No messages found."
            }
        
        # Get next page token and store it for future navigation
        next_page_token = result.get("next_page_token")
        # Only update the next token after navigation or new searches
        navigation_manager.set_next_page_token(next_page_token)
        
        response_text = self._format_messages_response(messages, display_format)
        
        # Add navigation commands
        navigation_commands = navigation_manager.get_navigation_commands()
        if navigation_commands:
            response_text += f"\n\n📄 Navigation: {' | '.join(navigation_commands)}"
        
        return {
            "action": "read",
            "messages": messages,
            "count": len(messages),
            "query_used": query,
            "display_format": display_format,
            "navigation": navigation,
            "next_page_token": next_page_token,
            "response": response_text
        }
    
    def _handle_summarize_request(self, user_input: str, intent_data: Dict[str, Any], user_id: str = "default") -> Dict[str, Any]:
        query = intent_data.get("gmail_query", "is:unread")
        limit = intent_data.get("limit", DEFAULT_EMAIL_LIMIT)
        
        print(f"Searching Gmail for summary with query: '{query}', limit: {limit}")
        result = self.gmail_service.search_messages(query, limit)
        messages = result["messages"]
        print(f"Found {len(messages)} messages, generating summary...")
        summary = self.gemini_client.summarize_emails(messages)
        
        return {
            "action": "summarize",
            "messages": messages,
            "count": len(messages),
            "summary": summary,
            "query_used": query,
            "response": f"Summary of {len(messages)} messages:\n\n{summary}"
        }
    
    def _handle_mark_read_request(self, user_input: str, intent_data: Dict[str, Any], user_id: str = "default") -> Dict[str, Any]:
        query = self.filter_engine.natural_language_to_query(user_input)
        limit = self._extract_limit(intent_data)
        
        result = self.gmail_service.search_messages(query, limit)
        messages = result["messages"]
        message_ids = [msg["id"] for msg in messages]
        
        if message_ids:
            success = self.gmail_service.mark_as_read(message_ids)
            if success:
                response = f"Marked {len(message_ids)} messages as read."
            else:
                response = "Failed to mark messages as read."
        else:
            response = "No messages found to mark as read."
        
        return {
            "action": "mark_read",
            "messages": messages,
            "count": len(messages),
            "success": success if message_ids else False,
            "response": response
        }
    
    def _handle_draft_request(self, user_input: str, intent_data: Dict[str, Any], user_id: str = "default") -> Dict[str, Any]:
        # For now, assume user wants to reply to the latest unread message
        result = self.gmail_service.search_messages("is:unread", 1)
        messages = result["messages"]
        
        if not messages:
            return {
                "action": "draft",
                "success": False,
                "response": "No messages found to reply to."
            }
        
        original_message = messages[0]
        draft_content = self.gemini_client.generate_draft_reply(original_message, user_input)
        
        # Extract recipient from original sender
        original_sender = original_message.get("sender", "")
        recipient_email = self._extract_email_from_sender(original_sender)
        
        if recipient_email:
            subject = f"Re: {original_message.get('subject', '')}"
            draft_id = self.gmail_service.create_draft(recipient_email, subject, draft_content)
            
            if draft_id:
                response = f"Draft created successfully. Draft ID: {draft_id}"
                success = True
            else:
                response = "Failed to create draft."
                success = False
        else:
            response = "Could not determine recipient email address."
            success = False
        
        return {
            "action": "draft",
            "original_message": original_message,
            "draft_content": draft_content,
            "success": success,
            "response": response
        }
    
    def _extract_limit(self, intent_data: Dict[str, Any]) -> int:
        limit = intent_data.get("limit", "default")
        if isinstance(limit, int):
            return min(limit, MAX_EMAIL_LIMIT)  # Cap for performance
        return DEFAULT_EMAIL_LIMIT
    
    
    def _format_messages_response(self, messages: List[Dict[str, Any]], display_format: str = "PREVIEW") -> str:
        if not messages:
            return "No messages found."
        
        response_lines = [f"Found {len(messages)} messages:\n"]
        
        for i, msg in enumerate(messages, 1):
            # print(f"{i}th full message before format: {msg}")
            sender = msg.get("sender", "Unknown")
            subject = msg.get("subject", "No subject")
            date = msg.get("date", "Unknown date")
            
            response_lines.append(f"{i}. From: {sender}")
            response_lines.append(f"   Subject: {subject}")
            response_lines.append(f"   Date: {date}")
            
            if display_format == "FULL":
                # Show complete email content
                body = msg.get("body", "No content")
                response_lines.append(f"   Content:\n{body}")
            else:
                # Show preview/snippet
                snippet = msg.get("snippet", "")[:100]
                response_lines.append(f"   Preview: {snippet}...")
            
            response_lines.append("")
        
        return "\n".join(response_lines)
    
    def _extract_email_from_sender(self, sender: str) -> Optional[str]:
        import re
        email_match = re.search(r'<([^>]+)>', sender)
        if email_match:
            return email_match.group(1)
        
        # Simple email pattern
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', sender)
        if email_match:
            return email_match.group(0)
        
        return None