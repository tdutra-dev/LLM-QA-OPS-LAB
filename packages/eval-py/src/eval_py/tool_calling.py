"""
Step 9 — Tool Calling: LLM-driven autonomous tool selection via OpenAI function calling.

Architecture Shift
──────────────────
Steps 1-8: The evaluator returns a suggested action (monitor, escalate, etc.)
           and the ActionExecutor blindly dispatches to the corresponding handler.

           This is deterministic but not adaptive — the system can't learn or
           adjust its responses based on complex context patterns.

Step 9:    The LLM receives the incident data + a JSON schema of available tools.
           OpenAI function calling returns which tools to invoke and with what
           arguments. The system executes those tool calls and returns both
           the analysis AND the results.

           This enables the LLM to make multi-tool decisions ("escalate AND
           monitor", "retry with specific backoff strategy", etc.) based on
           nuanced reasoning about the full incident context.

Design
──────
                    POST /evaluate/tool-call
                             │
                    evaluate_with_tools(incident)
                             │
                    ┌─────────────────────────────────────┐
                    │  OpenAI Chat Completion             │
                    │  model: gpt-4o-mini                 │
                    │  tools: [monitor, retry, escalate,  │
                    │          inspect_prompt, ...]       │
                    │  messages: [system_prompt, incident]│
                    │                                     │
                    │  → tool_calls: [                    │
                    │      {"function": "escalate",       │
                    │       "arguments": {"reason": ...}} │
                    │    ]                                │
                    └─────────────────────────────────────┘
                             │
                    execute_tool_calls(tool_calls)
                             │
                           foreach tool_call:
                             call handler & collect result
                             │
                           ToolCallingEvaluationResult
                    {status, score, toolCalls, toolResults}

Tool Schema
───────────
Each of the 6 ActionExecutor handlers becomes a tool definition with:
  - JSON schema for arguments (workflow, severity, reason, etc.)
  - Detailed description of when to use the tool
  - Examples in the function descriptions

This allows the LLM to understand not just WHAT tools are available, but
WHEN and HOW to use them appropriately.

Environment
───────────
Expects OPENAI_API_KEY in environment (or .env file).
Model: gpt-4o-mini for cost efficiency while maintaining function calling quality.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from openai import OpenAI

from .models import (
    EvaluationRequest,
    ToolCall,
    ToolCallArguments,
    ToolCallingEvaluationResult,
    ToolExecutionResult,
)

# Load environment variables from .env file if present
load_dotenv()

# ── OpenAI client ──────────────────────────────────────────────────────────────

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """Get or create the OpenAI client with API key from environment."""
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable is required for tool calling. "
                "Set it in your environment or create a .env file in the project root."
            )
        _client = OpenAI(api_key=api_key)
    return _client


# ── Tool definitions ───────────────────────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "monitor",
            "description": (
                "Activate enhanced monitoring for a workflow experiencing issues. "
                "Choose this for low-medium severity incidents where increased "
                "observability is the primary need. Suitable for sporadic errors "
                "or when establishing a performance baseline."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "workflow": {"type": "string", "description": "The workflow name to monitor"},
                    "severity": {"type": "string", "description": "Incident severity level"},
                    "reason": {
                        "type": "string",
                        "description": "Why enhanced monitoring is appropriate for this incident",
                    },
                    "context": {
                        "type": "object",
                        "description": "Additional context for monitoring configuration",
                        "additionalProperties": True,
                    },
                },
                "required": ["workflow", "severity", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "retry",
            "description": (
                "Schedule a retry of the failed operation. Choose this for "
                "transient technical errors, rate limits, or network timeouts. "
                "High/critical severity gets immediate retry; others are deferred."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "workflow": {"type": "string", "description": "The workflow to retry"},
                    "severity": {"type": "string", "description": "Incident severity level"},
                    "reason": {
                        "type": "string",
                        "description": "Justification for why a retry is likely to succeed",
                    },
                    "context": {
                        "type": "object",
                        "description": "Retry configuration (backoff strategy, max attempts, etc.)",
                        "additionalProperties": True,
                    },
                },
                "required": ["workflow", "severity", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "inspect_prompt",
            "description": (
                "Flag a prompt template for human review by prompt engineers. "
                "Choose this for semantic errors, hallucinations, or output "
                "quality issues that suggest the prompt needs refinement."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "workflow": {"type": "string", "description": "The workflow with prompt issues"},
                    "severity": {"type": "string", "description": "Incident severity level"},
                    "reason": {
                        "type": "string",
                        "description": "What specifically suggests the prompt needs review",
                    },
                    "context": {
                        "type": "object",
                        "description": "Details to include in the review ticket (error examples, etc.)",
                        "additionalProperties": True,
                    },
                },
                "required": ["workflow", "severity", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "inspect_schema",
            "description": (
                "Flag an output schema for human review. Choose this for "
                "schema validation errors, unexpected output formats, or "
                "contract violations that suggest a schema mismatch."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "workflow": {"type": "string", "description": "The workflow with schema issues"},
                    "severity": {"type": "string", "description": "Incident severity level"},
                    "reason": {
                        "type": "string",
                        "description": "Evidence that schema validation or structure is problematic",
                    },
                    "context": {
                        "type": "object",
                        "description": "Schema diff or validation error details",
                        "additionalProperties": True,
                    },
                },
                "required": ["workflow", "severity", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_provider",
            "description": (
                "Check the health status of the LLM provider (OpenAI, Anthropic, etc.). "
                "Choose this when errors suggest provider-side issues: widespread "
                "timeouts, unusual error codes, or degraded service quality."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "workflow": {"type": "string", "description": "The workflow affected by provider issues"},
                    "severity": {"type": "string", "description": "Incident severity level"},
                    "reason": {
                        "type": "string",
                        "description": "Why provider health is suspected (error patterns, timing, etc.)",
                    },
                    "context": {
                        "type": "object",
                        "description": "Provider details (source, error codes, timing data)",
                        "additionalProperties": True,
                    },
                },
                "required": ["workflow", "severity", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escalate",
            "description": (
                "Create a high-priority alert for human operators. Choose this "
                "for critical incidents, repeated failures, or situations that "
                "require immediate human intervention. Critical severity triggers "
                "an immediate page; others create tickets."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "workflow": {"type": "string", "description": "The workflow requiring escalation"},
                    "severity": {"type": "string", "description": "Incident severity level"},
                    "reason": {
                        "type": "string",
                        "description": "Why human intervention is necessary immediately",
                    },
                    "context": {
                        "type": "object",
                        "description": "Escalation details (urgency, team assignment, context)",
                        "additionalProperties": True,
                    },
                },
                "required": ["workflow", "severity", "reason"],
            },
        },
    },
]


# ── Tool execution handlers ────────────────────────────────────────────────────

def _execute_tool(tool_call: ToolCall) -> ToolExecutionResult:
    """
    Execute a single tool call and return the result.

    Delegates to the appropriate handler based on the function name.
    This mirrors the ActionExecutor handlers but accepts structured
    arguments from the LLM's function call.
    """
    func_name = tool_call.function
    args = tool_call.arguments
    executed_at = datetime.now(timezone.utc).isoformat()

    try:
        if func_name == "monitor":
            detail = (
                f"Enhanced monitoring activated for workflow '{args.workflow}' "
                f"based on LLM analysis: {args.reason}"
            )

        elif func_name == "retry":
            mode = "immediate" if args.severity == "critical" else "deferred"
            detail = (
                f"Retry scheduled ({mode}) for workflow '{args.workflow}'. "
                f"LLM reasoning: {args.reason}"
            )

        elif func_name == "inspect_prompt":
            detail = (
                f"Prompt review ticket created for workflow '{args.workflow}'. "
                f"LLM identified issue: {args.reason}"
            )

        elif func_name == "inspect_schema":
            detail = (
                f"Schema review ticket created for workflow '{args.workflow}'. "
                f"LLM detected problem: {args.reason}"
            )

        elif func_name == "check_provider":
            detail = (
                f"Provider health check initiated for workflow '{args.workflow}'. "
                f"LLM suspected: {args.reason}"
            )

        elif func_name == "escalate":
            channel = {
                "critical": "PagerDuty (immediate)",
                "high": "Slack #ops-alerts",
                "medium": "Jira (medium priority)",
                "low": "Jira (low priority)",
            }.get(args.severity, "Jira")
            detail = (
                f"Escalation triggered via {channel} for workflow '{args.workflow}'. "
                f"LLM reasoning: {args.reason}"
            )

        else:
            detail = f"Unknown tool function: {func_name}"
            outcome = "failed"

        outcome = "success"  # All our handlers currently simulate success

    except Exception as exc:
        detail = f"Tool execution failed: {exc}"
        outcome = "failed"

    return ToolExecutionResult(
        toolCallId=tool_call.id,
        function=func_name,
        outcome=outcome,  # type: ignore[arg-type]
        detail=detail,
        executedAt=executed_at,
    )


# ── Main evaluation function ───────────────────────────────────────────────────

def evaluate_with_tools(request: EvaluationRequest) -> ToolCallingEvaluationResult:
    """
    Evaluate an incident using OpenAI function calling.

    The LLM analyzes the incident and chooses which tools to invoke.
    We execute those tools and return both the analysis and results.
    """
    client = _get_client()
    incident = request.incident

    # System prompt that teaches the LLM about the incident analysis task
    system_prompt = """You are an expert LLM operations analyst. Your job is to analyze incidents in LLM pipelines and decide what remediation tools to use.

For each incident, you should:
1. Assess the severity and impact
2. Determine the most likely cause
3. Choose appropriate tools to address the issue
4. Provide clear reasoning for your choices

You can use multiple tools if the situation warrants it (e.g., "escalate" AND "monitor").

Scoring guidelines:
- 0-30: Minor issues, low impact
- 31-60: Moderate issues requiring attention  
- 61-85: Serious issues needing prompt remediation
- 86-100: Critical issues requiring immediate action

Status guidelines:
- ok: Score 0-40, issue is resolved or very minor
- needs_attention: Score 41-80, requires monitoring or intervention
- critical: Score 81-100, requires immediate action"""

    # User message with the incident details
    incident_prompt = f"""
Analyze this LLM pipeline incident:

Workflow: {incident.workflow}
Stage: {incident.stage}
Source: {incident.source}
Type: {incident.incidentType}
Category: {incident.category}
Severity: {incident.severity}
Message: {incident.message}
Timestamp: {incident.timestamp}

Please analyze this incident and call appropriate tools to address it."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": incident_prompt},
            ],
            tools=TOOL_DEFINITIONS,
            tool_choice="required",  # Force the LLM to call at least one tool
            temperature=0.1,         # Low temperature for consistent tool selection
        )

        message = response.choices[0].message
        
        # Extract tool calls from the LLM response
        tool_calls = []
        tool_results = []
        
        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    args_dict = json.loads(tc.function.arguments)
                    tool_call = ToolCall(
                        id=tc.id,
                        function=tc.function.name,
                        arguments=ToolCallArguments(**args_dict),
                    )
                    tool_calls.append(tool_call)
                    
                    # Execute the tool
                    result = _execute_tool(tool_call)
                    tool_results.append(result)
                    
                except Exception as exc:
                    # If tool parsing/execution fails, record it
                    result = ToolExecutionResult(
                        toolCallId=tc.id,
                        function=tc.function.name,
                        outcome="failed",
                        detail=f"Tool execution error: {exc}",
                        executedAt=datetime.now(timezone.utc).isoformat(),
                    )
                    tool_results.append(result)

        # Generate evaluation status and score
        # Use simple heuristics since we don't have the LLM provide these directly
        score = _calculate_score(incident, tool_calls)
        status = _determine_status(score)
        summary = f"LLM analysis with {len(tool_calls)} tool call(s)"
        reasoning = message.content or "LLM provided tool calls without text explanation"

        return ToolCallingEvaluationResult(
            status=status,
            score=score,
            summary=summary,
            reasoning=reasoning,
            toolCalls=tool_calls,
            toolResults=tool_results,
            tags=[incident.incidentType, incident.category, incident.workflow],
        )

    except Exception as exc:
        # Fallback if OpenAI call fails
        return ToolCallingEvaluationResult(
            status="critical",
            score=95,
            summary="Tool calling evaluation failed",
            reasoning=f"OpenAI API error: {exc}",
            toolCalls=[],
            toolResults=[],
            tags=["api_error"],
        )


def _calculate_score(incident, tool_calls: list[ToolCall]) -> int:
    """Calculate a score based on incident severity and tool choices."""
    base_score = {
        "low": 20,
        "medium": 40,
        "high": 70,
        "critical": 90,
    }.get(incident.severity, 50)
    
    # Adjust based on number of tools called
    if len(tool_calls) == 0:
        return max(10, base_score - 20)  # No tools suggests minimal issue
    elif len(tool_calls) > 2:
        return min(95, base_score + 15)  # Many tools suggests complex issue
    else:
        return base_score


def _determine_status(score: int):
    """Map score to evaluation status."""
    if score <= 40:
        return "ok"
    elif score <= 80:
        return "needs_attention"
    else:
        return "critical"