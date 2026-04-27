"""
Tests for the FastAPI endpoints defined in app.py.

Uses an inline test app that mirrors the real endpoints without the static-file
mount, which requires a ../frontend directory that does not exist in CI/test
environments.  Business logic (RAGSystem, AIGenerator, etc.) is mocked so these
tests focus on HTTP routing, request validation, response shape, and error
propagation.
"""
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from typing import List, Optional
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Pydantic models (mirror app.py)
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    sources: List[dict]
    session_id: str


class CourseStats(BaseModel):
    total_courses: int
    course_titles: List[str]


# ---------------------------------------------------------------------------
# Test app (no StaticFiles mount)
# ---------------------------------------------------------------------------

# Module-level mock swapped in per test via the reset_rag fixture below.
_rag = MagicMock()

app = FastAPI(title="Test RAG App")


@app.post("/api/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest):
    try:
        session_id = request.session_id
        if not session_id:
            session_id = _rag.session_manager.create_session()
        answer, sources = _rag.query(request.query, session_id)
        return QueryResponse(answer=answer, sources=sources, session_id=session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/courses", response_model=CourseStats)
async def get_course_stats():
    try:
        analytics = _rag.get_course_analytics()
        return CourseStats(
            total_courses=analytics["total_courses"],
            course_titles=analytics["course_titles"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str):
    _rag.session_manager.clear_session(session_id)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_rag():
    """Reset the module-level mock before each test and apply sensible defaults."""
    _rag.reset_mock()
    _rag.session_manager.create_session.return_value = "generated-session-id"
    _rag.query.return_value = ("Default answer.", [])
    _rag.get_course_analytics.return_value = {
        "total_courses": 0,
        "course_titles": [],
    }
    yield


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# POST /api/query
# ---------------------------------------------------------------------------

class TestQueryEndpoint:
    def test_successful_query_returns_200(self, client):
        response = client.post("/api/query", json={"query": "What is Python?"})
        assert response.status_code == 200

    def test_response_shape_matches_schema(self, client):
        _rag.query.return_value = ("A helpful answer.", [])
        _rag.session_manager.create_session.return_value = "sess-abc"

        data = client.post("/api/query", json={"query": "explain loops"}).json()

        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data

    def test_creates_session_when_none_provided(self, client):
        _rag.session_manager.create_session.return_value = "new-session-123"
        _rag.query.return_value = ("answer", [])

        data = client.post("/api/query", json={"query": "hello"}).json()

        _rag.session_manager.create_session.assert_called_once()
        assert data["session_id"] == "new-session-123"

    def test_uses_provided_session_id(self, client):
        _rag.query.return_value = ("answer", [])

        data = client.post(
            "/api/query", json={"query": "follow-up", "session_id": "existing-sess"}
        ).json()

        _rag.session_manager.create_session.assert_not_called()
        assert data["session_id"] == "existing-sess"

    def test_answer_from_rag_system_returned(self, client):
        _rag.query.return_value = ("RAG is Retrieval-Augmented Generation.", [])

        data = client.post("/api/query", json={"query": "what is RAG?"}).json()

        assert data["answer"] == "RAG is Retrieval-Augmented Generation."

    def test_sources_from_rag_system_returned(self, client):
        sources = [{"text": "Python 101 - Lesson 1", "url": "https://example.com"}]
        _rag.query.return_value = ("answer", sources)

        data = client.post("/api/query", json={"query": "decorators"}).json()

        assert data["sources"] == sources

    def test_missing_query_field_returns_422(self, client):
        response = client.post("/api/query", json={"session_id": "sess-1"})
        assert response.status_code == 422

    def test_empty_body_returns_422(self, client):
        response = client.post("/api/query", json={})
        assert response.status_code == 422

    def test_rag_error_returns_500(self, client):
        _rag.query.side_effect = RuntimeError("DB unavailable")

        response = client.post("/api/query", json={"query": "anything"})

        assert response.status_code == 500
        assert "DB unavailable" in response.json()["detail"]

    def test_query_forwarded_to_rag_system(self, client):
        _rag.query.return_value = ("answer", [])
        _rag.session_manager.create_session.return_value = "s1"

        client.post("/api/query", json={"query": "explain backprop"})

        call_args = _rag.query.call_args
        assert call_args[0][0] == "explain backprop"

    def test_wrong_http_method_returns_405(self, client):
        response = client.get("/api/query")
        assert response.status_code == 405


# ---------------------------------------------------------------------------
# GET /api/courses
# ---------------------------------------------------------------------------

class TestCoursesEndpoint:
    def test_successful_returns_200(self, client):
        _rag.get_course_analytics.return_value = {
            "total_courses": 3,
            "course_titles": ["A", "B", "C"],
        }
        response = client.get("/api/courses")
        assert response.status_code == 200

    def test_response_shape_matches_schema(self, client):
        _rag.get_course_analytics.return_value = {
            "total_courses": 1,
            "course_titles": ["Python 101"],
        }

        data = client.get("/api/courses").json()

        assert "total_courses" in data
        assert "course_titles" in data

    def test_total_courses_count_returned(self, client):
        _rag.get_course_analytics.return_value = {
            "total_courses": 5,
            "course_titles": ["A", "B", "C", "D", "E"],
        }

        data = client.get("/api/courses").json()

        assert data["total_courses"] == 5

    def test_course_titles_list_returned(self, client):
        titles = ["Python 101", "ML Fundamentals"]
        _rag.get_course_analytics.return_value = {
            "total_courses": 2,
            "course_titles": titles,
        }

        data = client.get("/api/courses").json()

        assert data["course_titles"] == titles

    def test_empty_catalog_returns_zero_courses(self, client):
        _rag.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": [],
        }

        data = client.get("/api/courses").json()

        assert data["total_courses"] == 0
        assert data["course_titles"] == []

    def test_rag_error_returns_500(self, client):
        _rag.get_course_analytics.side_effect = RuntimeError("analytics failed")

        response = client.get("/api/courses")

        assert response.status_code == 500
        assert "analytics failed" in response.json()["detail"]

    def test_wrong_http_method_returns_405(self, client):
        response = client.post("/api/courses")
        assert response.status_code == 405


# ---------------------------------------------------------------------------
# DELETE /api/session/{session_id}
# ---------------------------------------------------------------------------

class TestDeleteSessionEndpoint:
    def test_successful_delete_returns_200(self, client):
        response = client.delete("/api/session/sess-abc")
        assert response.status_code == 200

    def test_response_body_is_ok_status(self, client):
        data = client.delete("/api/session/sess-abc").json()
        assert data == {"status": "ok"}

    def test_calls_clear_session_with_correct_id(self, client):
        client.delete("/api/session/my-session-id")
        _rag.session_manager.clear_session.assert_called_once_with("my-session-id")

    def test_different_session_ids_forwarded_correctly(self, client):
        client.delete("/api/session/session-xyz")
        _rag.session_manager.clear_session.assert_called_once_with("session-xyz")
