"""
Tests for AIGenerator's tool-calling behaviour in ai_generator.py.

Covers: tools are passed to the API, the two-call loop triggers on tool_use,
tool_manager.execute_tool is invoked with the right arguments, and the
final response text is returned correctly.
"""
import pytest
from unittest.mock import MagicMock, patch, call
from ai_generator import AIGenerator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_generator():
    """Return an AIGenerator with a mocked Anthropic client."""
    with patch("ai_generator.anthropic.Anthropic"):
        gen = AIGenerator(api_key="test-key", model="claude-test-model")
    return gen


def make_text_response(text="Final answer."):
    """Simulate a Claude response that returns text directly (no tool use)."""
    content_block = MagicMock()
    content_block.type = "text"
    content_block.text = text
    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = [content_block]
    return response


def make_tool_use_response(tool_name="search_course_content", tool_input=None, tool_id="tu_001"):
    """Simulate a Claude response that requests a tool call."""
    if tool_input is None:
        tool_input = {"query": "what is RAG"}
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = tool_name
    tool_block.input = tool_input
    tool_block.id = tool_id
    response = MagicMock()
    response.stop_reason = "tool_use"
    response.content = [tool_block]
    return response


# ---------------------------------------------------------------------------
# Direct (no-tool) response path
# ---------------------------------------------------------------------------

class TestDirectResponse:
    def test_returns_text_when_no_tools_provided(self):
        gen = make_generator()
        gen.client.messages.create.return_value = make_text_response("Hello world.")
        result = gen.generate_response(query="What is Python?")
        assert result == "Hello world."

    def test_tools_not_in_api_params_when_not_provided(self):
        gen = make_generator()
        gen.client.messages.create.return_value = make_text_response()
        gen.generate_response(query="General question")
        call_kwargs = gen.client.messages.create.call_args[1]
        assert "tools" not in call_kwargs
        assert "tool_choice" not in call_kwargs

    def test_system_prompt_always_included(self):
        gen = make_generator()
        gen.client.messages.create.return_value = make_text_response()
        gen.generate_response(query="hello")
        call_kwargs = gen.client.messages.create.call_args[1]
        assert "system" in call_kwargs
        assert len(call_kwargs["system"]) > 0

    def test_conversation_history_appended_to_system_prompt(self):
        gen = make_generator()
        gen.client.messages.create.return_value = make_text_response()
        gen.generate_response(query="follow-up", conversation_history="User: Hi\nAssistant: Hello")
        call_kwargs = gen.client.messages.create.call_args[1]
        assert "Previous conversation" in call_kwargs["system"]
        assert "User: Hi" in call_kwargs["system"]


# ---------------------------------------------------------------------------
# Tool-calling path: first API call
# ---------------------------------------------------------------------------

class TestToolCallFirstRequest:
    def test_tools_added_to_api_call_when_provided(self):
        gen = make_generator()
        tool_defs = [{"name": "search_course_content", "description": "search", "input_schema": {}}]
        gen.client.messages.create.return_value = make_text_response()
        gen.generate_response(query="search something", tools=tool_defs, tool_manager=MagicMock())
        call_kwargs = gen.client.messages.create.call_args[1]
        assert call_kwargs["tools"] == tool_defs

    def test_tool_choice_set_to_auto(self):
        gen = make_generator()
        tool_defs = [{"name": "search_course_content", "description": "search", "input_schema": {}}]
        gen.client.messages.create.return_value = make_text_response()
        gen.generate_response(query="q", tools=tool_defs, tool_manager=MagicMock())
        call_kwargs = gen.client.messages.create.call_args[1]
        assert call_kwargs["tool_choice"] == {"type": "auto"}


# ---------------------------------------------------------------------------
# Tool-calling path: two-call loop
# ---------------------------------------------------------------------------

class TestTwoCallLoop:
    def test_tool_manager_execute_called_on_tool_use_stop(self):
        gen = make_generator()
        tool_input = {"query": "what is RAG", "course_name": "AI Course"}
        first_resp = make_tool_use_response(tool_input=tool_input)
        second_resp = make_text_response("RAG stands for Retrieval-Augmented Generation.")
        gen.client.messages.create.side_effect = [first_resp, second_resp]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "Search result text"
        tool_defs = [{"name": "search_course_content", "description": "s", "input_schema": {}}]

        result = gen.generate_response(query="explain RAG", tools=tool_defs, tool_manager=tool_manager)

        tool_manager.execute_tool.assert_called_once_with(
            "search_course_content", **tool_input
        )
        assert result == "RAG stands for Retrieval-Augmented Generation."

    def test_two_api_calls_made_when_tool_is_used(self):
        gen = make_generator()
        first_resp = make_tool_use_response()
        second_resp = make_text_response("Done.")
        gen.client.messages.create.side_effect = [first_resp, second_resp]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "tool output"
        tool_defs = [{"name": "search_course_content", "description": "s", "input_schema": {}}]

        gen.generate_response(query="q", tools=tool_defs, tool_manager=tool_manager)

        assert gen.client.messages.create.call_count == 2

    def test_tool_result_injected_as_user_message_in_second_call(self):
        gen = make_generator()
        first_resp = make_tool_use_response(tool_id="tu_abc")
        second_resp = make_text_response("Answer.")
        gen.client.messages.create.side_effect = [first_resp, second_resp]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "search result"
        tool_defs = [{"name": "search_course_content", "description": "s", "input_schema": {}}]

        gen.generate_response(query="q", tools=tool_defs, tool_manager=tool_manager)

        second_call_kwargs = gen.client.messages.create.call_args_list[1][1]
        messages = second_call_kwargs["messages"]
        # Last message should be the user-role tool_result
        tool_result_msg = messages[-1]
        assert tool_result_msg["role"] == "user"
        result_content = tool_result_msg["content"]
        assert isinstance(result_content, list)
        assert result_content[0]["type"] == "tool_result"
        assert result_content[0]["tool_use_id"] == "tu_abc"
        assert result_content[0]["content"] == "search result"

    def test_synthesis_call_does_not_include_tools(self):
        # Synthesis call only fires when both rounds exhaust — requires 4 responses:
        # generate_response(r1 tool_use) → loop r1(r2 tool_use) → loop r2(r3 tool_use) → synthesis(r4 text)
        gen = make_generator()
        r1 = make_tool_use_response(tool_id="tu_001")
        r2 = make_tool_use_response(tool_id="tu_002")
        r3 = make_tool_use_response(tool_id="tu_003")
        r4 = make_text_response("Final.")
        gen.client.messages.create.side_effect = [r1, r2, r3, r4]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "result"
        tool_defs = [{"name": "search_course_content", "description": "s", "input_schema": {}}]

        gen.generate_response(query="q", tools=tool_defs, tool_manager=tool_manager)

        assert gen.client.messages.create.call_count == 4
        synthesis_kwargs = gen.client.messages.create.call_args_list[-1][1]
        assert "tools" not in synthesis_kwargs
        assert "tool_choice" not in synthesis_kwargs

    def test_returns_final_text_after_tool_execution(self):
        gen = make_generator()
        first_resp = make_tool_use_response()
        second_resp = make_text_response("The final answer is 42.")
        gen.client.messages.create.side_effect = [first_resp, second_resp]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "some search result"
        tool_defs = [{"name": "search_course_content", "description": "s", "input_schema": {}}]

        result = gen.generate_response(query="q", tools=tool_defs, tool_manager=tool_manager)
        assert result == "The final answer is 42."

    def test_no_tool_execution_when_stop_reason_is_end_turn(self):
        gen = make_generator()
        gen.client.messages.create.return_value = make_text_response("Direct answer.")

        tool_manager = MagicMock()
        tool_defs = [{"name": "search_course_content", "description": "s", "input_schema": {}}]

        result = gen.generate_response(query="q", tools=tool_defs, tool_manager=tool_manager)

        tool_manager.execute_tool.assert_not_called()
        assert result == "Direct answer."
        assert gen.client.messages.create.call_count == 1


# ---------------------------------------------------------------------------
# Multi-round tool calling
# ---------------------------------------------------------------------------

class TestMultiRoundToolCalling:
    def _run(self, side_effects, tool_defs=None, tool_input_1=None, tool_input_2=None):
        """Helper: configure generator with given side effects and run."""
        gen = make_generator()
        gen.client.messages.create.side_effect = side_effects
        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "tool result"
        defs = tool_defs or [{"name": "search_course_content", "description": "s", "input_schema": {}}]
        gen.generate_response(query="q", tools=defs, tool_manager=tool_manager)
        return gen, tool_manager

    def test_three_api_calls_on_two_tool_rounds(self):
        r1 = make_tool_use_response(tool_id="tu_001")
        r2 = make_tool_use_response(tool_name="get_course_outline", tool_id="tu_002")
        r3 = make_text_response("Final answer.")
        gen, _ = self._run([r1, r2, r3])
        assert gen.client.messages.create.call_count == 3

    def test_round_two_call_includes_tools(self):
        r1 = make_tool_use_response(tool_id="tu_001")
        r2 = make_tool_use_response(tool_id="tu_002")
        r3 = make_text_response("Done.")
        gen, _ = self._run([r1, r2, r3])
        round2_kwargs = gen.client.messages.create.call_args_list[1][1]
        assert "tools" in round2_kwargs
        assert round2_kwargs["tool_choice"] == {"type": "auto"}

    def test_synthesis_call_omits_tools(self):
        # Synthesis fires when loop exhausts both rounds: 4 total API calls
        # call[0]=generate_response, call[1]=round1, call[2]=round2, call[3]=synthesis
        r1 = make_tool_use_response(tool_id="tu_001")
        r2 = make_tool_use_response(tool_id="tu_002")
        r3 = make_tool_use_response(tool_id="tu_003")
        r4 = make_text_response("Done.")
        gen, _ = self._run([r1, r2, r3, r4])
        assert gen.client.messages.create.call_count == 4
        synthesis_kwargs = gen.client.messages.create.call_args_list[3][1]
        assert "tools" not in synthesis_kwargs
        assert "tool_choice" not in synthesis_kwargs

    def test_messages_accumulate_across_two_rounds(self):
        r1 = make_tool_use_response(tool_id="tu_001")
        r2 = make_tool_use_response(tool_id="tu_002")
        r3 = make_text_response("Done.")
        gen, _ = self._run([r1, r2, r3])
        final_messages = gen.client.messages.create.call_args_list[2][1]["messages"]
        assert len(final_messages) == 5
        assert final_messages[0]["role"] == "user"       # original query
        assert final_messages[1]["role"] == "assistant"  # round-1 tool use
        assert final_messages[2]["role"] == "user"       # round-1 tool results
        assert final_messages[3]["role"] == "assistant"  # round-2 tool use
        assert final_messages[4]["role"] == "user"       # round-2 tool results

    def test_both_tools_executed_in_order(self):
        r1 = make_tool_use_response(tool_name="get_course_outline", tool_input={"course_title": "Python"}, tool_id="tu_001")
        r2 = make_tool_use_response(tool_name="search_course_content", tool_input={"query": "decorators"}, tool_id="tu_002")
        r3 = make_text_response("Answer.")
        gen, tool_manager = self._run([r1, r2, r3])
        assert tool_manager.execute_tool.call_count == 2
        first_call = tool_manager.execute_tool.call_args_list[0]
        second_call = tool_manager.execute_tool.call_args_list[1]
        assert first_call[0][0] == "get_course_outline"
        assert first_call[1] == {"course_title": "Python"}
        assert second_call[0][0] == "search_course_content"
        assert second_call[1] == {"query": "decorators"}

    def test_tool_result_ids_correct_per_round(self):
        r1 = make_tool_use_response(tool_id="tu_001")
        r2 = make_tool_use_response(tool_id="tu_002")
        r3 = make_text_response("Done.")
        gen, _ = self._run([r1, r2, r3])
        final_messages = gen.client.messages.create.call_args_list[2][1]["messages"]
        round1_results = final_messages[2]["content"]
        round2_results = final_messages[4]["content"]
        assert round1_results[0]["tool_use_id"] == "tu_001"
        assert round2_results[0]["tool_use_id"] == "tu_002"

    def test_tool_execution_error_does_not_abort_loop(self):
        gen = make_generator()
        r1 = make_tool_use_response(tool_id="tu_001")
        r2 = make_text_response("Recovered answer.")
        gen.client.messages.create.side_effect = [r1, r2]
        tool_manager = MagicMock()
        tool_manager.execute_tool.side_effect = RuntimeError("DB unavailable")
        tool_defs = [{"name": "search_course_content", "description": "s", "input_schema": {}}]
        result = gen.generate_response(query="q", tools=tool_defs, tool_manager=tool_manager)
        assert gen.client.messages.create.call_count == 2
        assert result == "Recovered answer."

    def test_two_calls_when_round_two_returns_end_turn(self):
        r1 = make_tool_use_response(tool_id="tu_001")
        r2 = make_text_response("No more tools needed.")
        gen, _ = self._run([r1, r2])
        # round-2 API call returned end_turn → no synthesis call
        assert gen.client.messages.create.call_count == 2

    def test_single_round_regression(self):
        gen = make_generator()
        r1 = make_tool_use_response(tool_id="tu_001")
        r2 = make_text_response("The answer is here.")
        gen.client.messages.create.side_effect = [r1, r2]
        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "tool result"
        tool_defs = [{"name": "search_course_content", "description": "s", "input_schema": {}}]
        result = gen.generate_response(query="q", tools=tool_defs, tool_manager=tool_manager)
        assert gen.client.messages.create.call_count == 2
        assert result == "The answer is here."
