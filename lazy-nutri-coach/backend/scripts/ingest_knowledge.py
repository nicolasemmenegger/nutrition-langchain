import sys
import os
# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.rag import ingest_directory
from app.config import settings

if __name__ == "__main__":
    ingest_directory(settings.kb_dir)
    print("Knowledge base ingested into Chroma at", settings.chroma_dir)
