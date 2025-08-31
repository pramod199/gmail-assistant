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



carplay app: 


  I am facing difficulty when creating draft email, while speaking recepient address until I finish saying I get response, can   │
│   you analyze how to fix it. once user stops saying then full process should have happened.


log when gemini gives error:
INFO - 09:57:01 - src.api.websocket.voice_handler - Starting Gemini response processing for user iM39zXKdKiY3STPuF2HzUaJiG9a2
INFO - 09:57:01 - src.core.voice.gemini_live_client - Starting Gemini Live response processing
DEBUG - 09:57:01 - src.core.voice.gemini_live_client - Session type: <class 'google.genai.live.AsyncSession'>
DEBUG - 09:57:01 - src.core.voice.gemini_live_client - Session methods: ['close', 'receive', 'send', 'send_client_content', 'send_realtime_input', 'send_tool_response', 'start_stream']
ERROR - 09:57:01 - src.core.voice.gemini_live_client - Error in process_responses: received 1011 (internal error) The service is currently unavailable.; then sent 1011 (internal error) The service is currently unavailable.
INFO - 09:57:01 - src.core.voice.gemini_live_client - Finished Gemini Live response processing
ERROR - 09:57:01 - src.api.websocket.voice_handler - Gemini response processing error for user iM39zXKdKiY3STPuF2HzUaJiG9a2: received 1011 (internal error) The service is currently unavailable.; then sent 1011 (internal error) The service is currently unavailable.
ERROR - 09:57:01 - src.api.websocket.voice_handler - Traceback: Traceback (most recent call last):
  File "/Users/pramod/src/projects/gmail-assistant/src/api/websocket/voice_handler.py", line 287, in _process_gemini_responses
    async for response in gemini_client.process_responses(gemini_session, function_handler=connection["function_handler"].handle_function_call):
  File "/Users/pramod/src/projects/gmail-assistant/src/core/voice/gemini_live_client.py", line 228, in process_responses
    async for response in session.receive():
  File "/Users/pramod/src/projects/gmail-assistant/.venv/lib/python3.11/site-packages/google/genai/live.py", line 443, in receive
    while result := await self._receive():
                    ^^^^^^^^^^^^^^^^^^^^^
  File "/Users/pramod/src/projects/gmail-assistant/.venv/lib/python3.11/site-packages/google/genai/live.py", line 524, in _receive
    raw_response = await self._ws.recv(decode=False)
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/pramod/src/projects/gmail-assistant/.venv/lib/python3.11/site-packages/websockets/asyncio/connection.py", line 322, in recv
    raise self.protocol.close_exc from self.recv_exc
websockets.exceptions.ConnectionClosedError: received 1011 (internal error) The service is currently unavailable.; then sent 1011 (internal error) The service is currently unavailable.

INFO - 09:57:01 - src.api.websocket.voice_handler - Response processing finished for user iM39zXKdKiY3STPuF2HzUaJiG9a2
ERROR - 09:57:01 - src.api.websocket.voice_handler - Response processing task failed for user iM39zXKdKiY3STPuF2HzUaJiG9a2: received 1011 (internal error) The service is currently unavailable.; then sent 1011 (internal error) The service is currently unavailable.
INFO - 09:57:01 - src.api.websocket.voice_handler - User iM39zXKdKiY3STPuF2HzUaJiG9a2 no longer connected or task cancelled, not restarting response processing

