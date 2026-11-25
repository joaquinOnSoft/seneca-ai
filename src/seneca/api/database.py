import logging
import sys
from datetime import datetime, timezone

from bson.objectid import ObjectId
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import ConnectionFailure, PyMongoError


class MongoDatabase:
    def __init__(self, mongo_uri, username=None, password=None, auth_source="admin"):
        self.mongo_uri = mongo_uri
        # Credentials are passed apart from the URI so they never end up in logs
        self._username = username
        self._password = password
        self._auth_source = auth_source
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
        if self._client is not None and self._db is not None:
            self.logger.info("MongoDB client already connected.")
            return

        try:
            credentials = {}
            if self._username:
                credentials = {"username": self._username, "password": self._password,
                               "authSource": self._auth_source}
            self._client = MongoClient(self.mongo_uri, **credentials)
            self._db = self._client.get_database()
            self.conversations_collection = self._db.conversations
            self.users_collection = self._db.users
            self.logger.info("MongoDB connected successfully.")
            self._ensure_indexes()
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

    def _ensure_indexes(self):
        # Index creation is idempotent; a failure must not prevent the API from starting
        try:
            self.conversations_collection.create_index(
                [("user_id", ASCENDING), ("created_at", DESCENDING)],
                name="user_id_created_at"
            )
            # The memory worker scans conversations by updated_at
            self.conversations_collection.create_index([("updated_at", ASCENDING)], name="updated_at")
        except PyMongoError as e:
            self.logger.warning(f"Could not create MongoDB indexes: {e}")

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
    def get_conversations(self, user_id, skip=0, limit=20, include_messages=False):
        if self.conversations_collection is None:
            raise PyMongoError("Conversations collection not initialized.")
        # pending_turn (seneca.api.chat) and memory (seneca.memory) are internal state, never listed
        internal = {"pending_turn": 0, "memory": 0}
        projection = internal if include_messages else {"messages": 0, **internal}
        return list(self.conversations_collection.find(
            {"user_id": user_id}, projection
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
        now = datetime.now(timezone.utc)
        new_conversation = {
            "user_id": user_id,
            "title": title,
            "created_at": now,
            "updated_at": now,
            "messages": messages
        }
        result = self.conversations_collection.insert_one(new_conversation)
        new_conversation['_id'] = result.inserted_id
        return new_conversation

    def update_conversation(self, conv_id_str, user_id, update_fields):
        if self.conversations_collection is None:
            raise PyMongoError("Conversations collection not initialized.")
        update = {"$set": {**update_fields, "updated_at": datetime.now(timezone.utc)}}
        if "messages" in update_fields:
            # Messages replaced: the memory worker must index the conversation again
            update["$unset"] = {"memory": ""}
        result = self.conversations_collection.update_one(
            {"_id": ObjectId(conv_id_str), "user_id": user_id}, update
        )
        return result.matched_count > 0

    def append_messages(self, conv_id_str, user_id, messages):
        if self.conversations_collection is None:
            raise PyMongoError("Conversations collection not initialized.")
        result = self.conversations_collection.update_one(
            {"_id": ObjectId(conv_id_str), "user_id": user_id},
            {"$push": {"messages": {"$each": messages}},
             "$set": {"updated_at": datetime.now(timezone.utc)}}
        )
        return result.matched_count > 0

    def set_pending_turn(self, conv_id_str, user_id, pending_turn):
        """Store the state of a chat turn that is waiting for client-side tool results."""
        if self.conversations_collection is None:
            raise PyMongoError("Conversations collection not initialized.")
        result = self.conversations_collection.update_one(
            {"_id": ObjectId(conv_id_str), "user_id": user_id},
            {"$set": {"pending_turn": pending_turn, "updated_at": datetime.now(timezone.utc)}}
        )
        return result.matched_count > 0

    def finish_turn(self, conv_id_str, user_id, messages):
        """Append the messages produced by a chat turn and drop its pending state, atomically."""
        if self.conversations_collection is None:
            raise PyMongoError("Conversations collection not initialized.")
        update = {"$unset": {"pending_turn": ""},
                  "$set": {"updated_at": datetime.now(timezone.utc)}}
        if messages:
            update["$push"] = {"messages": {"$each": messages}}
        result = self.conversations_collection.update_one(
            {"_id": ObjectId(conv_id_str), "user_id": user_id}, update
        )
        return result.matched_count > 0

    # --- Memory index state (see seneca.memory.indexer) ---
    def conversations_to_index(self, collection, limit=20):
        """Conversations whose turns are not (fully) in the Qdrant *collection* yet.

        Skips the ones waiting for tool results: their turn is not finished.
        """
        if self.conversations_collection is None:
            raise PyMongoError("Conversations collection not initialized.")
        query = {
            "pending_turn": {"$exists": False},
            "$or": [
                {"memory.collection": {"$ne": collection}},
                {"$expr": {"$lt": ["$memory.synced_at", "$updated_at"]}},
            ],
        }
        return list(self.conversations_collection.find(query).sort("updated_at", ASCENDING).limit(limit))

    def set_memory_state(self, conv_id_str, memory):
        """Store the indexing state of a conversation (does not touch updated_at)."""
        if self.conversations_collection is None:
            raise PyMongoError("Conversations collection not initialized.")
        self.conversations_collection.update_one({"_id": ObjectId(conv_id_str)}, {"$set": {"memory": memory}})

    def existing_conversation_ids(self, conv_id_strs):
        """The subset of *conv_id_strs* that still exist."""
        if self.conversations_collection is None:
            raise PyMongoError("Conversations collection not initialized.")
        object_ids = [ObjectId(i) for i in conv_id_strs if ObjectId.is_valid(i)]
        found = self.conversations_collection.find({"_id": {"$in": object_ids}}, {"_id": 1})
        return {str(doc["_id"]) for doc in found}

    def reset_memory_state(self):
        """Mark every conversation as not indexed (re-index from scratch)."""
        if self.conversations_collection is None:
            raise PyMongoError("Conversations collection not initialized.")
        return self.conversations_collection.update_many({}, {"$unset": {"memory": ""}}).modified_count

    def delete_conversation(self, conv_id_str, user_id):
        if self.conversations_collection is None:
            raise PyMongoError("Conversations collection not initialized.")
        result = self.conversations_collection.delete_one(
            {"_id": ObjectId(conv_id_str), "user_id": user_id}
        )
        return result.deleted_count > 0

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