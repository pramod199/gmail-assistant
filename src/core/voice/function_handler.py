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
    
    async def _ensure_session_initialized(self) -> Optional[Dict[str, Any]]:
        """Ensure user has an initialized session with message queue, create one if needed"""
        session_state = self.session.get_session_state(self.user_id)
        
        if not session_state or not session_state.get("message_queue"):
            logger.info(f"No session found for user {self.user_id}, initializing with read_messages")
            await self.read_messages()  # This will create the session
            session_state = self.session.get_session_state(self.user_id)
            
            if not session_state or not session_state.get("message_queue"):
                return None
        
        return session_state
    
    def _extract_email_from_sender(self, sender_string: str) -> str:
        """Extract actual email address from sender field"""
        import re
        if not sender_string:
            return ""
        
        # Handle format: "Name <email@example.com>"
        email_match = re.search(r'<([^>]+)>', sender_string)
        if email_match:
            return email_match.group(1)
        
        # Handle format: just "email@example.com"
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', sender_string)
        if email_match:
            return email_match.group(0)
        
        return ""  # Return empty if no valid email found
    
    def _cleanup_email(self, email: str) -> str:
        """Clean up email address from voice input issues"""
        if not email:
            return email
            
        # Remove all spaces (common voice parsing issue)
        cleaned = email.replace(" ", "")
        
        # Convert to lowercase (voice often capitalizes incorrectly)
        cleaned = cleaned.lower()
        
        # Only handle space and capitalization issues
        
        return cleaned
    
    def _validate_email(self, email: str) -> bool:
        """Validate email format - requires domain with dot (like Gmail)"""
        import re
        pattern = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
        return bool(re.match(pattern, email))
    
    def _validate_and_cleanup_email(self, raw_email: str) -> tuple[str, bool, str]:
        """
        Validate and cleanup email address, return (cleaned_email, is_valid, error_message)
        """
        if not raw_email:
            return "", False, "Email address is required"
        
        # First cleanup common voice parsing issues
        cleaned_email = self._cleanup_email(raw_email)
        
        # Check if cleaned version is valid
        if self._validate_email(cleaned_email):
            return cleaned_email, True, ""
        
        # If still invalid, provide helpful error message
        if "@" not in cleaned_email:
            return cleaned_email, False, f"Invalid email format: '{raw_email}'. Missing @ symbol. Please say the email address clearly, like 'john dot smith at gmail dot com'"
        elif "." not in cleaned_email.split("@")[1]:
            return cleaned_email, False, f"Invalid email format: '{raw_email}'. Missing domain extension. Please include '.com', '.org', etc."
        else:
            return cleaned_email, False, f"Invalid email format: '{raw_email}'. Please speak the email address clearly and slowly, like 'sarita kumari dot nitap at gmail dot com'"
    
    async def _resolve_reply_recipient(self, recipient_hint: str) -> Optional[str]:
        """Resolve recipient for reply drafts using current message context"""
        session_state = await self._ensure_session_initialized()
        if not session_state or not session_state.get("current_message_id"):
            return None  # No current message context for reply
        
        current_message_id = session_state["current_message_id"]
        message = await self.gmail.get_message_by_id(current_message_id)
        
        if message and message.get("sender"):
            extracted_email = self._extract_email_from_sender(message["sender"])
            if self._validate_email(extracted_email):
                logger.info(f"Resolved reply recipient '{recipient_hint}' to email '{extracted_email}' from current message")
                return extracted_email
        
        return None
    
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
        result = await self.gmail.search_messages(query=query, max_results=max_results)
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
        session_state = await self._ensure_session_initialized()
        if not session_state:
            return {"error": "Failed to initialize message session"}
        
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
        message = await self.gmail.get_message_by_id(message_id)
        
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
        result = await self.gmail.search_messages(query=current_query, max_results=10, page_token=next_page_token)
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
        session_state = await self._ensure_session_initialized()
        if not session_state:
            return {"error": "Failed to initialize message session"}
        
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
        message = await self.gmail.get_message_by_id(message_id)
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
        session_state = await self._ensure_session_initialized()
        if not session_state:
            return {"error": "Failed to initialize message session"}
        
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
            success = await self.gmail.mark_as_read([message_id])
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
    
    async def _create_reply_draft(self, content: str) -> Dict[str, Any]:
        """Helper to create a reply draft"""
        session_state = await self._ensure_session_initialized()
        if not session_state or not session_state.get("current_message_id"):
            return {"error": "Cannot create reply - no current message context"}
        
        current_message_id = session_state["current_message_id"]
        current_message = await self.gmail.get_message_by_id(current_message_id)
        
        if not current_message or not current_message.get("sender"):
            return {"error": "Cannot create reply - unable to access current message"}
        
        # Extract recipient email from current message sender
        final_recipient = self._extract_email_from_sender(current_message["sender"])
        if not self._validate_email(final_recipient):
            return {"error": "Cannot create reply - invalid sender email in current message"}
        
        # Store reply draft in Redis with context info
        reply_subject = current_message.get("subject", "")
        if not reply_subject.lower().startswith("re:"):
            reply_subject = f"Re: {reply_subject}"
        
        draft_data = {
            "recipient": final_recipient,
            "subject": reply_subject,
            "content": content,
            "reply_to": True,
            "original_message_id": current_message_id,
            "status": "editing"
        }
        
        success = self.session.store_draft(self.user_id, draft_data)
        if success:
            return {"response": f"Reply draft created. To: {final_recipient}, Subject: {reply_subject}. Say 'send the draft' when ready."}
        else:
            return {"error": "Failed to create reply draft"}
    
    async def _create_new_draft(self, recipient: str, subject: str, content: str) -> Dict[str, Any]:
        """Helper to create a new draft"""
        # Validate and cleanup email format
        cleaned_recipient, is_valid, error_msg = self._validate_and_cleanup_email(recipient)
        if not is_valid:
            return {"error": error_msg}
        
        # Store draft in Redis temporarily
        draft_data = {
            "recipient": cleaned_recipient,
            "subject": subject,
            "content": content,
            "reply_to": False,
            "status": "editing"
        }
        
        logger.info(f"Attempting to store draft for user {self.user_id}")
        logger.debug(f"Draft data: {draft_data}")
        success = self.session.store_draft(self.user_id, draft_data)
        logger.info(f"Draft storage result: {success}")
        
        if success:
            # Verify draft was actually stored
            stored_draft = self.session.get_draft(self.user_id)
            logger.info(f"Verification - draft retrieved: {stored_draft is not None}")
            if stored_draft:
                logger.debug(f"Stored draft content: recipient={stored_draft.get('recipient')}, subject={stored_draft.get('subject')}")
            return {"response": f"Draft created. To: {cleaned_recipient}, Subject: {subject}. Say 'send the draft' when ready."}
        else:
            logger.error(f"Failed to store draft in Redis for user {self.user_id}")
            return {"error": "Failed to create draft"}
    
    async def _send_draft(self) -> Dict[str, Any]:
        """Helper to send a draft"""
        draft = self.session.get_draft(self.user_id)
        if not draft:
            return {"error": "No draft found to send"}
        
        # Check if this is a reply draft or regular draft
        is_reply = draft.get("reply_to", False)
        
        if is_reply:
            # For reply drafts, get the original message for threading
            original_message_id = draft.get("original_message_id")
            if not original_message_id:
                return {"error": "Cannot send reply - missing original message reference"}
            
            original_message = await self.gmail.get_message_by_id(original_message_id)
            if not original_message:
                return {"error": "Cannot send reply - unable to access original message"}
            
            # Create reply draft with threading
            draft_id = await self.gmail.create_reply_draft(
                original_message, 
                draft["content"], 
                draft["recipient"]
            )
        else:
            # Regular draft
            draft_id = await self.gmail.create_draft(
                to=draft["recipient"],
                subject=draft["subject"],
                body=draft["content"]
            )
        
        if draft_id:
            # Clear the Redis draft since it's now created in Gmail
            self.session.clear_draft(self.user_id)
            return {"response": "Draft created successfully in Gmail, please review and send from Gmail!"}
        else:
            return {"error": "Failed to create draft for sending"}
    
    async def _edit_draft(self, **kwargs) -> Dict[str, Any]:
        """Helper to edit an existing draft"""
        # Get existing draft
        draft = self.session.get_draft(self.user_id)
        if not draft:
            return {"error": "No draft found to edit"}
        
        # Update provided fields, keep existing ones
        recipient = kwargs.get("recipient")
        subject = kwargs.get("subject")
        content = kwargs.get("content")
        
        # Validate and update recipient if provided
        if recipient:
            cleaned_recipient, is_valid, error_msg = self._validate_and_cleanup_email(recipient)
            if not is_valid:
                return {"error": error_msg}
            draft["recipient"] = cleaned_recipient
        
        # Update subject if provided
        if subject:
            draft["subject"] = subject
        
        # Update content if provided
        if content:
            draft["content"] = content
        
        # Store updated draft
        success = self.session.store_draft(self.user_id, draft)
        if success:
            return {"response": f"Draft updated. To: {draft['recipient']}, Subject: {draft['subject']}. Say 'send the draft' when ready."}
        else:
            return {"error": "Failed to update draft"}

    async def draft_email(self, action: str, **kwargs) -> Dict[str, Any]:
        """Handle email draft operations"""
        logger.debug(f"draft_email called with params: action={action}, kwargs={kwargs}")
        
        if action == "create":
            content = kwargs.get("content")
            reply_to = kwargs.get("reply_to", False)
            
            # Content is always required
            if not content:
                return {"error": "Content is required for creating draft"}
            
            if reply_to:
                return await self._create_reply_draft(content)
            else:
                # This is a new draft - validate all required parameters
                recipient = kwargs.get("recipient")
                subject = kwargs.get("subject")
                
                if not all([recipient, subject]):
                    return {"error": "Recipient and subject are required for new drafts"}
                
                return await self._create_new_draft(recipient, subject, content)
        
        elif action == "send":
            return await self._send_draft()
        
        elif action == "edit":
            return await self._edit_draft(**kwargs)
        
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