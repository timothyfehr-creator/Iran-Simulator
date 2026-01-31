#!/usr/bin/env python3
"""
MCP Server for GPT-5.2 Math Queries

Exposes a single tool `ask_gpt_math` for math-heavy Bayesian tasks.
Uses gpt-5.2-chat-latest model via OpenAI API.

Usage:
    # Run as MCP server (stdio transport)
    python -m src.mcp.math_model_server

    # Test directly
    python -m src.mcp.math_model_server --test "What is the posterior distribution..."
"""

import json
import sys
import asyncio
from typing import Any

# MCP protocol uses JSON-RPC over stdio
# We implement a minimal MCP server without heavy dependencies


def get_openai_client():
    """Lazy-load OpenAI client."""
    try:
        from openai import OpenAI
        from src.config.secrets import get_openai_key
        return OpenAI(api_key=get_openai_key())
    except ImportError:
        raise RuntimeError("openai package not installed. Run: pip install openai")


def call_gpt_math(prompt: str, system_prompt: str = None) -> dict:
    """
    Call GPT-5.2 Pro for a math-heavy query.

    Args:
        prompt: The math/Bayesian question to ask
        system_prompt: Optional system prompt (defaults to math expert)

    Returns:
        dict with 'response' and 'model' keys
    """
    client = get_openai_client()

    if system_prompt is None:
        system_prompt = (
            "You are an expert mathematician and statistician specializing in "
            "Bayesian inference, probability theory, and quantitative modeling. "
            "Provide rigorous, step-by-step derivations. Use LaTeX notation for "
            "equations when helpful. Be precise about assumptions and limitations."
        )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]

    response = client.chat.completions.create(
        model="gpt-5.2-chat-latest",  # GPT-5.2 chat model
        messages=messages,
        max_completion_tokens=4096
    )

    return {
        "response": response.choices[0].message.content,
        "model": response.model,
        "usage": {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens
        }
    }


# ============================================================================
# MCP Server Implementation (JSON-RPC over stdio)
# ============================================================================

TOOL_DEFINITION = {
    "name": "ask_gpt_math",
    "description": (
        "Ask GPT-5.2 Pro a math-heavy question. Best for Bayesian inference, "
        "probability calculations, statistical derivations, and quantitative modeling. "
        "Returns a detailed, step-by-step response."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "The math/statistics question to ask"
            },
            "system_prompt": {
                "type": "string",
                "description": "Optional custom system prompt (defaults to math expert persona)"
            }
        },
        "required": ["prompt"]
    }
}


def handle_request(request: dict) -> dict:
    """Handle a JSON-RPC request."""
    method = request.get("method", "")
    req_id = request.get("id")
    params = request.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "gpt-math-server",
                    "version": "1.0.0"
                }
            }
        }

    elif method == "notifications/initialized":
        # No response needed for notifications
        return None

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [TOOL_DEFINITION]
            }
        }

    elif method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name == "ask_gpt_math":
            try:
                result = call_gpt_math(
                    prompt=arguments.get("prompt", ""),
                    system_prompt=arguments.get("system_prompt")
                )
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": result["response"]
                            }
                        ],
                        "isError": False
                    }
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Error calling GPT-5.2 Pro: {str(e)}"
                            }
                        ],
                        "isError": True
                    }
                }
        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Unknown tool: {tool_name}"
                }
            }

    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}"
            }
        }


def run_server():
    """Run the MCP server over stdio."""
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break

            request = json.loads(line.strip())
            response = handle_request(request)

            if response is not None:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()

        except json.JSONDecodeError:
            continue
        except KeyboardInterrupt:
            break


def test_direct(prompt: str):
    """Test the GPT call directly without MCP."""
    print(f"Calling GPT-5.2 Pro with prompt:\n{prompt[:100]}...\n")
    result = call_gpt_math(prompt)
    print(f"Model: {result['model']}")
    print(f"Tokens: {result['usage']}")
    print(f"\nResponse:\n{result['response']}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="GPT-5.2 Pro Math MCP Server")
    parser.add_argument("--test", type=str, help="Test with a direct query")

    args = parser.parse_args()

    if args.test:
        test_direct(args.test)
    else:
        run_server()
