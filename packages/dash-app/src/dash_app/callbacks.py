"""
Dashboard callbacks for interactivity and data updates.

Handles all user interactions and automatic data refreshing for the dashboard.
Uses the api_client module to fetch data from the FastAPI backend.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Input, Output, State, callback, dash_table, html
from dash.exceptions import PreventUpdate

from . import api_client


# ── Tab switching ─────────────────────────────────────────────────────────────

@callback(
    Output("tab-content", "children"),
    Input("main-tabs", "value")
)
def render_tab_content(active_tab: str):
    """Switch between tab contents."""
    from .layout import create_overview_tab, create_analytics_tab, create_actions_tab, create_agent_tab
    
    if active_tab == "overview":
        return create_overview_tab()
    elif active_tab == "analytics":
        return create_analytics_tab()
    elif active_tab == "actions":
        return create_actions_tab()
    elif active_tab == "agent":
        return create_agent_tab()
    else:
        return html.Div("Tab not found")


# ── Overview tab callbacks ────────────────────────────────────────────────────

@callback(
    [Output("total-evaluations", "children"),
     Output("avg-score", "children"), 
     Output("system-health", "children"),
     Output("redis-status", "children"),
     Output("api-status", "children"),
     Output("api-status", "style"),
     Output("last-updated", "children")],
    Input("interval-component", "n_intervals")
)
def update_overview_cards(n_intervals: int):
    """Update the key metrics cards."""
    # Get health status
    health = api_client.get_health()
    health_status = health.get("status", "error")
    redis_status = health.get("redis", "unknown")
    
    # Get metrics
    metrics = api_client.get_metrics()
    total_evals = metrics.get("totalEvaluations", 0)
    avg_score = metrics.get("averageScore", 0.0)
    
    # API status styling
    api_connected = health_status == "ok"
    api_status_text = "connected" if api_connected else "disconnected"
    api_status_style = {"color": "#2ca02c" if api_connected else "#d62728"}
    
    # Timestamp
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    return (
        str(total_evals),
        f"{avg_score:.1f}",
        health_status.upper(),
        f"Redis: {redis_status}",
        api_status_text,
        api_status_style,
        timestamp,
    )


@callback(
    [Output("agent-status", "children"),
     Output("agent-cycles", "children")],
    Input("interval-component", "n_intervals")
)
def update_agent_status_card(n_intervals: int):
    """Update the agent status card."""
    status = api_client.get_agent_status()
    running = status.get("running", False)
    cycles = status.get("cyclesCompleted", 0)
    actions = status.get("actionsExecuted", 0)
    
    status_text = "RUNNING" if running else "STOPPED"
    cycles_text = f"{cycles} cycles, {actions} actions"
    
    return status_text, cycles_text


@callback(
    Output("status-pie-chart", "figure"),
    Input("interval-component", "n_intervals")
)
def update_status_pie_chart(n_intervals: int):
    """Update the evaluation status distribution pie chart."""
    metrics = api_client.get_metrics()
    by_status = metrics.get("byStatus", [])
    
    if not by_status:
        # Empty state
        return {
            "data": [],
            "layout": {
                "title": "No data available",
                "height": 400,
            }
        }
    
    statuses = [item["status"] for item in by_status]
    counts = [item["count"] for item in by_status]
    colors = {"ok": "#2ca02c", "needs_attention": "#ff7f0e", "critical": "#d62728"}
    
    fig = px.pie(
        values=counts,
        names=statuses,
        color=statuses,
        color_discrete_map=colors,
        title="Evaluation Status Distribution",
    )
    fig.update_traces(textposition='inside', textinfo='percent+label')
    fig.update_layout(height=400, showlegend=True)
    
    return fig


@callback(
    Output("severity-bar-chart", "figure"),
    Input("interval-component", "n_intervals")
)
def update_severity_bar_chart(n_intervals: int):
    """Update the severity distribution bar chart."""
    metrics = api_client.get_metrics()
    by_severity = metrics.get("bySeverity", {})
    
    if not by_severity:
        return {
            "data": [],
            "layout": {
                "title": "No data available",
                "height": 400,
            }
        }
    
    severities = list(by_severity.keys())
    counts = list(by_severity.values())
    colors = {"low": "#2ca02c", "medium": "#ff7f0e", "high": "#d62728", "critical": "#8b0000"}
    
    fig = px.bar(
        x=severities,
        y=counts,
        color=severities,
        color_discrete_map=colors,
        title="Incident Severity Breakdown",
        labels={"x": "Severity", "y": "Count"},
    )
    fig.update_layout(height=400, showlegend=False)
    
    return fig


@callback(
    [Output("workflows-list", "children"),
     Output("actions-list", "children")],
    Input("interval-component", "n_intervals")
)
def update_lists(n_intervals: int):
    """Update the workflows and actions lists."""
    metrics = api_client.get_metrics()
    workflows = metrics.get("workflows", [])
    top_actions = metrics.get("topSuggestedActions", [])
    
    # Workflows list
    if workflows:
        workflows_cards = [
            html.Div([
                html.Span(f"• {workflow}", className="me-2"),
                html.Small("active", className="text-muted"),
            ], className="mb-1") 
            for workflow in workflows[:5]  # Top 5
        ]
    else:
        workflows_cards = [html.P("No workflows found", className="text-muted")]
    
    # Actions list  
    if top_actions:
        actions_cards = [
            html.Div([
                html.Span(f"• {action['action']}", className="me-2"),
                html.Small(f"({action['count']})", className="text-muted"),
            ], className="mb-1")
            for action in top_actions[:5]  # Top 5
        ]
    else:
        actions_cards = [html.P("No actions found", className="text-muted")]
    
    return workflows_cards, actions_cards


# ── Analytics tab callbacks ───────────────────────────────────────────────────

@callback(
    [Output("daily-trend-chart", "figure"),
     Output("rolling-avg-chart", "figure"),
     Output("failure-rate-chart", "figure")],
    Input("interval-component", "n_intervals")
)
def update_analytics_charts(n_intervals: int):
    """Update all analytics charts from Pandas/Polars data."""
    analytics = api_client.get_analytics()
    
    # Daily trend (Pandas)
    daily_trend = analytics.get("dailyScoreTrend", [])
    if daily_trend:
        dates = [item["date"] for item in daily_trend]
        scores = [item["avgScore"] for item in daily_trend]
        
        trend_fig = px.line(
            x=dates, y=scores,
            title="Daily Average Score Trend",
            labels={"x": "Date", "y": "Average Score"},
        )
        trend_fig.update_traces(line_color="#1f77b4", line_width=3)
        trend_fig.update_layout(height=400)
    else:
        trend_fig = {"data": [], "layout": {"title": "No trend data", "height": 400}}
    
    # Rolling average
    rolling_avg = analytics.get("rollingAvgScore", [])
    if rolling_avg:
        rolling_fig = px.line(
            x=list(range(len(rolling_avg))), y=rolling_avg,
            title="7-Day Rolling Average Score",
            labels={"x": "Evaluation #", "y": "Rolling Avg Score"},
        )
        rolling_fig.update_traces(line_color="#2ca02c", line_width=3)
        rolling_fig.update_layout(height=400)
    else:
        rolling_fig = {"data": [], "layout": {"title": "No rolling avg data", "height": 400}}
    
    # Failure rates (Polars)
    workflow_failure = analytics.get("workflowFailure", [])
    if workflow_failure:
        workflows = [item["workflow"] for item in workflow_failure]
        failure_rates = [item["failureRate"] * 100 for item in workflow_failure]  # Convert to %
        
        failure_fig = px.bar(
            x=workflows, y=failure_rates,
            title="Workflow Failure Rates (%)",
            labels={"x": "Workflow", "y": "Failure Rate (%)"},
            color=failure_rates,
            color_continuous_scale="Reds",
        )
        failure_fig.update_layout(height=400, showlegend=False)
    else:
        failure_fig = {"data": [], "layout": {"title": "No failure rate data", "height": 400}}
    
    return trend_fig, rolling_fig, failure_fig


# ── Actions tab callbacks ─────────────────────────────────────────────────────

@callback(
    [Output("actions-timeline", "figure"),
     Output("recent-actions-table", "children")],
    Input("interval-component", "n_intervals")
)
def update_actions_tab(n_intervals: int):
    """Update the actions timeline and table."""
    actions = api_client.get_actions(limit=100)
    
    if not actions:
        empty_fig = {"data": [], "layout": {"title": "No action logs found", "height": 500}}
        empty_table = html.P("No recent actions", className="text-muted")
        return empty_fig, empty_table
    
    # Timeline chart
    df = pd.DataFrame(actions)
    df["executedAt"] = pd.to_datetime(df["executedAt"])
    
    color_map = {
        "monitor": "#1f77b4",
        "retry": "#ff7f0e", 
        "escalate": "#d62728",
        "inspect_prompt": "#2ca02c",
        "inspect_schema": "#9467bd",
        "check_provider": "#8c564b",
    }
    
    timeline_fig = px.scatter(
        df,
        x="executedAt",
        y="actionType", 
        color="actionType",
        color_discrete_map=color_map,
        hover_data=["workflow", "severity", "outcome"],
        title="Action Execution Timeline",
    )
    timeline_fig.update_traces(marker_size=8)
    timeline_fig.update_layout(height=500, showlegend=True)
    
    # Recent actions table
    recent_actions = actions[:10]  # Latest 10
    table_data = [
        {
            "Time": action["executedAt"][:19].replace("T", " "),
            "Action": action["actionType"],
            "Workflow": action["workflow"],
            "Severity": action["severity"],
            "Outcome": action["outcome"],
            "Detail": action["detail"][:50] + "..." if len(action["detail"]) > 50 else action["detail"],
        }
        for action in recent_actions
    ]
    
    table = dash_table.DataTable(
        data=table_data,
        columns=[{"name": col, "id": col} for col in table_data[0].keys() if table_data],
        style_cell={"textAlign": "left", "fontSize": "12px", "padding": "8px"},
        style_header={"backgroundColor": "#f8f9fa", "fontWeight": "bold"},
        style_data_conditional=[
            {
                "if": {"filter_query": "{Outcome} = success"},
                "backgroundColor": "#d4edda",
            },
            {
                "if": {"filter_query": "{Outcome} = failed"},
                "backgroundColor": "#f8d7da",
            },
        ],
        page_size=10,
    )
    
    return timeline_fig, table


# ── Agent control callbacks ───────────────────────────────────────────────────

@callback(
    Output("agent-control-feedback", "children"),
    [Input("start-agent-btn", "n_clicks"),
     Input("stop-agent-btn", "n_clicks")],
    State("interval-slider", "value"),
    prevent_initial_call=True
)
def handle_agent_controls(start_clicks: int, stop_clicks: int, interval: float):
    """Handle start/stop agent button clicks."""
    from dash import ctx
    
    if not ctx.triggered:
        raise PreventUpdate
    
    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    
    if button_id == "start-agent-btn":
        result = api_client.start_agent(interval=interval)
        if "error" in result:
            return html.Div([
                html.I(className="fas fa-times-circle text-danger me-2"),
                f"Failed to start agent: {result['error']}"
            ])
        else: 
            return html.Div([
                html.I(className="fas fa-check-circle text-success me-2"),
                f"Agent started (interval: {interval}s)"
            ])
    
    elif button_id == "stop-agent-btn":
        result = api_client.stop_agent()
        if "error" in result:
            return html.Div([
                html.I(className="fas fa-times-circle text-danger me-2"),
                f"Failed to stop agent: {result['error']}"
            ])
        else:
            cycles = result.get("cyclesCompleted", 0)
            actions = result.get("actionsExecuted", 0)
            return html.Div([
                html.I(className="fas fa-check-circle text-success me-2"),
                f"Agent stopped (completed {cycles} cycles, {actions} actions)"
            ])


@callback(
    Output("agent-metrics-chart", "figure"),
    Input("interval-component", "n_intervals")
)
def update_agent_metrics_chart(n_intervals: int):
    """Update the agent activity metrics chart."""
    status = api_client.get_agent_status()
    
    cycles = status.get("cyclesCompleted", 0)
    actions = status.get("actionsExecuted", 0)
    running = status.get("running", False)
    
    # Simple bar chart of agent activity
    fig = go.Figure(data=[
        go.Bar(name="Cycles", x=["Agent Activity"], y=[cycles], marker_color="#1f77b4"),
        go.Bar(name="Actions", x=["Agent Activity"], y=[actions], marker_color="#2ca02c"),
    ])
    
    fig.update_layout(
        title=f"Agent Activity - {'RUNNING' if running else 'STOPPED'}",
        yaxis_title="Count",
        height=400,
        barmode="group",
    )
    
    return fig