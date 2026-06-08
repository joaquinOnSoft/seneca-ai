# -*- coding: utf-8 -*-
"""
Created on Wed Jun  3 06:40:11 2026

@author: NachoWorks
"""

import uvicorn
from orchestrator.app import app

if __name__ == "__main__":
    # Run the FastAPI server for the orchestrator
    uvicorn.run(app, host="0.0.0.0", port=8000)