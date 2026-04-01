#!/usr/bin/env python3
"""
Capture Grafana dashboard screenshots for LinkedIn showcase.
Saves to docs/media/  with descriptive filenames.

Usage:
    python scripts/capture_dashboard.py
"""

import time
from pathlib import Path

from playwright.sync_api import sync_playwright

GRAFANA_URL  = "http://localhost:3000"
DASHBOARD    = "/d/llmqa-main/llm-qa-ops-lab-e28094-observability"
PARAMS       = "?orgId=1&from=now-10m&to=now"
USER, PASSWD = "admin", "llmqa_dev"
OUT_DIR      = Path(__file__).parent.parent / "docs" / "media"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def login(page):
    page.goto(f"{GRAFANA_URL}/login", wait_until="networkidle")
    page.fill('input[name="user"]', USER)
    page.fill('input[name="password"]', PASSWD)
    page.click('button[type="submit"]')
    # Grafana may redirect to /?orgId=1 or /home — just wait for login page to disappear
    page.wait_for_url(lambda url: "/login" not in url, timeout=10_000)
    time.sleep(1)
    print("  ✓ Logged in")


def go_to_dashboard(page):
    page.goto(f"{GRAFANA_URL}{DASHBOARD}{PARAMS}", wait_until="networkidle")
    # Wait for at least one panel to render (Grafana 10+ uses data-panelid)
    try:
        page.wait_for_selector("[data-panelid]", timeout=20_000)
    except Exception:
        pass  # continue even if selector not found — charts may still be visible
    time.sleep(5)  # extra settle time for chart animations
    print("  ✓ Dashboard loaded")


def capture(page, name: str, clip: dict | None = None):
    path = OUT_DIR / f"{name}.png"
    kwargs = {"path": str(path), "full_page": False}
    if clip:
        kwargs["clip"] = clip
    page.screenshot(**kwargs)
    print(f"  ✓ Saved: {path.name}")
    return path


def run():
    print(f"\n📸  Grafana Dashboard Screenshot Capture")
    print(f"   Output → {OUT_DIR}\n")

    # Panel top positions discovered by recon (px from page top, kiosk mode)
    # Row headers: Eval=56, RAG=398, HTTP=740, Agent=1082
    SECTIONS = [
        ("02_evaluation_metrics",  56,  "📊 Evaluation Metrics — rate, status donut, score p50/p95"),
        ("03_rag_metrics",        398,  "🔍 RAG Metrics — retrieval latency p50/p95/p99"),
        ("04_http_slo",           740,  "🌐 HTTP Latency SLO — /evaluate and /evaluate/rag"),
        ("05_agent_loop",        1082,  "🤖 Agent Loop Health — iterations, actions"),
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1600, "height": 900},
            device_scale_factor=2,   # retina-quality → 3200×1800 output
        )
        page = ctx.new_page()

        login(page)
        go_to_dashboard(page)

        # ── 1. Full dashboard — full page scroll ─────────────────────────────
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(1)
        path = OUT_DIR / "01_dashboard_full.png"
        page.screenshot(path=str(path), full_page=True)
        kb = path.stat().st_size // 1024
        print(f"  ✓ 01_dashboard_full.png  ({kb} KB) — full page")

        # ── 2–5. One viewport per dashboard section ──────────────────────────
        for filename, scroll_y, label in SECTIONS:
            page.evaluate(f"window.scrollTo(0, {scroll_y})")
            time.sleep(1.5)  # wait for charts to repaint after scroll
            path = OUT_DIR / f"{filename}.png"
            page.screenshot(path=str(path), full_page=False)
            kb = path.stat().st_size // 1024
            print(f"  ✓ {filename}.png  ({kb} KB) — {label}")

        browser.close()

    print(f"\n✅  All screenshots saved to {OUT_DIR}")
    print("   Files:")
    for f in sorted(OUT_DIR.glob("*.png")):
        kb = f.stat().st_size // 1024
        print(f"   {f.name}  ({kb} KB)")


if __name__ == "__main__":
    run()
