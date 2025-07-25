I am building gmail assistant, which can read gmail like unread, important, starred message. 
Assistant should be able to summarize it, mark it read or draft mail based on user input. 

this service will be used by multiple users to read their gmail. it is not for single use service.

In first phase lets build text based assistant and once we have robust text based assistant then we will make the realtime voice assistant on it. 
So think of product apis in terms of voice assistant perspective. 

We will use gemini for any llm use case.


Support for read message:
if user says read my 1st message -> it should preview first message by default. only give full message when user asks for read full message. 
once user says read my next message then it should read next message. and subsequent next should be working. 

once message is read, it should ask user if want to mark message as read (in case unread read) or have config to mark as unread. 

Support for summarize:
Message may be long and hard to go through it. so it should have support to summarize it.

Support for draft message:
system should ask user for input and based on it should draft a message with gemini. 

once drafted user can ask to edit old draft message. 

Support for mark as read request: 
user can say to mark message as read after reading it. 
