"""HTTP-based scraper for Portal Transparencia Chile.

Replaces Playwright with httpx + BeautifulSoup for faster, lighter scraping.
Uses direct HTTP requests to navigate the portal and extract data from
HTML tables, CSV downloads, or internal API endpoints.

Targets:
  https://www.portaltransparencia.cl/PortalPdT/pdtta/-/ta/MU{code}/{year}/A/{area}/{seccion}

Falls back gracefully when JavaScript rendering is required, logging
diagnostic HTML so the Playwright fallback can take over.
"""

import csv
import io
import json
import logging
import os
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlencode, urlparse, parse_qs

import httpx
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PORTAL_BASE = "https://www.portaltransparencia.cl/PortalPdT/pdtta"

DATA_DIR = os.environ.get("DATA_DIR", "/app/data")

MONTH_NAMES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

# Section codes in the portal URL structure
SECTION_CODES = {
    "planta": "4.1.1",
    "contrata": "4.1.2",
    "honorarios": "4.1.3",
    "escalas": "4.1.4",
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

MAX_RETRIES = 3
REQUEST_TIMEOUT = 30.0
RATE_LIMIT_DELAY = 1.5  # seconds between requests


# ---------------------------------------------------------------------------
# Column keywords for identifying correct tables
# ---------------------------------------------------------------------------

HONORARIOS_KEYWORDS = {"nombre", "rut", "remuneración", "remuneracion", "honorario", "función", "funcion"}
CONTRATA_PLANTA_KEYWORDS = {"nombre", "rut", "grado", "cargo", "remuneración", "remuneracion", "brut"}


class HTTPScraper:
    """Scrapes personnel data from Portal Transparencia using HTTP + BeautifulSoup."""

    def __init__(self, org_code: str):
        """
        Args:
            org_code: Organization code, e.g. "MU280" for San Antonio.
        """
        self.org_code = org_code
        self.client = httpx.Client(
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "es-CL,es;q=0.9,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            },
            follow_redirects=True,
            timeout=httpx.Timeout(REQUEST_TIMEOUT, connect=15.0),
        )
        self.raw_dir = Path(DATA_DIR) / "raw" / org_code
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def close(self):
        """Close the HTTP client."""
        try:
            self.client.close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _get_with_retry(self, url: str, retries: int = MAX_RETRIES) -> httpx.Response | None:
        """GET request with exponential backoff retries."""
        for attempt in range(1, retries + 1):
            try:
                logger.debug(f"GET {url} (attempt {attempt}/{retries})")
                resp = self.client.get(url)
                if resp.status_code == 200:
                    return resp
                logger.warning(f"HTTP {resp.status_code} for {url}")
                if resp.status_code in (429, 503):
                    wait = 2 ** attempt
                    logger.info(f"Rate limited, waiting {wait}s...")
                    time.sleep(wait)
                    continue
                if resp.status_code >= 400:
                    return resp
            except httpx.TimeoutException:
                logger.warning(f"Timeout on attempt {attempt} for {url}")
                if attempt < retries:
                    time.sleep(2 ** attempt)
            except httpx.HTTPError as e:
                logger.warning(f"HTTP error on attempt {attempt}: {e}")
                if attempt < retries:
                    time.sleep(2 ** attempt)
        return None

    def _rate_limit(self):
        """Sleep between requests to avoid overloading the portal."""
        time.sleep(RATE_LIMIT_DELAY)

    def _save_html(self, name: str, html: str):
        """Save raw HTML for diagnostic inspection."""
        try:
            path = self.raw_dir / f"http_{name}.html"
            path.write_text(html, encoding="utf-8")
            logger.info(f"Diagnostic HTML saved: {path} ({len(html)} bytes)")
        except Exception as e:
            logger.warning(f"Failed to save diagnostic HTML: {e}")

    def _parse_soup(self, html: str, encoding: str | None = None) -> BeautifulSoup:
        """Parse HTML into BeautifulSoup, trying lxml first then html.parser."""
        try:
            return BeautifulSoup(html, "lxml")
        except Exception:
            return BeautifulSoup(html, "html.parser")

    def _detect_encoding(self, resp: httpx.Response) -> str:
        """Detect response encoding from headers or content."""
        content_type = resp.headers.get("content-type", "")
        if "charset=" in content_type:
            charset = content_type.split("charset=")[-1].split(";")[0].strip()
            return charset
        # Try to detect from HTML meta tag
        text = resp.content[:2000].decode("ascii", errors="ignore")
        match = re.search(r'charset=["\']?([^"\'\s;>]+)', text, re.IGNORECASE)
        if match:
            return match.group(1)
        return "utf-8"

    def _get_html(self, url: str) -> str | None:
        """Fetch URL and return decoded HTML text, or None on failure."""
        resp = self._get_with_retry(url)
        if resp is None or resp.status_code != 200:
            return None
        encoding = self._detect_encoding(resp)
        for enc in [encoding, "utf-8", "latin-1", "cp1252"]:
            try:
                return resp.content.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue
        return resp.text

    # ------------------------------------------------------------------
    # URL construction
    # ------------------------------------------------------------------

    def _build_section_url(self, year: int, area: str, section_code: str) -> str:
        """Build the direct URL for a portal section.

        URL pattern: {PORTAL_BASE}/-/ta/{org_code}/{year}/A/{area}/{section_code}
        """
        return f"{PORTAL_BASE}/-/ta/{self.org_code}/{year}/A/{area}/{section_code}"

    def _build_month_url(self, year: int, area: str, section_code: str, month: int) -> str:
        """Build URL for a specific month within a section.

        The portal uses various URL patterns for monthly data. We try the most common ones.
        """
        month_name = MONTH_NAMES.get(month, str(month))
        return f"{PORTAL_BASE}/-/ta/{self.org_code}/{year}/A/{area}/{section_code}/{month_name}"

    def _build_org_url(self) -> str:
        """Build the main organization page URL."""
        return f"{PORTAL_BASE}?codOrganismo={self.org_code}"

    # ------------------------------------------------------------------
    # Level 0: Direct URL access
    # ------------------------------------------------------------------

    def _try_direct_url(self, year: int, area: str, section: str, month: int) -> str | None:
        """Attempt to access the data page via direct URL patterns.

        Returns the HTML content if successful, None otherwise.
        """
        section_code = SECTION_CODES.get(section, section)

        urls_to_try = [
            # Pattern 1: Full path with month name
            self._build_month_url(year, area, section_code, month),
            # Pattern 2: Section URL without month (data may be on main page)
            self._build_section_url(year, area, section_code),
            # Pattern 3: With numeric month
            f"{PORTAL_BASE}/-/ta/{self.org_code}/{year}/A/{area}/{section_code}/{month}",
            # Pattern 4: Query string params
            f"{PORTAL_BASE}?codOrganismo={self.org_code}&anio={year}&mes={month}&seccion={section_code}",
        ]

        for url in urls_to_try:
            logger.info(f"Trying direct URL: {url}")
            html = self._get_html(url)
            if html and len(html) > 500:
                self._save_html(f"direct_{section}_{year}_{month:02d}", html)
                # Check if page has actual data content (not just a redirect or error)
                soup = self._parse_soup(html)
                if self._page_has_data(soup, section):
                    logger.info(f"Direct URL success: {url}")
                    return html
                logger.debug(f"Direct URL returned page without data tables: {url}")
            self._rate_limit()

        return None

    def _page_has_data(self, soup: BeautifulSoup, section: str) -> bool:
        """Check if a page contains data tables or download links."""
        # Check for tables with data
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            if len(rows) > 2:
                return True

        # Check for download links
        for a in soup.find_all("a", href=True):
            href = a["href"].lower()
            if any(ext in href for ext in [".csv", ".xlsx", ".xls"]):
                return True

        return False

    # ------------------------------------------------------------------
    # Level 1: CSV/Excel download
    # ------------------------------------------------------------------

    def _try_csv_download(self, soup: BeautifulSoup, base_url: str,
                          section: str, year: int, month: int) -> list[dict] | None:
        """Search the HTML for CSV/Excel download links and fetch them."""
        download_patterns = [
            r'\.csv',
            r'\.xlsx?',
            r'export',
            r'descargar',
            r'download',
        ]

        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True).lower()
            href_lower = href.lower()

            is_download = False
            for pattern in download_patterns:
                if re.search(pattern, href_lower) or re.search(pattern, text):
                    is_download = True
                    break

            if is_download:
                full_url = urljoin(base_url, href)
                links.append({"url": full_url, "text": text, "href": href})

        if not links:
            logger.debug("No download links found on page")
            return None

        for link in links:
            url = link["url"]
            logger.info(f"Trying download: {url} ({link['text'][:50]})")
            try:
                resp = self._get_with_retry(url)
                if resp is None or resp.status_code != 200:
                    continue
                if len(resp.content) < 100:
                    continue

                content_type = resp.headers.get("content-type", "").lower()

                # Determine file type
                ext = "csv"
                if "excel" in content_type or "spreadsheet" in content_type or url.endswith((".xlsx", ".xls")):
                    ext = "xlsx"

                file_path = self.raw_dir / f"{section}_{year}_{month:02d}_http.{ext}"
                file_path.write_bytes(resp.content)
                logger.info(f"Downloaded: {file_path} ({len(resp.content)} bytes)")

                records = self._parse_csv(file_path)
                if records:
                    return records

                self._rate_limit()
            except Exception as e:
                logger.debug(f"Download from {url} failed: {e}")
                continue

        return None

    # ------------------------------------------------------------------
    # Level 2: HTML table parsing
    # ------------------------------------------------------------------

    def _parse_html_table(self, soup: BeautifulSoup, section: str) -> list[dict]:
        """Extract data from HTML tables in the page.

        Identifies the correct table by matching column keywords for the section type.
        """
        keywords = HONORARIOS_KEYWORDS if section == "honorarios" else CONTRATA_PLANTA_KEYWORDS
        tables = soup.find_all("table")

        best_table = None
        best_score = 0

        for table in tables:
            # Score table by how many expected keywords appear in headers
            headers = self._extract_table_headers(table)
            if not headers:
                continue
            header_text = " ".join(h.lower() for h in headers)
            score = sum(1 for kw in keywords if kw in header_text)
            row_count = len(table.find_all("tr"))

            if score > best_score and row_count > 1:
                best_score = score
                best_table = table

        if best_table is None:
            # Fallback: pick the largest table with > 3 columns and > 2 rows
            for table in tables:
                headers = self._extract_table_headers(table)
                rows = table.find_all("tr")
                if len(headers) >= 3 and len(rows) > 2:
                    best_table = table
                    break

        if best_table is None:
            logger.debug("No suitable data table found in HTML")
            return []

        headers = self._extract_table_headers(best_table)
        if not headers:
            return []

        records = self._extract_table_rows(best_table, headers)
        logger.info(f"HTML table parsing: {len(headers)} columns, {len(records)} rows")
        return records

    def _extract_table_headers(self, table: Tag) -> list[str]:
        """Extract column headers from a table element."""
        headers = []

        # Try <thead> <th>
        thead = table.find("thead")
        if thead:
            for th in thead.find_all("th"):
                headers.append(th.get_text(strip=True))
            if headers:
                return headers

            # Try <thead> <td>
            for td in thead.find_all("td"):
                headers.append(td.get_text(strip=True))
            if headers:
                return headers

        # Try first <tr> with <th> elements
        first_row = table.find("tr")
        if first_row:
            ths = first_row.find_all("th")
            if ths:
                return [th.get_text(strip=True) for th in ths]
            # First row with <td> as headers
            tds = first_row.find_all("td")
            if tds:
                candidate = [td.get_text(strip=True) for td in tds]
                # Check if first row looks like headers (contains text, not just numbers)
                if any(not c.replace(".", "").replace(",", "").isdigit() for c in candidate if c):
                    return candidate

        return headers

    def _extract_table_rows(self, table: Tag, headers: list[str]) -> list[dict]:
        """Extract data rows from a table given headers."""
        records = []

        # Find data rows
        tbody = table.find("tbody")
        if tbody:
            rows = tbody.find_all("tr")
        else:
            all_rows = table.find_all("tr")
            rows = all_rows[1:]  # skip header row

        for row in rows:
            cells = row.find_all(["td", "th"])
            if not cells:
                continue

            record = {}
            for j, cell in enumerate(cells):
                if j < len(headers):
                    text = cell.get_text(strip=True)
                    record[headers[j]] = text

            # Only include rows that have at least some non-empty values
            if any(v.strip() for v in record.values() if v):
                records.append(record)

        return records

    def _handle_pagination(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """Find pagination links and return URLs for subsequent pages."""
        next_urls = []

        # Pattern 1: "Siguiente" / ">>" links
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True).lower()
            if text in ("siguiente", ">>", "›", "next", ">"):
                href = a["href"]
                if href and not href.startswith("javascript:void"):
                    next_urls.append(urljoin(base_url, href))

        # Pattern 2: Numbered page links (e.g., ?page=2, ?p=2, ?cur=2)
        page_pattern = re.compile(r'[?&](page|p|cur|pag|pagina)=(\d+)', re.IGNORECASE)
        for a in soup.find_all("a", href=True):
            href = a["href"]
            match = page_pattern.search(href)
            if match:
                full_url = urljoin(base_url, href)
                if full_url not in next_urls:
                    next_urls.append(full_url)

        # Pattern 3: PrimeFaces/Liferay pagination
        for el in soup.find_all(class_=re.compile(r'paginator.*next|next.*page', re.IGNORECASE)):
            if el.name == "a" and el.get("href"):
                next_urls.append(urljoin(base_url, el["href"]))
            elif el.name in ("span", "button"):
                # May be a JS-driven element - can't follow via HTTP
                pass

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for url in next_urls:
            if url not in seen:
                seen.add(url)
                unique.append(url)

        return unique

    def _extract_all_pages(self, url: str, section: str, year: int, month: int,
                           max_pages: int = 50) -> list[dict]:
        """Extract data from a page and all its paginated successors."""
        all_records = []
        visited = set()
        current_url = url

        for page_num in range(max_pages):
            if current_url in visited:
                break
            visited.add(current_url)

            html = self._get_html(current_url)
            if not html:
                break

            soup = self._parse_soup(html)

            # Try CSV download first (only on first page)
            if page_num == 0:
                csv_records = self._try_csv_download(soup, current_url, section, year, month)
                if csv_records:
                    return csv_records

            # Parse HTML table
            page_records = self._parse_html_table(soup, section)
            if not page_records:
                if page_num == 0:
                    logger.debug("No records found on first page")
                break

            all_records.extend(page_records)
            logger.info(f"Page {page_num + 1}: {len(page_records)} rows (total: {len(all_records)})")

            # Find next page
            next_urls = self._handle_pagination(soup, current_url)
            next_url = None
            for candidate in next_urls:
                if candidate not in visited:
                    next_url = candidate
                    break

            if not next_url:
                break

            current_url = next_url
            self._rate_limit()

        return all_records

    # ------------------------------------------------------------------
    # Level 3: Discover internal API / AJAX endpoints
    # ------------------------------------------------------------------

    def _discover_ajax_endpoints(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """Inspect HTML for internal AJAX endpoints that might serve data."""
        endpoints = []

        # Search <script> tags for URLs
        for script in soup.find_all("script"):
            text = script.string or ""
            # Look for URL patterns in JavaScript
            url_patterns = re.findall(
                r'["\']((https?://[^"\']+|/[^"\']*(?:api|data|export|csv|json|servlet|resource)[^"\']*))["\']\s*',
                text, re.IGNORECASE
            )
            for match in url_patterns:
                url = match[0] if isinstance(match, tuple) else match
                full_url = urljoin(base_url, url)
                endpoints.append(full_url)

        # Search <form> actions
        for form in soup.find_all("form", action=True):
            action = form["action"]
            if action and not action.startswith("javascript:"):
                endpoints.append(urljoin(base_url, action))

        # Search data-* attributes
        for el in soup.find_all(attrs={"data-url": True}):
            endpoints.append(urljoin(base_url, el["data-url"]))
        for el in soup.find_all(attrs={"data-source": True}):
            endpoints.append(urljoin(base_url, el["data-source"]))
        for el in soup.find_all(attrs={"data-ajax-url": True}):
            endpoints.append(urljoin(base_url, el["data-ajax-url"]))

        # Search <iframe> src
        for iframe in soup.find_all("iframe", src=True):
            src = iframe["src"]
            if src and not src.startswith("javascript:"):
                endpoints.append(urljoin(base_url, src))

        # Deduplicate
        return list(dict.fromkeys(endpoints))

    def _try_ajax_endpoints(self, soup: BeautifulSoup, base_url: str,
                            section: str, year: int, month: int) -> list[dict]:
        """Attempt to fetch data from discovered AJAX endpoints."""
        endpoints = self._discover_ajax_endpoints(soup, base_url)
        if not endpoints:
            return []

        logger.info(f"Discovered {len(endpoints)} potential AJAX endpoints")

        for ep_url in endpoints[:10]:  # Limit attempts
            logger.debug(f"Trying AJAX endpoint: {ep_url}")
            try:
                resp = self._get_with_retry(ep_url, retries=1)
                if resp is None or resp.status_code != 200:
                    continue

                content_type = resp.headers.get("content-type", "").lower()

                # JSON response
                if "json" in content_type:
                    try:
                        data = resp.json()
                        records = self._parse_json_response(data)
                        if records:
                            logger.info(f"Got {len(records)} records from AJAX JSON: {ep_url}")
                            return records
                    except (json.JSONDecodeError, ValueError):
                        pass

                # HTML response with tables
                if "html" in content_type and len(resp.text) > 200:
                    ep_soup = self._parse_soup(resp.text)
                    records = self._parse_html_table(ep_soup, section)
                    if records:
                        logger.info(f"Got {len(records)} records from AJAX HTML: {ep_url}")
                        return records

                # CSV response
                if any(ct in content_type for ct in ["csv", "text/plain", "octet-stream"]):
                    file_path = self.raw_dir / f"{section}_{year}_{month:02d}_ajax.csv"
                    file_path.write_bytes(resp.content)
                    records = self._parse_csv(file_path)
                    if records:
                        return records

                self._rate_limit()
            except Exception as e:
                logger.debug(f"AJAX endpoint {ep_url} failed: {e}")
                continue

        return []

    def _parse_json_response(self, data) -> list[dict]:
        """Parse a JSON API response into a list of records."""
        if isinstance(data, list):
            if data and isinstance(data[0], dict):
                return data
            return []

        if isinstance(data, dict):
            # Common patterns: {"data": [...], ...} or {"rows": [...], ...}
            for key in ("data", "rows", "records", "items", "results", "content"):
                if key in data and isinstance(data[key], list):
                    items = data[key]
                    if items and isinstance(items[0], dict):
                        return items
            # Sometimes the dict itself contains arrays of values
            # with a separate "columns" key
            if "columns" in data and "data" in data:
                cols = data["columns"]
                rows = data["data"]
                if isinstance(cols, list) and isinstance(rows, list):
                    return [dict(zip(cols, row)) for row in rows if isinstance(row, list)]

        return []

    # ------------------------------------------------------------------
    # CSV parsing (shared with portal_scraper.py)
    # ------------------------------------------------------------------

    def _parse_csv(self, file_path: Path) -> list[dict]:
        """Parse CSV/Excel with robust encoding and delimiter detection."""
        suffix = file_path.suffix.lower()

        # Handle Excel files
        if suffix in (".xlsx", ".xls"):
            return self._parse_excel(file_path)

        # CSV parsing
        for encoding in ["utf-8", "latin-1", "cp1252", "iso-8859-1"]:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    content = f.read()
                for delimiter in [";", ",", "\t"]:
                    try:
                        reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
                        records = [dict(row) for row in reader]
                        if records and len(records[0]) > 1:
                            logger.info(f"Parsed CSV ({encoding}, delim='{delimiter}'): {len(records)} records")
                            return records
                    except csv.Error:
                        continue
            except UnicodeDecodeError:
                continue

        logger.warning(f"Could not parse CSV: {file_path}")
        return []

    def _parse_excel(self, file_path: Path) -> list[dict]:
        """Parse Excel file using pandas."""
        try:
            import pandas as pd
            df = pd.read_excel(file_path, engine="openpyxl")
            if df.empty:
                return []
            # Convert NaN to None
            df = df.where(df.notna(), None)
            records = df.to_dict("records")
            # Convert all values to strings (consistent with CSV parsing)
            for rec in records:
                for k, v in rec.items():
                    if v is not None:
                        rec[k] = str(v)
            logger.info(f"Parsed Excel: {len(records)} records")
            return records
        except Exception as e:
            logger.warning(f"Excel parsing failed for {file_path}: {e}")
            return []

    # ------------------------------------------------------------------
    # Normalization (same logic as portal_scraper.py)
    # ------------------------------------------------------------------

    def _normalize_honorarios(self, raw_records: list[dict]) -> list[dict]:
        """Normalize raw honorarios records to standard field names."""
        normalized = []
        for raw in raw_records:
            rec = {}
            for key, val in raw.items():
                k = key.lower().strip()
                if "nombre" in k or "persona" in k:
                    rec["nombre"] = val
                elif k == "rut" or "rut" in k:
                    rec["rut"] = val
                elif "descripci" in k and "funci" in k:
                    rec["descripcion_funcion"] = val
                elif "calificaci" in k or "profesi" in k:
                    rec["calificacion_profesional"] = val
                elif "fecha" in k and "inicio" in k:
                    rec["fecha_inicio"] = val
                elif "fecha" in k and ("t" in k and "rmino" in k):
                    rec["fecha_termino"] = val
                elif "brut" in k and ("remun" in k or "renta" in k):
                    rec["remuneracion_bruta"] = val
                elif ("l" in k and "quid" in k) and ("remun" in k or "renta" in k):
                    rec["remuneracion_liquida"] = val
                elif "monto" in k or "total" in k:
                    rec["monto_total"] = val
                elif "observ" in k:
                    rec["observaciones"] = val
                elif "vi" in k and "tic" in k:
                    rec["viatico"] = val
                elif "unidad" in k or "monet" in k:
                    rec["unidad_monetaria"] = val
            normalized.append(rec)
        return normalized

    def _normalize_contrata_planta(self, raw_records: list[dict]) -> list[dict]:
        """Normalize contrata/planta records to standard field names."""
        normalized = []
        for raw in raw_records:
            rec = {}
            for key, val in raw.items():
                k = key.lower().strip()
                if "nombre" in k or "persona" in k:
                    rec["nombre"] = val
                elif k == "rut" or "rut" in k:
                    rec["rut"] = val
                elif "grado" in k or "eus" in k:
                    rec["grado_eus"] = val
                elif "cargo" in k:
                    rec["cargo"] = val
                elif "calificaci" in k or "profesi" in k:
                    rec["calificacion_profesional"] = val
                elif "regi" in k:
                    rec["region"] = val
                elif "asignaci" in k:
                    rec["asignaciones"] = val
                elif "brut" in k:
                    rec["remuneracion_bruta"] = val
                elif "l" in k and "quid" in k:
                    rec["remuneracion_liquida"] = val
                elif "fecha" in k and "inicio" in k:
                    rec["fecha_inicio"] = val
                elif "fecha" in k and ("t" in k and "rmino" in k):
                    rec["fecha_termino"] = val
                elif "observ" in k:
                    rec["observaciones"] = val
                elif "hora" in k:
                    rec["horas"] = val
            normalized.append(rec)
        return normalized

    # ------------------------------------------------------------------
    # Main scraping orchestration (multi-level strategy)
    # ------------------------------------------------------------------

    def _scrape_section(self, section: str, area: str, year: int, month: int) -> list[dict]:
        """Scrape a specific section using the multi-level strategy.

        Level 0: Direct URL access
        Level 1: CSV/Excel download from discovered links
        Level 2: HTML table parsing with pagination
        Level 3: AJAX/API endpoint discovery
        """
        label = f"{section} {year}/{month:02d}"
        section_code = SECTION_CODES.get(section, section)

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(f"Scraping {label} via HTTP (attempt {attempt}/{MAX_RETRIES})")

                # Level 0: Try direct URLs
                html = self._try_direct_url(year, area, section, month)

                if html is None:
                    # Try the organization landing page as starting point
                    org_url = self._build_org_url()
                    html = self._get_html(org_url)
                    if html:
                        self._save_html(f"org_landing_{year}_{month:02d}", html)

                if html is None:
                    logger.warning(f"{label}: could not fetch any page on attempt {attempt}")
                    if attempt < MAX_RETRIES:
                        time.sleep(2 ** attempt)
                    continue

                soup = self._parse_soup(html)

                # Build base URL for resolving relative links
                base_url = self._build_section_url(year, area, section_code)

                # Level 1: Try CSV/Excel download
                csv_records = self._try_csv_download(soup, base_url, section, year, month)
                if csv_records:
                    logger.info(f"{label}: got {len(csv_records)} records via CSV download")
                    return self._normalize(csv_records, section)

                # Level 2: Parse HTML tables with pagination
                # First try all pages from the direct URL
                records = self._parse_html_table(soup, section)
                if records:
                    logger.info(f"{label}: got {len(records)} records from HTML table (page 1)")
                    # Check for pagination
                    next_urls = self._handle_pagination(soup, base_url)
                    visited = {base_url}
                    for next_url in next_urls:
                        if next_url in visited:
                            continue
                        visited.add(next_url)
                        self._rate_limit()
                        next_html = self._get_html(next_url)
                        if not next_html:
                            break
                        next_soup = self._parse_soup(next_html)
                        page_records = self._parse_html_table(next_soup, section)
                        if not page_records:
                            break
                        records.extend(page_records)
                        logger.info(f"{label}: additional page yielded {len(page_records)} rows (total: {len(records)})")
                        more_urls = self._handle_pagination(next_soup, next_url)
                        for mu in more_urls:
                            if mu not in visited:
                                next_urls.append(mu)

                    return self._normalize(records, section)

                # Level 3: Discover AJAX endpoints
                ajax_records = self._try_ajax_endpoints(soup, base_url, section, year, month)
                if ajax_records:
                    logger.info(f"{label}: got {len(ajax_records)} records via AJAX")
                    return self._normalize(ajax_records, section)

                # No data found - check if page requires JavaScript
                if self._page_requires_js(soup):
                    logger.warning(
                        f"{label}: page appears to require JavaScript rendering. "
                        "HTTP scraper cannot extract data; Playwright fallback recommended."
                    )
                    self._save_html(f"js_required_{section}_{year}_{month:02d}", html)
                    return []

                logger.warning(f"{label}: no data found on attempt {attempt}")
                self._save_html(f"no_data_{section}_{year}_{month:02d}_att{attempt}", html)

                if attempt < MAX_RETRIES:
                    wait = 2 ** attempt
                    logger.info(f"Retrying in {wait}s...")
                    time.sleep(wait)

            except Exception as e:
                logger.error(f"{label}: error on attempt {attempt}: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** attempt)

        logger.error(f"{label}: all {MAX_RETRIES} attempts exhausted, returning empty")
        return []

    def _normalize(self, records: list[dict], section: str) -> list[dict]:
        """Apply the correct normalizer based on section type."""
        if section == "honorarios":
            return self._normalize_honorarios(records)
        return self._normalize_contrata_planta(records)

    def _page_requires_js(self, soup: BeautifulSoup) -> bool:
        """Heuristic to detect if the page requires JavaScript to render data."""
        # Check for JSF/Liferay indicators
        indicators = [
            soup.find("noscript"),
            soup.find(attrs={"class": re.compile(r"portlet|liferay", re.IGNORECASE)}),
            soup.find("form", attrs={"id": re.compile(r"j_id|javax\.faces", re.IGNORECASE)}),
        ]
        if any(indicators):
            # But if there are also tables with data, JS may not be required
            tables = soup.find_all("table")
            for table in tables:
                if len(table.find_all("tr")) > 3:
                    return False
            return True

        # Check for empty body / loading placeholders
        body = soup.find("body")
        if body:
            text = body.get_text(strip=True)
            if len(text) < 200:
                return True

        return False

    # ------------------------------------------------------------------
    # Discovery helper (explores org page for data links)
    # ------------------------------------------------------------------

    def _discover_data_urls(self, area: str, year: int) -> dict[str, list[str]]:
        """Navigate the org landing page and discover URLs for each section.

        Returns a dict mapping section names to lists of discovered URLs.
        """
        discovered = {"honorarios": [], "contrata": [], "planta": [], "escalas": []}

        org_url = self._build_org_url()
        html = self._get_html(org_url)
        if not html:
            return discovered

        soup = self._parse_soup(html)

        # Look for links containing section keywords
        section_keywords = {
            "honorarios": ["honorario", "4.1.3", "contratadas a honorarios"],
            "contrata": ["contrata", "4.1.2", "personal a contrata"],
            "planta": ["planta", "4.1.1", "personal de planta"],
            "escalas": ["escala", "4.1.4", "remuneraciones"],
        }

        for a in soup.find_all("a", href=True):
            href = a["href"].lower()
            text = a.get_text(strip=True).lower()
            combined = f"{href} {text}"

            for section, keywords in section_keywords.items():
                if any(kw in combined for kw in keywords):
                    full_url = urljoin(org_url, a["href"])
                    if full_url not in discovered[section]:
                        discovered[section].append(full_url)

        return discovered

    # ------------------------------------------------------------------
    # Public API (same interface as PortalScraper)
    # ------------------------------------------------------------------

    def scrape_honorarios(self, area: str, year: int, month: int) -> list[dict]:
        """Scrape 'Personas naturales contratadas a honorarios' for one month."""
        return self._scrape_section("honorarios", area, year, month)

    def scrape_contrata(self, area: str, year: int, month: int) -> list[dict]:
        """Scrape 'Personal a Contrata' for one month."""
        return self._scrape_section("contrata", area, year, month)

    def scrape_planta(self, area: str, year: int, month: int) -> list[dict]:
        """Scrape 'Personal de Planta' for one month."""
        return self._scrape_section("planta", area, year, month)

    def scrape_escalas(self, year: int):
        """Download remuneration scale files (Excel/PDF).

        Tries to find and download scale files from the portal.
        """
        section_code = SECTION_CODES["escalas"]
        urls_to_try = [
            f"{PORTAL_BASE}/-/ta/{self.org_code}/{year}/A/Salud/{section_code}",
            f"{PORTAL_BASE}/-/ta/{self.org_code}/{year}/A/Educacion/{section_code}",
            f"{PORTAL_BASE}?codOrganismo={self.org_code}",
        ]

        downloaded = 0
        for url in urls_to_try:
            html = self._get_html(url)
            if not html:
                continue

            soup = self._parse_soup(html)

            # Look for downloadable files
            for a in soup.find_all("a", href=True):
                href = a["href"].lower()
                if any(ext in href for ext in [".xlsx", ".xls", ".pdf"]):
                    full_url = urljoin(url, a["href"])
                    try:
                        resp = self._get_with_retry(full_url, retries=1)
                        if resp and resp.status_code == 200 and len(resp.content) > 500:
                            ext = "xlsx"
                            if ".pdf" in href:
                                ext = "pdf"
                            elif ".xls" in href and ".xlsx" not in href:
                                ext = "xls"
                            file_path = self.raw_dir / f"escala_{year}_{downloaded}.{ext}"
                            file_path.write_bytes(resp.content)
                            logger.info(f"Escala downloaded: {file_path} ({len(resp.content)} bytes)")
                            downloaded += 1
                    except Exception as e:
                        logger.debug(f"Escala download from {full_url} failed: {e}")

            self._rate_limit()

        if downloaded == 0:
            logger.warning(f"No escala files downloaded for year {year}")
