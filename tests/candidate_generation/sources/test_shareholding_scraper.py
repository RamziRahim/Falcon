"""
Test for candidate_generation/sources/shareholding_scraper.py -- QoQ
Promoter/FII/DII trend classification. Uses a real (headless) Playwright
page loaded with synthetic HTML matching the confirmed live structure
(#shareholding > table.data-table, "Promoters +"/"FIIs +"/"DIIs +" row
labels, quarters in ascending chronological order) rather than mocking
Playwright's locator API -- more realistic, and avoids fragile mocking of
a fluent API surface.

Values below are the real RELIANCE.NS figures confirmed live: Promoter
50.00% -> 50.48% (INCREASING), FII 18.67% -> 17.19% (DECREASING), DII
20.46% -> 21.10% (INCREASING) -- both trend directions confirmed against
real data, not just synthetic numbers.
"""
from __future__ import annotations

import pytest
from playwright.sync_api import sync_playwright

from candidate_generation.sources.shareholding_scraper import _extract_from_page

SHAREHOLDING_HTML = """
<html><body>
<section id="shareholding" class="card card-large">
  <div id="quarterly-shp">
    <table class="data-table">
      <thead>
        <tr><th></th><th>Mar 2026</th><th>Jun 2026</th></tr>
      </thead>
      <tbody>
        <tr><td>Promoters&nbsp;<span class="blue-icon">+</span></td><td>50.00%</td><td>50.48%</td></tr>
        <tr><td>FIIs&nbsp;<span class="blue-icon">+</span></td><td>18.67%</td><td>17.19%</td></tr>
        <tr><td>DIIs&nbsp;<span class="blue-icon">+</span></td><td>20.46%</td><td>21.10%</td></tr>
        <tr><td>Government&nbsp;<span class="blue-icon">+</span></td><td>0.17%</td><td>0.17%</td></tr>
        <tr><td>Public&nbsp;<span class="blue-icon">+</span></td><td>10.70%</td><td>11.05%</td></tr>
        <tr class="sub"><td>No. of Shareholders</td><td>44,21,289</td><td>46,51,863</td></tr>
      </tbody>
    </table>
  </div>
</section>
</body></html>
"""


@pytest.fixture(scope="module")
def playwright_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        yield page
        browser.close()


class TestTrendDirection:

    def test_increasing_and_decreasing_classify_correctly(self, playwright_page):
        """The one place a >/< mixup would silently invert the signal:
        Promoter and DII genuinely increased QoQ, FII genuinely decreased."""
        playwright_page.set_content(SHAREHOLDING_HTML)

        result = _extract_from_page(playwright_page)

        assert result["promoter_pct_latest"] == pytest.approx(50.48)
        assert result["promoter_trend"] == "INCREASING"

        assert result["fii_pct_latest"] == pytest.approx(17.19)
        assert result["fii_trend"] == "DECREASING"

        assert result["dii_pct_latest"] == pytest.approx(21.10)
        assert result["dii_trend"] == "INCREASING"

    def test_flat_when_unchanged(self, playwright_page):
        flat_html = SHAREHOLDING_HTML.replace(
            '<td>Promoters&nbsp;<span class="blue-icon">+</span></td><td>50.00%</td><td>50.48%</td>',
            '<td>Promoters&nbsp;<span class="blue-icon">+</span></td><td>56.38%</td><td>56.38%</td>',
        )
        playwright_page.set_content(flat_html)

        result = _extract_from_page(playwright_page)

        assert result["promoter_trend"] == "FLAT"


class TestMissingSection:

    def test_missing_shareholding_section_returns_empty_result_not_crash(self, playwright_page):
        playwright_page.set_content("<html><body><p>no shareholding data here</p></body></html>")

        result = _extract_from_page(playwright_page)

        assert result["promoter_pct_latest"] is None
        assert result["promoter_trend"] is None
        assert result["fii_pct_latest"] is None
        assert result["dii_pct_latest"] is None
