import os.path
from typing import Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class GmailAuth:
    SCOPES = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/gmail.compose"
    ]
    
    def __init__(self, credentials_file: str = "credentials.json", token_file: str = "token.json"):
        self.credentials_file = credentials_file
        self.token_file = token_file
        self._credentials: Optional[Credentials] = None
    
    def authenticate(self) -> Credentials:
        creds = None
        
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file, self.SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"Token refresh failed: {e}")
                    creds = self._run_oauth_flow()
            else:
                creds = self._run_oauth_flow()
            
            with open(self.token_file, "w") as token:
                token.write(creds.to_json())
        
        self._credentials = creds
        return creds
    
    def _run_oauth_flow(self) -> Credentials:
        if not os.path.exists(self.credentials_file):
            raise FileNotFoundError(f"Credentials file not found: {self.credentials_file}")
        
        flow = InstalledAppFlow.from_client_secrets_file(
            self.credentials_file, self.SCOPES
        )
        creds = flow.run_local_server(port=0)
        return creds
    
    def get_credentials(self) -> Optional[Credentials]:
        if not self._credentials:
            return self.authenticate()
        return self._credentials
    
    def is_authenticated(self) -> bool:
        return self._credentials is not None and self._credentials.valid