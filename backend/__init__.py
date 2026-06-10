"""
Backend package exports.

Avoid importing submodules at package import time to prevent circular
imports when Streamlit loads the app. Import submodules explicitly where
they are needed (for example: `from backend import auth`).
"""

__all__ = []
