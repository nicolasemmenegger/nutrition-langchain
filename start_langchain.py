#!/usr/bin/env python3
"""Start script for the LangChain-based nutrition app backend"""

import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

def main():
    """Main startup function"""
    print("🚀 Starting Nutrition App Backend with LangChain Agents...")
    
    # Load environment variables
    env_path = Path('.env')
    if env_path.exists():
        load_dotenv(env_path)
        print("✅ Loaded environment variables from .env")
    else:
        print("⚠️ No .env file found. Creating one...")
        api_key = input("Please enter your OpenAI API key: ").strip()
        with open('.env', 'w') as f:
            f.write(f"OPENAI_API_KEY={api_key}\n")
        load_dotenv('.env')
        print("✅ Created .env file with API key")
    
    # Check for API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ Error: OPENAI_API_KEY not found in environment variables")
        print("Please add your OpenAI API key to the .env file:")
        print("OPENAI_API_KEY=your-api-key-here")
        sys.exit(1)
    
    print(f"✅ Found OpenAI API key ending in: ...{api_key[-4:]}")
    
    # Start the FastAPI server
    print("\n📡 Starting FastAPI server with LangChain agents...")
    print("Backend API will be available at: http://localhost:8001")
    print("API documentation at: http://localhost:8001/docs")
    print("\n🌐 To start the frontend, run in a new terminal:")
    print("   npm start")
    print("Then open: http://localhost:8000")
    print("\nPress Ctrl+C to stop the server\n")
    
    try:
        subprocess.run([
            sys.executable, "-m", "uvicorn",
            "backend.main_langchain:app",
            "--host", "0.0.0.0",
            "--port", "8001",
            "--reload"
        ])
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down server...")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()