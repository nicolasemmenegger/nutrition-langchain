from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
import json

@dataclass
class ChatMessage:
    role: str  # 'user', 'assistant', 'system'
    content: str
    timestamp: datetime = None
    metadata: Optional[Dict[str, Any]] = None
    category: Optional[str] = None
    name: Optional[str] = None  # Name of the assistant (e.g., 'conversation', 'meal_analyzer')
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class BaseAgent(ABC):
    """Base class for all agents"""
    
    def __init__(self, name: str, openai_api_key: str):
        self.name = name
        self.api_key = openai_api_key
    
    @abstractmethod
    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process the state and return updated state"""
        pass
    
    def get_chat_history(self, user_id: str, limit: int = 50) -> List[ChatMessage]:
        """Retrieve chat history from database"""
        try:
            # Import here to avoid circular imports
            from models import ChatHistory
            
            # Ensure consistent string user_id keying
            history_records = ChatHistory.get_user_history(str(user_id), limit)
            
            messages = []
            for record in reversed(history_records):  # Reverse to get chronological order
                metadata = json.loads(record.message_metadata) if record.message_metadata else None
                name = metadata.get('name') if metadata else None
                messages.append(ChatMessage(
                    role=record.role,
                    content=record.content,
                    timestamp=record.timestamp,
                    metadata=metadata,
                    category=record.category,
                    name=name
                ))
            
            return messages
            
        except Exception as e:
            print(f"Error retrieving chat history: {e}")
            # Return empty list as fallback
            return []
    
    def save_chat_message(self, user_id: str, message: ChatMessage):
        """Save chat message to database"""
        try:
            # Import here to avoid circular imports
            from models import ChatHistory
            
            # Include name in metadata if provided
            metadata = message.metadata or {}
            if message.name:
                metadata['name'] = message.name
            
            ChatHistory.save_message(
                user_id=str(user_id),
                role=message.role,
                content=message.content,
                metadata=metadata if metadata else None,
                category=message.category
            )
            
        except Exception as e:
            print(f"Error saving chat message: {e}")
            # Continue operation even if save fails