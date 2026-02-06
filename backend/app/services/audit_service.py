"""Audit service: match records against remuneration scales and detect anomalies."""
import logging
from sqlalchemy import select, and_, delete
from sqlalchemy.orm import Session
from app.models.personnel import (
    HonorariosRecord, ContrataRecord, PlantaRecord,
    RemunerationScale, AuditException,
)

logger = logging.getLogger(__name__)


def run_audit(
    db: Session,
    municipality_code: str,
    year: int,
    threshold_pct: float = 5.0,
):
    """Run heuristic matching audit for all records."""
    # Clear previous audit results
    db.execute(
        delete(AuditException).where(
            AuditException.municipality_code == municipality_code,
            AuditException.year == year,
        )
    )
    db.commit()

    # Load scales
    scales = db.execute(
        select(RemunerationScale).where(
            RemunerationScale.municipality_code == municipality_code,
            RemunerationScale.year == year,
        )
    ).scalars().all()

    scale_map = _build_scale_map(scales)

    count = 0

    # Audit honorarios
    honorarios = db.execute(
        select(HonorariosRecord).where(
            HonorariosRecord.municipality_code == municipality_code,
            HonorariosRecord.year == year,
        )
    ).scalars().all()

    for rec in honorarios:
        exception = _match_honorario(rec, scale_map, threshold_pct)
        if exception:
            exception.municipality_code = municipality_code
            exception.year = year
            db.add(exception)
            count += 1

    # Audit contrata
    contrata = db.execute(
        select(ContrataRecord).where(
            ContrataRecord.municipality_code == municipality_code,
            ContrataRecord.year == year,
        )
    ).scalars().all()

    for rec in contrata:
        exception = _match_contrata_planta(rec, scale_map, threshold_pct, "CONTRATA")
        if exception:
            exception.municipality_code = municipality_code
            exception.year = year
            db.add(exception)
            count += 1

    # Audit planta
    planta = db.execute(
        select(PlantaRecord).where(
            PlantaRecord.municipality_code == municipality_code,
            PlantaRecord.year == year,
        )
    ).scalars().all()

    for rec in planta:
        exception = _match_contrata_planta(rec, scale_map, threshold_pct, "PLANTA")
        if exception:
            exception.municipality_code = municipality_code
            exception.year = year
            db.add(exception)
            count += 1

    db.commit()
    logger.info(f"Audit completed: {count} exceptions found for {municipality_code}/{year}")
    return count


def _build_scale_map(scales: list[RemunerationScale]) -> dict:
    """Build lookup structures from scales for heuristic matching."""
    result = {
        "by_grado": {},
        "by_cargo": {},
        "by_calificacion": {},
    }
    for s in scales:
        if s.grado:
            key = s.grado.strip().upper()
            result["by_grado"][key] = s
        if s.cargo:
            key = s.cargo.strip().upper()
            result["by_cargo"][key] = s
        if s.calificacion:
            key = s.calificacion.strip().upper()
            result["by_calificacion"][key] = s
    return result


def _match_honorario(rec: HonorariosRecord, scale_map: dict, threshold_pct: float):
    """Heuristic matching for honorarios records."""
    if not rec.remuneracion_bruta or rec.remuneracion_bruta <= 0:
        return None

    valor_real = rec.remuneracion_bruta
    best_match = None
    best_confidence = 0.0
    match_method = None
    fields_used = []

    # Try matching by calificacion
    if rec.calificacion_profesional:
        key = rec.calificacion_profesional.strip().upper()
        if key in scale_map["by_calificacion"]:
            scale = scale_map["by_calificacion"][key]
            if scale.remuneracion_bruta_esperada:
                best_match = scale
                best_confidence = 0.8
                match_method = "calificacion_exacta"
                fields_used = ["calificacion_profesional"]

    # Try partial matching by cargo/función
    if not best_match and rec.descripcion_funcion:
        key = rec.descripcion_funcion.strip().upper()
        for cargo_key, scale in scale_map["by_cargo"].items():
            if cargo_key in key or key in cargo_key:
                if scale.remuneracion_bruta_esperada:
                    best_match = scale
                    best_confidence = 0.5
                    match_method = "funcion_parcial"
                    fields_used = ["descripcion_funcion"]
                    break

    if not best_match:
        return None

    valor_esperado = best_match.remuneracion_bruta_esperada
    diferencia = valor_real - valor_esperado
    diferencia_pct = (diferencia / valor_esperado * 100) if valor_esperado else 0

    if abs(diferencia_pct) < threshold_pct:
        return None

    return AuditException(
        month=rec.month,
        contract_type="HONORARIOS",
        record_id=rec.id,
        nombre=rec.nombre,
        cargo=rec.descripcion_funcion,
        convenio=rec.convenio,
        valor_real=valor_real,
        valor_esperado=valor_esperado,
        diferencia=diferencia,
        diferencia_pct=round(diferencia_pct, 2),
        threshold_pct=threshold_pct,
        match_method=match_method,
        match_confidence=best_confidence,
        fields_used=fields_used,
        explanation=f"Match por {match_method}: esperado {valor_esperado:,.0f}, real {valor_real:,.0f}, diff {diferencia_pct:+.1f}%",
        is_special=True,
    )


def _match_contrata_planta(rec, scale_map: dict, threshold_pct: float, contract_type: str):
    """Heuristic matching for contrata/planta records."""
    if not rec.remuneracion_bruta or rec.remuneracion_bruta <= 0:
        return None

    valor_real = rec.remuneracion_bruta
    best_match = None
    best_confidence = 0.0
    match_method = None
    fields_used = []

    # Try matching by grado
    if rec.grado_eus:
        key = rec.grado_eus.strip().upper()
        if key in scale_map["by_grado"]:
            scale = scale_map["by_grado"][key]
            if scale.remuneracion_bruta_esperada:
                best_match = scale
                best_confidence = 0.9
                match_method = "grado_exacto"
                fields_used = ["grado_eus"]

    # Try matching by cargo
    if not best_match and rec.cargo:
        key = rec.cargo.strip().upper()
        if key in scale_map["by_cargo"]:
            scale = scale_map["by_cargo"][key]
            if scale.remuneracion_bruta_esperada:
                best_match = scale
                best_confidence = 0.7
                match_method = "cargo_exacto"
                fields_used = ["cargo"]

    # Partial cargo match
    if not best_match and rec.cargo:
        key = rec.cargo.strip().upper()
        for cargo_key, scale in scale_map["by_cargo"].items():
            if cargo_key in key or key in cargo_key:
                if scale.remuneracion_bruta_esperada:
                    best_match = scale
                    best_confidence = 0.4
                    match_method = "cargo_parcial"
                    fields_used = ["cargo"]
                    break

    if not best_match:
        return None

    valor_esperado = best_match.remuneracion_bruta_esperada
    diferencia = valor_real - valor_esperado
    diferencia_pct = (diferencia / valor_esperado * 100) if valor_esperado else 0

    if abs(diferencia_pct) < threshold_pct:
        return None

    return AuditException(
        month=rec.month,
        contract_type=contract_type,
        record_id=rec.id,
        nombre=rec.nombre,
        cargo=rec.cargo,
        convenio=None,
        valor_real=valor_real,
        valor_esperado=valor_esperado,
        diferencia=diferencia,
        diferencia_pct=round(diferencia_pct, 2),
        threshold_pct=threshold_pct,
        match_method=match_method,
        match_confidence=best_confidence,
        fields_used=fields_used,
        explanation=f"Match por {match_method}: esperado {valor_esperado:,.0f}, real {valor_real:,.0f}, diff {diferencia_pct:+.1f}%",
        is_special=True,
    )
