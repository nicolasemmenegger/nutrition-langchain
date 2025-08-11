#!/usr/bin/env python3
"""
Nutrition App Backend Launcher
This script handles OpenAI authentication and starts the FastAPI server.
"""

import os
import sys
import getpass
import subprocess
from pathlib import Path

def check_dependencies():
    """Check if required packages are installed"""
    required_packages = [
        'fastapi', 'uvicorn', 'langchain', 'langchain-openai', 
        'openai', 'dotenv', 'pydantic', 'PIL'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Missing required packages:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\n🔧 Install them with:")
        print("   pip install -r requirements.txt")
        return False
    
    return True

def get_openai_api_key():
    """Get OpenAI API key from user input or environment"""
    # Check if already set in environment
    api_key = os.getenv('OPENAI_API_KEY')
    
    if api_key:
        print(f"✅ Found OpenAI API key in environment (ends with: ...{api_key[-4:]})")
        return api_key
    
    # Check .env file
    env_file = Path('.env')
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                if line.startswith('OPENAI_API_KEY='):
                    api_key = line.split('=', 1)[1].strip().strip('"\'')
                    print(f"✅ Found OpenAI API key in .env file (ends with: ...{api_key[-4:]})")
                    return api_key
    
    # Prompt user for API key
    print("🔑 OpenAI API Key Required")
    print("   Get your API key from: https://platform.openai.com/api-keys")
    print()
    
    while True:
        api_key = getpass.getpass("Enter your OpenAI API key: ").strip()
        
        if not api_key:
            print("❌ API key cannot be empty. Please try again.")
            continue
        
        if not api_key.startswith('sk-'):
            print("❌ Invalid API key format. OpenAI keys start with 'sk-'")
            continue
        
        if len(api_key) < 20:
            print("❌ API key seems too short. Please check and try again.")
            continue
        
        break
    
    # Ask if user wants to save the key
    save_key = input("💾 Save API key to .env file? (y/n): ").lower().strip()
    
    if save_key in ('y', 'yes'):
        with open('.env', 'w') as f:
            f.write(f"OPENAI_API_KEY={api_key}\n")
        print("✅ API key saved to .env file")
    
    return api_key

def test_openai_connection(api_key):
    """Test OpenAI API connection"""
    print("🔍 Testing OpenAI connection...")
    
    try:
        from langchain_openai import ChatOpenAI
        from langchain.schema import HumanMessage
        
        client = ChatOpenAI(
            model="gpt-4o-mini",
            openai_api_key=api_key,
            temperature=0.1
        )
        
        # Simple test
        response = client.invoke([
            HumanMessage(content="Hello, respond with 'Connection successful'")
        ])
        
        if "successful" in response.content.lower():
            print("✅ OpenAI connection successful!")
            return True
        else:
            print("⚠️  OpenAI responded but with unexpected content")
            return True  # Still working, just different response
            
    except Exception as e:
        print(f"❌ OpenAI connection failed: {e}")
        return False

def start_server(api_key):
    """Start the FastAPI server with the OpenAI API key"""
    print("🚀 Starting Nutrition Analysis Server...")
    
    # Set environment variable for the server
    env = os.environ.copy()
    env['OPENAI_API_KEY'] = api_key
    
    # Start the server
    try:
        import uvicorn
        from backend.main import app, initialize_openai
        
        # Initialize OpenAI in the app
        if initialize_openai(api_key):
            print("✅ OpenAI initialized successfully")
        else:
            print("❌ Failed to initialize OpenAI")
            return False
        
        print("🌐 Server starting at: http://localhost:8001")
        print("📖 API docs available at: http://localhost:8001/docs")
        print("🛑 Press Ctrl+C to stop the server")
        print()
        
        # Run the server
        uvicorn.run(app, host="0.0.0.0", port=8001, reload=False)
        
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Server failed to start: {e}")
        return False
    
    return True

def main():
    """Main function"""
    print("🥗 Nutrition App Backend Launcher")
    print("=" * 40)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Get OpenAI API key
    api_key = get_openai_api_key()
    
    # Test connection
    if not test_openai_connection(api_key):
        print("❌ Cannot continue without working OpenAI connection")
        sys.exit(1)
    
    # Start server
    if not start_server(api_key):
        sys.exit(1)

if __name__ == "__main__":
    main()