"""
Tests for CourseSearchTool.execute() in search_tools.py.

Covers: query dispatch, course/lesson filters, empty/error results,
formatted output structure, and last_sources tracking.
"""
import pytest
from unittest.mock import MagicMock, patch
from search_tools import CourseSearchTool
from vector_store import SearchResults


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_store(documents=None, metadata=None, error=None):
    """Return a mocked VectorStore pre-configured with search results."""
    store = MagicMock()
    if error:
        store.search.return_value = SearchResults(
            documents=[], metadata=[], distances=[], error=error
        )
    else:
        docs = documents or []
        metas = metadata or []
        dists = [0.1] * len(docs)
        store.search.return_value = SearchResults(
            documents=docs, metadata=metas, distances=dists
        )
    return store


# ---------------------------------------------------------------------------
# execute() — argument forwarding
# ---------------------------------------------------------------------------

class TestExecuteArguments:
    def test_query_only_passed_to_store(self):
        store = make_store(documents=["chunk text"], metadata=[{"course_title": "Python 101"}])
        tool = CourseSearchTool(store)
        tool.execute(query="what is a decorator")
        store.search.assert_called_once_with(
            query="what is a decorator",
            course_name=None,
            lesson_number=None,
        )

    def test_course_name_filter_forwarded(self):
        store = make_store(documents=["chunk"], metadata=[{"course_title": "Python 101"}])
        tool = CourseSearchTool(store)
        tool.execute(query="decorators", course_name="Python")
        _, kwargs = store.search.call_args
        assert kwargs["course_name"] == "Python"

    def test_lesson_number_filter_forwarded(self):
        store = make_store(documents=["chunk"], metadata=[{"course_title": "Python 101", "lesson_number": 3}])
        tool = CourseSearchTool(store)
        tool.execute(query="loops", lesson_number=3)
        _, kwargs = store.search.call_args
        assert kwargs["lesson_number"] == 3

    def test_both_filters_forwarded(self):
        store = make_store(
            documents=["chunk"],
            metadata=[{"course_title": "Python 101", "lesson_number": 2}],
        )
        tool = CourseSearchTool(store)
        tool.execute(query="lists", course_name="Python", lesson_number=2)
        _, kwargs = store.search.call_args
        assert kwargs["course_name"] == "Python"
        assert kwargs["lesson_number"] == 2


# ---------------------------------------------------------------------------
# execute() — empty / error result handling
# ---------------------------------------------------------------------------

class TestExecuteEdgeCases:
    def test_returns_error_message_when_results_contain_error(self):
        store = make_store(error="No course found matching 'Ghost'")
        tool = CourseSearchTool(store)
        result = tool.execute(query="anything", course_name="Ghost")
        assert result == "No course found matching 'Ghost'"

    def test_empty_results_no_filter(self):
        store = make_store()
        tool = CourseSearchTool(store)
        result = tool.execute(query="unknown topic")
        assert result == "No relevant content found."

    def test_empty_results_with_course_name(self):
        store = make_store()
        tool = CourseSearchTool(store)
        result = tool.execute(query="unknown topic", course_name="Python")
        assert "Python" in result
        assert "No relevant content found" in result

    def test_empty_results_with_lesson_number(self):
        store = make_store()
        tool = CourseSearchTool(store)
        result = tool.execute(query="unknown topic", lesson_number=5)
        assert "lesson 5" in result.lower()

    def test_empty_results_with_both_filters(self):
        store = make_store()
        tool = CourseSearchTool(store)
        result = tool.execute(query="x", course_name="ML", lesson_number=2)
        assert "ML" in result
        assert "2" in result


# ---------------------------------------------------------------------------
# execute() — formatted output
# ---------------------------------------------------------------------------

class TestExecuteOutput:
    def test_output_contains_course_title(self):
        store = make_store(
            documents=["Some lesson text."],
            metadata=[{"course_title": "Python 101"}],
        )
        tool = CourseSearchTool(store)
        result = tool.execute(query="decorators")
        assert "Python 101" in result

    def test_output_contains_lesson_number_when_present(self):
        store = make_store(
            documents=["Lesson content."],
            metadata=[{"course_title": "Python 101", "lesson_number": 4}],
        )
        tool = CourseSearchTool(store)
        result = tool.execute(query="decorators")
        assert "Lesson 4" in result

    def test_output_does_not_show_lesson_when_absent(self):
        store = make_store(
            documents=["Course intro."],
            metadata=[{"course_title": "Python 101"}],
        )
        tool = CourseSearchTool(store)
        result = tool.execute(query="intro")
        assert "Lesson" not in result

    def test_multiple_results_all_appear_in_output(self):
        store = make_store(
            documents=["Doc A", "Doc B"],
            metadata=[
                {"course_title": "Course A", "lesson_number": 1},
                {"course_title": "Course B", "lesson_number": 2},
            ],
        )
        tool = CourseSearchTool(store)
        result = tool.execute(query="topic")
        assert "Doc A" in result
        assert "Doc B" in result
        assert "Course A" in result
        assert "Course B" in result


# ---------------------------------------------------------------------------
# last_sources tracking
# ---------------------------------------------------------------------------

class TestLastSources:
    def test_sources_empty_initially(self):
        store = make_store()
        tool = CourseSearchTool(store)
        assert tool.last_sources == []

    def test_sources_populated_after_successful_search(self):
        store = make_store(
            documents=["content"],
            metadata=[{"course_title": "Python 101", "lesson_number": 2}],
        )
        store.get_lesson_link.return_value = "https://example.com/lesson2"
        tool = CourseSearchTool(store)
        tool.execute(query="topic")
        assert len(tool.last_sources) == 1
        assert tool.last_sources[0]["text"] == "Python 101 - Lesson 2"
        assert tool.last_sources[0]["url"] == "https://example.com/lesson2"

    def test_sources_include_course_title_only_when_no_lesson(self):
        store = make_store(
            documents=["intro"],
            metadata=[{"course_title": "Python 101"}],
        )
        tool = CourseSearchTool(store)
        tool.execute(query="intro")
        assert tool.last_sources[0]["text"] == "Python 101"
        assert tool.last_sources[0]["url"] is None

    def test_sources_updated_on_each_call(self):
        store = MagicMock()
        store.search.side_effect = [
            SearchResults(
                documents=["first"],
                metadata=[{"course_title": "Course 1"}],
                distances=[0.1],
            ),
            SearchResults(
                documents=["second"],
                metadata=[{"course_title": "Course 2"}],
                distances=[0.1],
            ),
        ]
        tool = CourseSearchTool(store)
        tool.execute(query="first query")
        tool.execute(query="second query")
        assert tool.last_sources[0]["text"] == "Course 2"

    def test_sources_empty_after_empty_results(self):
        store = make_store()
        tool = CourseSearchTool(store)
        tool.last_sources = [{"text": "stale", "url": None}]
        tool.execute(query="nothing")
        # Empty results should overwrite last_sources with empty list
        assert tool.last_sources == []
