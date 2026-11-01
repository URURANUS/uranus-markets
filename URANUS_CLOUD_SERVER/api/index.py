import os
import sys

# Ensure parent directory is in Python path to import main, core, markets, store
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
