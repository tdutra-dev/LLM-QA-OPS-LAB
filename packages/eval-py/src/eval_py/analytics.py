"""
Step 4 – Pandas + Polars analytics engine.

Two independent computation paths run on the same raw data:

  pandas_analytics(rows) → DailyScoreTrend list + rolling average series
  polars_analytics(rows) → SeverityBucket list + WorkflowFailureRate list

The data contract is a plain list-of-dicts so neither library is coupled to
SQLAlchemy ORM objects.  main.py converts ORM rows before calling here.
"""
from __future__ import annotations

import importlib.metadata
from typing import Any

import pandas as pd
import polars as pl

from eval_py.models import (
    AnalyticsReport,
    DailyScoreTrend,
    SeverityBucket,
    WorkflowFailureRate,
)


# ─── helpers ──────────────────────────────────────────────────────────────────

def _lib_versions() -> str:
    pd_ver = importlib.metadata.version("pandas")
    pl_ver = importlib.metadata.version("polars")
    return f"pandas=={pd_ver} polars=={pl_ver}"


# ─── Pandas path ──────────────────────────────────────────────────────────────

def pandas_analytics(
    rows: list[dict[str, Any]],
) -> tuple[list[DailyScoreTrend], list[float]]:
    """
    Uses Pandas to produce:
    1. daily_score_trend  – mean(eval_score) grouped by calendar day.
    2. rolling_avg_score  – 7-evaluation rolling mean (last 10 values returned).

    Pandas strengths used here:
    - pd.to_datetime  for timestamp parsing
    - DatetimeIndex + Grouper("D") for calendar-day resampling
    - Series.rolling() for the sliding window
    """
    if not rows:
        return [], []

    df = pd.DataFrame(rows)
    df["received_at"] = pd.to_datetime(df["received_at"], utc=True)
    df["eval_score"] = pd.to_numeric(df["eval_score"], errors="coerce").fillna(0)

    # 1. Daily trend: group by calendar day, compute mean score + row count
    df_daily = (
        df.set_index("received_at")
        .resample("D")["eval_score"]
        .agg(avgScore="mean", count="size")
        .dropna(subset=["avgScore"])  # skip empty days
        .reset_index()
    )
    daily_trend = [
        DailyScoreTrend(
            date=row["received_at"].strftime("%Y-%m-%d"),
            avgScore=round(float(row["avgScore"]), 2),
            count=int(row["count"]),
        )
        for _, row in df_daily.iterrows()
    ]

    # 2. Rolling average: 7-evaluation window (min_periods=1 so we get data
    #    even when fewer than 7 records exist).  Return last 10 values.
    rolling = (
        df.sort_values("received_at")["eval_score"]
        .rolling(window=7, min_periods=1)
        .mean()
        .round(2)
        .tail(10)
        .tolist()
    )

    return daily_trend, [float(v) for v in rolling]


# ─── Polars path ──────────────────────────────────────────────────────────────

def polars_analytics(
    rows: list[dict[str, Any]],
) -> tuple[list[SeverityBucket], list[WorkflowFailureRate]]:
    """
    Uses Polars to produce:
    1. severity_distrib    – count + % per severity level.
    2. workflow_failure    – total/failed/failure_rate per workflow.

    Polars strengths used here:
    - pl.from_dicts for zero-copy construction
    - .group_by().agg() with lazy expressions
    - .with_columns() for derived columns (percentage, failure rate)
    - method chaining (functional, immutable API)
    """
    if not rows:
        return [], []

    df = pl.from_dicts(
        rows,
        schema_overrides={
            "eval_score": pl.Int32,
            "severity": pl.Utf8,
            "workflow": pl.Utf8,
            "eval_status": pl.Utf8,
        },
    )

    total = len(df)

    # 1. Severity distribution
    sev_df = (
        df.group_by("severity")
        .agg(pl.len().alias("count"))
        .with_columns(
            (pl.col("count") / total * 100).round(1).alias("pct")
        )
        .sort("count", descending=True)
    )
    severity_distrib = [
        SeverityBucket(
            severity=row["severity"],
            count=row["count"],
            pct=row["pct"],
        )
        for row in sev_df.iter_rows(named=True)
    ]

    # 2. Workflow failure rate  (non-"ok" status counts as failed)
    wf_df = (
        df.with_columns(
            (pl.col("eval_status") != "ok").cast(pl.Int32).alias("is_failed")
        )
        .group_by("workflow")
        .agg(
            pl.len().alias("total"),
            pl.col("is_failed").sum().alias("failed"),
        )
        .with_columns(
            (pl.col("failed") / pl.col("total")).round(4).alias("failureRate")
        )
        .sort("failureRate", descending=True)
    )
    workflow_failure = [
        WorkflowFailureRate(
            workflow=row["workflow"],
            total=row["total"],
            failed=row["failed"],
            failureRate=row["failureRate"],
        )
        for row in wf_df.iter_rows(named=True)
    ]

    return severity_distrib, workflow_failure


# ─── Public entry point ───────────────────────────────────────────────────────

def build_analytics_report(rows: list[dict[str, Any]]) -> AnalyticsReport:
    """
    Orchestrates both computation paths and returns a unified AnalyticsReport.
    Called by the FastAPI endpoint; rows come from the ORM store.
    """
    daily_trend, rolling_avg = pandas_analytics(rows)
    severity_distrib, workflow_failure = polars_analytics(rows)

    return AnalyticsReport(
        totalRows=len(rows),
        computedBy=_lib_versions(),
        dailyScoreTrend=daily_trend,
        rollingAvgScore=rolling_avg,
        severityDistrib=severity_distrib,
        workflowFailure=workflow_failure,
    )
