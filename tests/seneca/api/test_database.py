import pytest
from unittest.mock import MagicMock, patch
from bson.objectid import ObjectId
from datetime import datetime, timezone
from src.seneca.api.database import MongoDatabase
from pymongo.errors import ConnectionFailure

@pytest.fixture
def db():
    database = MongoDatabase("mongodb://localhost:27017/test_db")
    return database

def test_connect_success(db):
    with patch('src.seneca.api.database.MongoClient') as MockMongoClient:
        mock_mongo_instance = MagicMock()
        MockMongoClient.return_value = mock_mongo_instance
        
        # Call connect
        result = db.connect()
        
        assert result is True
        assert db.is_connected() is True
        assert db.conversations_collection is not None

def test_connect_already_connected(db):
    db.conversations_collection = MagicMock()
    with patch('src.seneca.api.database.MongoClient') as MockMongoClient:
        result = db.connect()
        assert result is True
        MockMongoClient.assert_not_called()

def test_connect_failure(db):
    with patch('src.seneca.api.database.MongoClient', side_effect=ConnectionFailure("Error")):
        result = db.connect()
        assert result is False
        assert db.is_connected() is False

def test_get_conversations(db):
    db.conversations_collection = MagicMock()
    
    expected_data = [{"_id": "test1"}, {"_id": "test2"}]
    # Mock chain: find().sort().skip().limit()
    mock_find = MagicMock()
    mock_sort = MagicMock()
    mock_skip = MagicMock()
    mock_limit = MagicMock()
    
    db.conversations_collection.find.return_value = mock_find
    mock_find.sort.return_value = mock_sort
    mock_sort.skip.return_value = mock_skip
    mock_skip.limit.return_value = expected_data
    
    result = db.get_conversations("user123", skip=10, limit=5)
    
    assert result == expected_data
    db.conversations_collection.find.assert_called_once_with({"user_id": "user123"})
    mock_find.sort.assert_called_once_with("created_at", -1)
    mock_sort.skip.assert_called_once_with(10)
    mock_skip.limit.assert_called_once_with(5)

def test_get_conversations_not_connected(db):
    with pytest.raises(ConnectionError, match="Database not connected"):
        db.get_conversations("user123")

def test_get_conversation_by_id(db):
    db.conversations_collection = MagicMock()
    
    expected_doc = {"_id": "conv1", "user_id": "user123"}
    db.conversations_collection.find_one.return_value = expected_doc
    
    # With user_id
    result = db.get_conversation_by_id("507f1f77bcf86cd799439011", user_id="user123")
    assert result == expected_doc
    db.conversations_collection.find_one.assert_called_with(
        {"_id": ObjectId("507f1f77bcf86cd799439011"), "user_id": "user123"}
    )
    
    # Without user_id
    result = db.get_conversation_by_id("507f1f77bcf86cd799439011")
    assert result == expected_doc
    db.conversations_collection.find_one.assert_called_with(
        {"_id": ObjectId("507f1f77bcf86cd799439011")}
    )

def test_get_conversation_by_id_not_connected(db):
    with pytest.raises(ConnectionError, match="Database not connected"):
        db.get_conversation_by_id("some_id")

def test_check_conversation_exists(db):
    db.conversations_collection = MagicMock()
    
    db.conversations_collection.find_one.return_value = {"_id": "conv1"}
    assert db.check_conversation_exists("507f1f77bcf86cd799439011") is True
    
    db.conversations_collection.find_one.return_value = None
    assert db.check_conversation_exists("507f1f77bcf86cd799439011") is False

def test_create_conversation(db):
    db.conversations_collection = MagicMock()
    
    new_id = ObjectId()
    mock_insert_result = MagicMock()
    mock_insert_result.inserted_id = new_id
    db.conversations_collection.insert_one.return_value = mock_insert_result
    
    messages = [{"role": "user", "content": "hi", "timestamp": "2023-01-01T00:00:00Z"}]
    
    result = db.create_conversation("user123", "Title", messages)
    
    assert result["_id"] == new_id
    assert result["user_id"] == "user123"
    assert result["title"] == "Title"
    assert result["messages"] == messages
    assert isinstance(result["created_at"], datetime)
    
    db.conversations_collection.insert_one.assert_called_once()
    inserted_doc = db.conversations_collection.insert_one.call_args[0][0]
    assert inserted_doc["title"] == "Title"

def test_update_conversation(db):
    db.conversations_collection = MagicMock()
    
    # Match found
    mock_update_result = MagicMock()
    mock_update_result.matched_count = 1
    db.conversations_collection.update_one.return_value = mock_update_result
    
    result = db.update_conversation("507f1f77bcf86cd799439011", "user123", {"title": "New Title"})
    assert result is True
    db.conversations_collection.update_one.assert_called_once_with(
        {"_id": ObjectId("507f1f77bcf86cd799439011"), "user_id": "user123"},
        {"$set": {"title": "New Title"}}
    )
    
    # Match not found
    mock_update_result.matched_count = 0
    result = db.update_conversation("507f1f77bcf86cd799439011", "user123", {"title": "New Title"})
    assert result is False
