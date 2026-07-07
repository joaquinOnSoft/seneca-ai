import logging
import sys
from datetime import datetime, timezone

from bson.objectid import ObjectId
from seneca.utils.passlib_bcrypt_fix import _passlib_bcrypt_module  # noqa: F401 — "Applies the patch via side effect
# noinspection PyUnresolvedReferences
from passlib.hash import bcrypt

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, PyMongoError


class MongoDatabase:
    def __init__(self, mongo_uri):
        self.mongo_uri = mongo_uri
        self._client = None
        self._db = None
        self.conversations_collection = None
        self.users_collection = None
        self._is_mock = False # Flag to indicate if this is a mock instance

        # Configure logger for this class
        self.logger = logging.getLogger(self.__class__.__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def connect(self):
        if self._client and self._db:
            self.logger.info("MongoDB client already connected.")
            return

        try:
            self._client = MongoClient(self.mongo_uri)
            self._db = self._client.get_database()
            self.conversations_collection = self._db.conversations
            self.users_collection = self._db.users
            self.logger.info("MongoDB connected successfully.")
        except ConnectionFailure as e:
            self.logger.error(f"Failed to connect to MongoDB: {e}", exc_info=True)
            self._client = None
            self._db = None
            self.conversations_collection = None
            self.users_collection = None
            raise # Re-raise to indicate connection failure
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during MongoDB connection: {e}", exc_info=True)
            self._client = None
            self._db = None
            self.conversations_collection = None
            self.users_collection = None
            raise

    def is_connected(self):
        if self._is_mock: # Mock instances are always considered "connected" for testing purposes
            return True
        return self._client is not None and self._db is not None

    def close(self):
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
            self.conversations_collection = None
            self.users_collection = None
            self.logger.info("MongoDB connection closed.")

    # --- Conversation Methods ---
    def get_conversations(self, user_id, skip=0, limit=20):
        if self.conversations_collection is None:
            raise PyMongoError("Conversations collection not initialized.")
        return list(self.conversations_collection.find(
            {"user_id": user_id}
        ).sort("created_at", -1).skip(skip).limit(limit))

    def get_conversation_by_id(self, conv_id_str, user_id=None):
        if self.conversations_collection is None:
            raise PyMongoError("Conversations collection not initialized.")
        query = {"_id": ObjectId(conv_id_str)}
        if user_id:
            query["user_id"] = user_id
        return self.conversations_collection.find_one(query)

    def check_conversation_exists(self, conv_id_str):
        if self.conversations_collection is None:
            raise PyMongoError("Conversations collection not initialized.")
        return self.conversations_collection.find_one({"_id": ObjectId(conv_id_str)}) is not None

    def create_conversation(self, user_id, title, messages):
        if self.conversations_collection is None:
            raise PyMongoError("Conversations collection not initialized.")
        new_conversation = {
            "user_id": user_id,
            "title": title,
            "created_at": datetime.now(timezone.utc),
            "messages": messages
        }
        result = self.conversations_collection.insert_one(new_conversation)
        new_conversation['_id'] = result.inserted_id
        return new_conversation

    def update_conversation(self, conv_id_str, user_id, update_fields):
        if self.conversations_collection is None:
            raise PyMongoError("Conversations collection not initialized.")
        result = self.conversations_collection.update_one(
            {"_id": ObjectId(conv_id_str), "user_id": user_id},
            {"$set": update_fields}
        )
        return result.matched_count > 0

    # --- User/Auth Methods ---
    def get_user_by_username(self, username):
        if self.users_collection is None:
            raise PyMongoError("Users collection not initialized.")
        return self.users_collection.find_one({"user_name": username})

    def get_user_by_id(self, user_id):
        if self.users_collection is None:
            raise PyMongoError("Users collection not initialized.")
        return self.users_collection.find_one({"_id": ObjectId(user_id)})

    def find_user_by_refresh_token(self, refresh_token_hash):
        if self.users_collection is None:
            raise PyMongoError("Users collection not initialized.")
        # Find user where any refresh token matches the hash and is not revoked and not expired
        return self.users_collection.find_one({
            "refresh_tokens": {
                "$elemMatch": {
                    "token_hash": refresh_token_hash,
                    "expires_at": {"$gt": datetime.now(timezone.utc)},
                    "revoked": False
                }
            }
        })

    def add_refresh_token_to_user(self, user_id, token_hash, expires_at):
        if self.users_collection is None:
            raise PyMongoError("Users collection not initialized.")
        self.users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$push": {"refresh_tokens": {
                "token_hash": token_hash,
                "issued_at": datetime.now(timezone.utc),
                "expires_at": expires_at,
                "revoked": False
            }}}
        )

    def revoke_refresh_token(self, user_id, token_hash):
        if self.users_collection is None:
            raise PyMongoError("Users collection not initialized.")
        result = self.users_collection.update_one(
            {"_id": ObjectId(user_id), "refresh_tokens.token_hash": token_hash},
            {"$set": {"refresh_tokens.$.revoked": True}}
        )
        return result.matched_count > 0