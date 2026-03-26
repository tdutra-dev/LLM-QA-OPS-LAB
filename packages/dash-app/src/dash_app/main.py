"""
LLM-QA-OPS Interactive Dashboard

A comprehensive web dashboard for monitoring and controlling the LLM evaluation
and autonomous action system. Provides real-time visualization of metrics,
analytics, action logs, and agent control.

Usage
─────
    python -m dash_app.main
    
    # Or with custom settings:
    EVAL_API_URL=http://localhost:8010 python -m dash_app.main
    
    # Dashboard will be available at http://localhost:8050

Architecture
────────────
The dashboard fetches data from the FastAPI evaluation service via HTTP and
presents it through interactive Plotly charts and Bootstrap components.

Features:
- Overview: Key metrics, status distributions, workflow activity
- Analytics: Time series trends with Pandas/Polars visualizations  
- Actions: Audit trail of autonomous actions with filtering
- Agent Control: Start/stop the autonomous agent loop

Auto-refreshes every 10 seconds for near real-time monitoring.
"""
from __future__ import annotations

import dash
import dash_bootstrap_components as dbc

# Initialize the Dash app with Bootstrap theme
app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"
    ],
    suppress_callback_exceptions=True,
    title="LLM-QA-OPS Dashboard",
)

# Import layout and callbacks after app initialization to avoid circular imports
from .layout import create_main_layout
from . import callbacks  # noqa: F401 - callbacks register themselves

# Set the layout
app.layout = create_main_layout()

def main():
    """Run the dashboard application."""
    print("🚀 Starting LLM-QA-OPS Dashboard...")
    print("📊 Dashboard will be available at: http://localhost:8050")
    print("🔌 Connecting to FastAPI backend at: http://localhost:8010")
    print("🔄 Auto-refresh interval: 10 seconds")
    print()
    print("📈 Dashboard Features:")
    print("  • Overview: Real-time metrics and system status")
    print("  • Analytics: Time series trends and failure analysis")
    print("  • Actions: Autonomous action audit trail")
    print("  • Agent Control: Start/stop autonomous loop")
    print()
    
    app.run(
        debug=True,
        host="0.0.0.0",
        port=8050,
    )


if __name__ == "__main__":
    main()