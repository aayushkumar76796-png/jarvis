#!/usr/bin/env bash
# Starts Jarvis on THIS PC with PC control ON, reachable from your tablet on the same Wi-Fi.
export JARVIS_LOCAL=1
pip install -r requirements.txt -r requirements-local.txt
streamlit run Jarvis.py --server.address 0.0.0.0
