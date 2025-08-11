from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import base64
import os
from datetime import datetime
import uvicorn
from dotenv import load_dotenv

try:
    from agents_structured import StructuredOrchestratorAgent as OrchestratorAgent
except ImportError:
    try:
        from backend.agents_structured import StructuredOrchestratorAgent as OrchestratorAgent
    except ImportError:
        try:
            from agents_simple import SimpleOrchestratorAgent as OrchestratorAgent
        except ImportError:
            from backend.agents_simple import SimpleOrchestratorAgent as OrchestratorAgent

# Load environment variables
load_dotenv()

app = FastAPI(title="Nutrition Chat API with LangChain", version="2.0.0")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global orchestrator instance
orchestrator: Optional[OrchestratorAgent] = None
current_api_key = None

class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = "default"

class ChatResponse(BaseModel):
    success: bool
    message: str
    session_id: str
    nutrition_data: Optional[Dict[str, Any]] = None

def initialize_orchestrator(api_key: str):
    """Initialize the orchestrator agent with the provided API key"""
    global orchestrator, current_api_key
    try:
        print(f"🔧 Initializing Orchestrator Agent with key ending in: ...{api_key[-4:]}")
        
        orchestrator = OrchestratorAgent(api_key=api_key)
        current_api_key = api_key
        
        # Test the connection
        test_result = orchestrator.process_message(
            "Hello, I'm testing the connection.",
            session_id="test"
        )
        
        if test_result["success"]:
            print("✅ Orchestrator Agent initialized successfully!")
            print(f"📄 Test response: {test_result['message'][:100]}...")
            return True
        else:
            print(f"❌ Failed to initialize Orchestrator: {test_result['message']}")
            return False
            
    except Exception as e:
        print(f"❌ Failed to initialize Orchestrator: {e}")
        orchestrator = None
        current_api_key = None
        return False

@app.on_event("startup")
async def startup_event():
    """Initialize the orchestrator on startup if API key is available"""
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        print("🚀 Found OPENAI_API_KEY in environment, initializing orchestrator...")
        initialize_orchestrator(api_key)
    else:
        print("⚠️ No OPENAI_API_KEY found in environment. Please set it in .env file or call /initialize endpoint")

@app.post("/initialize")
async def initialize_api(api_key: str):
    """Initialize the orchestrator with an API key"""
    if initialize_orchestrator(api_key):
        return {"success": True, "message": "Orchestrator initialized successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to initialize orchestrator")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "orchestrator_initialized": orchestrator is not None,
        "api_version": "2.0.0",
        "using": "LangChain Agents"
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatMessage):
    """Chat with the nutrition coach orchestrator"""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized. Please set OPENAI_API_KEY.")
    
    try:
        print(f"💬 Chat request from session {request.session_id}: '{request.message[:50]}...'")
        
        result = orchestrator.process_message(
            message=request.message,
            session_id=request.session_id
        )
        
        if result["success"]:
            return ChatResponse(
                success=True,
                message=result["message"],
                session_id=request.session_id,
                nutrition_data=result.get("nutrition_data")
            )
        else:
            raise HTTPException(status_code=500, detail=result["message"])
        
    except Exception as e:
        print(f"❌ Chat error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")

@app.post("/chat-vision", response_model=ChatResponse)
async def chat_vision(
    message: str = Form(...),
    session_id: Optional[str] = Form("default"),
    image: Optional[UploadFile] = File(None),
    image_url: Optional[str] = Form(None),
):
    """Send a text prompt + an image to analyze nutrition"""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized. Please set OPENAI_API_KEY.")
    
    if image is None and not image_url:
        raise HTTPException(status_code=400, detail="Please provide 'image' or 'image_url'")
    
    try:
        image_data = None
        
        # Process uploaded image
        if image is not None:
            img_bytes = await image.read()
            mime = image.content_type or "image/png"
            image_data = f"data:{mime};base64,{base64.b64encode(img_bytes).decode('utf-8')}"
        else:
            # Use provided URL
            image_data = image_url
        
        print(f"🖼️ Vision request from session {session_id}: '{message[:50]}...' with image")
        
        result = orchestrator.process_message(
            message=message,
            image_data=image_data,
            session_id=session_id
        )
        
        if result["success"]:
            return ChatResponse(
                success=True,
                message=result["message"],
                session_id=session_id,
                nutrition_data=result.get("nutrition_data")
            )
        else:
            raise HTTPException(status_code=500, detail=result["message"])
        
    except Exception as e:
        print(f"❌ Vision chat error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Vision analysis failed: {str(e)}")

@app.post("/clear-conversation")
async def clear_conversation(session_id: str = "default"):
    """Clear conversation history for a session"""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    
    result = orchestrator.clear_memory(session_id=session_id)
    print(f"🧹 Cleared conversation for session: {session_id}")
    return result

@app.get("/conversation-info/{session_id}")
async def get_conversation_info(session_id: str = "default"):
    """Get information about the current conversation"""
    if not orchestrator:
        return {"session_id": session_id, "message_count": 0, "exists": False}
    
    history = orchestrator.get_conversation_history(session_id=session_id)
    
    return {
        "session_id": session_id,
        "message_count": len(history),
        "exists": True,
        "messages": history
    }

@app.post("/analyze-nutrition")
async def analyze_nutrition(
    food_description: str = Form(...),
    image: Optional[UploadFile] = File(None),
):
    """Direct endpoint for nutrition analysis without conversation context"""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    
    try:
        image_data = None
        
        if image is not None:
            img_bytes = await image.read()
            mime = image.content_type or "image/png"
            image_data = f"data:{mime};base64,{base64.b64encode(img_bytes).decode('utf-8')}"
        
        # Use the nutrition agent directly
        result = orchestrator.nutrition_agent.analyze(
            text=food_description,
            image_data=image_data
        )
        
        return {
            "success": True,
            "nutrition_data": result
        }
        
    except Exception as e:
        print(f"❌ Nutrition analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)