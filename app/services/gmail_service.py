from typing import Optional, Any, List, Dict
import base64
import logging
from email.message import EmailMessage
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from app.services.user_config_manager import UserConfigManager

logger = logging.getLogger(__name__)


class GmailService:
    def __init__(self, credentials: Credentials, user_id: str):
        """
        Initialize Gmail service with user credentials and configuration
        
        Args:
            credentials: Google OAuth2 credentials for the user
            user_id: Firebase user ID for configuration management (mandatory)
        """
        self.credentials = credentials
        self.user_id = user_id
        self._service = None
        self.config_manager = UserConfigManager()
    
    def get_service(self):
        if not self._service:
            self._service = build("gmail", "v1", credentials=self.credentials)
        return self._service
    
    
    async def get_message_by_id(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Convenience method for API controllers - get single message by ID
        """
        return await self.get_message_details(message_id)
    
    async def search_message_ids(self, query: str = "is:unread", max_results: int = 10, page_token: str = None) -> Dict[str, Any]:
        """Search for message IDs only (lightweight, no message content)"""
        try:
            logger.info("GMAIL API CALL - List Message IDs Only")
            logger.info(f"Request query: '{query}', max_results: {max_results}")
            
            service = self.get_service()
            request_params = {
                "userId": "me",
                "q": query,
                "maxResults": max_results
            }
            
            if page_token:
                request_params["pageToken"] = page_token
                
            result = service.users().messages().list(**request_params).execute()
            
            messages = result.get("messages", [])
            message_ids = [msg["id"] for msg in messages]
            logger.info(f"GMAIL RESPONSE: Found {len(message_ids)} message IDs")
            
            return {
                "message_ids": message_ids,
                "next_page_token": result.get("nextPageToken"),
                "result_size_estimate": result.get("resultSizeEstimate", len(message_ids))
            }
            
        except HttpError as error:
            logger.error(f"ERROR GMAIL API: {error}")
            return {"message_ids": [], "next_page_token": None, "result_size_estimate": 0}
        except Exception as error:
            logger.error(f"ERROR Unexpected: {error}")
            return {"message_ids": [], "next_page_token": None, "result_size_estimate": 0}
    
    async def get_message_details(self, message_id: str) -> Optional[Dict[str, Any]]:
        try:
            logger.debug(f"GMAIL API CALL - Get Message Details: {message_id}")
            
            service = self.get_service()
            message = service.users().messages().get(
                userId="me",
                id=message_id,
                format="full"
            ).execute()
            
            parsed = self._parse_message(message)
            logger.debug(f"GMAIL RESPONSE: Parsed message - Subject: {parsed.get('subject', 'No subject')[:50]}")
            
            # Check user config and auto-mark as read if enabled
            auto_mark_read = self.config_manager.get_config_value(self.user_id, "auto_mark_as_read", default=True)
            if auto_mark_read and "UNREAD" in parsed.get("labels", []):
                logger.debug(f"Auto-marking message {message_id} as read based on user config")
                await self.mark_as_read([message_id])
                # Remove UNREAD from parsed labels to reflect the change
                if "labels" in parsed:
                    parsed["labels"] = [label for label in parsed["labels"] if label != "UNREAD"]
            
            return parsed
            
        except HttpError as error:
            logger.error(f"ERROR GMAIL API get message: {error}")
            return None
        except Exception as error:
            logger.error(f"ERROR Unexpected get message: {error}")
            return None
    
    async def mark_as_read(self, message_ids: List[str]) -> bool:
        try:
            service = self.get_service()
            
            for msg_id in message_ids:
                service.users().messages().modify(
                    userId="me",
                    id=msg_id,
                    body={"removeLabelIds": ["UNREAD"]}
                ).execute()
            
            return True
            
        except HttpError as error:
            logger.error(f"Error marking messages as read: {error}")
            return False
        except Exception as error:
            logger.error(f"Unexpected error: {error}")
            return False
    
    async def create_draft(self, to: str, subject: str, body: str, thread_id: str = None, 
                          message_id: str = None, references: str = None) -> Optional[str]:
        """Create draft or send message (with optional threading for replies) based on user configuration"""
        try:
            # Create email message - Gmail handles all threading automatically
            message = EmailMessage()
            message.set_content(body)
            message["To"] = to
            message["Subject"] = subject
            
            # Add threading headers if provided (Gmail handles formatting)
            if message_id:
                message["In-Reply-To"] = message_id
            if references:
                message["References"] = references
            
            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            # Check user config for auto-send behavior
            auto_send = self.config_manager.get_config_value(self.user_id, "auto_send_drafts", default=False)
            
            if auto_send:
                # Send the message directly
                logger.info(f"Auto-sending {'reply' if message_id else 'message'} to {to} based on user config")
                return await self._send_encoded_message(encoded_message)
            else:
                # Create as draft
                logger.info(f"Creating {'reply draft' if message_id else 'draft'} for {to} based on user config")
                return await self._create_encoded_draft(encoded_message, thread_id)
            
        except Exception as error:
            logger.error(f"Unexpected error in create_draft: {error}")
            return None
    
    async def _send_encoded_message(self, encoded_message: str) -> Optional[str]:
        """Send an encoded email message"""
        try:
            service = self.get_service()
            
            send_message = {"raw": encoded_message}
            
            sent_message = service.users().messages().send(
                userId="me",
                body=send_message
            ).execute()
            
            logger.info(f"Message sent successfully, message ID: {sent_message.get('id')}")
            return sent_message.get("id")
            
        except HttpError as error:
            logger.error(f"Error sending message: {error}")
            return None
        except Exception as error:
            logger.error(f"Unexpected error sending message: {error}")
            return None
    
    async def _create_encoded_draft(self, encoded_message: str, thread_id: str = None) -> Optional[str]:
        """Create a Gmail draft from encoded message"""
        try:
            service = self.get_service()
            
            create_message = {"message": {"raw": encoded_message}}
            if thread_id:
                create_message["message"]["threadId"] = thread_id
            
            draft = service.users().drafts().create(
                userId="me",
                body=create_message
            ).execute()
            
            return draft.get("id")
            
        except HttpError as error:
            logger.error(f"Error creating draft: {error}")
            return None
        except Exception as error:
            logger.error(f"Unexpected error creating draft: {error}")
            return None
    
    
    def _parse_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        headers = message.get("payload", {}).get("headers", [])
        
        subject = ""
        sender = ""
        reply_to = ""
        date = ""
        message_id = ""
        references = ""
        in_reply_to = ""
        
        for header in headers:
            name = header.get("name", "").lower()
            value = header.get("value", "")
            
            if name == "subject":
                subject = value
            elif name == "from":
                sender = value
            elif name == "reply-to":
                reply_to = value
            elif name == "date":
                date = value
            elif name == "message-id":
                message_id = value
            elif name == "references":
                references = value
            elif name == "in-reply-to":
                in_reply_to = value
        
        body = self._extract_body(message.get("payload", {}))
        
        return {
            "id": message.get("id"),
            "thread_id": message.get("threadId"),
            "subject": subject,
            "sender": sender,
            "reply_to": reply_to,
            "date": date,
            "body": body,
            "snippet": message.get("snippet", ""),
            "labels": message.get("labelIds", []),
            "message_id": message_id,
            "references": references,
            "in_reply_to": in_reply_to
        }
    
    def _extract_body(self, payload: Dict[str, Any]) -> str:
        import re
        
        body = ""
        
        if "parts" in payload:
            for part in payload["parts"]:
                if part.get("mimeType") == "text/plain":
                    data = part.get("body", {}).get("data", "")
                    if data:
                        raw_body = base64.urlsafe_b64decode(data).decode("utf-8")
                        body = self._clean_html_content(raw_body)
                        break
        elif payload.get("mimeType") == "text/plain":
            data = payload.get("body", {}).get("data", "")
            if data:
                raw_body = base64.urlsafe_b64decode(data).decode("utf-8")
                body = self._clean_html_content(raw_body)
        
        return body or payload.get("snippet", "")
    
    def _clean_html_content(self, content: str) -> str:
        import re
        
        # Remove CSS style blocks (both <style> tags and raw CSS)
        content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL)
        
        # Remove raw CSS (anything that looks like CSS rules)
        content = re.sub(r'[^{}]*\{[^{}]*\}', '', content)
        
        # Remove HTML tags but preserve some structure
        content = re.sub(r'<[^>]+>', '\n', content)
        
        # Replace common HTML entities with readable text
        entity_map = {
            '&#8377;': 'Rs. ',  # Rupee symbol
            '&#10004;': '[✓] ',  # Checkmark
            '&#8594;': '-> ',    # Right arrow
            '&nbsp;': ' ',       # Non-breaking space
            '&amp;': '&',        # Ampersand
            '&lt;': '<',         # Less than
            '&gt;': '>',         # Greater than
        }
        
        for entity, replacement in entity_map.items():
            content = content.replace(entity, replacement)
        
        # Remove any remaining HTML entities
        content = re.sub(r'&#\d+;', '', content)
        content = re.sub(r'&[a-zA-Z]+;', '', content)
        
        # Clean up whitespace but preserve some structure
        lines = content.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line:  # Only keep non-empty lines
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)