# -*- coding: utf-8 -*-
"""
Created on Sat May 30 06:42:30 2026

@author: NachoWorks
"""

from typing import Dict, List

class ContextManager:
    def __init__(self):
        # Initialize a dictionary to store conversation contexts for each user
        self.contexts: Dict[str, List[Dict]] = {}

    def get_context(self, user_id: str) -> Dict:
        """
        Retrieve the conversation context for a specific user.

        Args:
            user_id (str): Unique identifier for the user.

        Returns:
            Dict: Context containing conversation history.
        """
        return {"history": self.contexts.get(user_id, [])}

    def update_context(self, user_id: str, query: str, response: str):
        """
        Update the conversation context for a user with the latest query and response.

        Args:
            user_id (str): Unique identifier for the user.
            query (str): User's latest query.
            response (str): Model's response to the query.
        """
        if user_id not in self.contexts:
            self.contexts[user_id] = []
        self.contexts[user_id].append({"query": query, "response": response})