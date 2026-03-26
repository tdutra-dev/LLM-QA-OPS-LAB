"""
Dashboard layout components and styling.

Defines the visual structure of the LLM-QA-OPS dashboard using Dash components
and Bootstrap styling for a professional operations center appearance.
"""
from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dcc, html

# Color scheme for consistent styling
COLORS = {
    "primary": "#1f77b4",     # Blue
    "success": "#2ca02c",     # Green  
    "warning": "#ff7f0e",     # Orange
    "danger": "#d62728",      # Red
    "info": "#17a2b8",        # Cyan
    "light": "#f8f9fa",       # Light gray
    "dark": "#343a40",        # Dark gray
    "background": "#fafbfc",  # Very light gray
}

def create_navbar():
    """Create the top navigation bar."""
    return dbc.NavbarSimple(
        brand="LLM-QA-OPS Dashboard",
        brand_href="#",
        color="dark",
        dark=True,
        className="mb-4",
        children=[
            dbc.NavItem(
                dbc.Badge(
                    "Step 10 - Interactive Analytics",
                    color="info",
                    className="me-2",
                )
            ),
        ],
    )


def create_overview_tab():
    """Create the overview metrics tab content."""
    return dbc.Container([
        dbc.Row([
            # Key metrics cards
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4("Total Evaluations", className="card-title text-primary"),
                        html.H2(id="total-evaluations", children="--", className="text-center"),
                        html.P("Incidents processed", className="text-muted text-center"),
                    ])
                ], color="light", outline=True)
            ], width=3),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4("Average Score", className="card-title text-success"),
                        html.H2(id="avg-score", children="--", className="text-center"),
                        html.P("Quality metric", className="text-muted text-center"),
                    ])
                ], color="light", outline=True)
            ], width=3),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4("Agent Status", className="card-title text-info"),
                        html.H2(id="agent-status", children="--", className="text-center"),
                        html.P(id="agent-cycles", children="-- cycles", className="text-muted text-center"),
                    ])
                ], color="light", outline=True)
            ], width=3),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4("System Health", className="card-title text-warning"),
                        html.H2(id="system-health", children="--", className="text-center"),
                        html.P(id="redis-status", children="Redis: --", className="text-muted text-center"),
                    ])
                ], color="light", outline=True)
            ], width=3),
        ], className="mb-4"),
        
        dbc.Row([
            # Status distribution pie chart
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("Evaluation Status Distribution")),
                    dbc.CardBody([
                        dcc.Graph(id="status-pie-chart", style={"height": "400px"}),
                    ])
                ])
            ], width=6),
            
            # Severity distribution bar chart  
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("Incident Severity Breakdown")),
                    dbc.CardBody([
                        dcc.Graph(id="severity-bar-chart", style={"height": "400px"}),
                    ])
                ])
            ], width=6),
        ], className="mb-4"),
        
        dbc.Row([
            # Top workflows and actions
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("Active Workflows")),
                    dbc.CardBody([
                        html.Div(id="workflows-list"),
                    ])
                ])
            ], width=6),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("Top Suggested Actions")),
                    dbc.CardBody([
                        html.Div(id="actions-list"),
                    ])
                ])
            ], width=6),
        ])
    ], fluid=True)


def create_analytics_tab():
    """Create the analytics tab content."""
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("Daily Score Trend (Pandas Analytics)")),
                    dbc.CardBody([
                        dcc.Graph(id="daily-trend-chart", style={"height": "400px"}),
                    ])
                ])
            ], width=12),
        ], className="mb-4"),
        
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("Rolling Average Score (7-day window)")),
                    dbc.CardBody([
                        dcc.Graph(id="rolling-avg-chart", style={"height": "400px"}),
                    ])
                ])
            ], width=6),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("Workflow Failure Rates (Polars Analytics)")),
                    dbc.CardBody([
                        dcc.Graph(id="failure-rate-chart", style={"height": "400px"}),
                    ])
                ])
            ], width=6),
        ])
    ], fluid=True)


def create_actions_tab():
    """Create the actions audit trail tab content."""
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H5("Action Execution Timeline"),
                        dbc.ButtonGroup([
                            dbc.Button("All", id="filter-all", size="sm", color="primary"),
                            dbc.Button("Monitor", id="filter-monitor", size="sm", color="secondary"),
                            dbc.Button("Retry", id="filter-retry", size="sm", color="secondary"),
                            dbc.Button("Escalate", id="filter-escalate", size="sm", color="secondary"),
                        ], className="float-end"),
                    ]),
                    dbc.CardBody([
                        dcc.Graph(id="actions-timeline", style={"height": "500px"}),
                    ])
                ])
            ], width=12),
        ], className="mb-4"),
        
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("Recent Action Logs")),
                    dbc.CardBody([
                        html.Div(id="recent-actions-table"),
                    ])
                ])
            ], width=12),
        ])
    ], fluid=True)


def create_agent_tab():
    """Create the agent loop control tab content."""
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("Agent Loop Control")),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.P("Control the autonomous agent loop:", className="mb-3"),
                                dbc.ButtonGroup([
                                    dbc.Button(
                                        "Start Agent", 
                                        id="start-agent-btn", 
                                        color="success", 
                                        className="me-2"
                                    ),
                                    dbc.Button(
                                        "Stop Agent", 
                                        id="stop-agent-btn", 
                                        color="danger"
                                    ),
                                ]),
                                html.Div(id="agent-control-feedback", className="mt-3"),
                            ], width=6),
                            
                            dbc.Col([
                                html.Div([
                                    html.P("Polling Interval:"),
                                    dcc.Slider(
                                        id="interval-slider",
                                        min=1, max=30, value=5,
                                        marks={i: f"{i}s" for i in [1, 5, 10, 15, 30]},
                                        tooltip={"placement": "bottom", "always_visible": True}
                                    ),
                                ])
                            ], width=6),
                        ])
                    ])
                ])
            ], width=12),
        ], className="mb-4"),
        
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("Agent Activity Metrics")),
                    dbc.CardBody([
                        dcc.Graph(id="agent-metrics-chart", style={"height": "400px"}),
                    ])
                ])
            ], width=12),
        ])
    ], fluid=True)


def create_main_layout():
    """Create the main dashboard layout with tabs."""
    return html.Div([
        # Auto-refresh component  
        dcc.Interval(
            id="interval-component",
            interval=10*1000,  # 10 seconds
            n_intervals=0
        ),
        
        # Navigation bar
        create_navbar(),
        
        # Main content with tabs
        dbc.Container([
            dcc.Tabs(id="main-tabs", value="overview", children=[
                dcc.Tab(label="Overview", value="overview"),
                dcc.Tab(label="Analytics", value="analytics"), 
                dcc.Tab(label="Actions", value="actions"),
                dcc.Tab(label="Agent Control", value="agent"),
            ], className="mb-4"),
            
            # Tab content
            html.Div(id="tab-content"),
            
        ], fluid=True, style={"backgroundColor": COLORS["background"], "minHeight": "100vh"}),
        
        # Status bar
        dbc.Container([
            html.Hr(),
            dbc.Row([
                dbc.Col([
                    html.Small([
                        "Last updated: ", 
                        html.Span(id="last-updated", children="--"),
                        " | FastAPI: ",
                        html.Span(id="api-status", children="disconnected", 
                                 style={"color": COLORS["danger"]}),
                    ], className="text-muted"),
                ], width=12),
            ])
        ], fluid=True),
    ])