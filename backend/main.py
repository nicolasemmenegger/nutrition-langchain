from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any   # <- allow Any for multimodal content
import base64


import os
import time
from datetime import datetime
import uvicorn

app = FastAPI(title="Nutrition Chat API", version="1.0.0")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global OpenAI client and conversation storage
openai_client = None
current_api_key = None
conversations: Dict[str, List[Dict[str, Any]]] = {}  # was Dict[str, List[Dict[str, str]]]

def _bytes_to_data_url(b: bytes, mime: str = "image/png") -> str:
    return f"data:{mime};base64," + base64.b64encode(b).decode("utf-8")

class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = "default"

class ChatResponse(BaseModel):
    success: bool
    message: str
    session_id: str

# System prompt for nutrition coaching
NUTRITION_COACH_PROMPT = """You are a professional nutrition coach and dietitian. Your role is to:

1. Help users track their food intake and nutrition
2. Provide accurate nutritional information about foods
3. Give personalized nutrition advice based on user goals
4. Answer questions about healthy eating, meal planning, and nutrition
5. Be supportive and encouraging while maintaining scientific accuracy

Guidelines:
- Always ask for clarification if food descriptions are unclear
- Provide specific nutritional values when possible (calories, macronutrients)
- Consider individual needs, preferences, and dietary restrictions
- Recommend consulting healthcare professionals for medical nutrition therapy
- Keep responses conversational and helpful

Remember: You're having an ongoing conversation, so maintain context from previous messages."""

def initialize_openai(api_key: str):
    """Initialize OpenAI client with the provided API key"""
    global openai_client, current_api_key
    try:
        print(f"🔧 Initializing OpenAI client with key ending in: ...{api_key[-4:]}")
        
        from openai import OpenAI
        openai_client = OpenAI(api_key=api_key)
        current_api_key = api_key
        
        print("🧪 Testing OpenAI connection with Responses API...")
        test_response = openai_client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": NUTRITION_COACH_PROMPT},
                {"role": "user", "content": "Hello, I'm testing the connection."}
            ],
            temperature=0.1,
        )
        
        print("✅ OpenAI Responses API connection successful!")
        print("📄 RAW API RESPONSE:")
        print(test_response)
        print("\n" + "="*50 + "\n")
        
        return True
    except Exception as e:
        print(f"❌ Failed to initialize OpenAI: {e}")
        print(f"💡 Note: Responses API might not be available, falling back to regular chat completions")
        
        # Fallback to regular chat completions if Responses API is not available
        try:
            test_response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": NUTRITION_COACH_PROMPT},
                    {"role": "user", "content": "Hello, I'm testing the connection."}
                ],
                temperature=0.1,
                user=f"nutrition-app-test-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            
            print("✅ OpenAI chat completions connection successful!")
            print("📄 RAW API RESPONSE:")
            print(test_response)
            print("\n" + "="*50 + "\n")
            
            return True
        except Exception as fallback_error:
            print(f"❌ Fallback also failed: {fallback_error}")
            return False

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "openai_initialized": openai_client is not None}

# ---------- New endpoint: text reply using image as context ----------
@app.post("/chat-vision", response_model=ChatResponse)
async def chat_vision(
    message: str = Form(...),
    session_id: Optional[str] = Form("default"),
    image: Optional[UploadFile] = File(None),
    image_url: Optional[str] = Form(None),
    model: str = Form("gpt-4o-mini"),
    temperature: float = Form(0.2),
):
    """
    Send a text prompt + an image (file or URL) to a vision model and get a text-only reply.
    - Provide one of: 'image' (UploadFile) or 'image_url' (http(s) or data URL).
    - Uses the same per-session conversation memory.
    """
    if not openai_client:
        raise HTTPException(status_code=503, detail="OpenAI not initialized")

    if image is None and not image_url:
        raise HTTPException(status_code=400, detail="Please provide 'image' or 'image_url'")

    # Ensure session initialized
    if session_id not in conversations:
        conversations[session_id] = [{"role": "system", "content": NUTRITION_COACH_PROMPT}]

    # Build multimodal content block for the user turn
    user_content: List[Dict[str, Any]] = [
        {"type": "text", "text": message}
    ]

    try:
        # Use uploaded file if present
        if image is not None:
            img_bytes = await image.read()
            mime = image.content_type or "image/png"
            data_url = _bytes_to_data_url(img_bytes, mime=mime)
            user_content.append({
                "type": "image_url",
                "image_url": {"url": data_url}
            })
        else:
            # Use provided URL (can be http(s) or data URL)
            user_content.append({
                "type": "image_url",
                "image_url": {"url": image_url}
            })

        # Append to conversation (vision turn)
        conversations[session_id].append({"role": "user", "content": user_content})

        # Call vision-capable chat model
        response = openai_client.chat.completions.create(
            model=model,                     # e.g., "gpt-4o-mini" or "gpt-4o"
            messages=conversations[session_id],
            temperature=temperature,
            user=f"nutrition-vision-{session_id}-{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        )

        assistant_message = response.choices[0].message.content

        # Save assistant reply to history
        conversations[session_id].append({"role": "assistant", "content": assistant_message})

        # Trim history (keep system + last 20)
        if len(conversations[session_id]) > 21:
            conversations[session_id] = [conversations[session_id][0]] + conversations[session_id][-20:]

        return ChatResponse(success=True, message=assistant_message, session_id=session_id)

    except Exception as e:
        print(f"❌ Vision chat error: {str(e)}")
        # Remove the last appended user message on failure to avoid polluting context
        if conversations.get(session_id, [None])[-1].get("role") == "user":
            conversations[session_id].pop()
        raise HTTPException(status_code=500, detail=f"Vision chat failed: {str(e)}")

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatMessage):
    """Chat with the nutrition coach"""
    if not openai_client:
        raise HTTPException(status_code=503, detail="OpenAI not initialized")
    
    try:
        session_id = request.session_id
        
        # Initialize conversation for new sessions
        if session_id not in conversations:
            conversations[session_id] = [
                {"role": "system", "content": NUTRITION_COACH_PROMPT}
            ]
        
        # Add user message to conversation
        conversations[session_id].append({"role": "user", "content": request.message})
        
        print(f"💬 Chat request from session {session_id}: '{request.message[:50]}...'")
        print(f"📊 Conversation length: {len(conversations[session_id])} messages")
        
        # Try using Responses API first, fallback to regular chat completions
        try:
            print("🔄 Attempting to use OpenAI Responses API...")
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=conversations[session_id],
            )

            print("✅ Used Responses API successfully!")
        except Exception as responses_error:
            print(f"⚠️ Responses API failed: {responses_error}")
            print("🔄 Falling back to regular chat completions...")
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=conversations[session_id],
                temperature=0.1,
                user=f"nutrition-app-{session_id}-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            print("✅ Used regular chat completions successfully!")
        
        print("📄 RAW API RESPONSE:")
        print(response)
        print("\n" + "="*50 + "\n")
        
        # Add assistant response to conversation
        assistant_message = response.choices[0].message.content
        conversations[session_id].append({"role": "assistant", "content": assistant_message})
        
        # Keep conversation length manageable (last 20 messages + system prompt)
        if len(conversations[session_id]) > 21:
            conversations[session_id] = [conversations[session_id][0]] + conversations[session_id][-20:]
        
        return ChatResponse(
            success=True,
            message=assistant_message,
            session_id=session_id
        )
        
    except Exception as e:
        print(f"❌ Chat error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")

@app.post("/clear-conversation")
async def clear_conversation(session_id: str = "default"):
    """Clear conversation history for a session"""
    if session_id in conversations:
        conversations[session_id] = [
            {"role": "system", "content": NUTRITION_COACH_PROMPT}
        ]
        print(f"🧹 Cleared conversation for session: {session_id}")
        return {"success": True, "message": f"Conversation cleared for session {session_id}"}
    else:
        return {"success": False, "message": f"No conversation found for session {session_id}"}

@app.get("/conversation-info/{session_id}")
async def get_conversation_info(session_id: str = "default"):
    """Get information about the current conversation"""
    if session_id not in conversations:
        return {"session_id": session_id, "message_count": 0, "exists": False}
    
    return {
        "session_id": session_id,
        "message_count": len(conversations[session_id]) - 1,  # Exclude system message
        "exists": True,
        "messages": conversations[session_id][1:] if len(conversations[session_id]) > 1 else []  # Exclude system message
    }

@app.get("/test-responses-api")
async def test_responses_api():
    """Test the OpenAI Responses API specifically"""
    if not openai_client:
        raise HTTPException(status_code=503, detail="OpenAI not initialized")
    
    try:
        print("🧪 Testing OpenAI Responses API directly...")
        
        # Try Responses API
        try:
            response = openai_client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Say 'Responses API is working' if you can see this."}
                ],
                temperature=0.1,
            )
            
            print("✅ Responses API test successful!")
            print("📄 RAW RESPONSES API RESPONSE:")
            print(response)
            print("\n" + "="*50 + "\n")
            
            return {
                "success": True,
                "api_used": "responses_api",
                "response_content": response.choices[0].message.content,
                "raw_response": str(response)
            }
            
        except Exception as responses_error:
            print(f"❌ Responses API failed: {responses_error}")
            
            # Fallback to regular API
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Say 'Regular chat completions API is working' if you can see this."}
                ],
                temperature=0.1,
                user=f"nutrition-app-api-test-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            
            print("✅ Regular chat completions test successful!")
            print("📄 RAW CHAT COMPLETIONS RESPONSE:")
            print(response)
            print("\n" + "="*50 + "\n")
            
            return {
                "success": True,
                "api_used": "chat_completions",
                "responses_api_error": str(responses_error),
                "response_content": response.choices[0].message.content,
                "raw_response": str(response)
            }
        
    except Exception as e:
        print(f"❌ API test failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "api_used": "none"
        }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)