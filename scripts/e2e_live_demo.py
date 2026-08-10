"""Run the real low-pressure happy path in a browser and capture the final workspace."""

from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CHAT_PLACEHOLDER = "Ask about a transition"


def wait_for_clean_rerun(page) -> None:
    expect(page.get_by_placeholder(CHAT_PLACEHOLDER)).to_be_enabled(timeout=300_000)
    expect(page.locator(".js-plotly-plot")).to_have_count(1, timeout=60_000)
    page.wait_for_timeout(3_000)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8765")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".cache/e2e/live_low_pressure.png",
    )
    parser.add_argument(
        "--overview-output",
        type=Path,
        default=ROOT / ".cache/e2e/live_overview.png",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path="/usr/bin/google-chrome",
            headless=True,
            args=["--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto(args.url, wait_until="networkidle", timeout=60_000)

        chat = page.get_by_placeholder(CHAT_PLACEHOLDER)
        expect(chat).to_be_visible(timeout=30_000)
        chat.fill(
            "Optimize transition 1630 to 2210. Minimize transition time and transition "
            "resin, explain why the pressure constraint matters, and leave the full 3x3 "
            "overview visible."
        )
        chat.press("Enter")
        messages = page.locator('[data-testid="stChatMessage"]')
        expect(messages).to_have_count(2, timeout=300_000)
        wait_for_clean_rerun(page)

        chat = page.get_by_placeholder(CHAT_PLACEHOLDER)
        chat.fill("Why is low pressure bad, and why not simply slow or stagger the feed changes?")
        chat.press("Enter")
        expect(messages).to_have_count(4, timeout=300_000)
        wait_for_clean_rerun(page)

        chat_history = page.locator(".st-key-agent-transcript")
        expect(chat_history).to_have_count(1)
        chat_history.evaluate("element => { element.scrollTop = element.scrollHeight; }")
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(500)

        args.output.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=args.output, full_page=True)

        expect(page.get_by_text("Density", exact=True)).to_be_visible(timeout=30_000)
        wait_for_clean_rerun(page)

        tr02_control = page.get_by_label("Show TR-02")
        expect(tr02_control).to_be_checked()
        tr02_control.click(force=True)
        wait_for_clean_rerun(page)
        plot = page.locator(".js-plotly-plot")
        assert not plot.evaluate(
            "plot => plot.data.some(trace => trace.meta?.transition_id === 'TR-02')"
        )
        tr02_control = page.get_by_label("Show TR-02")
        tr02_control.click(force=True)
        wait_for_clean_rerun(page)
        assert plot.evaluate(
            "plot => plot.data.some(trace => trace.meta?.transition_id === 'TR-02')"
        )

        chat_history = page.locator(".st-key-agent-transcript")
        chat_history.evaluate("element => { element.scrollTop = element.scrollHeight; }")
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(500)
        args.overview_output.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=args.overview_output, full_page=True)

        print(f"screenshot={args.output}")
        print(f"overview_screenshot={args.overview_output}")
        print(f"assistant={messages.nth(3).inner_text()}")
        browser.close()


if __name__ == "__main__":
    main()
