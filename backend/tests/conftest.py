import sys
import os
from unittest.mock import MagicMock
import pytest

# Ensure the backend directory is on sys.path so test files can import backend modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def sample_sources():
    return [
        {"text": "Python 101 - Lesson 1", "url": "https://example.com/lesson1"},
        {"text": "Python 101 - Lesson 2", "url": "https://example.com/lesson2"},
    ]


@pytest.fixture
def mock_rag_system(sample_sources):
    """Pre-configured RAGSystem mock with sensible defaults."""
    rag = MagicMock()
    rag.session_manager.create_session.return_value = "test-session-id"
    rag.query.return_value = ("Test answer.", sample_sources)
    rag.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["Python 101", "ML Fundamentals"],
    }
    return rag
