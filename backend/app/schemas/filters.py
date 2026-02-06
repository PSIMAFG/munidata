from pydantic import BaseModel, Field
from typing import Optional


class DashboardFilters(BaseModel):
    municipality_code: str = Field(..., description="Municipality code e.g. '280'")
    area: str = Field(default="Salud")
    year: int = Field(default=2025)
    months: list[int] = Field(default_factory=lambda: list(range(1, 13)))
    contract_types: list[str] = Field(
        default_factory=lambda: ["HONORARIOS", "CONTRATA", "PLANTA"]
    )
    convenios: list[str] = Field(default_factory=list)
    search_text: Optional[str] = None
    audit_flag_special: Optional[bool] = None


class ScrapeRunRequest(BaseModel):
    municipality_code: str
    area: str = "Salud"
    year: int = 2025
    months: list[int] = Field(default_factory=lambda: list(range(1, 13)))
    kinds: list[str] = Field(
        default_factory=lambda: ["honorarios", "contrata", "planta", "escalas"]
    )


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=500)
    sort_by: Optional[str] = None
    sort_desc: bool = False


class AuditConfig(BaseModel):
    municipality_code: str
    year: int = 2025
    threshold_pct: float = Field(default=5.0, ge=0, le=100)


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    municipality_code: str
    area: str = "Salud"
    year: int = 2025
    months: list[int] = Field(default_factory=lambda: list(range(1, 13)))
    contract_types: list[str] = Field(
        default_factory=lambda: ["HONORARIOS", "CONTRATA", "PLANTA"]
    )
    convenios: list[str] = Field(default_factory=list)


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    municipality_code: Optional[str] = None
    area: Optional[str] = None
    year: Optional[int] = None
    months: Optional[list[int]] = None
    contract_types: Optional[list[str]] = None
    convenios: Optional[list[str]] = None
