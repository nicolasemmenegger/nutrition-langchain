# 🥗 AI-Powered Nutrition Chat App

A modern nutrition tracking application with AI-powered analysis using OpenAI and a chat-based interface.

## Features

### 🤖 **AI-Powered Analysis**
- **Smart food recognition** from natural language descriptions using GPT-4o-mini
- **Image analysis** of meals using OpenAI Vision API
- **Nutrition questions** answered by AI assistant
- **Accurate calorie estimation** based on comprehensive food knowledge

### 💬 **Chat Interface**  
- **Conversational interaction** - just tell it what you ate
- **Image upload** with drag-and-drop support
- **Real-time nutrition tracking** in the header
- **Requires AI backend** for all functionality

### 📱 **Modern UX**
- **Mobile-responsive design** 
- **Real-time typing indicators**
- **Connection status** with clear error messages
- **Local data persistence** for daily totals

## Quick Start

### ⚠️ **Backend Required**
This app requires the AI backend to be running for all functionality.

### 1. Install Backend Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start the Backend (with OpenAI)
```bash
python start_backend.py
```
You'll be prompted to enter your OpenAI API key. Get one at: https://platform.openai.com/api-keys

### 3. Start the Frontend
```bash
npm start
```

### 4. Open in Browser
Navigate to `http://localhost:8000`

**Important:** The frontend will show error messages and disable the interface if the backend is not running.

## Usage Examples

### 🍎 **Text-Based Logging**
- "I had 2 eggs and toast for breakfast"
- "Ate 200g chicken breast with rice"
- "Had a large salad with avocado"

### 📸 **Image-Based Logging**
- Upload a photo of your meal
- AI will identify foods and estimate nutrition
- Add context with additional text

### ❓ **Nutrition Questions**
- "How much protein should I eat daily?"
- "What are healthy snack options?"
- "Is my diet balanced?"

## API Endpoints

The FastAPI backend provides these endpoints:

- `GET /health` - Health check and OpenAI status
- `POST /analyze-text` - Analyze text for nutrition info
- `POST /analyze-image` - Analyze uploaded images
- `POST /upload-image` - Handle file uploads

## Architecture

```
┌─────────────────┐    HTTP/JSON    ┌──────────────────┐
│   Frontend      │ ◄──────────────► │   FastAPI        │
│   (HTML/JS)     │                 │   Backend        │
└─────────────────┘                 └──────────────────┘
                                            │
                                            ▼
                                    ┌──────────────────┐
                                    │   OpenAI API     │
                                    │   (GPT-4o-mini)  │
                                    └──────────────────┘
```

## Configuration

### Backend Configuration
- **OpenAI Model**: GPT-4o-mini (configurable in `backend/main.py`)
- **Port**: 8001 (configurable)
- **CORS**: Enabled for localhost development

### Frontend Configuration
- **API URL**: `http://localhost:8001` (configurable in `script.js`)
- **Fallback Mode**: Enabled when backend unavailable
- **Storage**: Local Storage for persistence

## Development

### Run Both Services
```bash
npm run dev-full
```

### Backend Only
```bash
npm run backend
```

### Frontend Only  
```bash
npm start
```

## Error Handling

When the backend is unavailable, the app will:
- **Show clear error messages** explaining the issue
- **Disable the interface** to prevent confusion
- **Display connection status** in the chat
- **Guide users** to start the backend server

## Requirements

### Backend
- Python 3.8+
- FastAPI
- LangChain
- OpenAI API key

### Frontend
- Modern web browser with JavaScript enabled
- Camera access (optional, for image upload)
- **Backend connection required** - no offline functionality

## License

MIT License - feel free to use and modify!

## Support

For issues or questions:
1. **Check backend status**: Visit `http://localhost:8001/health`
2. **Verify OpenAI API key**: Ensure it's valid and has credits
3. **Check dependencies**: Run `pip install -r requirements.txt`
4. **Frontend errors**: The app will clearly indicate backend connection issues

**Remember**: This app requires the backend to be running for all functionality.