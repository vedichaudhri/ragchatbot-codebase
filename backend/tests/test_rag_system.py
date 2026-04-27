"""
Tests for RAGSystem.query() with content-related questions in rag_system.py.

Covers: tool definitions forwarded to the AI, sources returned after tool use,
sources reset after retrieval, session history injected correctly, and the
response returned by the generator is surfaced to the caller.
"""
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_rag_system():
    """
    Build a RAGSystem with all heavy dependencies mocked out.
    Patches constructors so no ChromaDB, sentence-transformer, or
    Anthropic client is actually created.
    """
    with (
        patch("rag_system.DocumentProcessor"),
        patch("rag_system.VectorStore"),
        patch("rag_system.AIGenerator"),
        patch("rag_system.SessionManager"),
        patch("rag_system.ToolManager"),
        patch("rag_system.CourseSearchTool"),
        patch("rag_system.CourseOutlineTool"),
    ):
        from rag_system import RAGSystem

        cfg = MagicMock()
        cfg.ANTHROPIC_API_KEY = "test-key"
        cfg.ANTHROPIC_MODEL = "claude-test"
        cfg.CHROMA_PATH = "/tmp/chroma"
        cfg.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
        cfg.MAX_RESULTS = 5
        cfg.CHUNK_SIZE = 800
        cfg.CHUNK_OVERLAP = 100
        cfg.MAX_HISTORY = 2

        rag = RAGSystem(cfg)
    return rag


# ---------------------------------------------------------------------------
# query() — core orchestration
# ---------------------------------------------------------------------------

class TestQueryOrchestration:
    def test_generate_response_called_with_user_query(self):
        rag = make_rag_system()
        rag.ai_generator.generate_response.return_value = "test answer"
        rag.tool_manager.get_tool_definitions.return_value = []
        rag.tool_manager.get_last_sources.return_value = []

        rag.query("What is gradient descent?")

        call_kwargs = rag.ai_generator.generate_response.call_args[1]
        assert "gradient descent" in call_kwargs["query"]

    def test_tool_definitions_passed_to_generator(self):
        rag = make_rag_system()
        tool_defs = [{"name": "search_course_content", "description": "s", "input_schema": {}}]
        rag.tool_manager.get_tool_definitions.return_value = tool_defs
        rag.ai_generator.generate_response.return_value = "answer"
        rag.tool_manager.get_last_sources.return_value = []

        rag.query("What is backpropagation?")

        call_kwargs = rag.ai_generator.generate_response.call_args[1]
        assert call_kwargs["tools"] == tool_defs

    def test_tool_manager_passed_to_generator(self):
        rag = make_rag_system()
        rag.tool_manager.get_tool_definitions.return_value = []
        rag.ai_generator.generate_response.return_value = "answer"
        rag.tool_manager.get_last_sources.return_value = []

        rag.query("some question")

        call_kwargs = rag.ai_generator.generate_response.call_args[1]
        assert call_kwargs["tool_manager"] is rag.tool_manager

    def test_response_returned_to_caller(self):
        rag = make_rag_system()
        rag.tool_manager.get_tool_definitions.return_value = []
        rag.ai_generator.generate_response.return_value = "RAG is awesome."
        rag.tool_manager.get_last_sources.return_value = []

        response, _ = rag.query("explain RAG")
        assert response == "RAG is awesome."


# ---------------------------------------------------------------------------
# query() — sources lifecycle
# ---------------------------------------------------------------------------

class TestSourcesLifecycle:
    def test_sources_returned_from_tool_manager(self):
        rag = make_rag_system()
        rag.tool_manager.get_tool_definitions.return_value = []
        rag.ai_generator.generate_response.return_value = "answer"
        expected_sources = [{"text": "Python 101 - Lesson 3", "url": "https://example.com"}]
        rag.tool_manager.get_last_sources.return_value = expected_sources

        _, sources = rag.query("how do decorators work?")
        assert sources == expected_sources

    def test_sources_reset_after_retrieval(self):
        rag = make_rag_system()
        rag.tool_manager.get_tool_definitions.return_value = []
        rag.ai_generator.generate_response.return_value = "answer"
        rag.tool_manager.get_last_sources.return_value = []

        rag.query("some question")

        rag.tool_manager.reset_sources.assert_called_once()

    def test_reset_called_after_get_last_sources(self):
        """reset_sources must be called after get_last_sources, not before."""
        rag = make_rag_system()
        rag.tool_manager.get_tool_definitions.return_value = []
        rag.ai_generator.generate_response.return_value = "answer"

        call_order = []
        rag.tool_manager.get_last_sources.side_effect = lambda: call_order.append("get") or []
        rag.tool_manager.reset_sources.side_effect = lambda: call_order.append("reset")

        rag.query("q")
        assert call_order == ["get", "reset"]

    def test_empty_sources_returned_when_no_tool_called(self):
        rag = make_rag_system()
        rag.tool_manager.get_tool_definitions.return_value = []
        rag.ai_generator.generate_response.return_value = "general answer"
        rag.tool_manager.get_last_sources.return_value = []

        _, sources = rag.query("what is machine learning?")
        assert sources == []


# ---------------------------------------------------------------------------
# query() — session / conversation history
# ---------------------------------------------------------------------------

class TestSessionHandling:
    def test_no_history_when_no_session_id(self):
        rag = make_rag_system()
        rag.tool_manager.get_tool_definitions.return_value = []
        rag.ai_generator.generate_response.return_value = "answer"
        rag.tool_manager.get_last_sources.return_value = []

        rag.query("hello")

        call_kwargs = rag.ai_generator.generate_response.call_args[1]
        assert call_kwargs.get("conversation_history") is None

    def test_history_fetched_when_session_id_provided(self):
        rag = make_rag_system()
        rag.tool_manager.get_tool_definitions.return_value = []
        rag.ai_generator.generate_response.return_value = "answer"
        rag.tool_manager.get_last_sources.return_value = []
        rag.session_manager.get_conversation_history.return_value = "previous chat"

        rag.query("follow-up question", session_id="sess-123")

        rag.session_manager.get_conversation_history.assert_called_once_with("sess-123")
        call_kwargs = rag.ai_generator.generate_response.call_args[1]
        assert call_kwargs["conversation_history"] == "previous chat"

    def test_exchange_saved_after_response(self):
        rag = make_rag_system()
        rag.tool_manager.get_tool_definitions.return_value = []
        rag.ai_generator.generate_response.return_value = "my answer"
        rag.tool_manager.get_last_sources.return_value = []

        rag.query("what is backprop?", session_id="sess-456")

        rag.session_manager.add_exchange.assert_called_once_with(
            "sess-456", "what is backprop?", "my answer"
        )

    def test_exchange_not_saved_without_session(self):
        rag = make_rag_system()
        rag.tool_manager.get_tool_definitions.return_value = []
        rag.ai_generator.generate_response.return_value = "answer"
        rag.tool_manager.get_last_sources.return_value = []

        rag.query("stateless question")

        rag.session_manager.add_exchange.assert_not_called()


# ---------------------------------------------------------------------------
# query() — content-query specific scenarios
# ---------------------------------------------------------------------------

class TestContentQueryScenarios:
    def test_content_query_returns_answer_and_sources(self):
        rag = make_rag_system()
        rag.tool_manager.get_tool_definitions.return_value = [
            {"name": "search_course_content", "description": "search", "input_schema": {}}
        ]
        rag.ai_generator.generate_response.return_value = "Decorators wrap functions."
        rag.tool_manager.get_last_sources.return_value = [
            {"text": "Python 101 - Lesson 3", "url": "https://example.com/lesson3"}
        ]

        response, sources = rag.query("What are Python decorators?")

        assert response == "Decorators wrap functions."
        assert sources[0]["text"] == "Python 101 - Lesson 3"

    def test_unrelated_query_returns_answer_with_empty_sources(self):
        rag = make_rag_system()
        rag.tool_manager.get_tool_definitions.return_value = [
            {"name": "search_course_content", "description": "search", "input_schema": {}}
        ]
        rag.ai_generator.generate_response.return_value = "The sky is blue due to Rayleigh scattering."
        rag.tool_manager.get_last_sources.return_value = []

        response, sources = rag.query("Why is the sky blue?")

        assert "Rayleigh scattering" in response
        assert sources == []

    def test_query_string_wrapped_in_prompt_template(self):
        """RAGSystem wraps the raw query in a prompt before passing to the generator."""
        rag = make_rag_system()
        rag.tool_manager.get_tool_definitions.return_value = []
        rag.ai_generator.generate_response.return_value = "answer"
        rag.tool_manager.get_last_sources.return_value = []

        rag.query("explain neural networks")

        call_kwargs = rag.ai_generator.generate_response.call_args[1]
        # The raw user query should be embedded inside the prompt sent to the AI
        assert "explain neural networks" in call_kwargs["query"]
