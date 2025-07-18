import re
from datetime import datetime, timedelta
from typing import Optional
from config.settings import DEFAULT_QUERY


class FilterEngine:
    def __init__(self):
        self.default_query = DEFAULT_QUERY
    
    def natural_language_to_query(self, text: str) -> str:
        if not text:
            return self.default_query
        
        text_lower = text.lower().strip()
        query_parts = []
        
        # Handle basic status filters
        if any(word in text_lower for word in ["unread", "new"]):
            query_parts.append("is:unread")
        elif any(word in text_lower for word in ["read", "old"]):
            query_parts.append("-is:unread")
        
        if any(word in text_lower for word in ["important", "priority"]):
            query_parts.append("is:important")
        
        if any(word in text_lower for word in ["starred", "star", "favorite"]):
            query_parts.append("is:starred")
        
        # Handle sender filters
        from_match = re.search(r'from\s+([^\s,]+)', text_lower)
        if from_match:
            query_parts.append(f"from:{from_match.group(1)}")
        
        # Handle subject filters
        subject_match = re.search(r'about\s+(.+?)(?:\s+from|\s+to|$)', text_lower)
        if subject_match:
            subject = subject_match.group(1).strip()
            query_parts.append(f'subject:"{subject}"')
        
        # Handle time-based filters
        if "today" in text_lower:
            today = datetime.now().strftime("%Y/%m/%d")
            query_parts.append(f"after:{today}")
        elif "yesterday" in text_lower:
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y/%m/%d")
            today = datetime.now().strftime("%Y/%m/%d")
            query_parts.append(f"after:{yesterday}")
            query_parts.append(f"before:{today}")
        elif "this week" in text_lower:
            week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y/%m/%d")
            query_parts.append(f"after:{week_ago}")
        
        # Handle attachment filters
        if "attachment" in text_lower:
            query_parts.append("has:attachment")
        
        # Handle specific labels
        if "inbox" in text_lower:
            query_parts.append("in:inbox")
        elif "sent" in text_lower:
            query_parts.append("in:sent")
        elif "drafts" in text_lower:
            query_parts.append("in:drafts")
        
        # If no specific filters found, default to unread
        if not query_parts:
            query_parts.append(self.default_query)
        
        return " ".join(query_parts)
    
    def get_default_query(self) -> str:
        return self.default_query