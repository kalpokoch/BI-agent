
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent
from langchain_groq import ChatGroq
import os

# ─────────────────────────────────────────────
# LLM SETUP — Groq (Llama 3.3 70B Versatile)
# ─────────────────────────────────────────────

def get_llm():
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0,
        max_retries=2,
        max_tokens=4096,  # Control response length
    )

def get_fallback_llm():
    """Get fallback LLM for rate limit scenarios."""
    return ChatGroq(
        model="llama-3.1-8b-instant",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0,
        max_retries=2,
        max_tokens=4096,
    )

# ─────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """
You are a Business Intelligence assistant for a founder/executive at a drone survey company.
You have access to live Monday.com data through two tools:
  - get_deals_data       -> for pipeline, revenue, deal stages, closure probability, sector-wise deals
  - get_work_orders_data -> for operational data, work status, billing, collections, quantities

RULES YOU MUST FOLLOW:
1. Always call the appropriate tool FIRST before answering any business question.
   Never answer from memory or make up numbers.
2. If a question touches both deals and operations, call BOTH tools.
3. After fetching data, clean and analyze it before responding.
4. Always mention data quality caveats when relevant.
5. Format financial figures in Indian number system using Rs. prefix.
   Express large numbers as Lakhs (L) or Crores (Cr). Example: Rs.21.16 Cr
6. When dates are ambiguous, use the current date context and clarify your assumption.
7. If a query is vague, ask ONE clarifying question before fetching data.
8. Always end responses with a 1-line insight or recommendation.

CURRENT DATE CONTEXT: March 1, 2026
CURRENT FINANCIAL YEAR: FY 2025-26 (April 2025 - March 2026)
CURRENT QUARTER: Q4 FY25-26 (January - March 2026)
"""


# ─────────────────────────────────────────────
# AGENT BUILDER
# ─────────────────────────────────────────────

def build_agent(tools: list):
    llm = get_llm()
    agent = create_react_agent(model=llm, tools=tools)
    return agent

def build_fallback_agent(tools: list):
    """Build agent with fallback LLM for rate limit scenarios."""
    fallback_llm = get_fallback_llm()
    agent = create_react_agent(model=fallback_llm, tools=tools)
    return agent


# ─────────────────────────────────────────────
# CHAT HISTORY FORMATTER
# ─────────────────────────────────────────────

def format_chat_history(history: list) -> list:
    messages = []
    for msg in history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))
    return messages


# ─────────────────────────────────────────────
# QUERY RUNNER
# ─────────────────────────────────────────────

def run_query(agent_executor, user_input: str, chat_history: list) -> dict:
    try:
        result = agent_executor.invoke({
            "messages": [
                *format_chat_history(chat_history),
                HumanMessage(content=user_input)
            ]
        })
        
        # Extract the final message from the result
        final_message = result.get("messages", [])[-1] if result.get("messages") else None
        output = final_message.content if final_message else "I could not generate a response."
        
        # Extract tool calls and results from messages for visualization reuse
        tool_results = extract_tool_results_from_messages(result.get("messages", []))
        
        # Extract intermediate steps for trace display
        intermediate_steps = extract_intermediate_steps_from_messages(result.get("messages", []))
        
        return {
            "output": output,
            "intermediate_steps": intermediate_steps,
            "tool_results": tool_results,  # Add tool results for reuse
            "error": None
        }
    except Exception as e:
        error_msg = str(e)
        
        # Check for rate limit errors and attempt fallback
        if ("429" in error_msg or "rate_limit_exceeded" in error_msg.lower() or 
            "quota" in error_msg.lower() or "exhausted" in error_msg.lower()):
            
            try:
                # Try fallback model
                from tools import get_deals_data, get_work_orders_data
                fallback_agent = build_fallback_agent([get_deals_data, get_work_orders_data])
                
                result = fallback_agent.invoke({
                    "messages": [
                        *format_chat_history(chat_history),
                        HumanMessage(content=user_input)
                    ]
                })
                
                final_message = result.get("messages", [])[-1] if result.get("messages") else None
                output = final_message.content if final_message else "I could not generate a response."
                
                # Add fallback notification to response
                fallback_notice = "\n\n⚡ *Note: Switched to faster model due to rate limits on primary model.*"
                
                # Extract tool calls and results from fallback messages
                tool_results = extract_tool_results_from_messages(result.get("messages", []))
                
                # Extract intermediate steps for trace display
                intermediate_steps = extract_intermediate_steps_from_messages(result.get("messages", []))
                
                return {
                    "output": output + fallback_notice,
                    "intermediate_steps": intermediate_steps,
                    "tool_results": tool_results,
                    "error": None,
                    "fallback_used": True
                }
                
            except Exception as fallback_error:
                return {
                    "output": f"⚠️ Both primary and fallback models unavailable. Please try again later. Error: {str(fallback_error)}",
                    "intermediate_steps": [],
                    "tool_results": {},
                    "error": str(fallback_error)
                }
        
        # Handle non-rate-limit errors
        friendly = f"An error occurred: {error_msg}"
        return {
            "output": f"Warning: {friendly}",
            "intermediate_steps": [],
            "tool_results": {},
            "error": error_msg
        }


# ─────────────────────────────────────────────
# TOOL TRACE FORMATTER
# ─────────────────────────────────────────────

def extract_tool_results_from_messages(messages: list) -> dict:
    """Extract tool call results from LangGraph agent messages for reuse."""
    tool_results = {}
    
    for message in messages:
        # Check for AI messages with tool calls
        if hasattr(message, 'tool_calls') and message.tool_calls:
            for tool_call in message.tool_calls:
                tool_name = tool_call.get('name', '')
                if tool_name in ['get_deals_data', 'get_work_orders_data']:
                    # Find the corresponding tool message with the result
                    tool_call_id = tool_call.get('id')
                    for msg in messages:
                        if (hasattr(msg, 'tool_call_id') and 
                            msg.tool_call_id == tool_call_id and
                            hasattr(msg, 'content')):
                            tool_results[tool_name] = msg.content
                            break
    
    return tool_results


def extract_intermediate_steps_from_messages(messages: list) -> list:
    """Extract intermediate steps from LangGraph messages for trace display."""
    intermediate_steps = []
    
    for i, message in enumerate(messages):
        # Check for AI messages with tool calls
        if hasattr(message, 'tool_calls') and message.tool_calls:
            for tool_call in message.tool_calls:
                # Create a mock action object
                class MockAction:
                    def __init__(self, tool_name, tool_input):
                        self.tool = tool_name
                        self.tool_input = tool_input
                
                tool_name = tool_call.get('name', '')
                tool_input = tool_call.get('args', {})
                
                # Find the corresponding tool message with the result
                tool_call_id = tool_call.get('id')
                output = "Tool result not found"
                
                for msg in messages[i+1:]:  # Look at messages after the tool call
                    if (hasattr(msg, 'tool_call_id') and 
                        msg.tool_call_id == tool_call_id and
                        hasattr(msg, 'content')):
                        output = msg.content
                        break
                
                action = MockAction(tool_name, tool_input)
                intermediate_steps.append((action, output))
    
    return intermediate_steps

def format_tool_traces(intermediate_steps: list) -> list:
    traces = []
    for action, output in intermediate_steps:
        traces.append({
            "tool_name": action.tool,
            "tool_input": str(action.tool_input),
            "tool_output_preview": (
                str(output)[:300] + "..." if len(str(output)) > 300 else str(output)
            )
        })
    return traces
