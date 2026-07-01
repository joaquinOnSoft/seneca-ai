import logging
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, PyMongoError
from bson.objectid import ObjectId
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

class MongoDatabase:
    """Wrapper class for MongoDB operations."""
    
    def __init__(self, uri: str):
        self.uri = uri
        self.client = None
        self.db = None
        self.conversations_collection = None

    def connect(self) -> bool:
        """Establishes connection to MongoDB."""
        if self.is_connected():
            return True
            
        try:
            self.client = MongoClient(self.uri)
            self.db = self.client.get_database()
            self.conversations_collection = self.db.conversations
            logger.info("MongoDB connected successfully.")
            return True
        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {e}", exc_info=True)
            self.conversations_collection = None
            return False
        except Exception as e:
            logger.error(f"An unexpected error occurred during MongoDB connection: {e}", exc_info=True)
            self.conversations_collection = None
            return False

    def is_connected(self) -> bool:
        """Checks if the connection to the database is active."""
        return self.conversations_collection is not None

    def get_conversations(self, user_id: str, skip: int = 0, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieves a paginated list of conversations for a specific user."""
        if not self.is_connected():
            raise ConnectionError("Database not connected")
            
        return list(self.conversations_collection.find(
            {"user_id": user_id}
        ).sort("created_at", -1).skip(skip).limit(limit))

    def get_conversation_by_id(self, conversation_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieves a single conversation by its ID, optionally filtering by user_id."""
        if not self.is_connected():
            raise ConnectionError("Database not connected")
            
        query = {"_id": ObjectId(conversation_id)}
        if user_id:
            query["user_id"] = user_id
            
        return self.conversations_collection.find_one(query)

    def check_conversation_exists(self, conversation_id: str) -> bool:
        """Checks if a conversation exists regardless of user ownership."""
        if not self.is_connected():
            raise ConnectionError("Database not connected")
            
        return self.conversations_collection.find_one({"_id": ObjectId(conversation_id)}) is not None

    def create_conversation(self, user_id: str, title: str, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Creates a new conversation document."""
        if not self.is_connected():
            raise ConnectionError("Database not connected")
            
        new_conversation = {
            "user_id": user_id,
            "title": title,
            "created_at": datetime.now(timezone.utc),
            "messages": messages
        }
        result = self.conversations_collection.insert_one(new_conversation)
        new_conversation['_id'] = result.inserted_id
        return new_conversation

    def update_conversation(self, conversation_id: str, user_id: str, update_fields: Dict[str, Any]) -> bool:
        """Updates specific fields of an existing conversation."""
        if not self.is_connected():
            raise ConnectionError("Database not connected")
            
        result = self.conversations_collection.update_one(
            {"_id": ObjectId(conversation_id), "user_id": user_id},
            {"$set": update_fields}
        )
        return result.matched_count > 0
