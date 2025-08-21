from typing import Dict, Any, List, Optional
import asyncio
import re
import logging
from datetime import datetime, timezone
from ..gmail_client.gmail_service import GmailService
from ..session.session_manager import SessionManager

logger = logging.getLogger(__name__)


class GmailFunctionHandler:
    """Handle function calls from Gemini Live API and execute Gmail operations"""
    
    def __init__(self, gmail_service: GmailService, session_manager: SessionManager, user_id: str):
        self.gmail = gmail_service
        self.session = session_manager
        self.user_id = user_id
    
    async def handle_function_call(self, function_call: Dict[str, Any]) -> Dict[str, Any]:
        """Route function calls to appropriate handlers"""
        function_name = function_call.get("name")
        parameters = function_call.get("parameters", {})
        
        logger.info(f"Executing function: {function_name} with params: {parameters}")
        
        try:
            if function_name == "read_messages":
                return await self.read_messages(**parameters)
            elif function_name == "navigate_messages":
                return await self.navigate_messages(**parameters)
            elif function_name == "summarize_message":
                return await self.summarize_message(**parameters)
            elif function_name == "mark_message":
                return await self.mark_message(**parameters)
            elif function_name == "draft_email":
                return await self.draft_email(**parameters)
            else:
                return {"error": f"Unknown function: {function_name}"}
        
        except Exception as e:
            logger.error(f"Function execution error: {e}")
            return {"error": str(e)}
    
    async def read_messages(self, gmail_query: str = None, filter_type: str = None, 
                          message_index: Optional[int] = None, read_full: bool = False, 
                          max_results: int = 10) -> Dict[str, Any]:
        """
        Read Gmail messages with flexible query support
        
        Args:
            gmail_query: Direct Gmail search query (e.g., "from:john@example.com", "is:important from:boss")
            filter_type: Simple filter fallback ("unread", "important", "starred", "all") 
            message_index: Specific message index to read
            read_full: Whether to read full message content
            max_results: Maximum number of messages to fetch
        """
        logger.debug(f"read_messages called with params: gmail_query={gmail_query}, filter_type={filter_type}, message_index={message_index}, read_full={read_full}, max_results={max_results}")
        
        # Get or initialize session
        session_state = self.session.get_or_init_session(self.user_id)
        
        # Build query - prioritize gmail_query over filter_type
        if gmail_query:
            query = gmail_query
        elif filter_type:
            # Fallback to simple filter mapping
            query_map = {
                "unread": "is:unread",
                "important": "is:important", 
                "starred": "is:starred",
                "all": ""
            }
            query = query_map.get(filter_type, "is:unread")
        else:
            query = "is:unread"  # Default
        
        # Fetch messages using existing GmailService (already handles HTML cleaning, etc.)
        result = self.gmail.search_messages(query=query, max_results=max_results)
        messages = result.get("messages", [])
        next_page_token = result.get("next_page_token")
        
        if not messages:
            self.session.update_session_navigation(
                self.user_id,
                current_filter=filter_type or "custom",
                current_query=query,
                message_queue=[],
                total_messages=0,
                current_index=0
            )
            return {
                "response": f"No messages found for query: {query}",
                "messages_count": 0
            }
        
        # Update session with message queue
        message_ids = [msg["id"] for msg in messages]
        self.session.update_session_navigation(
            self.user_id,
            current_filter=filter_type or "custom",
            current_query=query,
            message_queue=message_ids,
            total_messages=len(messages),
            current_index=0,
            next_page_token=next_page_token
        )
        
        # Determine which message to read
        if message_index is not None and 0 <= message_index < len(messages):
            target_message = messages[message_index]
            self.session.update_session_navigation(self.user_id, current_index=message_index)
        else:
            # Read first message by default (as per PRD requirements)
            target_message = messages[0]
            self.session.update_session_navigation(self.user_id, current_index=0)
        
        # Format message for voice (content is already cleaned by GmailService)
        formatted_message = self.format_message_for_voice(target_message, read_full)
        
        # Update session with current message
        self.session.update_session_navigation(
            self.user_id,
            current_message_id=target_message["id"]
        )
        
        return {
            "response": formatted_message,
            "messages_count": len(messages),
            "current_index": self.session.get_session_state(self.user_id).get("current_index", 0),
            "has_more": next_page_token is not None,
            "query_used": query
        }
    
    async def navigate_messages(self, direction: str, search_criteria: Optional[Dict] = None) -> Dict[str, Any]:
        """Navigate through messages"""
        logger.debug(f"navigate_messages called with params: direction={direction}, search_criteria={search_criteria}")
        session_state = self.session.get_session_state(self.user_id)
        
        if not session_state or not session_state.get("message_queue"):
            return {"error": "No messages loaded. Please read messages first."}
        
        message_queue = session_state["message_queue"]
        current_index = session_state.get("current_index", 0)
        next_page_token = session_state.get("next_page_token")
        
        if direction == "next":
            if current_index + 1 < len(message_queue):
                # Move to next message in current queue
                new_index = current_index + 1
            elif next_page_token:
                # Fetch next page
                return await self.fetch_next_page()
            else:
                return {"response": "You've reached the last message. No more messages available."}
        
        elif direction == "previous":
            if current_index > 0:
                new_index = current_index - 1
            else:
                return {"response": "You're already at the first message."}
        
        elif direction == "first":
            new_index = 0
        
        elif direction == "last":
            new_index = len(message_queue) - 1
        
        else:
            return {"error": f"Invalid navigation direction: {direction}"}
        
        # Get the message at new index (already cleaned by GmailService)
        message_id = message_queue[new_index]
        message = self.gmail.get_message_by_id(message_id)
        
        if not message:
            return {"error": "Message not found"}
        
        # Update session
        self.session.update_session_navigation(
            self.user_id,
            current_index=new_index,
            current_message_id=message_id
        )
        
        formatted_message = self.format_message_for_voice(message, read_full=False)
        
        return {
            "response": formatted_message,
            "current_index": new_index,
            "total_messages": len(message_queue)
        }
    
    async def fetch_next_page(self) -> Dict[str, Any]:
        """Fetch next page of messages using pagination token"""
        logger.debug(f"fetch_next_page called for user: {self.user_id}")
        session_state = self.session.get_session_state(self.user_id)
        next_page_token = session_state.get("next_page_token")
        current_query = session_state.get("current_query", "is:unread")
        
        if not next_page_token:
            return {"response": "No more messages available."}
        
        # Fetch next page using current query
        result = self.gmail.search_messages(query=current_query, max_results=10, page_token=next_page_token)
        new_messages = result.get("messages", [])
        new_next_token = result.get("next_page_token")
        
        if not new_messages:
            return {"response": "No more messages available."}
        
        # Extend message queue
        current_queue = session_state["message_queue"]
        new_message_ids = [msg["id"] for msg in new_messages]
        extended_queue = current_queue + new_message_ids
        
        # Move to first message of new page
        new_index = len(current_queue)  # Index of first new message
        
        self.session.update_session_navigation(
            self.user_id,
            message_queue=extended_queue,
            current_index=new_index,
            next_page_token=new_next_token,
            current_message_id=new_messages[0]["id"],
            total_messages=len(extended_queue)
        )
        
        formatted_message = self.format_message_for_voice(new_messages[0], read_full=False)
        
        return {
            "response": formatted_message,
            "current_index": new_index,
            "total_messages": len(extended_queue),
            "has_more": new_next_token is not None
        }
    
    async def summarize_message(self, message_index: Optional[int] = None) -> Dict[str, Any]:
        """Summarize current or specified message"""
        logger.debug(f"summarize_message called with params: message_index={message_index}")
        session_state = self.session.get_session_state(self.user_id)
        
        if not session_state or not session_state.get("message_queue"):
            return {"error": "No messages loaded. Please read messages first."}
        
        # Determine which message to summarize
        if message_index is not None:
            if 0 <= message_index < len(session_state["message_queue"]):
                message_id = session_state["message_queue"][message_index]
            else:
                return {"error": f"Invalid message index: {message_index}"}
        else:
            message_id = session_state.get("current_message_id")
            if not message_id:
                return {"error": "No current message to summarize"}
        
        # Get message details (already cleaned by GmailService)
        message = self.gmail.get_message_by_id(message_id)
        if not message:
            return {"error": "Message not found"}
        
        # Create summary
        summary = self.create_message_summary(message)
        
        return {
            "response": f"Message summary: {summary}",
            "message_subject": message.get("subject", "No subject"),
            "message_sender": message.get("sender", "Unknown sender")
        }
    
    async def mark_message(self, action: str, message_index: Optional[int] = None) -> Dict[str, Any]:
        """Mark message with specified action"""
        logger.debug(f"mark_message called with params: action={action}, message_index={message_index}")
        session_state = self.session.get_session_state(self.user_id)
        
        if not session_state or not session_state.get("message_queue"):
            return {"error": "No messages loaded. Please read messages first."}
        
        # Determine which message to mark
        if message_index is not None:
            if 0 <= message_index < len(session_state["message_queue"]):
                message_id = session_state["message_queue"][message_index]
            else:
                return {"error": f"Invalid message index: {message_index}"}
        else:
            message_id = session_state.get("current_message_id")
            if not message_id:
                return {"error": "No current message to mark"}
        
        # Execute action
        success = False
        action_msg = ""
        
        if action == "read":
            success = self.gmail.mark_as_read([message_id])
            action_msg = "marked as read"
        elif action == "unread":
            # TODO: Implement mark as unread in gmail_service
            action_msg = "mark as unread not implemented yet"
        elif action in ["star", "unstar", "archive", "delete"]:
            action_msg = f"{action} not implemented yet"
        else:
            return {"error": f"Invalid action: {action}"}
        
        if success:
            return {"response": f"Message {action_msg} successfully."}
        else:
            return {"error": f"Failed to {action} message."}
    
    async def draft_email(self, action: str, **kwargs) -> Dict[str, Any]:
        """Handle email draft operations"""
        logger.debug(f"draft_email called with params: action={action}, kwargs={kwargs}")
        
        if action == "create":
            recipient = kwargs.get("recipient")
            subject = kwargs.get("subject") 
            content = kwargs.get("content")
            
            if not all([recipient, subject, content]):
                return {"error": "Recipient, subject, and content are required for creating draft"}
            
            # Store draft in Redis temporarily
            draft_data = {
                "recipient": recipient,
                "subject": subject,
                "content": content,
                "status": "editing"
            }
            
            success = self.session.store_draft(self.user_id, draft_data)
            if success:
                return {"response": f"Draft created. To: {recipient}, Subject: {subject}. Say 'send the draft' when ready."}
            else:
                return {"error": "Failed to create draft"}
        
        elif action == "send":
            draft = self.session.get_draft(self.user_id)
            if not draft:
                return {"error": "No draft found to send"}
            
            # Create and send draft via Gmail
            draft_id = self.gmail.create_draft(
                to=draft["recipient"],
                subject=draft["subject"],
                body=draft["content"]
            )
            
            if draft_id:
                # success = self.gmail.send_draft(draft_id)  # don't send in actual
                # if success:
                #     self.session.clear_draft(self.user_id)
                #     return {"response": "Email sent successfully!"}
                # else:
                #     return {"error": "Failed to send email"}
                return {"response": "Draft created successfully, please review from gmail!"}
            else:
                return {"error": "Failed to create draft for sending"}
        
        elif action == "cancel":
            self.session.clear_draft(self.user_id)
            return {"response": "Draft cancelled and removed."}
        
        else:
            return {"error": f"Invalid draft action: {action}"}
    
    def format_message_for_voice(self, message: Dict[str, Any], read_full: bool = False) -> str:
        """
        Format message content for natural voice delivery.
        Note: Content is already cleaned of HTML/CSS by GmailService._clean_html_content()
        This function focuses on voice-specific formatting.
        """
        logger.debug(f"format_message_for_voice called with params: message_id={message.get('id', 'unknown')}, subject={message.get('subject', 'No subject')[:50]}, read_full={read_full}")
        sender = message.get("sender", "Unknown sender")
        subject = message.get("subject", "No subject")
        date = message.get("date", "Unknown date") 
        snippet = message.get("snippet", "")
        body = message.get("body", snippet)  # Body is already cleaned by GmailService
        
        # Extract clean sender name (remove email address part)
        sender_name = self.extract_sender_name(sender)
        
        # Convert timestamp to natural language for voice
        natural_date = self.format_date_for_voice(date)
        
        # Format content based on read_full preference
        if read_full and body and len(body.strip()) > 0:
            # For full reading, break long content into voice-friendly chunks
            formatted_body = self.format_content_for_voice(body)
            return f"Message from {sender_name}, received {natural_date}, subject: {subject}. {formatted_body}"
        else:
            # For preview, use snippet or first part of body
            preview_text = snippet if snippet else (body[:150] + "..." if len(body) > 150 else body)
            preview_text = self.format_content_for_voice(preview_text)
            return f"Message from {sender_name}, subject: {subject}. {preview_text}. Say 'read full message' for complete content."
    
    def extract_sender_name(self, sender: str) -> str:
        """Extract clean sender name from email field"""
        logger.debug(f"extract_sender_name called with params: sender={sender}")
        if not sender or sender == "Unknown sender":
            return "Unknown sender"
        
        # Handle format: "Name <email@example.com>"
        if "<" in sender and ">" in sender:
            name_part = sender.split("<")[0].strip()
            if name_part:  # If name part exists and not empty
                # Remove quotes if present
                name_part = name_part.strip('"\'')
                return name_part if name_part else "Unknown sender"
            else:
                # No name, extract email
                email_part = sender.split("<")[1].split(">")[0]
                return email_part.split("@")[0] if "@" in email_part else email_part
        
        # Handle format: just "email@example.com"
        elif "@" in sender:
            return sender.split("@")[0]
        
        # Handle plain name or other format
        else:
            return sender.strip()
    
    def format_date_for_voice(self, date_str: str) -> str:
        """Convert email date to natural voice format"""
        logger.debug(f"format_date_for_voice called with params: date_str={date_str}")
        if not date_str or date_str == "Unknown date":
            return "unknown date"
        
        try:
            # Try to parse common email date formats
            # Gmail typically returns RFC 2822 format like "Mon, 18 Dec 2023 10:30:00 +0000"
            import email.utils
            parsed_time = email.utils.parsedate_to_datetime(date_str)
            
            if not parsed_time:
                return "unknown date"
            
            now = datetime.now(timezone.utc)
            parsed_utc = parsed_time.replace(tzinfo=timezone.utc) if parsed_time.tzinfo is None else parsed_time
            diff = now - parsed_utc
            
            if diff.days == 0:
                if diff.seconds < 3600:  # Less than 1 hour
                    minutes = max(1, diff.seconds // 60)  # At least 1 minute
                    return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
                else:  # Less than 24 hours
                    hours = diff.seconds // 3600
                    return f"{hours} hour{'s' if hours > 1 else ''} ago"
            elif diff.days == 1:
                return "yesterday"
            elif diff.days < 7:
                return f"{diff.days} days ago"
            elif diff.days < 30:
                weeks = diff.days // 7
                return f"{weeks} week{'s' if weeks > 1 else ''} ago"
            else:
                # For older emails, use readable date
                return parsed_time.strftime("%B %d, %Y")
        except Exception as e:
            logger.warning(f"Date parsing error: {e}")
            # If parsing fails, try simple fallback
            try:
                # Try to extract just the readable part
                if "," in date_str:
                    return date_str.split(",")[1].strip().split(" ")[0:3]  # Month day year
                else:
                    return date_str.split()[0:3] if " " in date_str else date_str
            except:
                return "unknown date"
    
    def format_content_for_voice(self, content: str) -> str:
        """
        Format text content for natural voice delivery.
        Content is already HTML-cleaned by GmailService.
        """
        logger.debug(f"format_content_for_voice called with content length: {len(content) if content else 0}")
        if not content:
            return ""
        
        # Start with the already-cleaned content
        formatted = content.strip()
        
        # Replace multiple newlines and whitespace with single spaces
        formatted = re.sub(r'\n\s*\n', '. ', formatted)  # Double newlines become periods
        formatted = re.sub(r'\n', ' ', formatted)         # Single newlines become spaces
        formatted = re.sub(r'\s+', ' ', formatted)        # Multiple spaces become single space
        
        # Ensure proper punctuation spacing (fix the issue you found)
        formatted = re.sub(r'([.!?])\s*', r'\1 ', formatted)  # Punctuation + single space
        formatted = re.sub(r'([.!?])\s+', r'\1 ', formatted)  # Remove multiple spaces after punctuation
        
        # Handle common email patterns for voice
        formatted = re.sub(r'\b([A-Z]{3,})\b', lambda m: m.group(1).lower(), formatted)  # Convert ACRONYMS to lowercase
        
        # Handle special characters and symbols for voice
        replacements = {
            '&': ' and ',
            '@': ' at ',
            '#': ' hashtag ',
            '$': ' dollar ',
            '%': ' percent ',
            '+': ' plus ',
            '=': ' equals ',
            '<': ' less than ',
            '>': ' greater than ',
            '|': ' or ',
            '~': ' tilde ',
            '^': ' caret ',
            '_': ' underscore ',
            '--': ' dash ',
            '...': '... '  # Ensure space after ellipsis
        }
        
        for symbol, replacement in replacements.items():
            formatted = formatted.replace(symbol, replacement)
        
        # Clean up any double spaces created by replacements
        formatted = re.sub(r'\s+', ' ', formatted)
        
        # Handle long content by chunking at sentence boundaries
        if len(formatted) > 800:  # Reasonable length for voice
            # Try to break at sentence boundaries
            sentences = re.split(r'([.!?])\s+', formatted)
            
            # Reconstruct sentences with punctuation
            reconstructed = []
            for i in range(0, len(sentences) - 1, 2):
                if i + 1 < len(sentences):
                    sentence = sentences[i] + sentences[i + 1]
                    reconstructed.append(sentence)
            
            # Take first few sentences that fit within limit
            truncated = ""
            for sentence in reconstructed:
                if len(truncated + sentence) > 800:
                    break
                truncated += sentence + " "
            
            if len(truncated.strip()) < len(formatted):
                truncated = truncated.strip() + " ... The message continues. Say 'continue reading' for more."
            
            formatted = truncated
        
        # Final cleanup
        formatted = formatted.strip()
        
        # Ensure it ends with proper punctuation for voice
        if formatted and not formatted[-1] in '.!?':
            formatted += '.'
        
        return formatted
    
    def create_message_summary(self, message: Dict[str, Any]) -> str:
        """Create a simple summary of the message"""
        logger.debug(f"create_message_summary called with params: message_id={message.get('id', 'unknown')}, subject={message.get('subject', 'No subject')[:50]}")
        subject = message.get("subject", "No subject")
        sender = message.get("sender", "Unknown")
        body = message.get("body", message.get("snippet", ""))  # Body already cleaned by GmailService
        
        # Extract sender name
        sender_name = self.extract_sender_name(sender)
        
        # Simple summary logic
        word_count = len(body.split()) if body else 0
        
        summary = f"Email from {sender_name} about '{subject}'. Message contains approximately {word_count} words."
        
        # Add key information if body is available
        if body:
            # Look for action items or important keywords
            important_words = [
                "urgent", "asap", "deadline", "meeting", "call", 
                "response required", "action required", "important",
                "follow up", "reminder", "due", "schedule"
            ]
            
            body_lower = body.lower()
            found_keywords = [word for word in important_words if word in body_lower]
            
            if found_keywords:
                # Limit to top 3 keywords to avoid long lists
                top_keywords = found_keywords[:3]
                summary += f" Contains important keywords: {', '.join(top_keywords)}."
            
            # Check for questions (might need response)
            question_count = body.count('?')
            if question_count > 0:
                summary += f" Contains {question_count} question{'s' if question_count > 1 else ''}."
        
        return summary