#!/usr/bin/env python3
"""Render docs/pdf_src/summary.html to docs/dbt-parquet-s3-summary.pdf.

Uses Playwright Chromium with an explicit Letter page format (do not rely
on CSS default page size). Grayscale is enforced by the HTML itself.

Usage: python3 render_pdf.py
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

SRC = Path(__file__).resolve().parent / "summary.html"
OUT = Path(__file__).resolve().parent.parent / "dbt-parquet-s3-summary.pdf"


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(SRC.as_uri())
        page.wait_for_load_state("networkidle")
        page.pdf(
            path=str(OUT),
            format="Letter",
            margin={
                "top": "0.45in",
                "bottom": "0.4in",
                "left": "0.55in",
                "right": "0.55in",
            },
            print_background=True,
        )
        browser.close()
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
