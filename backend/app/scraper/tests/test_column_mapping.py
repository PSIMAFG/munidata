"""Tests for column_mapping module.

Verifies that header-based alias mapping correctly handles:
1. Honorarios: RUT must not contain money values; Monto Total must be numeric.
2. Planta/Contrata: Rem. Bruta must not be empty when the source has it.
3. Column order changes should not break mapping.
4. Colspan in headers should not cause column shifts.

Run with: python -m pytest backend/app/scraper/tests/test_column_mapping.py -v
Or standalone: python backend/app/scraper/tests/test_column_mapping.py
"""

import sys
import os

# Allow running from repo root without installed package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from app.scraper.column_mapping import (
    normalize_header,
    build_header_index,
    get_cell,
    parse_money_clp,
    is_rut,
    is_rut_loose,
    looks_like_money,
    normalize_honorarios,
    normalize_contrata_planta,
    extract_headers_with_colspan,
    ALIASES_RUT,
    ALIASES_NOMBRE,
    ALIASES_HONORARIOS_MONTO,
    ALIASES_HONORARIOS_REM_BRUTA,
    ALIASES_CP_REM_BRUTA,
    ALIASES_CP_REM_LIQUIDA,
)


# ===================================================================
# HTML fixture helpers (simulate BeautifulSoup tags for colspan test)
# ===================================================================

class FakeTag:
    """Minimal mock of a BeautifulSoup Tag for testing extract_headers_with_colspan."""
    def __init__(self, text, colspan=None):
        self._text = text
        self._colspan = colspan

    def get_text(self, strip=False):
        return self._text.strip() if strip else self._text

    def get(self, attr, default=None):
        if attr == "colspan":
            return str(self._colspan) if self._colspan else default
        return default


# ===================================================================
# Unit tests: normalize_header
# ===================================================================

def test_normalize_header_basic():
    assert normalize_header("Remuneración Bruta") == "remuneracion bruta"
    assert normalize_header("Rem. Líquida") == "rem liquida"
    assert normalize_header("NOMBRE") == "nombre"
    assert normalize_header("  RUT  ") == "rut"
    assert normalize_header("Fecha de Inicio") == "fecha de inicio"


def test_normalize_header_accents_and_dots():
    assert normalize_header("Remuneración Bruta Mensualizada") == "remuneracion bruta mensualizada"
    assert normalize_header("Calificación Profesional") == "calificacion profesional"
    assert normalize_header("Descripción de la Función") == "descripcion de la funcion"
    assert normalize_header("Rem. Bruta") == "rem bruta"
    assert normalize_header("Rem. Líquida") == "rem liquida"


def test_normalize_header_empty():
    assert normalize_header("") == ""
    assert normalize_header("   ") == ""


# ===================================================================
# Unit tests: build_header_index
# ===================================================================

def test_build_header_index():
    headers = ["Nombre", "RUT", "Rem. Bruta", "Rem. Líquida"]
    idx = build_header_index(headers)
    assert idx["nombre"] == 0
    assert idx["rut"] == 1
    assert idx["rem bruta"] == 2
    assert idx["rem liquida"] == 3


# ===================================================================
# Unit tests: get_cell (dict-based)
# ===================================================================

def test_get_cell_exact_match():
    row = {"Nombre": "Juan Pérez", "RUT": "12.345.678-9", "Rem. Bruta": "$ 1.200.000"}
    hi = build_header_index(list(row.keys()))
    assert get_cell(row, hi, ALIASES_NOMBRE) == "Juan Pérez"
    assert get_cell(row, hi, ALIASES_RUT) == "12.345.678-9"


def test_get_cell_substring_match():
    # Portal uses longer header names
    row = {
        "Nombre Completo del Funcionario": "María López",
        "Rut Funcionario": "11.222.333-4",
        "Remuneración Bruta Mensualizada": "$ 800.000",
        "Remuneración Líquida Mensualizada": "$ 650.000",
    }
    hi = build_header_index(list(row.keys()))
    assert get_cell(row, hi, ALIASES_NOMBRE) == "María López"
    assert get_cell(row, hi, ALIASES_RUT) == "11.222.333-4"
    assert get_cell(row, hi, ALIASES_CP_REM_BRUTA) == "$ 800.000"
    assert get_cell(row, hi, ALIASES_CP_REM_LIQUIDA) == "$ 650.000"


# ===================================================================
# Unit tests: parse_money_clp
# ===================================================================

def test_parse_money_clp_basic():
    assert parse_money_clp("$ 458.832") == 458832.0
    assert parse_money_clp("$ 1.234.567") == 1234567.0
    assert parse_money_clp("1.234,56") == 1234.56
    assert parse_money_clp("800000") == 800000.0
    assert parse_money_clp("$ 0") == 0.0


def test_parse_money_clp_negative():
    assert parse_money_clp("($ 500.000)") == -500000.0


def test_parse_money_clp_empty():
    assert parse_money_clp(None) is None
    assert parse_money_clp("") is None
    assert parse_money_clp("-") is None
    assert parse_money_clp("no informa") is None
    assert parse_money_clp("n/a") is None
    assert parse_money_clp("s/i") is None


# ===================================================================
# Unit tests: is_rut / looks_like_money
# ===================================================================

def test_is_rut():
    assert is_rut("12.345.678-9") is True
    assert is_rut("12345678-9") is True
    assert is_rut("12.345.678-K") is True
    assert is_rut("9.876.543-2") is True
    # Invalid
    assert is_rut("$ 458.832") is False
    assert is_rut("1.234.567") is False  # no check digit
    assert is_rut("") is False
    assert is_rut(None) is False
    assert is_rut("Juan Pérez") is False


def test_looks_like_money():
    assert looks_like_money("$ 458.832") is True
    assert looks_like_money("1.234.567") is True
    assert looks_like_money("$ 0") is True
    assert looks_like_money("12.345.678-9") is False  # RUT, not money
    assert looks_like_money("Juan Pérez") is False
    assert looks_like_money("") is False
    assert looks_like_money(None) is False


# ===================================================================
# Integration tests: Honorarios normalization
# ===================================================================

def test_honorarios_basic_mapping():
    """Standard honorarios table headers should map correctly."""
    raw_records = [{
        "Nombre": "ANDREA SILVA MUÑOZ",
        "Rut": "15.432.876-5",
        "Descripción de la Función": "Profesional CESFAM",
        "Calificación Profesional": "Kinesióloga",
        "Fecha de Inicio": "01/01/2025",
        "Fecha de Término": "31/12/2025",
        "Remuneración Bruta": "$ 1.200.000",
        "Remuneración Líquida": "$ 950.000",
        "Monto Total": "$ 1.200.000",
        "Observaciones": "Convenio CESFAM Sur",
    }]
    result = normalize_honorarios(raw_records)
    assert len(result) == 1
    r = result[0]
    assert r["nombre"] == "ANDREA SILVA MUÑOZ"
    assert r["rut"] == "15.432.876-5"
    assert is_rut(r["rut"]), f"RUT should be valid: {r['rut']}"
    assert r["monto_total"] == "$ 1.200.000"
    assert r["remuneracion_bruta"] == "$ 1.200.000"
    assert r["remuneracion_liquida"] == "$ 950.000"


def test_honorarios_column_shift_recovery():
    """BUG REPRODUCTION: When RUT field contains a money value like '$ 458.832',
    the defensive validation should recover by:
    1. Moving the money value to monto_total
    2. Scanning for a real RUT in other cells
    """
    # Simulate shifted columns: RUT gets the Monto value
    raw_records = [{
        "Nombre": "PEDRO GÓMEZ",
        "Rut": "$ 458.832",  # BUG: money value in RUT field
        "Descripción de la Función": "15.999.888-7",  # RUT ended up here
        "Calificación Profesional": "Técnico",
        "Monto Total": "",  # Empty due to shift
    }]
    result = normalize_honorarios(raw_records)
    r = result[0]

    # RUT should NOT contain a money value
    assert r["rut"] != "$ 458.832", "RUT must not contain money values"

    # The money value should end up in monto_total
    assert r["monto_total"] == "$ 458.832", "Monto Total should capture the shifted money value"

    # The real RUT should be recovered from scanning other cells
    assert r["rut"] == "15.999.888-7", "Real RUT should be found by scanning cells"


def test_honorarios_different_column_order():
    """Columns in a different order should still map correctly."""
    raw_records = [{
        "Monto Total": "$ 900.000",
        "Observaciones": "Sin convenio",
        "Rut": "11.222.333-4",
        "Calificación Profesional": "Médico",
        "Nombre": "DR. JUAN CASTRO",
        "Descripción de la Función": "Médico APS",
        "Fecha de Inicio": "01/03/2025",
        "Fecha de Término": "31/12/2025",
    }]
    result = normalize_honorarios(raw_records)
    r = result[0]
    assert r["nombre"] == "DR. JUAN CASTRO"
    assert r["rut"] == "11.222.333-4"
    assert is_rut(r["rut"])
    assert r["monto_total"] == "$ 900.000"


def test_honorarios_alternative_headers():
    """Portal might use alternative header names (e.g., 'Prestador' instead of 'Nombre')."""
    raw_records = [{
        "Prestador": "CAROLINA VEGA",
        "RUT Prestador": "14.555.666-7",
        "Función": "Psicóloga COSAM",
        "Profesión": "Psicóloga",
        "Honorario Total Bruto Mensualizado": "$ 1.500.000",
        "Pago": "$ 1.500.000",
    }]
    result = normalize_honorarios(raw_records)
    r = result[0]
    assert r["nombre"] == "CAROLINA VEGA"
    assert r["rut"] == "14.555.666-7"
    assert is_rut(r["rut"])
    # monto_total should be captured
    assert r["monto_total"] == "$ 1.500.000"


# ===================================================================
# Integration tests: Contrata/Planta normalization
# ===================================================================

def test_contrata_planta_basic_mapping():
    """Standard contrata/planta headers should map correctly."""
    raw_records = [{
        "Nombre": "LUIS MARTÍNEZ SOTO",
        "Rut": "10.111.222-3",
        "Grado EUS": "15",
        "Cargo": "Enfermero(a)",
        "Calificación Profesional": "Enfermero",
        "Región": "Valparaíso",
        "Asignaciones": "$ 150.000",
        "Remuneración Bruta Mensualizada": "$ 1.800.000",
        "Remuneración Líquida Mensualizada": "$ 1.400.000",
        "Fecha de Inicio": "01/01/2020",
        "Fecha de Término": "indefinido",
        "Observaciones": "",
        "Horas": "44",
    }]
    result = normalize_contrata_planta(raw_records)
    assert len(result) == 1
    r = result[0]
    assert r["nombre"] == "LUIS MARTÍNEZ SOTO"
    assert r["rut"] == "10.111.222-3"
    assert is_rut(r["rut"])
    assert r["remuneracion_bruta"] == "$ 1.800.000", "Rem. Bruta must not be empty"
    assert r["remuneracion_liquida"] == "$ 1.400.000"
    assert r["grado_eus"] == "15"
    assert r["cargo"] == "Enfermero(a)"


def test_contrata_planta_bruta_not_empty():
    """BUG REPRODUCTION: Rem. Bruta must not be systematically empty
    when it exists in the source data.
    """
    raw_records = [{
        "Nombre": "ANA ROJAS",
        "RUT": "9.888.777-6",
        "Grado": "12",
        "Cargo": "Técnico Dental",
        "Rem. Bruta": "$ 900.000",
        "Rem. Líquida": "$ 720.000",
    }]
    result = normalize_contrata_planta(raw_records)
    r = result[0]
    assert r["remuneracion_bruta"] is not None, "Rem. Bruta must not be None"
    assert r["remuneracion_bruta"] == "$ 900.000", "Rem. Bruta must have the correct value"
    assert r["remuneracion_liquida"] == "$ 720.000"


def test_contrata_planta_alternative_bruta_header():
    """Portal might use 'Total Haberes' instead of 'Rem. Bruta'."""
    raw_records = [{
        "Nombre": "PEDRO SÁNCHEZ",
        "RUT": "8.765.432-1",
        "Grado": "10",
        "Cargo": "Administrativo",
        "Total Haberes": "$ 1.100.000",
        "Líquido a Pago": "$ 850.000",
    }]
    result = normalize_contrata_planta(raw_records)
    r = result[0]
    assert r["remuneracion_bruta"] == "$ 1.100.000", "Total Haberes should map to remuneracion_bruta"
    assert r["remuneracion_liquida"] == "$ 850.000", "Líquido a Pago should map to remuneracion_liquida"


def test_contrata_planta_column_order_shuffled():
    """Different column order should not break mapping."""
    raw_records = [{
        "Remuneración Líquida": "$ 600.000",
        "Cargo": "Auxiliar",
        "Remuneración Bruta": "$ 800.000",
        "Nombre": "JOSÉ DÍAZ",
        "Grado EUS": "20",
        "Rut": "7.654.321-K",
    }]
    result = normalize_contrata_planta(raw_records)
    r = result[0]
    assert r["nombre"] == "JOSÉ DÍAZ"
    assert r["rut"] == "7.654.321-K"
    assert r["remuneracion_bruta"] == "$ 800.000"
    assert r["remuneracion_liquida"] == "$ 600.000"


# ===================================================================
# Integration tests: Colspan handling
# ===================================================================

def test_extract_headers_with_colspan():
    """Headers with colspan should expand to correct number of columns."""
    cells = [
        FakeTag("Nombre"),
        FakeTag("RUT"),
        FakeTag("Remuneración", colspan=2),  # spans 2 columns
        FakeTag("Observaciones"),
    ]
    headers = extract_headers_with_colspan(cells)
    assert len(headers) == 5  # 1 + 1 + 2 + 1
    assert headers[0] == "Nombre"
    assert headers[1] == "RUT"
    assert headers[2] == "Remuneración"
    assert headers[3] == "Remuneración (2)"
    assert headers[4] == "Observaciones"


def test_extract_headers_no_colspan():
    """Without colspan, should work normally."""
    cells = [
        FakeTag("A"),
        FakeTag("B"),
        FakeTag("C"),
    ]
    headers = extract_headers_with_colspan(cells)
    assert headers == ["A", "B", "C"]


# ===================================================================
# Standalone runner
# ===================================================================

def _run_all():
    """Run all tests and report results."""
    import inspect
    tests = [
        (name, func)
        for name, func in sorted(globals().items())
        if name.startswith("test_") and callable(func)
    ]

    passed = 0
    failed = 0
    errors = []

    for name, func in tests:
        try:
            func()
            passed += 1
            print(f"  PASS  {name}")
        except AssertionError as e:
            failed += 1
            errors.append((name, str(e)))
            print(f"  FAIL  {name}: {e}")
        except Exception as e:
            failed += 1
            errors.append((name, f"ERROR: {e}"))
            print(f"  ERROR {name}: {e}")

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    print(f"{'='*60}")

    if errors:
        print("\nFailures:")
        for name, msg in errors:
            print(f"  - {name}: {msg}")
        return False
    return True


if __name__ == "__main__":
    print("Running column_mapping verification tests...\n")
    success = _run_all()
    sys.exit(0 if success else 1)
