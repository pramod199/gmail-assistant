from typing import Optional, Any, List, Dict
import base64
from email.message import EmailMessage
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials

from ..auth.gmail_auth import GmailAuth


class GmailService:
    def __init__(self, auth: Optional[GmailAuth] = None):
        self.auth = auth or GmailAuth()
        self._service = None
    
    def get_service(self):
        if not self._service:
            credentials = self.auth.authenticate()
            self._service = build("gmail", "v1", credentials=credentials)
        return self._service
    
    def test_connection(self) -> bool:
        try:
            service = self.get_service()
            service.users().getProfile(userId="me").execute()
            return True
        except HttpError as error:
            print(f"Gmail API connection failed: {error}")
            return False
        except Exception as error:
            print(f"Unexpected error: {error}")
            return False
    
    def search_messages(self, query: str = "is:unread", max_results: int = 10, page_token: str = None) -> Dict[str, Any]:
        try:
            print("GMAIL API CALL - List Messages")
            print(f"Request query: '{query}', max_results: {max_results}")
            
            service = self.get_service()
            request_params = {
                "userId": "me",  # TODO: Replace with actual user_id for multi-user service
                "q": query,
                "maxResults": max_results
            }
            
            if page_token:
                request_params["pageToken"] = page_token
                
            result = service.users().messages().list(**request_params).execute()
            
            messages = result.get("messages", [])
            print(f"GMAIL RESPONSE: Found {len(messages)} message IDs")
            
            detailed_messages = []
            
            for i, msg in enumerate(messages, 1):
                print(f"Fetching message {i}/{len(messages)}: {msg['id']}")
                details = self.get_message_details(msg["id"])
                if details:
                    detailed_messages.append(details)
            
            print(f"Retrieved {len(detailed_messages)} complete messages")
            
            # Return both messages and pagination info
            return {
                "messages": detailed_messages,
                "next_page_token": result.get("nextPageToken"),
                "result_size_estimate": result.get("resultSizeEstimate", len(detailed_messages))
            }
            
        except HttpError as error:
            print(f"ERROR GMAIL API: {error}")
            return {"messages": [], "next_page_token": None, "result_size_estimate": 0}
        except Exception as error:
            print(f"ERROR Unexpected: {error}")
            return {"messages": [], "next_page_token": None, "result_size_estimate": 0}
    
    def get_message_details(self, message_id: str) -> Optional[Dict[str, Any]]:
        try:
            print(f"GMAIL API CALL - Get Message Details: {message_id}")
            
            service = self.get_service()
            message = service.users().messages().get(
                userId="me",
                id=message_id,
                format="full"
            ).execute()
            
            parsed = self._parse_message(message)
            print(f"GMAIL RESPONSE: Parsed message - Subject: {parsed.get('subject', 'No subject')[:50]}")
            
            return parsed
            
        except HttpError as error:
            print(f"ERROR GMAIL API get message: {error}")
            return None
        except Exception as error:
            print(f"ERROR Unexpected get message: {error}")
            return None
    
    def mark_as_read(self, message_ids: List[str]) -> bool:
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
            print(f"Error marking messages as read: {error}")
            return False
        except Exception as error:
            print(f"Unexpected error: {error}")
            return False
    
    def create_draft(self, to: str, subject: str, body: str) -> Optional[str]:
        try:
            service = self.get_service()
            
            message = EmailMessage()
            message.set_content(body)
            message["To"] = to
            message["Subject"] = subject
            
            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            create_message = {"message": {"raw": encoded_message}}
            
            draft = service.users().drafts().create(
                userId="me",
                body=create_message
            ).execute()
            
            return draft.get("id")
            
        except HttpError as error:
            print(f"Error creating draft: {error}")
            return None
        except Exception as error:
            print(f"Unexpected error: {error}")
            return None
    
    def _parse_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        headers = message.get("payload", {}).get("headers", [])
        
        subject = ""
        sender = ""
        date = ""
        
        for header in headers:
            name = header.get("name", "").lower()
            value = header.get("value", "")
            
            if name == "subject":
                subject = value
            elif name == "from":
                sender = value
            elif name == "date":
                date = value
        
        body = self._extract_body(message.get("payload", {}))
        
        return {
            "id": message.get("id"),
            "thread_id": message.get("threadId"),
            "subject": subject,
            "sender": sender,
            "date": date,
            "body": body,
            "snippet": message.get("snippet", ""),
            "labels": message.get("labelIds", [])
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