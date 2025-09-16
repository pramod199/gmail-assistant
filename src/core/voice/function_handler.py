from typing import Dict, Any, List, Optional
import asyncio
import re
import logging
import email.utils
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
    
    async def read_messages(self, gmail_query: str = None, message_index: Optional[int] = None, 
                          read_full: bool = False, max_results: int = 10, page_token: str = None) -> Dict[str, Any]:
        """
        Read Gmail messages with flexible query support and pagination
        
        Args:
            gmail_query: Gmail search query (e.g., "from:john@example.com", "is:important from:boss"). Defaults to "is:unread"
            message_index: Specific message index to read (ignored if page_token provided)
            read_full: Whether to read full message content
            max_results: Maximum number of messages to fetch
            page_token: If provided, extend current session with next page of results
        """
        logger.debug(f"read_messages called with params: gmail_query={gmail_query}, message_index={message_index}, read_full={read_full}, max_results={max_results}, page_token={page_token}")
        
        # Get or initialize session
        session_state = self.session.get_or_init_session(self.user_id)
        
        # Determine query and current queue
        if page_token:
            # Pagination mode - use stored query and extend current queue
            query = session_state.get("current_query", "is:unread")
            current_queue = session_state.get("message_queue", [])
        else:
            # Fresh session mode - use provided or default query
            query = gmail_query or "is:unread"
            current_queue = []
        
        # Fetch message IDs
        result = await self.gmail.search_message_ids(query=query, max_results=max_results, page_token=page_token)
        new_message_ids = result.get("message_ids", [])
        next_page_token = result.get("next_page_token")
        
        # Handle no messages found
        if not new_message_ids:
            response = "No more messages available." if page_token else f"No messages found for query: {query}"
            if not page_token:
                # Update session only for fresh queries
                self.session.update_session_navigation(
                    self.user_id,
                    current_query=query,
                    message_queue=[],
                    total_messages=0,
                    current_index=0
                )
            return {
                "response": response,
                "messages_count": len(current_queue) if page_token else 0
            }
        
        # Build final message queue
        extended_queue = current_queue + new_message_ids
        
        # Determine target message index
        if page_token:
            # For pagination, read first message of new page
            target_index = len(current_queue)
        else:
            # For fresh session, use provided index or default to 0
            target_index = message_index if message_index is not None and 0 <= message_index < len(new_message_ids) else 0
        
        target_message_id = extended_queue[target_index]
        
        # Fetch full content only for the target message
        target_message = await self.gmail.get_message_by_id(target_message_id)
        if not target_message:
            return {"error": "Failed to fetch target message"}
        
        # Cache current message in Redis (1 hour TTL)
        self.session.store_current_message(self.user_id, target_message, ttl=3600)
        
        # Update session with navigation data
        self.session.update_session_navigation(
            self.user_id,
            current_query=query,
            message_queue=extended_queue,
            total_messages=len(extended_queue),
            current_index=target_index,
            current_message_id=target_message_id,
            next_page_token=next_page_token
        )
        
        # Format message for voice (content is already cleaned by GmailService)
        formatted_message = self.format_message_for_voice(target_message, read_full)
        
        return {
            "response": formatted_message,
            "messages_count": len(extended_queue),
            "current_index": target_index,
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
                # Fetch next page using read_messages with pagination
                return await self.read_messages(page_token=next_page_token)
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
        
        # Get the message at new index (direct fetch since it's a new message)
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
        
        # Cache the new current message
        self.session.store_current_message(self.user_id, message, ttl=3600)
        
        formatted_message = self.format_message_for_voice(message, read_full=False)
        
        return {
            "response": formatted_message,
            "current_index": new_index,
            "total_messages": len(message_queue)
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
        
        # Get message with caching support
        message = await self._get_message_with_cache(message_id)
        if not message:
            return {"error": "Message not found"}
        
        # Return message content for Gemini Live AI to summarize naturally
        return {
            "message_content": {
                "subject": message.get("subject", "No subject"),
                "sender": message.get("sender", "Unknown sender"),
                "date": message.get("date", "Unknown date"),
                "body": message.get("body", message.get("snippet", ""))
            },
            "response": f"Here's the message to summarize: From {message.get('sender', 'Unknown')}, Subject: {message.get('subject', 'No subject')}, Content: {message.get('body', message.get('snippet', ''))}"
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
            # Don't clear draft when user says "no" - just acknowledge and wait for next action
            draft = self.session.get_draft(self.user_id)
            if draft:
                return {"response": "Draft kept. You can edit it or send it later."}
            else:
                return {"response": "Okay."}
        
        else:
            return {"error": f"Invalid draft action: {action}"}

    async def _create_reply_draft(self, content: str) -> Dict[str, Any]:
        """Helper to create a reply draft"""
        session_state = await self._ensure_session_initialized()
        if not session_state or not session_state.get("current_message_id"):
            return {"error": "Cannot create reply - no current message context"}
        
        current_message_id = session_state["current_message_id"]
        current_message = await self._get_message_with_cache(current_message_id)
        
        if not current_message:
            return {"error": "Cannot create reply - unable to access current message"}
        
        # Use Reply-To if present, otherwise use From (RFC 2822) - Gmail handles email parsing
        reply_to_header = current_message.get("reply_to", "").strip()
        sender_header = current_message.get("sender", "")
        final_recipient = reply_to_header if reply_to_header else sender_header
        
        if not final_recipient:
            return {"error": "Cannot create reply - no recipient information in current message"}
        
        # Format reply body with quoted original message
        formatted_content = self._format_reply_body(content, current_message)
        
        # Store reply draft in Redis with complete threading info (no need to re-fetch)
        draft_data = {
            "recipient": final_recipient,
            "subject": current_message.get("subject", ""),  # Original subject, gmail_service will add "Re: "
            "content": formatted_content,  # Already formatted with quoted original
            "is_reply": True,
            "status": "editing",
            # Threading information for gmail_service
            "thread_id": current_message.get("thread_id"),
            "message_id": current_message.get("message_id", ""),
            "references": current_message.get("references", "")
        }
        
        success = self.session.store_draft(self.user_id, draft_data)
        if success:
            return {"response": f"Reply draft created. To: {draft_data['recipient']}, Subject: {draft_data['subject']}. Say 'send the draft' when ready."}
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
        
        # Use unified create_draft method for both regular and reply drafts
        is_reply = draft.get("is_reply", False)
        
        if is_reply:
            # Use threading information stored in Redis (no need to re-fetch message)
            draft_id = await self.gmail.create_draft(
                to=draft["recipient"],
                subject=draft["subject"],
                body=draft["content"],
                thread_id=draft.get("thread_id"),
                message_id=draft.get("message_id"),
                references=draft.get("references")
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

    def _format_reply_body(self, reply_content: str, original_message: Dict[str, Any]) -> str:
        """Format reply body with quoted original message"""
        sender = original_message.get("sender", "Unknown sender")
        date = original_message.get("date", "Unknown date")
        original_body = original_message.get("body", "")
        
        # Fallback to snippet if body is empty
        if not original_body or original_body.strip() == "":
            original_body = original_message.get("snippet", "")
            logger.info(f"Message body was empty, using snippet as fallback")
        
        # Format date to local timezone like Gmail UI
        formatted_date = self._format_date_for_reply(date)
        
        # Format original message with > prefix on each line
        quoted_body = ""
        if original_body:
            quoted_lines = original_body.split('\n')
            quoted_body = '\n'.join(f"> {line}" for line in quoted_lines)
        
        # Standard Gmail reply format with full sender info
        reply_body = f"{reply_content}\n\nOn {formatted_date}, {sender} wrote:\n{quoted_body}"
        
        return reply_body

    def _format_date_for_reply(self, date_str: str) -> str:
        """Format email date like Gmail: convert UTC to local timezone"""
        if not date_str or date_str == "Unknown date":
            return "unknown date"
        
        try:
            # Parse the RFC 2822 date (handles timezone info)
            parsed_time = email.utils.parsedate_to_datetime(date_str)
            if not parsed_time:
                return date_str
            
            # Convert to local timezone (system timezone)
            local_time = parsed_time.astimezone()
            
            # Format like Gmail: "Mon, Sep 16, 2025 at 5:53 PM" 
            # Use %d and %I instead of %-d and %-I for better compatibility
            day = local_time.day  # Remove leading zero manually
            hour = local_time.hour % 12
            if hour == 0:
                hour = 12
            
            formatted = f"{local_time.strftime('%a, %b')} {day}, {local_time.year} at {hour}:{local_time.strftime('%M %p')}"
            return formatted
            
        except Exception as e:
            logger.warning(f"Date formatting error: {e}, using fallback")
            # Fallback to original if parsing fails
            return date_str
    
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
        
        # Convert timestamp to natural language for voice
        natural_date = self.format_date_for_voice(date)
        
        # Format content based on read_full preference
        if read_full and body and len(body.strip()) > 0:
            # For full reading, break long content into voice-friendly chunks
            formatted_body = self.format_content_for_voice(body)
            return f"Message from {sender}, received {natural_date}, subject: {subject}. {formatted_body}"
        else:
            # For preview, use snippet or first part of body
            preview_text = snippet if snippet else (body[:150] + "..." if len(body) > 150 else body)
            preview_text = self.format_content_for_voice(preview_text)
            return f"Message from {sender}, subject: {subject}. {preview_text}. Say 'read full message' for complete content."
    
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

    async def _get_message_with_cache(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Get message from cache if available, otherwise fetch from Gmail API and cache it"""
        # Check if this is the current cached message
        session_state = self.session.get_session_state(self.user_id)
        current_message_id = session_state.get("current_message_id") if session_state else None
        
        if message_id == current_message_id:
            # Try to get from cache first
            cached_message = self.session.get_current_message(self.user_id)
            if cached_message:
                logger.debug(f"Message {message_id} retrieved from cache")
                return cached_message
        
        # Cache miss or different message - fetch from Gmail API
        logger.debug(f"Fetching message {message_id} from Gmail API")
        message = await self.gmail.get_message_by_id(message_id)
        
        if message and message_id == current_message_id:
            # Cache only if this is the current message (avoid overwriting cache with wrong message)
            self.session.store_current_message(self.user_id, message, ttl=3600)
            logger.debug(f"Message {message_id} cached for 1 hour")
        
        return message

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
    