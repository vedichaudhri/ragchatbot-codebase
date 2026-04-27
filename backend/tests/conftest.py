import sys
import os

# Ensure the backend directory is on sys.path so test files can import backend modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
