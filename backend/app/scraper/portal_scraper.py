"""Playwright-based scraper for Portal Transparencia Chile."""
import os
import csv
import io
import re
import time
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, Browser, TimeoutError as PwTimeout

logger = logging.getLogger(__name__)

MONTH_NAMES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

PORTAL_BASE = "https://www.portaltransparencia.cl/PortalPdT/directorio-de-organismos-regulados/"

DATA_DIR = os.environ.get("DATA_DIR", "/app/data")


class PortalScraper:
    def __init__(self, org_code: str):
        self.org_code = org_code
        self.pw = sync_playwright().start()
        self.browser: Browser = self.pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        self.context = self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
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

    def _navigate_to_org(self):
        url = f"{PORTAL_BASE}?org={self.org_code}"
        logger.info(f"Navigating to {url}")
        self.page.goto(url, wait_until="networkidle", timeout=60000)
        time.sleep(2)

    def _screenshot(self, name: str):
        try:
            path = self.raw_dir / f"screenshot_{name}.png"
            self.page.screenshot(path=str(path))
            logger.info(f"Screenshot saved: {path}")
        except Exception as e:
            logger.warning(f"Screenshot failed: {e}")

    def _try_download_csv(self, section_name: str, area: str, year: int, month: int) -> list[dict] | None:
        """Attempt to find and click CSV download button. Returns parsed records or None."""
        try:
            download_btns = self.page.locator("a:has-text('Descargar'), button:has-text('CSV'), a:has-text('CSV'), a[href*='.csv']")
            if download_btns.count() > 0:
                with self.page.expect_download(timeout=30000) as download_info:
                    download_btns.first.click()
                download = download_info.value
                file_path = self.raw_dir / f"{section_name}_{year}_{month:02d}.csv"
                download.save_as(str(file_path))
                logger.info(f"CSV downloaded: {file_path}")
                return self._parse_csv(file_path)
        except (PwTimeout, Exception) as e:
            logger.warning(f"CSV download failed for {section_name} {month}: {e}")
        return None

    def _extract_table_data(self, max_pages: int = 50) -> list[dict]:
        """Fallback: extract data from HTML table with pagination."""
        all_records = []
        for page_num in range(max_pages):
            try:
                table = self.page.locator("table.tabla-datos, table.dataTable, table[id*='tabla'], table.table")
                if table.count() == 0:
                    table = self.page.locator("table").first
                if table.count() == 0:
                    break

                headers = []
                ths = table.locator("thead th, thead td")
                for i in range(ths.count()):
                    headers.append(ths.nth(i).inner_text().strip())

                if not headers:
                    first_row = table.locator("tr").first
                    tds = first_row.locator("td, th")
                    for i in range(tds.count()):
                        headers.append(tds.nth(i).inner_text().strip())

                rows = table.locator("tbody tr")
                for i in range(rows.count()):
                    cells = rows.nth(i).locator("td")
                    record = {}
                    for j in range(min(cells.count(), len(headers))):
                        record[headers[j]] = cells.nth(j).inner_text().strip()
                    if record:
                        all_records.append(record)

                # Try pagination
                next_btn = self.page.locator(
                    "a:has-text('Siguiente'), button:has-text('Siguiente'), "
                    "a:has-text('>>'), .paginate_button.next:not(.disabled), "
                    "li.next:not(.disabled) a"
                )
                if next_btn.count() > 0 and next_btn.first.is_visible():
                    next_btn.first.click()
                    self.page.wait_for_load_state("networkidle", timeout=15000)
                    time.sleep(1)
                else:
                    break
            except Exception as e:
                logger.warning(f"Table extraction page {page_num} error: {e}")
                break

        return all_records

    def _parse_csv(self, file_path: Path) -> list[dict]:
        """Parse a CSV file with robust encoding handling."""
        for encoding in ["utf-8", "latin-1", "cp1252", "iso-8859-1"]:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    content = f.read()
                reader = csv.DictReader(io.StringIO(content), delimiter=";")
                records = []
                for row in reader:
                    records.append(dict(row))
                if records:
                    return records
            except (UnicodeDecodeError, csv.Error):
                continue
        return []

    def _normalize_honorarios(self, raw_records: list[dict]) -> list[dict]:
        """Normalize raw honorarios records to standard field names.

        Portal columns (actual names from transparencia):
          Año, Mes, Nombre completo, Grado EUS (si corresponde),
          Descripción de la función, Calificación profesional o formación,
          Región, **Honorario Total Bruto Mensualizado**,
          Remuneración líquida mensualizada, Tipo de pago, Descripción pago,
          Número de cuotas, Fecha de inicio, Fecha de término,
          Observaciones, Enlace funciones desarrolladas, Viáticos
        """
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
                elif "calificaci" in k or "profesi" in k or "formaci" in k:
                    rec["calificacion_profesional"] = val
                elif "fecha" in k and "inicio" in k:
                    rec["fecha_inicio"] = val
                elif "fecha" in k and "rmino" in k:
                    rec["fecha_termino"] = val
                # "Honorario Total Bruto Mensualizado" - primary for honorarios
                elif "honorario" in k and "brut" in k:
                    rec["remuneracion_bruta"] = val
                # "Remuneración bruta" generic fallback
                elif "brut" in k and "remun" in k:
                    rec.setdefault("remuneracion_bruta", val)
                # Any column with "brut" that hasn't been captured yet
                elif "brut" in k and "remuneracion_bruta" not in rec:
                    rec["remuneracion_bruta"] = val
                # "Remuneración líquida mensualizada"
                elif "quid" in k:
                    rec["remuneracion_liquida"] = val
                elif "observ" in k:
                    rec["observaciones"] = val
                elif "vi" in k and "tic" in k:
                    rec["viatico"] = val
                elif "grado" in k:
                    rec["grado_eus"] = val
                elif "regi" in k and "regi" in k:
                    rec["region"] = val
            # Copy bruta to monto_total for honorarios
            if "remuneracion_bruta" in rec:
                rec["monto_total"] = rec["remuneracion_bruta"]
            normalized.append(rec)
        return normalized

    def _normalize_contrata_planta(self, raw_records: list[dict]) -> list[dict]:
        """Normalize contrata/planta records.

        Portal columns (actual names from transparencia):
          Año, Mes, Nombre Completo, Grado EUS, Cargo o Función,
          Calificación Profesional, Región,
          **Remuneración bruta del mes (incluye bonos e incentivos, asig. especiales, horas extras)**,
          Remuneración líquida del mes, Asignaciones especiales,
          Fecha de inicio, Fecha de término, Observaciones, Horas extras

        IMPORTANT: "bruta" must be checked BEFORE "líquida" to avoid mis-mapping.
        The bruta column contains the full cost to the service.
        """
        normalized = []
        for raw in raw_records:
            rec = {}
            # First pass: identify bruta and liquida columns by exact header matching
            bruta_key = None
            liquida_key = None
            for key in raw.keys():
                k = key.lower().strip()
                if "brut" in k:
                    bruta_key = key
                elif "quid" in k:
                    liquida_key = key

            for key, val in raw.items():
                k = key.lower().strip()
                if "nombre" in k or "persona" in k:
                    rec["nombre"] = val
                elif k == "rut" or "rut" in k:
                    rec["rut"] = val
                elif "grado" in k or "eus" in k:
                    rec["grado_eus"] = val
                elif "cargo" in k or ("funci" in k and "descripci" not in k):
                    rec["cargo"] = val
                elif "calificaci" in k or "profesi" in k or "formaci" in k:
                    rec["calificacion_profesional"] = val
                elif "regi" in k:
                    rec["region"] = val
                elif "asignaci" in k or "especial" in k:
                    rec["asignaciones"] = val
                elif key == bruta_key:
                    rec["remuneracion_bruta"] = val
                elif key == liquida_key:
                    rec["remuneracion_liquida"] = val
                elif "fecha" in k and "inicio" in k:
                    rec["fecha_inicio"] = val
                elif "fecha" in k and "rmino" in k:
                    rec["fecha_termino"] = val
                elif "observ" in k:
                    rec["observaciones"] = val
                elif "hora" in k and "extra" in k:
                    rec["horas"] = val
                elif "hora" in k:
                    rec["horas"] = val
            normalized.append(rec)
        return normalized

    def _navigate_to_section(self, section_text: str, area: str, year: int, month: int = None):
        """Navigate to a specific section in the portal."""
        self._navigate_to_org()
        self._screenshot(f"org_home")

        # Click on "Personal y remuneraciones"
        try:
            personal_link = self.page.locator(
                "a:has-text('Personal y remuneraciones'), "
                "a:has-text('04'), "
                "span:has-text('Personal y remuneraciones')"
            )
            if personal_link.count() > 0:
                personal_link.first.click()
                self.page.wait_for_load_state("networkidle", timeout=30000)
                time.sleep(2)
        except Exception as e:
            logger.warning(f"Click 'Personal y remuneraciones' failed: {e}")

        self._screenshot(f"personal_section")

        # Click on section (e.g., "Personas naturales contratadas a honorarios")
        try:
            section_link = self.page.locator(f"a:has-text('{section_text}'), span:has-text('{section_text}')")
            if section_link.count() > 0:
                section_link.first.click()
                self.page.wait_for_load_state("networkidle", timeout=30000)
                time.sleep(2)
        except Exception as e:
            logger.warning(f"Click section '{section_text}' failed: {e}")

        self._screenshot(f"section_{section_text[:20]}")

        # Select area (e.g., "Salud")
        try:
            area_select = self.page.locator(
                f"select option:has-text('{area}'), "
                f"a:has-text('{area}'), "
                f"li:has-text('{area}')"
            )
            if area_select.count() > 0:
                area_select.first.click()
                self.page.wait_for_load_state("networkidle", timeout=15000)
                time.sleep(1)
        except Exception as e:
            logger.warning(f"Select area '{area}' failed: {e}")

        # Select year
        try:
            year_select = self.page.locator(
                f"select option:has-text('{year}'), "
                f"a:has-text('{year}'), "
                f"li:has-text('{year}')"
            )
            if year_select.count() > 0:
                year_select.first.click()
                self.page.wait_for_load_state("networkidle", timeout=15000)
                time.sleep(1)
        except Exception as e:
            logger.warning(f"Select year '{year}' failed: {e}")

        # Select month if specified
        if month:
            month_name = MONTH_NAMES.get(month, str(month))
            try:
                month_select = self.page.locator(
                    f"select option:has-text('{month_name}'), "
                    f"a:has-text('{month_name}'), "
                    f"li:has-text('{month_name}')"
                )
                if month_select.count() > 0:
                    month_select.first.click()
                    self.page.wait_for_load_state("networkidle", timeout=15000)
                    time.sleep(1)
            except Exception as e:
                logger.warning(f"Select month '{month_name}' failed: {e}")

        self._screenshot(f"ready_{section_text[:10]}_{year}_{month}")

    def scrape_honorarios(self, area: str, year: int, month: int) -> list[dict]:
        """Scrape honorarios for a specific month."""
        self._navigate_to_section(
            section_text="Personas naturales contratadas a honorarios",
            area=area, year=year, month=month,
        )

        # Try CSV download first
        records = self._try_download_csv("honorarios", area, year, month)
        if records:
            return self._normalize_honorarios(records)

        # Fallback: extract table
        logger.info(f"Falling back to table extraction for honorarios {year}/{month}")
        raw = self._extract_table_data()
        return self._normalize_honorarios(raw)

    def scrape_contrata(self, area: str, year: int, month: int) -> list[dict]:
        """Scrape contrata for a specific month."""
        self._navigate_to_section(
            section_text="Personal a Contrata",
            area=area, year=year, month=month,
        )

        records = self._try_download_csv("contrata", area, year, month)
        if records:
            return self._normalize_contrata_planta(records)

        logger.info(f"Falling back to table extraction for contrata {year}/{month}")
        raw = self._extract_table_data()
        return self._normalize_contrata_planta(raw)

    def scrape_planta(self, area: str, year: int, month: int) -> list[dict]:
        """Scrape planta for a specific month."""
        self._navigate_to_section(
            section_text="Personal de Planta",
            area=area, year=year, month=month,
        )

        records = self._try_download_csv("planta", area, year, month)
        if records:
            return self._normalize_contrata_planta(records)

        logger.info(f"Falling back to table extraction for planta {year}/{month}")
        raw = self._extract_table_data()
        return self._normalize_contrata_planta(raw)

    def scrape_escalas(self, year: int):
        """Download remuneration scale Excel files."""
        self._navigate_to_org()

        try:
            escala_link = self.page.locator(
                "a:has-text('Escala de remuneraciones'), "
                "a:has-text('escala'), "
                "span:has-text('Escala')"
            )
            if escala_link.count() > 0:
                escala_link.first.click()
                self.page.wait_for_load_state("networkidle", timeout=30000)
                time.sleep(2)

            # Try to find Excel downloads
            excel_links = self.page.locator(
                "a[href*='.xlsx'], a[href*='.xls'], "
                "a:has-text('Descargar'), a:has-text('Excel')"
            )
            for i in range(min(excel_links.count(), 5)):
                try:
                    with self.page.expect_download(timeout=30000) as dl:
                        excel_links.nth(i).click()
                    download = dl.value
                    file_path = self.raw_dir / f"escala_{year}_{i}.xlsx"
                    download.save_as(str(file_path))
                    logger.info(f"Escala downloaded: {file_path}")
                except Exception as e:
                    logger.warning(f"Escala download {i} failed: {e}")
        except Exception as e:
            logger.error(f"Escalas scraping failed: {e}")
