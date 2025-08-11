# Quick Start Guide

## Setup (First Time Only)

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Create `.env` file with your OpenAI API key:
```bash
echo "OPENAI_API_KEY=your-api-key-here" > .env
```

## Running the Application

You need two terminal windows:

### Terminal 1 - Backend (Port 8001)
```bash
python start_langchain.py
```

### Terminal 2 - Frontend (Port 8000)
```bash
npm start
```

Then open your browser to: **http://localhost:8000**

## Alternative: Run Both Together

If you have npm and concurrently installed:
```bash
npm run dev-full
```

This will start both backend and frontend simultaneously.

## URLs

- Frontend: http://localhost:8000
- Backend API: http://localhost:8001
- API Docs: http://localhost:8001/docs

## Features

- 📷 Upload food photos for nutrition analysis
- 💬 Chat with AI nutrition coach
- 📊 Get detailed calorie and macro breakdowns
- 🧠 Powered by LangChain agents for intelligent responses