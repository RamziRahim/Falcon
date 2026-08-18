"""
Test for candidate_generation/sources/screener_adapter.py's has_next_page()
-- the Leadership screen.query pagination bug (Falcon only ever parsed
page 1 of Screener's custom-query results, silently truncating a 132-match,
3-page result set down to 50). Real headless Playwright page loaded with
set_content(), matching this project's existing convention (see
test_shareholding_scraper.py) rather than mocking Playwright's locator API.

Pagination markup below matches the live structure confirmed against
Screener.in's own Leadership query results: a ".pagination" div containing
page-number links plus a "Next " link (present on every page except the
last, where it's absent entirely -- not disabled/greyed out).
"""
from __future__ import annotations

import pytest
from playwright.sync_api import sync_playwright

from candidate_generation.sources.screener_adapter import has_next_page

PAGE_WITH_NEXT_HTML = """
<html><body>
<table><tbody>
<tr data-row-company-id="1"><td>1</td><td><a href="/company/ABC/">ABC Ltd</a></td>
<td>100</td><td>20</td><td>6000</td><td>1</td><td>50</td><td>10</td><td>200</td>
<td>8</td><td>15</td><td>3</td><td>55</td><td>120</td><td>110</td></tr>
</tbody></table>
<div class="pagination"> Previous
1
2
3
<a href="?sort=&order=&query=x&page=2">Next </a>
Results per page
10
25
50
</div>
</body></html>
"""

LAST_PAGE_HTML = """
<html><body>
<table><tbody>
<tr data-row-company-id="99"><td>99</td><td><a href="/company/XYZ/">XYZ Ltd</a></td>
<td>100</td><td>20</td><td>6000</td><td>1</td><td>50</td><td>10</td><td>200</td>
<td>8</td><td>15</td><td>3</td><td>55</td><td>120</td><td>110</td></tr>
</tbody></table>
<div class="pagination"> Previous
1
2
3
Results per page
10
25
50
</div>
</body></html>
"""


@pytest.fixture(scope="module")
def playwright_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        yield page
        browser.close()


class TestHasNextPage:

    def test_true_when_next_link_present(self, playwright_page):
        playwright_page.set_content(PAGE_WITH_NEXT_HTML)
        assert has_next_page(playwright_page) is True

    def test_false_on_last_page_where_next_link_is_absent(self, playwright_page):
        """The real failure mode this pins: Screener removes the "Next"
        link entirely on the last page rather than disabling it -- a
        locator count of the Next link, not a disabled-attribute check,
        is what correctly signals end-of-results."""
        playwright_page.set_content(LAST_PAGE_HTML)
        assert has_next_page(playwright_page) is False
