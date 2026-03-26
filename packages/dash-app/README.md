# LLM-QA-OPS Dashboard

Interactive web dashboard for monitoring and controlling the LLM evaluation and autonomous action system.

## Features

### 📊 Overview Tab
- **Key Metrics**: Total evaluations, average score, agent status, system health
- **Status Distribution**: Pie chart of evaluation statuses (ok, needs_attention, critical)
- **Severity Breakdown**: Bar chart of incident severities (low, medium, high, critical)
- **Active Workflows**: List of workflows currently processing incidents
- **Top Actions**: Most frequently triggered autonomous actions

### 📈 Analytics Tab 
- **Daily Score Trend**: Time series visualization of quality metrics (Pandas analytics)
- **Rolling Average**: 7-day rolling average score for trend analysis
- **Workflow Failure Rates**: Performance breakdown by workflow (Polars analytics)

### 🎯 Actions Tab
- **Action Timeline**: Scatter plot of autonomous actions over time
- **Recent Actions Table**: Detailed audit trail with filtering and search
- **Action Type Filtering**: Focus on specific action types (monitor, retry, escalate, etc.)

### 🤖 Agent Control Tab
- **Agent Management**: Start/stop the autonomous agent loop
- **Interval Control**: Adjust polling frequency (1-30 seconds)
- **Activity Metrics**: Real-time cycles and actions counters

## Quick Start

### Prerequisites
- FastAPI evaluation service running on `localhost:8010`
- Python 3.11+ environment

### Installation

1. **Create virtual environment**:
   ```bash
   cd packages/dash-app
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   # or .venv\Scripts\activate  # Windows
   ```

2. **Install dependencies**:
   ```bash
   pip install -e .
   ```

### Running the Dashboard

1. **Start the dashboard**:
   ```bash
   python -m dash_app.main
   ```

2. **Open in browser**: http://localhost:8050

3. **Verify connection**: The status bar should show "FastAPI: connected"

## Configuration

### Environment Variables

- `EVAL_API_URL`: FastAPI backend URL (default: `http://localhost:8010`)

Example:
```bash
EVAL_API_URL=http://localhost:8010 python -m dash_app.main
```

### Auto-Refresh
- Dashboard auto-refreshes every 10 seconds
- All charts and metrics update automatically
- No manual refresh needed

## Architecture

```
Dashboard (port 8050) ──HTTP──> FastAPI (port 8010) ──> PostgreSQL + Redis
       │                              │
   Dash + Plotly              Evaluation Engine
   Bootstrap UI              Autonomous Actions
```

## Dashboard Structure

```
packages/dash-app/
├── pyproject.toml          # Dependencies and package config
├── README.md              # This file
└── src/dash_app/
    ├── __init__.py        # Package initialization
    ├── main.py           # Application entry point
    ├── api_client.py     # FastAPI HTTP client
    ├── layout.py         # UI components and styling
    └── callbacks.py      # Interactivity and data updates
```

## Development

### Adding New Charts

1. **Add API endpoint** in `api_client.py`
2. **Create layout component** in `layout.py`
3. **Implement callback** in `callbacks.py`
4. **Update main layout** to include the new component

### Styling
- Uses Bootstrap 5 theme via `dash-bootstrap-components`
- Color scheme defined in `layout.py` `COLORS` dictionary
- Font Awesome icons for visual elements

### Error Handling
- All API calls have timeout protection (5 seconds)
- Graceful fallbacks when FastAPI is unavailable
- Connection status indicator in the status bar

## Troubleshooting

### "FastAPI: disconnected"
- Ensure FastAPI service is running on `localhost:8010`
- Check firewall/network connectivity
- Verify `EVAL_API_URL` environment variable

### Charts not updating
- Check browser console for JavaScript errors
- Verify dashboard auto-refresh is working (status bar timestamp)
- Restart the dashboard if callbacks fail

### Performance Issues
- Reduce auto-refresh interval if needed
- Check FastAPI response times
- Monitor browser memory usage with large datasets

## Production Deployment

For production use:
1. Set `debug=False` in `main.py`
2. Use a proper WSGI server (Gunicorn, uWSGI)
3. Configure reverse proxy (nginx) if needed
4. Set appropriate `EVAL_API_URL` for your environment