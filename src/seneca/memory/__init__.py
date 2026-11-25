"""
seneca.memory – Long-term memory: search across the user's past conversations.

MongoDB stays the source of truth. A background worker
(:mod:`seneca.memory.worker`) splits every conversation into turns (a user
message plus the assistant's reply), embeds them with an Ollama embedding
model and stores them in Qdrant. When the user writes, the chat service
(:mod:`seneca.api.chat`) searches Qdrant for related turns of *other*
conversations of the same user and adds them to the prompt.

Qdrant is a disposable index: it can always be rebuilt from MongoDB
(``python -m seneca.memory.worker --reindex``).

See docs/memory.md.
"""
