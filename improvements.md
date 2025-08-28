while web socket connection it need gmail cred also from redis, in prod how will be the flow for this? do we need to authorize and then try websocket. 
     │  Frontend Client Flow                                                                    │
     │                                                                                                  │
     │ 1. Initial Authentication: User logs in via Firebase Auth → gets Firebase token                  │
     │ 2. Gmail Authorization Check: Frontend calls /api/auth/gmail/status to check if Gmail authorized │
     │ 3. Gmail OAuth (if needed): If not authorized, redirect to /api/auth/gmail/authorize             │
     │ 4. WebSocket Connection: Only connect after confirming both Firebase + Gmail auth

suggestion: Connection State Management:                                                                                              │ │
│ │   - Implement connection timeouts                                                                                            │ │
│ │   - Add heartbeat mechanism for connection health

while reading message two or more filter can be combined, like (important , unread) (starred, read) (unread, -updated, -social)

if user says read my first message it will go to which func read_message ot navigate_message? as this has read and next both word.

create_message_summary is not using AI. 

     elif action == "unread":
            # TODO: Implement mark as unread in gmail_service
            action_msg = "mark as unread not implemented yet"
        elif action in ["star", "unstar", "archive", "delete"]:
            action_msg = f"{action} not implemented yet"

draft should be done with help of ai but not happening in voice. 
-> two type 1 new draft other replay to existing message 
for reply check gmail api -> native reply in gmail method

cleanup_user_data of session manager is not being used, I see session is not being removed, do we need to remove it or it work as of now. 
analyze

Add session TTL support:                                                                                                  │ │
│ │   - Sessions auto-expire after configurable time (e.g., 24 hours)                                                            │ │
│ │   - Update last_active timestamp on each interaction


P0 funcationality:
1. 


carplay app: 


lets analyze draft email process and then check it is implemented correct or not: 
2 scenario: 
1. draft new email to a recepient - here email validation should be present and error if not valid email. 
2. replay to current message: in this case we know sender, current message and subject. we should follow current native gmail reply and ask user for content only. other details are already present, let me know body will include existing message? 

we should handle these two scenario both. 