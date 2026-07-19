"""
Vercel serverless bridge — adds backend/ to sys.path then imports app.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from main import app
