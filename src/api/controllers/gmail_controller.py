from fastapi import APIRouter, HTTPException, Depends, Query, Request
from pydantic import BaseModel
from typing import Optional, List

from src.api.middleware.auth import get_current_user
from src.core.auth.user_credential_store import UserCredentialStore
from src.core.gmail_client.gmail_service import GmailService
from src.core.llm.gemini_client import GeminiClient
from src.interface.nlp_processor import NLPProcessor


router = APIRouter()

# Initialize services
credential_store = UserCredentialStore()
gemini_client = GeminiClient()


class ProcessRequestModel(BaseModel):
    query: str


class CreateDraftModel(BaseModel):
    to: str
    subject: str
    body: str


class GmailMessage(BaseModel):
    id: str
    subject: str
    sender: str
    date: str
    snippet: str
    is_unread: bool


class ProcessResponse(BaseModel):
    response: str
    action_taken: str
    messages_processed: Optional[int] = None


class DraftResponse(BaseModel):
    id: str
    subject: str
    to: str
    created_date: str
    body: str


class CreateDraftResponse(BaseModel):
    draft_id: str
    message: str


def _get_user_gmail_service(user_id: str) -> GmailService:
    """Get Gmail service for authenticated user"""
    credentials = credential_store.get_credentials(user_id)
    
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Gmail authorization required. Please authorize Gmail access first."
        )
    
    return GmailService(credentials)


@router.post("/process", response_model=ProcessResponse)
async def process_natural_language_request(
    request_data: ProcessRequestModel,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """
    Process natural language request for Gmail operations
    
    Examples:
    - "Show me my unread emails"
    - "Summarize important messages from today"
    - "Mark the last 3 emails as read"
    - "Draft a reply to John's email"
    """
    try:
        user_id = user["user_id"]
        
        # Get user's Gmail service
        gmail_service = _get_user_gmail_service(user_id)
        
        # Create NLP processor for this user
        nlp_processor = NLPProcessor(gmail_service, gemini_client)
        
        # Process the request
        result = nlp_processor.process_user_request(request_data.query, user_id)
        
        return ProcessResponse(
            response=result.get("response", "Request processed successfully"),
            action_taken=result.get("action", "unknown"),
            messages_processed=result.get("messages_processed")
        )
        
    except Exception as e:
        if "Gmail authorization required" in str(e):
            # Import here to avoid circular imports
            from .auth_controller import _generate_auth_url
            auth_url = _generate_auth_url(user_id)
            
            return ProcessResponse(
                response=f"Gmail authorization required. Please visit: {auth_url}",
                action_taken="auth_required",
                messages_processed=0
            )
        
        print(f"Error processing request: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}"
        )


@router.get("/messages", response_model=List[GmailMessage])
async def get_messages(
    user: dict = Depends(get_current_user),
    max_results: int = Query(10, le=50, description="Maximum number of messages to return"),
    query: Optional[str] = Query(None, description="Gmail search query (e.g., 'is:unread', 'from:example@gmail.com')")
):
    """
    Get Gmail messages for authenticated user
    
    Supports Gmail search syntax:
    - is:unread, is:read, is:important, is:starred
    - from:email@example.com, to:email@example.com
    - subject:keyword, has:attachment
    - newer_than:1d, older_than:1w
    """
    try:
        user_id = user["user_id"]
        gmail_service = _get_user_gmail_service(user_id)
        
        # Get messages
        messages = await gmail_service.get_messages(
            max_results=max_results,
            query=query or ""
        )
        
        # Convert to response format
        gmail_messages = []
        for msg in messages:
            gmail_messages.append(GmailMessage(
                id=msg["id"],
                subject=msg.get("subject", "No Subject"),
                sender=msg.get("sender", "Unknown"),
                date=msg.get("date", ""),
                snippet=msg.get("snippet", ""),
                is_unread="UNREAD" in msg.get("labelIds", [])
            ))
        
        return gmail_messages
        
    except Exception as e:
        if "Gmail authorization required" in str(e):
            raise HTTPException(status_code=401, detail=str(e))
        
        print(f"Error getting messages: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting messages: {str(e)}"
        )


@router.get("/messages/{message_id}")
async def get_message_content(
    message_id: str,
    user: dict = Depends(get_current_user)
):
    """Get full content of a specific message"""
    try:
        user_id = user["user_id"]
        gmail_service = _get_user_gmail_service(user_id)
        
        message = await gmail_service.get_message_by_id(message_id)
        
        if not message:
            raise HTTPException(
                status_code=404,
                detail="Message not found"
            )
        
        return message
        
    except Exception as e:
        if "Gmail authorization required" in str(e):
            raise HTTPException(status_code=401, detail=str(e))
        
        print(f"Error getting message: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting message: {str(e)}"
        )


@router.post("/messages/{message_id}/mark-read")
async def mark_message_read(
    message_id: str,
    user: dict = Depends(get_current_user)
):
    """Mark a specific message as read"""
    try:
        user_id = user["user_id"]
        gmail_service = _get_user_gmail_service(user_id)
        
        success = await gmail_service.mark_as_read([message_id])
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Failed to mark message as read"
            )
        
        return {"message": "Message marked as read successfully"}
        
    except Exception as e:
        if "Gmail authorization required" in str(e):
            raise HTTPException(status_code=401, detail=str(e))
        
        print(f"Error marking message as read: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error marking message as read: {str(e)}"
        )


@router.post("/drafts", response_model=CreateDraftResponse)
async def create_draft(
    draft: CreateDraftModel,
    user: dict = Depends(get_current_user)
):
    """Create a new draft"""
    try:
        user_id = user["user_id"]
        gmail_service = _get_user_gmail_service(user_id)
        
        draft_id = await gmail_service.create_draft(
            to=draft.to,
            subject=draft.subject,
            body=draft.body
        )
        
        if not draft_id:
            raise HTTPException(
                status_code=400,
                detail="Failed to create draft"
            )
        
        return CreateDraftResponse(
            draft_id=draft_id,
            message="Draft created successfully"
        )
        
    except Exception as e:
        if "Gmail authorization required" in str(e):
            raise HTTPException(status_code=401, detail=str(e))
        
        print(f"Error creating draft: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error creating draft: {str(e)}"
        )


@router.get("/drafts", response_model=List[DraftResponse])
async def get_drafts(
    user: dict = Depends(get_current_user),
    max_results: int = Query(10, le=50, description="Maximum number of drafts to return")
):
    """Get user's drafts"""
    try:
        user_id = user["user_id"]
        gmail_service = _get_user_gmail_service(user_id)
        
        drafts = await gmail_service.get_drafts(max_results=max_results)
        
        # Convert to response format
        draft_responses = []
        for draft in drafts:
            # Extract "To" from message - drafts store recipients differently
            to_email = ""
            # Try to get from parsed headers first
            if "headers" in draft:
                for header in draft["headers"]:
                    if header.get("name", "").lower() == "to":
                        to_email = header.get("value", "")
                        break
            
            # If not found, try direct fields
            if not to_email:
                to_email = draft.get("to", draft.get("recipient", ""))
            
            draft_responses.append(DraftResponse(
                id=draft.get("draft_id", draft.get("id", "")),
                subject=draft.get("subject", "No Subject"),
                to=to_email,
                created_date=draft.get("date", ""),
                body=draft.get("body", "")
            ))
        
        return draft_responses
        
    except Exception as e:
        if "Gmail authorization required" in str(e):
            raise HTTPException(status_code=401, detail=str(e))
        
        print(f"Error getting drafts: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting drafts: {str(e)}"
        )


@router.get("/drafts/{draft_id}")
async def get_draft_details(
    draft_id: str,
    user: dict = Depends(get_current_user)
):
    """Get details of a specific draft"""
    try:
        user_id = user["user_id"]
        gmail_service = _get_user_gmail_service(user_id)
        
        draft = await gmail_service.get_draft_by_id(draft_id)
        
        if not draft:
            raise HTTPException(
                status_code=404,
                detail="Draft not found"
            )
        
        return draft
        
    except Exception as e:
        if "Gmail authorization required" in str(e):
            raise HTTPException(status_code=401, detail=str(e))
        
        print(f"Error getting draft: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting draft: {str(e)}"
        )


@router.post("/drafts/{draft_id}/send")
async def send_draft(
    draft_id: str,
    user: dict = Depends(get_current_user)
):
    """Send a draft"""
    try:
        user_id = user["user_id"]
        gmail_service = _get_user_gmail_service(user_id)
        
        success = await gmail_service.send_draft(draft_id)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Failed to send draft"
            )
        
        return {"message": "Draft sent successfully"}
        
    except Exception as e:
        if "Gmail authorization required" in str(e):
            raise HTTPException(status_code=401, detail=str(e))
        
        print(f"Error sending draft: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error sending draft: {str(e)}"
        )


@router.delete("/drafts/{draft_id}")
async def delete_draft(
    draft_id: str,
    user: dict = Depends(get_current_user)
):
    """Delete a draft"""
    try:
        user_id = user["user_id"]
        gmail_service = _get_user_gmail_service(user_id)
        
        success = await gmail_service.delete_draft(draft_id)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Failed to delete draft"
            )
        
        return {"message": "Draft deleted successfully"}
        
    except Exception as e:
        if "Gmail authorization required" in str(e):
            raise HTTPException(status_code=401, detail=str(e))
        
        print(f"Error deleting draft: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting draft: {str(e)}"
        )