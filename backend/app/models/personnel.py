import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Text, Date, DateTime, Boolean,
    ForeignKey, Index, Enum as SAEnum, JSON
)
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class ContractType(str, enum.Enum):
    HONORARIOS = "HONORARIOS"
    CONTRATA = "CONTRATA"
    PLANTA = "PLANTA"


class ScrapeRunStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    municipality_code = Column(String(10), nullable=False, index=True)
    area = Column(String(50), nullable=False, default="Salud")
    year = Column(Integer, nullable=False)
    months = Column(JSON, nullable=False)  # list of ints
    contract_types = Column(JSON, nullable=False)  # list of ContractType values
    status = Column(SAEnum(ScrapeRunStatus), default=ScrapeRunStatus.PENDING)
    celery_task_id = Column(String(255), nullable=True)
    error_message = Column(Text, nullable=True)
    records_loaded = Column(Integer, default=0)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class HonorariosRecord(Base):
    __tablename__ = "honorarios_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    municipality_code = Column(String(10), nullable=False, index=True)
    area = Column(String(50), nullable=False, default="Salud")
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    scrape_run_id = Column(Integer, ForeignKey("scrape_runs.id"), nullable=True)

    # Core fields from portal
    nombre = Column(String(300), nullable=True)
    rut = Column(String(20), nullable=True)
    descripcion_funcion = Column(Text, nullable=True)
    calificacion_profesional = Column(String(300), nullable=True)
    fecha_inicio = Column(String(50), nullable=True)
    fecha_termino = Column(String(50), nullable=True)
    remuneracion_bruta = Column(Float, nullable=True)
    remuneracion_liquida = Column(Float, nullable=True)
    monto_total = Column(Float, nullable=True)
    viatic = Column(Float, nullable=True)
    unidad_monetaria = Column(String(30), nullable=True, default="Pesos")
    observaciones = Column(Text, nullable=True)

    # Derived
    convenio = Column(String(200), nullable=True, index=True)

    __table_args__ = (
        Index("ix_hon_muni_year_month", "municipality_code", "year", "month"),
        Index("ix_hon_convenio", "convenio"),
    )


class ContrataRecord(Base):
    __tablename__ = "contrata_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    municipality_code = Column(String(10), nullable=False, index=True)
    area = Column(String(50), nullable=False, default="Salud")
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=True)
    scrape_run_id = Column(Integer, ForeignKey("scrape_runs.id"), nullable=True)

    nombre = Column(String(300), nullable=True)
    rut = Column(String(20), nullable=True)
    grado_eus = Column(String(50), nullable=True)
    cargo = Column(String(300), nullable=True)
    calificacion_profesional = Column(String(300), nullable=True)
    region = Column(String(100), nullable=True)
    asignaciones = Column(Float, nullable=True)
    unidad_monetaria = Column(String(30), nullable=True, default="Pesos")
    remuneracion_bruta = Column(Float, nullable=True)
    remuneracion_liquida = Column(Float, nullable=True)
    fecha_inicio = Column(String(50), nullable=True)
    fecha_termino = Column(String(50), nullable=True)
    observaciones = Column(Text, nullable=True)
    horas = Column(String(50), nullable=True)

    __table_args__ = (
        Index("ix_cont_muni_year_month", "municipality_code", "year", "month"),
    )


class PlantaRecord(Base):
    __tablename__ = "planta_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    municipality_code = Column(String(10), nullable=False, index=True)
    area = Column(String(50), nullable=False, default="Salud")
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=True)
    scrape_run_id = Column(Integer, ForeignKey("scrape_runs.id"), nullable=True)

    nombre = Column(String(300), nullable=True)
    rut = Column(String(20), nullable=True)
    grado_eus = Column(String(50), nullable=True)
    cargo = Column(String(300), nullable=True)
    calificacion_profesional = Column(String(300), nullable=True)
    region = Column(String(100), nullable=True)
    asignaciones = Column(Float, nullable=True)
    unidad_monetaria = Column(String(30), nullable=True, default="Pesos")
    remuneracion_bruta = Column(Float, nullable=True)
    remuneracion_liquida = Column(Float, nullable=True)
    fecha_inicio = Column(String(50), nullable=True)
    fecha_termino = Column(String(50), nullable=True)
    observaciones = Column(Text, nullable=True)
    horas = Column(String(50), nullable=True)

    __table_args__ = (
        Index("ix_pla_muni_year_month", "municipality_code", "year", "month"),
    )


class RemunerationScale(Base):
    __tablename__ = "remuneration_scales"

    id = Column(Integer, primary_key=True, autoincrement=True)
    municipality_code = Column(String(10), nullable=False, index=True)
    year = Column(Integer, nullable=False)
    contract_type = Column(String(30), nullable=False)
    grado = Column(String(50), nullable=True)
    cargo = Column(String(300), nullable=True)
    calificacion = Column(String(300), nullable=True)
    remuneracion_bruta_esperada = Column(Float, nullable=True)
    remuneracion_liquida_esperada = Column(Float, nullable=True)
    asignaciones = Column(Float, nullable=True)
    raw_data = Column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_scale_muni_year", "municipality_code", "year"),
    )


class AuditException(Base):
    __tablename__ = "audit_exceptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    municipality_code = Column(String(10), nullable=False, index=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=True)
    contract_type = Column(String(30), nullable=False)
    record_id = Column(Integer, nullable=False)
    nombre = Column(String(300), nullable=True)
    cargo = Column(String(300), nullable=True)
    convenio = Column(String(200), nullable=True)
    valor_real = Column(Float, nullable=True)
    valor_esperado = Column(Float, nullable=True)
    diferencia = Column(Float, nullable=True)
    diferencia_pct = Column(Float, nullable=True)
    threshold_pct = Column(Float, nullable=True)
    match_method = Column(String(100), nullable=True)
    match_confidence = Column(Float, nullable=True)
    fields_used = Column(JSON, nullable=True)
    explanation = Column(Text, nullable=True)
    is_special = Column(Boolean, default=True)

    __table_args__ = (
        Index("ix_audit_muni_year", "municipality_code", "year"),
    )
