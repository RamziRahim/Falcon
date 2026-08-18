"""
Test for candidate_generation/source_runner.py's collect_all_pages() -- the
fix for the Leadership screen.query pagination bug (Screener.in paginates
custom-query results at a fixed 50/page; run_source() used to call
parse_results() exactly once, silently truncating any query matching more
than 50 stocks to its first page -- confirmed live: the Leadership query's
real 132-match result set was actually spread across 3 pages).

Uses a real headless Playwright page with page.route() intercepting
requests to a fake origin and serving a 3-page fixture (2+2+1 rows) with
real relative "Next" hrefs, same shape as Screener's own pagination
markup -- so the browser itself resolves and navigates the relative URLs,
exactly as it does against the real site, rather than mocking Playwright's
click/navigation behavior.
"""
from __future__ import annotations

import pytest
from playwright.sync_api import sync_playwright

import candidate_generation.source_runner as source_runner
from candidate_generation.source_runner import collect_all_pages

BASE_URL = "https://example.test/screen/raw/"


def _row(row_id: int, symbol: str, name: str) -> str:
    values = ["100", "20", "6000", "1", "50", "10", "200", "8", "15", "3", "55", "120", "110"]
    cells = "".join(f"<td>{v}</td>" for v in values)
    return (
        f'<tr data-row-company-id="{row_id}">'
        f"<td>{row_id}</td><td><a href='/company/{symbol}/'>{name}</a></td>{cells}"
        f"</tr>"
    )


def _page_html(rows: list[str], next_href: str | None) -> str:
    next_link = f'<a href="{next_href}">Next </a>' if next_href else ""
    return f"""
    <html><body>
    <table><tbody>{''.join(rows)}</tbody></table>
    <div class="pagination"> Previous 1 2 3 {next_link} Results per page 10 25 50 </div>
    </body></html>
    """


PAGE_1_HTML = _page_html(
    [_row(1, "SYMONE", "Company One"), _row(2, "SYMTWO", "Company Two")],
    next_href="?page=2",
)
PAGE_2_HTML = _page_html(
    [_row(3, "SYMTHREE", "Company Three"), _row(4, "SYMFOUR", "Company Four")],
    next_href="?page=3",
)
PAGE_3_HTML = _page_html(
    [_row(5, "SYMFIVE", "Company Five")],
    next_href=None,
)

FIXTURE_PAGES = {
    BASE_URL: PAGE_1_HTML,
    f"{BASE_URL}?page=2": PAGE_2_HTML,
    f"{BASE_URL}?page=3": PAGE_3_HTML,
}


@pytest.fixture()
def playwright_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        yield page
        browser.close()


def _serve_fixture(page, pages: dict[str, str]):
    def handler(route):
        html = pages.get(route.request.url, "<html><body>unexpected request</body></html>")
        route.fulfill(status=200, content_type="text/html", body=html)

    page.route("https://example.test/**", handler)


class TestCollectAllPages:

    def test_aggregates_rows_from_every_page_not_just_the_first(self, playwright_page):
        """The exact regression this fix targets: before collect_all_pages()
        existed, run_source() parsed only the page currently loaded (page 1)
        and never followed "Next" -- a 3-page result set collapsed to page
        1's rows alone. This proves all 3 pages are actually visited."""
        _serve_fixture(playwright_page, FIXTURE_PAGES)
        playwright_page.goto(BASE_URL)

        df = collect_all_pages(playwright_page)

        assert len(df) == 5
        assert sorted(df["Symbol"]) == [
            "SYMFIVE.NS", "SYMFOUR.NS", "SYMONE.NS", "SYMTHREE.NS", "SYMTWO.NS",
        ]

    def test_stops_once_the_last_page_has_no_next_link(self, playwright_page):
        """Confirms the loop terminates on its own real signal (no Next
        link) rather than running until MAX_PAGES -- a request for a page
        past the fixture's last one would hit the "unexpected request"
        fallback and corrupt the result, which this also implicitly guards."""
        _serve_fixture(playwright_page, FIXTURE_PAGES)
        playwright_page.goto(BASE_URL)

        df = collect_all_pages(playwright_page)

        assert "unexpected request" not in "".join(df.astype(str).values.flatten())

    def test_max_pages_safety_cap_prevents_an_infinite_loop(self, playwright_page, monkeypatch):
        """A page that always claims to have a next page (e.g. a stale
        selector matching a persistent element) must not hang the scan
        forever -- MAX_PAGES bounds it."""
        monkeypatch.setattr(source_runner, "MAX_PAGES", 3)

        def always_has_next(route):
            html = _page_html([_row(1, "LOOP", "Looping Co")], next_href="?page=999")
            route.fulfill(status=200, content_type="text/html", body=html)

        playwright_page.route("https://example.test/**", always_has_next)
        playwright_page.goto(BASE_URL)

        df = collect_all_pages(playwright_page)

        assert len(df) == 3
