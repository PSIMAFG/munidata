"""Playwright-based scraper for Portal Transparencia Chile.

Targets the real Transparencia Activa pages at:
  https://www.portaltransparencia.cl/PortalPdT/pdtta?codOrganismo=MU{code}

The portal runs on Liferay/JSF with heavy AJAX rendering.
Strategy:
  1. Navigate with Playwright, wait for JSF to settle
  2. Expand section "04. Personal y remuneraciones"
  3. Click into sub-sections (honorarios / contrata / planta)
  4. Extract paginated HTML tables
  5. Resilience: multiple selector fallbacks, generous timeouts, retries
"""

import csv
import io
import json
import os
import logging
import time
import re
from pathlib import Path

import httpx
from playwright.sync_api import (
    sync_playwright,
    Page,
    Browser,
    Locator,
    TimeoutError as PwTimeout,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PORTAL_BASE = (
    "https://www.portaltransparencia.cl/PortalPdT/pdtta"
)

DATA_DIR = os.environ.get("DATA_DIR", "/app/data")

MONTH_NAMES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

# Default navigation / AJAX timeout (Liferay is slow)
NAV_TIMEOUT = 60_000   # 60 s
AJAX_TIMEOUT = 45_000  # 45 s
CLICK_DELAY = 2        # seconds to sleep after clicks for JSF re-render

MAX_RETRIES = 3

# ---------------------------------------------------------------------------
# Selector banks (tried in order; first match wins)
# ---------------------------------------------------------------------------

SECTION_PERSONAL_SELECTORS = [
    "text=04. Personal y remuneraciones",
    "text=Personal y remuneraciones",
    "li:has-text('Personal y remuneraciones') >> a",
    "a:has-text('Personal y remuneraciones')",
    "span:has-text('Personal y remuneraciones')",
    "text=04.",
    "[class*='personal']",
    "a[title*='Personal']",
]

HONORARIOS_SELECTORS = [
    "text=Personas naturales contratadas a honorarios",
    "a:has-text('Personas naturales contratadas a honorarios')",
    "text=honorarios",
    "a:has-text('Honorarios')",
    "li:has-text('honorarios') >> a",
    "text=Dotación a Honorarios",
]

CONTRATA_SELECTORS = [
    "text=Personal a Contrata",
    "a:has-text('Personal a Contrata')",
    "text=contrata",
    "a:has-text('Contrata')",
    "li:has-text('contrata') >> a",
    "text=Dotación a contrata",
]

PLANTA_SELECTORS = [
    "text=Personal de Planta",
    "a:has-text('Personal de Planta')",
    "text=planta",
    "a:has-text('Planta')",
    "li:has-text('planta') >> a",
    "text=Dotación de planta",
]

ESCALAS_SELECTORS = [
    "text=Escala de remuneraciones",
    "a:has-text('Escala de remuneraciones')",
    "a:has-text('Escala')",
    "span:has-text('Escala')",
]

NEXT_PAGE_SELECTORS = [
    "a:has-text('Siguiente')",
    ".paginate_button.next:not(.disabled)",
    "a:has-text('>>')",
    "li.next:not(.disabled) a",
    "button:has-text('Siguiente')",
    "a.ui-paginator-next:not(.ui-state-disabled)",
    ".ui-paginator-next:not(.ui-state-disabled)",
    "span.ui-paginator-next:not(.ui-state-disabled)",
]

TABLE_SELECTORS = [
    "table.tabla-datos",
    "table.dataTable",
    "table[id*='tabla']",
    "table.table",
    "table[role='grid']",
    "div.ui-datatable table",
    ".ui-datatable-tablewrapper table",
]


class PortalScraper:
    """Scrapes personnel data from Portal Transparencia Chile."""

    def __init__(self, org_code: str):
        """
        Args:
            org_code: Organization code, e.g. "MU280" for San Antonio.
        """
        self.org_code = org_code
        self.pw = sync_playwright().start()
        self.browser: Browser = self.pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        self.context = self.browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            java_script_enabled=True,
        )
        self.page: Page = self.context.new_page()
        self.raw_dir = Path(DATA_DIR) / "raw" / org_code
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def close(self):
        try:
            self.browser.close()
            self.pw.stop()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    def _screenshot(self, name: str):
        """Save a debug screenshot."""
        try:
            path = self.raw_dir / f"screenshot_{name}.png"
            self.page.screenshot(path=str(path), full_page=True)
            logger.info(f"Screenshot saved: {path}")
        except Exception as e:
            logger.warning(f"Screenshot failed: {e}")

    def _save_html(self, name: str):
        """Save raw HTML of the current page for debugging."""
        try:
            path = self.raw_dir / f"html_{name}.html"
            html = self.page.content()
            path.write_text(html, encoding="utf-8")
            logger.info(f"HTML saved: {path} ({len(html)} bytes)")
        except Exception as e:
            logger.warning(f"HTML save failed: {e}")

    def _wait_for_ajax(self, timeout_ms: int = AJAX_TIMEOUT):
        """Wait for Liferay/JSF AJAX to settle."""
        try:
            self.page.wait_for_load_state("networkidle", timeout=timeout_ms)
        except PwTimeout:
            logger.debug("networkidle timed out, continuing anyway")
        # Extra sleep for JSF re-render
        time.sleep(CLICK_DELAY)

    def _try_click(self, selectors: list[str], description: str) -> bool:
        """Try each selector in order; click the first visible match.

        Returns True if a click succeeded.
        """
        for sel in selectors:
            try:
                loc = self.page.locator(sel)
                # Filter to visible elements only
                for i in range(loc.count()):
                    el = loc.nth(i)
                    if el.is_visible():
                        logger.info(f"Clicking '{description}' via selector: {sel} (match {i})")
                        el.scroll_into_view_if_needed()
                        time.sleep(0.5)
                        el.click()
                        self._wait_for_ajax()
                        return True
            except Exception as e:
                logger.debug(f"Selector '{sel}' for '{description}' failed: {e}")
                continue
        logger.warning(f"No selector matched for '{description}'")
        return False

    def _try_select_option(self, label: str, value: str) -> bool:
        """Try to select a value from a <select> or click a link/tab.

        The portal may use native <select>, JSF <select>, tabs, or links
        for area/year/month filters.
        """
        selectors = [
            # Native <select> by label text
            f"select:near(:text('{label}'))",
            # Any <select> containing the option
            f"select:has(option:has-text('{value}'))",
            # Link / tab
            f"a:has-text('{value}')",
            f"li:has-text('{value}') >> a",
            f"span:has-text('{value}')",
            # PrimeFaces selectOneMenu
            f"div[class*='selectonemenu']:near(:text('{label}'))",
        ]

        # First try native <select>
        for sel in selectors[:2]:
            try:
                loc = self.page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    tag = loc.first.evaluate("el => el.tagName")
                    if tag and tag.upper() == "SELECT":
                        loc.first.select_option(label=value)
                        logger.info(f"Selected '{value}' in <select> for '{label}'")
                        self._wait_for_ajax()
                        return True
            except Exception as e:
                logger.debug(f"Select option '{value}' via '{sel}' failed: {e}")

        # Try PrimeFaces selectOneMenu (click trigger, then click option in panel)
        try:
            trigger = self.page.locator(
                f"div[class*='selectonemenu']:near(:text('{label}')) .ui-selectonemenu-trigger"
            )
            if trigger.count() > 0 and trigger.first.is_visible():
                trigger.first.click()
                time.sleep(1)
                option = self.page.locator(f"li[data-label='{value}'], li:has-text('{value}')")
                if option.count() > 0 and option.first.is_visible():
                    option.first.click()
                    logger.info(f"Selected '{value}' via PrimeFaces menu for '{label}'")
                    self._wait_for_ajax()
                    return True
        except Exception as e:
            logger.debug(f"PrimeFaces select for '{label}' failed: {e}")

        # Fallback: click any visible link/tab with the value text
        for sel in selectors[2:]:
            try:
                loc = self.page.locator(sel)
                for i in range(min(loc.count(), 5)):
                    el = loc.nth(i)
                    if el.is_visible():
                        el.click()
                        logger.info(f"Clicked '{value}' for '{label}' via '{sel}'")
                        self._wait_for_ajax()
                        return True
            except Exception as e:
                logger.debug(f"Click '{value}' via '{sel}' failed: {e}")

        logger.warning(f"Could not select '{value}' for filter '{label}'")
        return False

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _navigate_to_org(self):
        """Navigate to the Transparencia Activa page for this organization."""
        url = f"{PORTAL_BASE}?codOrganismo={self.org_code}"
        logger.info(f"Navigating to {url}")
        self.page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
        self._wait_for_ajax()
        self._screenshot("01_org_home")
        self._save_html("01_org_home")

    def _expand_personal_section(self) -> bool:
        """Find and expand '04. Personal y remuneraciones'."""
        clicked = self._try_click(SECTION_PERSONAL_SELECTORS, "Personal y remuneraciones")
        self._screenshot("02_personal_section")
        if not clicked:
            self._save_html("02_personal_section_FAIL")
        return clicked

    def _click_subsection(self, selectors: list[str], name: str) -> bool:
        """Click into a personnel sub-section (honorarios/contrata/planta)."""
        clicked = self._try_click(selectors, name)
        self._screenshot(f"03_{name[:15]}")
        if not clicked:
            self._save_html(f"03_{name[:15]}_FAIL")
        return clicked

    def _apply_filters(self, area: str, year: int, month: int | None = None):
        """Apply area / year / month filters on the current view."""
        # Area
        if area:
            self._try_select_option("Área", area)
            self._try_select_option("Area", area)  # without accent
            self._screenshot("04_area_selected")

        # Year
        self._try_select_option("Año", str(year))
        self._try_select_option("Periodo", str(year))
        self._screenshot("05_year_selected")

        # Month
        if month:
            month_name = MONTH_NAMES.get(month, str(month))
            self._try_select_option("Mes", month_name)
            self._try_select_option("Periodo", month_name)
            self._screenshot(f"06_month_{month:02d}")

    def _navigate_to_section(
        self,
        subsection_selectors: list[str],
        subsection_name: str,
        area: str,
        year: int,
        month: int | None = None,
    ):
        """Full navigation: org page -> personal section -> subsection -> filters."""
        self._navigate_to_org()
        self._expand_personal_section()
        self._click_subsection(subsection_selectors, subsection_name)
        self._apply_filters(area, year, month)
        self._screenshot(f"07_ready_{subsection_name[:10]}_{year}_{month}")
        self._save_html(f"07_ready_{subsection_name[:10]}_{year}_{month}")

    # ------------------------------------------------------------------
    # Table extraction (Level 2)
    # ------------------------------------------------------------------

    def _find_data_table(self) -> Locator | None:
        """Find the main data table on the page using multiple selectors."""
        # Try specific selectors first
        for sel in TABLE_SELECTORS:
            try:
                loc = self.page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    return loc.first
            except Exception:
                continue

        # Fallback: any visible <table> with more than 5 rows
        try:
            tables = self.page.locator("table:visible")
            for i in range(tables.count()):
                tbl = tables.nth(i)
                rows = tbl.locator("tr")
                if rows.count() > 5:
                    logger.info(f"Using generic table (index {i}) with {rows.count()} rows")
                    return tbl
        except Exception:
            pass

        return None

    def _extract_headers(self, table: Locator) -> list[str]:
        """Extract column headers from a table.

        Accounts for colspan attributes to ensure header count matches
        data cell count, preventing column shift bugs.
        """
        headers = []

        def _extract_with_colspan(locator: Locator) -> list[str]:
            """Extract headers from a Playwright Locator, expanding colspan."""
            result = []
            for i in range(locator.count()):
                cell = locator.nth(i)
                text = cell.inner_text().strip()
                try:
                    colspan = int(cell.get_attribute("colspan") or "1")
                except (ValueError, TypeError):
                    colspan = 1
                result.append(text)
                for j in range(1, colspan):
                    result.append(f"{text} ({j + 1})")
            return result

        # Try <thead> <th>
        ths = table.locator("thead th")
        if ths.count() > 0:
            headers = _extract_with_colspan(ths)
            if headers:
                return headers

        # Try <thead> <td>
        tds = table.locator("thead td")
        if tds.count() > 0:
            headers = _extract_with_colspan(tds)
            if headers:
                return headers

        # Try first <tr> cells as headers
        first_row = table.locator("tr").first
        cells = first_row.locator("th, td")
        headers = _extract_with_colspan(cells)

        return headers

    def _extract_rows(self, table: Locator, headers: list[str]) -> list[dict]:
        """Extract data rows from a table given headers."""
        records = []
        rows = table.locator("tbody tr")
        if rows.count() == 0:
            # No <tbody>, skip first row (headers) and use all <tr>
            all_rows = table.locator("tr")
            row_start = 1  # skip header row
            for i in range(row_start, all_rows.count()):
                cells = all_rows.nth(i).locator("td")
                record = {}
                for j in range(min(cells.count(), len(headers))):
                    text = cells.nth(j).inner_text().strip()
                    record[headers[j]] = text
                if any(record.values()):
                    records.append(record)
        else:
            for i in range(rows.count()):
                cells = rows.nth(i).locator("td")
                record = {}
                for j in range(min(cells.count(), len(headers))):
                    text = cells.nth(j).inner_text().strip()
                    record[headers[j]] = text
                if any(record.values()):
                    records.append(record)
        return records

    def _has_next_page(self) -> bool:
        """Check if there is a clickable 'Next' button."""
        for sel in NEXT_PAGE_SELECTORS:
            try:
                loc = self.page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible() and loc.first.is_enabled():
                    return True
            except Exception:
                continue
        return False

    def _click_next_page(self) -> bool:
        """Click the 'Next' pagination button. Returns True if successful."""
        for sel in NEXT_PAGE_SELECTORS:
            try:
                loc = self.page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible() and loc.first.is_enabled():
                    loc.first.click()
                    self._wait_for_ajax()
                    return True
            except Exception:
                continue
        return False

    def _extract_table_data(self, max_pages: int = 100) -> list[dict]:
        """Extract all data from the current paginated HTML table.

        Handles pagination by clicking 'Next' until no more pages.
        """
        all_records = []
        headers = None

        for page_num in range(max_pages):
            table = self._find_data_table()
            if table is None:
                if page_num == 0:
                    logger.warning("No data table found on page")
                    self._screenshot("no_table_found")
                    self._save_html("no_table_found")
                break

            # Get headers from first page only
            if headers is None:
                headers = self._extract_headers(table)
                if not headers:
                    logger.warning("Could not extract table headers")
                    break
                logger.info(f"Table headers ({len(headers)}): {headers[:5]}...")

            page_records = self._extract_rows(table, headers)
            if not page_records:
                break

            all_records.extend(page_records)
            logger.info(f"Page {page_num + 1}: extracted {len(page_records)} rows (total: {len(all_records)})")

            # Try to go to next page
            if not self._click_next_page():
                break

        logger.info(f"Total records extracted from table: {len(all_records)}")
        return all_records

    # ------------------------------------------------------------------
    # CSV download attempt
    # ------------------------------------------------------------------

    def _try_download_csv(self, section_name: str, area: str, year: int, month: int) -> list[dict] | None:
        """Look for a CSV/Excel download button and parse the result.

        Strategy:
        1. Try direct href CSV/Excel links via HTTP download (fastest)
        2. Try Playwright click-based download with multiple selectors
        """
        # --- Strategy 1: Find direct download links and fetch via HTTP ---
        direct_records = self._try_direct_link_download(section_name, year, month)
        if direct_records:
            return direct_records

        # --- Strategy 2: Click-based download via Playwright ---
        download_selectors = [
            # Portal Transparencia common buttons
            "a:has-text('Descargar')",
            "a:has-text('Descargar CSV')",
            "a:has-text('Descargar Excel')",
            "button:has-text('Descargar')",
            # CSV specific
            "button:has-text('CSV')",
            "a:has-text('CSV')",
            "a[href*='.csv']",
            # Export buttons
            "a:has-text('Exportar')",
            "button:has-text('Exportar')",
            "a:has-text('Exportar a CSV')",
            "a:has-text('Exportar a Excel')",
            # PrimeFaces/Liferay export components
            "a[class*='ui-export']",
            "button[class*='export']",
            "a[class*='export']",
            ".ui-datatable-export a",
            "a[href*='export']",
            # Icon-based buttons (some portals use icons)
            "a[title*='Descargar']",
            "a[title*='CSV']",
            "a[title*='Excel']",
            "a[title*='Exportar']",
            "button[title*='Descargar']",
            # Generic download links
            "a[href*='.xlsx']",
            "a[href*='.xls']",
            "a[download]",
        ]
        for sel in download_selectors:
            try:
                loc = self.page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    logger.info(f"Trying CSV download via selector: {sel}")
                    with self.page.expect_download(timeout=30_000) as download_info:
                        loc.first.click()
                    download = download_info.value
                    suggested = download.suggested_filename or ""
                    ext = suggested.rsplit(".", 1)[-1].lower() if "." in suggested else "csv"
                    file_path = self.raw_dir / f"{section_name}_{year}_{month:02d}.{ext}"
                    download.save_as(str(file_path))
                    logger.info(f"CSV downloaded via click: {file_path} (suggested: {suggested})")
                    return self._parse_csv(file_path)
            except PwTimeout:
                logger.debug(f"Download via '{sel}' timed out")
            except Exception as e:
                logger.debug(f"Download via '{sel}' failed: {e}")
        return None

    def _try_direct_link_download(self, section_name: str, year: int, month: int) -> list[dict] | None:
        """Find direct href links on page and download via HTTP requests."""
        try:
            # Extract all links from the page that look like data downloads
            links = self.page.evaluate("""() => {
                const anchors = document.querySelectorAll('a[href]');
                return Array.from(anchors)
                    .map(a => ({href: a.href, text: a.innerText.trim()}))
                    .filter(a => {
                        const h = a.href.toLowerCase();
                        const t = a.text.toLowerCase();
                        return h.endsWith('.csv') || h.endsWith('.xlsx') || h.endsWith('.xls')
                            || h.includes('export') || h.includes('descargar')
                            || h.includes('download') || h.includes('csv')
                            || t.includes('csv') || t.includes('descargar')
                            || t.includes('exportar') || t.includes('excel');
                    });
            }""")

            if not links:
                logger.debug("No direct download links found on page")
                return None

            # Get cookies from Playwright session to use in HTTP request
            cookies = self.context.cookies()
            cookie_jar = httpx.Cookies()
            for c in cookies:
                cookie_jar.set(c["name"], c["value"], domain=c.get("domain", ""))

            client = httpx.Client(
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                },
                cookies=cookie_jar,
                follow_redirects=True,
                timeout=30.0,
            )

            for link in links:
                href = link.get("href", "")
                if not href or href.startswith("javascript:"):
                    continue
                try:
                    logger.info(f"Trying direct HTTP download: {href[:100]}...")
                    resp = client.get(href)
                    if resp.status_code == 200 and len(resp.content) > 100:
                        content_type = resp.headers.get("Content-Type", "").lower()
                        if any(ct in content_type for ct in ["csv", "text", "excel", "spreadsheet", "octet-stream"]):
                            ext = "csv"
                            if "excel" in content_type or "spreadsheet" in content_type:
                                ext = "xlsx"
                            file_path = self.raw_dir / f"{section_name}_{year}_{month:02d}_direct.{ext}"
                            file_path.write_bytes(resp.content)
                            logger.info(f"Direct HTTP download successful: {file_path} ({len(resp.content)} bytes)")
                            records = self._parse_csv(file_path)
                            if records:
                                client.close()
                                return records
                except Exception as e:
                    logger.debug(f"Direct download from {href[:80]} failed: {e}")
                    continue

            client.close()

        except Exception as e:
            logger.debug(f"Direct link extraction failed: {e}")
        return None

    def _extract_from_raw_html(self) -> list[dict]:
        """Fallback: parse table data directly from page HTML source.

        Uses BeautifulSoup for robust HTML parsing, including colspan
        handling to prevent column shift bugs.
        """
        try:
            from bs4 import BeautifulSoup
            from app.scraper.column_mapping import extract_headers_with_colspan

            html = self.page.content()
            soup = BeautifulSoup(html, "html.parser")
            tables = soup.find_all("table")

            for table in tables:
                # Extract headers with colspan support
                thead = table.find("thead")
                header_cells = []
                if thead:
                    header_cells = thead.find_all("th") or thead.find_all("td")
                if not header_cells:
                    first_row = table.find("tr")
                    if first_row:
                        header_cells = first_row.find_all("th")
                        if not header_cells:
                            header_cells = first_row.find_all("td")

                if not header_cells:
                    continue

                headers = extract_headers_with_colspan(header_cells)
                if len(headers) < 3:
                    continue

                # Extract data rows
                tbody = table.find("tbody")
                if tbody:
                    rows = tbody.find_all("tr")
                else:
                    all_rows = table.find_all("tr")
                    rows = all_rows[1:]  # skip header row

                records = []
                for row in rows:
                    cells = row.find_all("td")
                    cell_texts = [c.get_text(strip=True) for c in cells]
                    if len(cell_texts) >= len(headers) and any(cell_texts):
                        record = {}
                        for j, header in enumerate(headers):
                            if j < len(cell_texts):
                                record[header] = cell_texts[j]
                        records.append(record)

                if len(records) > 2:
                    logger.info(f"Raw HTML parsing found table with {len(headers)} cols, {len(records)} rows")
                    return records

        except Exception as e:
            logger.debug(f"Raw HTML parsing failed: {e}")
        return []

    def _parse_csv(self, file_path: Path) -> list[dict]:
        """Parse CSV with robust encoding handling (Chilean portals use Latin-1 often)."""
        for encoding in ["utf-8", "latin-1", "cp1252", "iso-8859-1"]:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    content = f.read()
                # Try semicolon delimiter first (standard in Chilean CSV), then comma
                for delimiter in [";", ",", "\t"]:
                    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
                    records = [dict(row) for row in reader]
                    if records and len(records[0]) > 1:
                        logger.info(f"Parsed CSV ({encoding}, delim='{delimiter}'): {len(records)} records")
                        return records
            except (UnicodeDecodeError, csv.Error):
                continue
        logger.warning(f"Could not parse CSV: {file_path}")
        return []

    # ------------------------------------------------------------------
    # Normalization (maps raw column names to standard DB fields)
    # ------------------------------------------------------------------

    def _normalize_honorarios(self, raw_records: list[dict]) -> list[dict]:
        """Normalize raw honorarios records to standard field names.

        Uses header-based alias matching (column_mapping module) instead of
        fragile index/substring matching. This prevents column shift bugs
        when the portal changes header order or naming.
        """
        from app.scraper.column_mapping import normalize_honorarios
        return normalize_honorarios(raw_records)

    def _normalize_contrata_planta(self, raw_records: list[dict]) -> list[dict]:
        """Normalize contrata/planta records to standard field names.

        Uses header-based alias matching (column_mapping module) instead of
        fragile index/substring matching. This prevents column shift bugs
        when the portal changes header order or naming.
        """
        from app.scraper.column_mapping import normalize_contrata_planta
        return normalize_contrata_planta(raw_records)

    # ------------------------------------------------------------------
    # Scrape with retry logic (Level 3: resilience)
    # ------------------------------------------------------------------

    def _scrape_with_retry(
        self,
        subsection_selectors: list[str],
        subsection_name: str,
        normalizer,
        area: str,
        year: int,
        month: int,
    ) -> list[dict]:
        """Attempt to scrape a section with retries and fallbacks.

        Strategy:
        1. Navigate to the correct section
        2. Try CSV download
        3. Fallback: extract HTML table
        4. Retry up to MAX_RETRIES times on failure
        """
        label = f"{subsection_name} {year}/{month:02d}"

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(f"Scraping {label} (attempt {attempt}/{MAX_RETRIES})")

                self._navigate_to_section(
                    subsection_selectors=subsection_selectors,
                    subsection_name=subsection_name,
                    area=area,
                    year=year,
                    month=month,
                )

                # Level 1: Try CSV download
                records = self._try_download_csv(subsection_name, area, year, month)
                if records:
                    logger.info(f"{label}: got {len(records)} records via CSV")
                    return normalizer(records)

                # Level 2: Extract HTML table via Playwright
                logger.info(f"{label}: no CSV, extracting HTML table")
                raw = self._extract_table_data()
                if raw:
                    logger.info(f"{label}: got {len(raw)} records from HTML table")
                    return normalizer(raw)

                # Level 3: Parse raw HTML source for table data
                logger.info(f"{label}: no Playwright table, trying raw HTML parsing")
                raw = self._extract_from_raw_html()
                if raw:
                    logger.info(f"{label}: got {len(raw)} records from raw HTML")
                    return normalizer(raw)

                # No data found
                logger.warning(f"{label}: no data found on attempt {attempt}")
                self._screenshot(f"no_data_{subsection_name[:10]}_{year}_{month:02d}_att{attempt}")
                self._save_html(f"no_data_{subsection_name[:10]}_{year}_{month:02d}_att{attempt}")

                if attempt < MAX_RETRIES:
                    wait = 5 * attempt
                    logger.info(f"Retrying in {wait}s...")
                    time.sleep(wait)

            except PwTimeout as e:
                logger.error(f"{label}: timeout on attempt {attempt}: {e}")
                self._screenshot(f"timeout_{subsection_name[:10]}_{month:02d}_att{attempt}")
                if attempt < MAX_RETRIES:
                    time.sleep(5 * attempt)
            except Exception as e:
                logger.error(f"{label}: error on attempt {attempt}: {e}")
                self._screenshot(f"error_{subsection_name[:10]}_{month:02d}_att{attempt}")
                if attempt < MAX_RETRIES:
                    time.sleep(5 * attempt)

        logger.error(f"{label}: all {MAX_RETRIES} attempts exhausted, returning empty")
        return []

    # ------------------------------------------------------------------
    # Public API (same interface as before)
    # ------------------------------------------------------------------

    def scrape_honorarios(self, area: str, year: int, month: int) -> list[dict]:
        """Scrape 'Personas naturales contratadas a honorarios' for one month."""
        return self._scrape_with_retry(
            subsection_selectors=HONORARIOS_SELECTORS,
            subsection_name="honorarios",
            normalizer=self._normalize_honorarios,
            area=area,
            year=year,
            month=month,
        )

    def scrape_contrata(self, area: str, year: int, month: int) -> list[dict]:
        """Scrape 'Personal a Contrata' for one month."""
        return self._scrape_with_retry(
            subsection_selectors=CONTRATA_SELECTORS,
            subsection_name="contrata",
            normalizer=self._normalize_contrata_planta,
            area=area,
            year=year,
            month=month,
        )

    def scrape_planta(self, area: str, year: int, month: int) -> list[dict]:
        """Scrape 'Personal de Planta' for one month."""
        return self._scrape_with_retry(
            subsection_selectors=PLANTA_SELECTORS,
            subsection_name="planta",
            normalizer=self._normalize_contrata_planta,
            area=area,
            year=year,
            month=month,
        )

    def scrape_escalas(self, year: int):
        """Download remuneration scale files (Excel/PDF)."""
        try:
            self._navigate_to_org()
            self._expand_personal_section()
            self._click_subsection(ESCALAS_SELECTORS, "Escala de remuneraciones")

            # Try year filter
            self._try_select_option("Año", str(year))

            self._screenshot(f"escalas_{year}")

            # Try to download files
            download_selectors = [
                "a[href*='.xlsx']",
                "a[href*='.xls']",
                "a:has-text('Descargar')",
                "a:has-text('Excel')",
                "a[href*='.pdf']",
            ]
            downloaded = 0
            for sel in download_selectors:
                try:
                    loc = self.page.locator(sel)
                    for i in range(min(loc.count(), 5)):
                        el = loc.nth(i)
                        if el.is_visible():
                            with self.page.expect_download(timeout=30_000) as dl:
                                el.click()
                            download = dl.value
                            ext = download.suggested_filename.split(".")[-1] if "." in download.suggested_filename else "xlsx"
                            file_path = self.raw_dir / f"escala_{year}_{downloaded}.{ext}"
                            download.save_as(str(file_path))
                            logger.info(f"Escala downloaded: {file_path}")
                            downloaded += 1
                except Exception as e:
                    logger.debug(f"Escala download via '{sel}' failed: {e}")

            if downloaded == 0:
                logger.warning(f"No escala files downloaded for year {year}")
                self._save_html(f"escalas_{year}_no_downloads")

        except Exception as e:
            logger.error(f"Escalas scraping failed: {e}")
            self._screenshot(f"escalas_error_{year}")
