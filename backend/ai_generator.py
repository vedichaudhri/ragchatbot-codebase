import anthropic
from typing import List, Optional, Dict, Any

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""
    
    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to a comprehensive search tool for course information.

Search Tool Usage:
- Use the search tool **only** for questions about specific course content or detailed educational materials
- **Up to two sequential tool calls per query** — use a second tool call only when the first result is needed to inform the next search
- Synthesize search results into accurate, fact-based responses
- If search yields no results, state this clearly without offering alternatives

Outline Tool Usage:
- Use the outline tool for questions about course structure, lesson lists, or "what lessons" queries
- An outline lookup may precede a content search when you need to identify a specific lesson before searching for related material
- Return the course title, course link, and each lesson number and title exactly as provided

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without searching
- **Course-specific questions**: Use the search or outline tool as appropriate, then answer
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, search explanations, or question-type analysis
 - Do not mention "based on the search results"


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""

    MAX_TOOL_ROUNDS = 2
    
    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        
        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }
    
    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional tool usage and conversation context.
        
        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools
            
        Returns:
            Generated response as string
        """
        
        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history 
            else self.SYSTEM_PROMPT
        )
        
        # Prepare API call parameters efficiently
        api_params = {
            **self.base_params,
            "messages": [{"role": "user", "content": query}],
            "system": system_content
        }
        
        # Add tools if available
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}
        
        # Get response from Claude
        response = self.client.messages.create(**api_params)
        
        # Handle tool execution if needed
        if response.stop_reason == "tool_use" and tool_manager:
            return self._run_tool_rounds(response, api_params, tool_manager)
        
        # Return direct response
        return response.content[0].text
    
    def _run_tool_rounds(self, initial_response, base_params: Dict[str, Any], tool_manager) -> str:
        """
        Execute up to MAX_TOOL_ROUNDS sequential tool-call rounds, then return final text.

        Tools are re-included in each within-loop API call so Claude can chain calls.
        If Claude stops requesting tools before the round limit, returns immediately
        without a redundant synthesis call.
        """
        messages = base_params["messages"].copy()
        needs_synthesis = True
        current_response = initial_response

        for _ in range(self.MAX_TOOL_ROUNDS):
            messages.append({"role": "assistant", "content": current_response.content})

            tool_results = []
            for block in current_response.content:
                if block.type == "tool_use":
                    try:
                        result = tool_manager.execute_tool(block.name, **block.input)
                    except Exception as e:
                        result = f"Tool error: {e}"
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            messages.append({"role": "user", "content": tool_results})

            current_response = self.client.messages.create(**{
                **self.base_params,
                "messages": messages,
                "system": base_params["system"],
                "tools": base_params["tools"],
                "tool_choice": {"type": "auto"}
            })

            if current_response.stop_reason != "tool_use":
                needs_synthesis = False
                break

        if needs_synthesis:
            current_response = self.client.messages.create(**{
                **self.base_params,
                "messages": messages,
                "system": base_params["system"]
            })

        return current_response.content[0].text