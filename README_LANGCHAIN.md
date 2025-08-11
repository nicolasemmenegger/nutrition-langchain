# AI Nutrition Assistant with LangChain Agents

## Overview

This is a sophisticated nutrition tracking application that uses LangChain agents to coordinate intelligent food analysis and provide personalized nutrition coaching. The system features:

- **Orchestrator Agent**: Main coordinator that manages user interactions and delegates to specialized agents
- **Nutrition Analysis Agent**: Specialized agent for analyzing food images and text to estimate calories and macronutrients
- **Vision Capabilities**: Analyze food photos to estimate nutritional content
- **Conversation Memory**: Maintains context across interactions for personalized coaching

## Architecture

### Agent System

1. **OrchestratorAgent** (`backend/agents.py`)
   - Manages overall conversation flow
   - Routes requests to appropriate specialized agents
   - Maintains conversation memory using LangChain's ConversationBufferMemory
   - Uses ReAct pattern for decision making

2. **NutritionAgent** (`backend/agents.py`)
   - Specialized for nutrition analysis
   - Processes both text descriptions and images
   - Estimates calories, protein, carbs, and fat
   - Provides confidence levels for estimates

3. **CalorieEstimationTool** (`backend/agents.py`)
   - Tool used by agents to perform nutrition calculations
   - Supports multimodal input (text + image)
   - Parses structured nutrition data from LLM responses

### API Endpoints

- `POST /chat` - Text-based conversation with the orchestrator
- `POST /chat-vision` - Analyze food images with text descriptions
- `POST /analyze-nutrition` - Direct nutrition analysis without conversation context
- `GET /health` - Check system status
- `POST /clear-conversation` - Reset conversation memory
- `GET /conversation-info/{session_id}` - Get conversation history

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure OpenAI API Key

Create a `.env` file in the root directory:

```env
OPENAI_API_KEY=your-openai-api-key-here
```

### 3. Start the Backend

```bash
python start_langchain.py
```

Or run directly:

```bash
uvicorn backend.main_langchain:app --host 0.0.0.0 --port 8001 --reload
```

### 4. Open the Frontend

Open `index_langchain.html` in your web browser.

## Features

### Intelligent Food Analysis
- Upload photos of meals for automatic nutrition estimation
- Describe food in text for analysis
- Get detailed breakdowns of calories and macronutrients

### Conversational AI Coach
- Natural language interactions
- Maintains context across conversations
- Provides personalized nutrition advice
- Answers questions about healthy eating

### Agent Coordination
- Orchestrator intelligently routes requests
- Specialized agents handle specific tasks
- Tools provide structured data extraction
- Memory maintains conversation continuity

## How It Works

1. **User Input**: User sends text message or uploads food image
2. **Orchestrator Processing**: Main agent analyzes intent and context
3. **Tool Selection**: Orchestrator decides which tools/agents to use
4. **Specialized Analysis**: Nutrition agent performs detailed analysis
5. **Response Generation**: Comprehensive response with nutrition data
6. **Memory Update**: Conversation saved for context

## Example Usage

### Text Analysis
```
User: "I had a grilled chicken salad with olive oil dressing"
Assistant: Analyzes and provides calorie/macro breakdown
```

### Image Analysis
```
User: [Uploads photo of pasta dish]
Assistant: Identifies food, estimates portions, provides nutrition data
```

### Nutrition Advice
```
User: "How can I increase my protein intake?"
Assistant: Provides personalized recommendations based on context
```

## Project Structure

```
nutrition-app/
├── backend/
│   ├── agents.py           # LangChain agents and tools
│   ├── main_langchain.py   # FastAPI server with agent integration
│   └── main.py            # Original backend (preserved)
├── index_langchain.html    # Updated frontend for agents
├── index.html             # Original frontend (preserved)
├── start_langchain.py     # Startup script for agent version
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variable template
└── README_LANGCHAIN.md   # This file
```

## Key Improvements Over Original

1. **Agent-Based Architecture**: Modular, extensible design using LangChain agents
2. **Intelligent Routing**: Orchestrator decides best approach for each query
3. **Tool Integration**: Structured tools for specific tasks
4. **Better Context Management**: LangChain memory for conversation continuity
5. **Confidence Scoring**: Agents provide confidence levels for estimates
6. **Extensibility**: Easy to add new specialized agents and tools

## Troubleshooting

### Backend Won't Start
- Ensure Python 3.8+ is installed
- Check all dependencies are installed: `pip install -r requirements.txt`
- Verify `.env` file exists with valid OpenAI API key

### Agent Not Initialized
- Check OpenAI API key is valid
- Ensure internet connection for API calls
- Check console for specific error messages

### Image Analysis Not Working
- Ensure image is in supported format (JPG, PNG)
- Check file size is reasonable (<5MB)
- Verify vision model (gpt-4o-mini) is accessible

## Future Enhancements

- Add more specialized agents (meal planning, recipe suggestions)
- Implement user profiles and tracking
- Add database for persistent storage
- Create mobile app version
- Integrate with fitness trackers
- Add voice input/output capabilities