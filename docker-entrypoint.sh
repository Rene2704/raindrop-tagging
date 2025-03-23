#!/bin/bash

# Start the FastAPI server in the background
uvicorn raindrop_information_extaction.api:app --host 0.0.0.0 --port 8000 &

# Start the Streamlit frontend
streamlit run raindrop_information_extaction/frontend.py --server.port 8501 --server.address 0.0.0.0 