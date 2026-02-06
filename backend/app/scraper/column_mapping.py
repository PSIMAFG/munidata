"""Header-based column mapping for Portal Transparencia tables.

Replaces fragile index-based (tds[N]) extraction with header-name-driven
mapping. This makes parsing resilient to column reordering, inserted/removed
columns, and colspan variations across different municipalities.

Usage:
    headers = extract_headers_from_table(...)
    header_index = build_header_index(headers)
    for row in rows:
        nombre = get_cell(row, header_index, ALIASES_NOMBRE)
        rut    = get_cell(row, header_index, ALIASES_RUT)
        ...
"""

import re
import unicodedata
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------

def normalize_header(text: str) -> str:
    """Normalize a header string for fuzzy matching.

    Strips accents/diacritics, lowercases, removes dots/extra whitespace,
    and collapses consecutive spaces. This allows matching headers like
    "Remuneración Bruta" against alias "remuneracion bruta".
    """
    if not text:
        return ""
    # NFD decomposition then strip combining marks (accents)
    nfkd = unicodedata.normalize("NFKD", text)
    without_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Lowercase, strip dots, collapse whitespace
    result = without_accents.lower()
    result = result.replace(".", " ").replace("_", " ")
    result = re.sub(r"\s+", " ", result).strip()
    return result


def build_header_index(headers: list[str]) -> dict[str, int]:
    """Build a mapping from normalized header text to column index.

    Args:
        headers: Raw header strings as extracted from <th>/<td>.

    Returns:
        Dict mapping normalized header -> column index.
        If duplicate normalized headers exist, the first occurrence wins.
    """
    index = {}
    for i, raw in enumerate(headers):
        key = normalize_header(raw)
        if key and key not in index:
            index[key] = i
    return index


def get_cell(
    row: dict[str, str] | list[str],
    header_index: dict[str, int],
    aliases: list[str],
) -> Optional[str]:
    """Extract a cell value from a row using alias-based header matching.

    Tries each alias in order. For each alias, first attempts an exact match
    against normalized headers, then falls back to substring containment.

    Args:
        row: Either a dict {header: value} or a list of cell strings.
        header_index: Mapping from normalized header -> column index.
        aliases: List of normalized alias strings to try, in priority order.

    Returns:
        The cell text (stripped) or None if no alias matched.
    """
    if isinstance(row, dict):
        return _get_cell_from_dict(row, header_index, aliases)
    return _get_cell_from_list(row, header_index, aliases)


def _get_cell_from_dict(
    row: dict[str, str],
    header_index: dict[str, int],
    aliases: list[str],
) -> Optional[str]:
    """Get cell from a {header: value} dict using alias matching."""
    # Build a normalized version of the row keys
    norm_map = {}
    for key in row:
        nk = normalize_header(key)
        if nk not in norm_map:
            norm_map[nk] = key

    # Phase 1: Exact match on normalized key
    for alias in aliases:
        if alias in norm_map:
            val = row[norm_map[alias]]
            return val.strip() if isinstance(val, str) else str(val).strip() if val is not None else None

    # Phase 2: Substring containment (alias is a substring of header)
    for alias in aliases:
        for nk, orig_key in norm_map.items():
            if alias in nk:
                val = row[orig_key]
                return val.strip() if isinstance(val, str) else str(val).strip() if val is not None else None

    # Phase 3: Header is a substring of alias (for very short headers)
    for alias in aliases:
        for nk, orig_key in norm_map.items():
            if nk and len(nk) > 2 and nk in alias:
                val = row[orig_key]
                return val.strip() if isinstance(val, str) else str(val).strip() if val is not None else None

    return None


def _get_cell_from_list(
    row: list[str],
    header_index: dict[str, int],
    aliases: list[str],
) -> Optional[str]:
    """Get cell from a list of cell values using header_index + aliases."""
    # Phase 1: Exact match
    for alias in aliases:
        if alias in header_index:
            idx = header_index[alias]
            if 0 <= idx < len(row):
                val = row[idx]
                return val.strip() if isinstance(val, str) else str(val).strip() if val is not None else None

    # Phase 2: Substring containment
    for alias in aliases:
        for header_key, idx in header_index.items():
            if alias in header_key and 0 <= idx < len(row):
                val = row[idx]
                return val.strip() if isinstance(val, str) else str(val).strip() if val is not None else None

    return None


# ---------------------------------------------------------------------------
# Chilean money / RUT parsing
# ---------------------------------------------------------------------------

_MONEY_RE = re.compile(
    r"^\s*\$?\s*-?\s*[\d.,]+\s*$"
)


def parse_money_clp(text: Optional[str]) -> Optional[float]:
    """Parse a Chilean peso amount string into a float.

    Handles: "$", thousand-separator dots, decimal commas, spaces,
    parentheses (negative), and common non-numeric placeholders.

    Examples:
        "$ 1.234.567"  -> 1234567.0
        "1.234,56"     -> 1234.56
        "($ 500.000)"  -> -500000.0
        "$ 458.832"    -> 458832.0
        ""             -> None
        "-"            -> None
    """
    if text is None:
        return None
    cleaned = str(text).strip()
    if not cleaned:
        return None

    lower = cleaned.lower()
    if lower in ("", "-", "--", "no informa", "no aplica", "n/a", "s/i", "sin información"):
        return None

    # Handle parentheses as negative
    negative = False
    if cleaned.startswith("(") and cleaned.endswith(")"):
        negative = True
        cleaned = cleaned[1:-1]

    # Remove currency symbol and whitespace
    cleaned = cleaned.replace("$", "").replace(" ", "").strip()
    if not cleaned:
        return None

    try:
        # Chilean format: dots as thousands separator, comma as decimal
        # Detect: if there's a comma, it's the decimal separator
        if "," in cleaned:
            # Remove dots (thousand sep), replace comma with dot (decimal)
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            # Only dots: if there's more than one dot, they're thousands separators
            # If there's exactly one dot with 3 digits after, it's a thousands separator
            dot_count = cleaned.count(".")
            if dot_count > 1:
                cleaned = cleaned.replace(".", "")
            elif dot_count == 1:
                parts = cleaned.split(".")
                if len(parts[1]) == 3:
                    # e.g. "458.832" -> thousands separator
                    cleaned = cleaned.replace(".", "")
                # else: "458.83" -> decimal point (keep as is)

        result = float(cleaned)
        return -result if negative else result
    except (ValueError, TypeError):
        return None


def looks_like_money(text: Optional[str]) -> bool:
    """Check if a string looks like a monetary value (contains $ or digit patterns)."""
    if not text:
        return False
    t = str(text).strip()
    if "$" in t:
        return True
    # Check for patterns like "1.234.567" or "458.832" (thousands-separated numbers)
    if re.match(r"^\s*-?\s*\d{1,3}(\.\d{3})+\s*$", t):
        return True
    return False


# Chilean RUT validation
_RUT_PATTERN = re.compile(
    r"^\s*\d{1,2}\.?\d{3}\.?\d{3}-?[\dkK]\s*$"
)

_RUT_LOOSE = re.compile(
    r"\d{7,8}-?[\dkK]"
)


def is_rut(text: Optional[str]) -> bool:
    """Check if text looks like a valid Chilean RUT.

    Accepts formats: 12.345.678-9, 12345678-9, 123456789, 12.345.678-K
    Must have 7-8 digits + check digit (0-9 or K).
    """
    if not text:
        return False
    t = str(text).strip()
    if not t:
        return False
    return bool(_RUT_PATTERN.match(t))


def is_rut_loose(text: Optional[str]) -> bool:
    """Looser RUT check - just needs to contain a RUT-like pattern."""
    if not text:
        return False
    return bool(_RUT_LOOSE.search(str(text).strip()))


# ---------------------------------------------------------------------------
# Alias definitions for Portal Transparencia columns
# ---------------------------------------------------------------------------
# All aliases are pre-normalized (lowercase, no accents, no dots).
# They are tried in order; first match wins.

# -- Common fields (shared by all section types) --

ALIASES_NOMBRE = [
    "nombre",
    "nombre completo",
    "nombre funcionario",
    "nombre persona",
    "persona",
    "nombre y apellido",
    "apellido nombre",
    "funcionario",
    "prestador",
    "nombre prestador",
    "nombre proveedor",
    "proveedor",
]

ALIASES_RUT = [
    "rut",
    "rut funcionario",
    "rut prestador",
    "rut proveedor",
    "run",
    "cedula",
    "cedula identidad",
]

# -- Honorarios-specific fields --

ALIASES_HONORARIOS_FUNCION = [
    "descripcion de la funcion",
    "descripcion funcion",
    "funcion",
    "descripcion de la función",  # just in case normalize misses
    "cargo",
    "actividad",
]

ALIASES_HONORARIOS_CALIFICACION = [
    "calificacion profesional",
    "calificacion",
    "profesion",
    "titulo profesional",
    "titulo",
    "formacion",
]

ALIASES_HONORARIOS_FECHA_INICIO = [
    "fecha de inicio",
    "fecha inicio",
    "inicio contrato",
    "fecha inicio contrato",
    "desde",
]

ALIASES_HONORARIOS_FECHA_TERMINO = [
    "fecha de termino",
    "fecha termino",
    "termino contrato",
    "fecha termino contrato",
    "hasta",
    "fecha de término",
]

ALIASES_HONORARIOS_MONTO = [
    "monto total",
    "monto bruto",
    "monto",
    "total",
    "honorarios",
    "honorario",
    "honorario total bruto mensualizado",
    "honorario bruto mensual",
    "pago bruto",
    "pago",
    "monto pago",
    "remuneracion bruta mensualizada",
]

ALIASES_HONORARIOS_REM_BRUTA = [
    "remuneracion bruta",
    "rem bruta",
    "renta bruta",
    "total haberes",
    "total imponible",
    "haberes",
    "bruto",
    "sueldo bruto",
]

ALIASES_HONORARIOS_REM_LIQUIDA = [
    "remuneracion liquida",
    "rem liquida",
    "renta liquida",
    "liquido",
    "liquido a pago",
    "sueldo liquido",
    "neto",
]

ALIASES_HONORARIOS_OBSERVACIONES = [
    "observaciones",
    "observacion",
    "detalle",
    "notas",
    "glosa",
]

ALIASES_HONORARIOS_VIATICO = [
    "viatico",
    "viaticos",
    "asignacion viatico",
]

ALIASES_HONORARIOS_UNIDAD_MONETARIA = [
    "unidad monetaria",
    "moneda",
    "tipo moneda",
]

# -- Contrata/Planta-specific fields --

ALIASES_CP_GRADO = [
    "grado eus",
    "grado",
    "grado e u s",
    "escala",
    "nivel",
]

ALIASES_CP_CARGO = [
    "cargo",
    "cargo o funcion",
    "funcion",
    "puesto",
]

ALIASES_CP_CALIFICACION = [
    "calificacion profesional",
    "calificacion",
    "profesion",
    "titulo",
    "formacion",
]

ALIASES_CP_REGION = [
    "region",
    "comuna",
    "localidad",
    "lugar desempeno",
]

ALIASES_CP_ASIGNACIONES = [
    "asignaciones",
    "asignacion",
    "otras asignaciones",
    "bonos",
    "total asignaciones",
]

ALIASES_CP_REM_BRUTA = [
    "remuneracion bruta",
    "rem bruta",
    "remuneracion bruta mensualizada",
    "renta bruta",
    "total haberes",
    "total imponible",
    "haberes",
    "bruto",
    "sueldo bruto",
]

ALIASES_CP_REM_LIQUIDA = [
    "remuneracion liquida",
    "rem liquida",
    "remuneracion liquida mensualizada",
    "renta liquida",
    "liquido",
    "liquido a pago",
    "sueldo liquido",
    "neto",
]

ALIASES_CP_FECHA_INICIO = [
    "fecha de inicio",
    "fecha inicio",
    "inicio",
    "fecha ingreso",
    "desde",
]

ALIASES_CP_FECHA_TERMINO = [
    "fecha de termino",
    "fecha termino",
    "termino",
    "fecha egreso",
    "hasta",
]

ALIASES_CP_OBSERVACIONES = [
    "observaciones",
    "observacion",
    "detalle",
    "notas",
    "glosa",
]

ALIASES_CP_HORAS = [
    "horas",
    "horas semanales",
    "jornada",
    "tipo jornada",
    "horas contrato",
]

# -- Periodo / Mes (useful for honorarios) --

ALIASES_PERIODO = [
    "periodo",
    "mes",
    "mes pago",
    "fecha pago",
]


# ---------------------------------------------------------------------------
# High-level normalization functions for each section type
# ---------------------------------------------------------------------------

def normalize_honorarios_record(raw: dict[str, str]) -> dict[str, any]:
    """Normalize a single raw honorarios record using header-based alias matching.

    Builds a header index from the record's keys and uses aliases to map
    each field correctly, regardless of column order or naming variations.

    Args:
        raw: Dict with raw header names as keys and cell text as values.

    Returns:
        Dict with standardized field names.
    """
    header_index = build_header_index(list(raw.keys()))

    rec = {}
    rec["nombre"] = get_cell(raw, header_index, ALIASES_NOMBRE)
    rec["rut"] = get_cell(raw, header_index, ALIASES_RUT)
    rec["descripcion_funcion"] = get_cell(raw, header_index, ALIASES_HONORARIOS_FUNCION)
    rec["calificacion_profesional"] = get_cell(raw, header_index, ALIASES_HONORARIOS_CALIFICACION)
    rec["fecha_inicio"] = get_cell(raw, header_index, ALIASES_HONORARIOS_FECHA_INICIO)
    rec["fecha_termino"] = get_cell(raw, header_index, ALIASES_HONORARIOS_FECHA_TERMINO)
    rec["remuneracion_bruta"] = get_cell(raw, header_index, ALIASES_HONORARIOS_REM_BRUTA)
    rec["remuneracion_liquida"] = get_cell(raw, header_index, ALIASES_HONORARIOS_REM_LIQUIDA)
    rec["monto_total"] = get_cell(raw, header_index, ALIASES_HONORARIOS_MONTO)
    rec["observaciones"] = get_cell(raw, header_index, ALIASES_HONORARIOS_OBSERVACIONES)
    rec["viatico"] = get_cell(raw, header_index, ALIASES_HONORARIOS_VIATICO)
    rec["unidad_monetaria"] = get_cell(raw, header_index, ALIASES_HONORARIOS_UNIDAD_MONETARIA)

    # --- Defensive validation ---
    # If RUT looks like a money value, the columns are shifted.
    # Try to recover by scanning all cells for a real RUT.
    rut_val = rec.get("rut")
    if rut_val and not is_rut(rut_val) and looks_like_money(rut_val):
        logger.warning(
            f"Honorarios: RUT field contains money value '{rut_val}', "
            "attempting column shift recovery"
        )
        # The money value in RUT likely belongs to monto_total
        if not rec.get("monto_total") or not looks_like_money(rec.get("monto_total", "")):
            rec["monto_total"] = rut_val

        # Scan all cells for a real RUT
        real_rut = None
        for val in raw.values():
            if val and is_rut(str(val).strip()):
                real_rut = str(val).strip()
                break
        rec["rut"] = real_rut

    # If monto_total is empty but remuneracion_bruta has a value, use it as monto_total
    if not rec.get("monto_total") and rec.get("remuneracion_bruta"):
        rec["monto_total"] = rec["remuneracion_bruta"]

    return rec


def normalize_contrata_planta_record(raw: dict[str, str]) -> dict[str, any]:
    """Normalize a single raw contrata/planta record using header-based alias matching.

    Args:
        raw: Dict with raw header names as keys and cell text as values.

    Returns:
        Dict with standardized field names.
    """
    header_index = build_header_index(list(raw.keys()))

    rec = {}
    rec["nombre"] = get_cell(raw, header_index, ALIASES_NOMBRE)
    rec["rut"] = get_cell(raw, header_index, ALIASES_RUT)
    rec["grado_eus"] = get_cell(raw, header_index, ALIASES_CP_GRADO)
    rec["cargo"] = get_cell(raw, header_index, ALIASES_CP_CARGO)
    rec["calificacion_profesional"] = get_cell(raw, header_index, ALIASES_CP_CALIFICACION)
    rec["region"] = get_cell(raw, header_index, ALIASES_CP_REGION)
    rec["asignaciones"] = get_cell(raw, header_index, ALIASES_CP_ASIGNACIONES)
    rec["remuneracion_bruta"] = get_cell(raw, header_index, ALIASES_CP_REM_BRUTA)
    rec["remuneracion_liquida"] = get_cell(raw, header_index, ALIASES_CP_REM_LIQUIDA)
    rec["fecha_inicio"] = get_cell(raw, header_index, ALIASES_CP_FECHA_INICIO)
    rec["fecha_termino"] = get_cell(raw, header_index, ALIASES_CP_FECHA_TERMINO)
    rec["observaciones"] = get_cell(raw, header_index, ALIASES_CP_OBSERVACIONES)
    rec["horas"] = get_cell(raw, header_index, ALIASES_CP_HORAS)

    # --- Defensive validation ---
    # If RUT looks like money, columns are shifted
    rut_val = rec.get("rut")
    if rut_val and not is_rut(rut_val) and looks_like_money(rut_val):
        logger.warning(
            f"Contrata/Planta: RUT field contains money value '{rut_val}', "
            "attempting column shift recovery"
        )
        real_rut = None
        for val in raw.values():
            if val and is_rut(str(val).strip()):
                real_rut = str(val).strip()
                break
        rec["rut"] = real_rut

    # If remuneracion_bruta is empty but we can find a numeric column that
    # looks like it via the raw data, log a warning.
    if not rec.get("remuneracion_bruta") and rec.get("remuneracion_liquida"):
        logger.warning(
            "Contrata/Planta: remuneracion_bruta is empty but "
            "remuneracion_liquida has a value. Check portal header mapping."
        )

    return rec


def normalize_honorarios(raw_records: list[dict]) -> list[dict]:
    """Normalize a batch of raw honorarios records."""
    return [normalize_honorarios_record(r) for r in raw_records]


def normalize_contrata_planta(raw_records: list[dict]) -> list[dict]:
    """Normalize a batch of raw contrata/planta records."""
    return [normalize_contrata_planta_record(r) for r in raw_records]


# ---------------------------------------------------------------------------
# Colspan-aware header extraction for BeautifulSoup tables
# ---------------------------------------------------------------------------

def extract_headers_with_colspan(header_cells) -> list[str]:
    """Extract headers from table header cells, accounting for colspan.

    When a <th> has colspan=N, we emit N header entries: the text for the
    first and empty strings for the remaining, so the header count matches
    the data cell count.

    Args:
        header_cells: Iterable of BeautifulSoup Tag elements (<th> or <td>).

    Returns:
        List of header strings, with length matching the actual column count.
    """
    headers = []
    for cell in header_cells:
        text = cell.get_text(strip=True)
        try:
            colspan = int(cell.get("colspan", 1))
        except (ValueError, TypeError):
            colspan = 1
        headers.append(text)
        # Pad with numbered variants for extra spanned columns
        for i in range(1, colspan):
            headers.append(f"{text} ({i + 1})")
    return headers
