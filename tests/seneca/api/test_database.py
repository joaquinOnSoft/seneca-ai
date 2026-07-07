import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
from bson.objectid import ObjectId
from pymongo.errors import ConnectionFailure, PyMongoError

from seneca.api.database import MongoDatabase
from seneca.utils.passlib_bcrypt_fix import _passlib_bcrypt_module  # noqa: F401 — "Applies the patch via side effect
# noinspection PyUnresolvedReferences
from passlib.hash import bcrypt

# Mock config for MongoDatabase
class MockConfig:
    def __init__(self):
        self.mongodb_uri = "mongodb://mock_host:27017/mock_db"
        self.jwt_access_token_expires_in = 900
        self.jwt_refresh_token_expires_in_days = 7


@pytest.fixture
def mock_mongo_client():
    """Mocks pymongo.MongoClient and its methods as imported by MongoDatabase."""
    # Patch MongoClient where it's imported in seneca.api.database
    with patch('seneca.api.database.MongoClient') as MockMongoClient:
        mock_client_instance = MagicMock()
        mock_db_instance_obj = MagicMock()  # Renamed to avoid confusion with fixture name

        # Mock collections
        mock_db_instance_obj.conversations = MagicMock()
        mock_db_instance_obj.users = MagicMock()

        mock_client_instance.get_database.return_value = mock_db_instance_obj

        # Ensure the close method is mocked on the client instance
        mock_client_instance.close.return_value = None

        # Yield the MockMongoClient class and the pre-configured mock instances
        yield MockMongoClient, mock_client_instance, mock_db_instance_obj


@pytest.fixture
def mock_db_instance(mock_mongo_client):
    """Provides a MongoDatabase instance with a mocked MongoClient, and ensures it's connected."""
    MockMongoClient, mock_client_instance, mock_db_instance_obj = mock_mongo_client
    MockMongoClient.return_value = mock_client_instance  # Ensure successful connection for this fixture
    db = MongoDatabase(MockConfig().mongodb_uri)
    db.connect()  # This will use the patched MongoClient and set _client, _db, etc.
    yield db


@pytest.fixture
def sample_user_data():
    return {
        "_id": ObjectId(),
        "user_id": "test_user_1",
        "user_name": "testuser",
        "user_full_name": "Test User",
        "password_hash": bcrypt.hash("testpassword"),
        "api_key": "some_api_key",
        "refresh_tokens": []
    }


@pytest.fixture
def sample_conversation_data():
    return {
        "_id": ObjectId(),
        "user_id": "test_user_1",
        "title": "Test Conversation",
        "created_at": datetime.now(timezone.utc),
        "messages": [{"role": "user", "content": "Hello",
                      "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}]
    }


# --- Tests for MongoDatabase Connection ---

def test_mongo_database_init(mock_mongo_client):
    db = MongoDatabase("mongodb://localhost:27017/testdb")
    assert db.mongo_uri == "mongodb://localhost:27017/testdb"
    assert not db.is_connected()


def test_mongo_database_connect_success(mock_mongo_client):
    MockMongoClient, mock_client_instance, mock_db_instance_obj = mock_mongo_client
    MockMongoClient.return_value = mock_client_instance  # Set return value for this test
    db = MongoDatabase("mongodb://localhost:27017/testdb")
    db.connect()
    MockMongoClient.assert_called_once_with("mongodb://localhost:27017/testdb")
    assert db.is_connected()
    assert db._client == mock_client_instance
    assert db._db == mock_db_instance_obj
    assert db.conversations_collection == mock_db_instance_obj.conversations
    assert db.users_collection == mock_db_instance_obj.users


def test_mongo_database_connect_failure():  # Removed mock_mongo_client fixture
    with patch('seneca.api.database.MongoClient') as MockMongoClient:  # Patch directly in test
        MockMongoClient.side_effect = ConnectionFailure("Mock connection failed")
        db = MongoDatabase("mongodb://localhost:27017/testdb")
        with pytest.raises(ConnectionFailure):
            db.connect()
        assert not db.is_connected()
        MockMongoClient.assert_called_once_with("mongodb://localhost:27017/testdb")


def test_mongo_database_close(mock_db_instance):
    db_instance = mock_db_instance
    mock_client = db_instance._client  # capture before close() sets it to None
    db_instance.close()
    mock_client.close.assert_called_once()
    assert not db_instance.is_connected()


# --- Tests for Conversation Methods ---

def test_get_conversations(mock_db_instance, sample_conversation_data):
    mock_db_instance.conversations_collection.find.return_value.sort.return_value.skip.return_value.limit.return_value = [
        sample_conversation_data]
    conversations = mock_db_instance.get_conversations("test_user_1")
    assert len(conversations) == 1
    assert conversations[0]["_id"] == sample_conversation_data["_id"]
    mock_db_instance.conversations_collection.find.assert_called_once_with({"user_id": "test_user_1"})


def test_get_conversation_by_id_with_user_id(mock_db_instance, sample_conversation_data):
    mock_db_instance.conversations_collection.find_one.return_value = sample_conversation_data
    conversation = mock_db_instance.get_conversation_by_id(str(sample_conversation_data["_id"]), "test_user_1")
    assert conversation["_id"] == sample_conversation_data["_id"]
    mock_db_instance.conversations_collection.find_one.assert_called_once_with(
        {"_id": sample_conversation_data["_id"], "user_id": "test_user_1"})


def test_get_conversation_by_id_without_user_id(mock_db_instance, sample_conversation_data):
    mock_db_instance.conversations_collection.find_one.return_value = sample_conversation_data
    conversation = mock_db_instance.get_conversation_by_id(str(sample_conversation_data["_id"]))
    assert conversation["_id"] == sample_conversation_data["_id"]
    mock_db_instance.conversations_collection.find_one.assert_called_once_with({"_id": sample_conversation_data["_id"]})


def test_check_conversation_exists(mock_db_instance, sample_conversation_data):
    mock_db_instance.conversations_collection.find_one.return_value = sample_conversation_data
    exists = mock_db_instance.check_conversation_exists(str(sample_conversation_data["_id"]))
    assert exists is True
    mock_db_instance.conversations_collection.find_one.assert_called_once_with({"_id": sample_conversation_data["_id"]})


def test_create_conversation(mock_db_instance):
    user_id = "test_user_1"
    title = "New Chat"
    messages = [
        {"role": "user", "content": "Hi", "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}]

    mock_insert_result = MagicMock()
    mock_insert_result.inserted_id = ObjectId()
    mock_db_instance.conversations_collection.insert_one.return_value = mock_insert_result

    new_conv = mock_db_instance.create_conversation(user_id, title, messages)

    assert new_conv["user_id"] == user_id
    assert new_conv["title"] == title
    assert new_conv["messages"] == messages
    assert new_conv["_id"] == mock_insert_result.inserted_id
    mock_db_instance.conversations_collection.insert_one.assert_called_once()


def test_update_conversation_success(mock_db_instance, sample_conversation_data):
    mock_db_instance.conversations_collection.update_one.return_value.matched_count = 1
    updated = mock_db_instance.update_conversation(str(sample_conversation_data["_id"]), "test_user_1",
                                                   {"title": "Updated Title"})
    assert updated is True
    mock_db_instance.conversations_collection.update_one.assert_called_once_with(
        {"_id": sample_conversation_data["_id"], "user_id": "test_user_1"},
        {"$set": {"title": "Updated Title"}}
    )


def test_update_conversation_not_found(mock_db_instance):
    mock_db_instance.conversations_collection.update_one.return_value.matched_count = 0
    updated = mock_db_instance.update_conversation(str(ObjectId()), "test_user_1", {"title": "Updated Title"})
    assert updated is False


# --- Tests for User/Auth Methods ---

def test_get_user_by_username(mock_db_instance, sample_user_data):
    mock_db_instance.users_collection.find_one.return_value = sample_user_data
    user = mock_db_instance.get_user_by_username("testuser")
    assert user["user_name"] == "testuser"
    mock_db_instance.users_collection.find_one.assert_called_once_with({"user_name": "testuser"})


def test_get_user_by_id(mock_db_instance, sample_user_data):
    mock_db_instance.users_collection.find_one.return_value = sample_user_data
    user = mock_db_instance.get_user_by_id(str(sample_user_data["_id"]))
    assert user["_id"] == sample_user_data["_id"]
    mock_db_instance.users_collection.find_one.assert_called_once_with({"_id": sample_user_data["_id"]})


def test_find_user_by_refresh_token(mock_db_instance, sample_user_data):
    token_hash = bcrypt.hash("refresh_token_abc")
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    sample_user_data["refresh_tokens"].append(
        {"token_hash": token_hash, "issued_at": datetime.now(timezone.utc), "expires_at": expires_at, "revoked": False})

    mock_db_instance.users_collection.find_one.return_value = sample_user_data
    user = mock_db_instance.find_user_by_refresh_token(token_hash)
    assert user["_id"] == sample_user_data["_id"]
    mock_db_instance.users_collection.find_one.assert_called_once()  # Check if called with elemMatch query


def test_add_refresh_token_to_user(mock_db_instance, sample_user_data):
    user_id = str(sample_user_data["_id"])
    token_hash = bcrypt.hash("new_refresh_token")
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    mock_db_instance.add_refresh_token_to_user(user_id, token_hash, expires_at)
    mock_db_instance.users_collection.update_one.assert_called_once()
    args, kwargs = mock_db_instance.users_collection.update_one.call_args
    assert args[0]["_id"] == ObjectId(user_id)
    assert "$push" in args[1]
    assert args[1]["$push"]["refresh_tokens"]["token_hash"] == token_hash


def test_revoke_refresh_token_success(mock_db_instance, sample_user_data):
    token_hash = bcrypt.hash("token_to_revoke")
    mock_db_instance.users_collection.update_one.return_value.matched_count = 1
    revoked = mock_db_instance.revoke_refresh_token(str(sample_user_data["_id"]), token_hash)
    assert revoked is True
    mock_db_instance.users_collection.update_one.assert_called_once_with(
        {"_id": sample_user_data["_id"], "refresh_tokens.token_hash": token_hash},
        {"$set": {"refresh_tokens.$.revoked": True}}
    )


def test_revoke_refresh_token_not_found(mock_db_instance, sample_user_data):
    token_hash = bcrypt.hash("non_existent_token")
    mock_db_instance.users_collection.update_one.return_value.matched_count = 0
    revoked = mock_db_instance.revoke_refresh_token(str(sample_user_data["_id"]), token_hash)
    assert revoked is False