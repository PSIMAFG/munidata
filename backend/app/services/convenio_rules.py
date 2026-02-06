"""Configurable rules to derive 'convenio' from Observaciones field."""
import re
from typing import Optional

# Ordered rules: first match wins
CONVENIO_PATTERNS: list[tuple[str, str]] = [
    (r"(?i)\bSENAME\b", "SENAME"),
    (r"(?i)\bSENAMEF\b", "SENAMEF"),
    (r"(?i)\bMEJOR\s*NI[ÑN]EZ\b", "MEJOR NIÑEZ"),
    (r"(?i)\bCHILE\s*CRECE\b", "CHILE CRECE CONTIGO"),
    (r"(?i)\bSEPJ\b", "SEPJ"),
    (r"(?i)\bCOSAM\b", "COSAM"),
    (r"(?i)\bCECOF\b", "CECOF"),
    (r"(?i)\bCESFAM\b", "CESFAM"),
    (r"(?i)\bSAR\b", "SAR"),
    (r"(?i)\bSAPU\b", "SAPU"),
    (r"(?i)\bPROGRAMA\s+DE\s+SALUD\s+MENTAL\b", "SALUD MENTAL"),
    (r"(?i)\bSALUD\s*MENTAL\b", "SALUD MENTAL"),
    (r"(?i)\bSSR\b", "SSR"),
    (r"(?i)\bPROGRAMA\s+CARDIOVASCULAR\b", "CARDIOVASCULAR"),
    (r"(?i)\bCARDIOVASCULAR\b", "CARDIOVASCULAR"),
    (r"(?i)\bPROGRAMA\s+ODONTOL[ÓO]GICO\b", "ODONTOLOGICO"),
    (r"(?i)\bPROGRAMA\s+RESPIRATORIO\b", "RESPIRATORIO"),
    (r"(?i)\bIRA[\s/-]*ERA\b", "IRA-ERA"),
    (r"(?i)\bPROGRAMA\s+EPILEPSIA\b", "EPILEPSIA"),
    (r"(?i)\bPROGRAMA\s+POSTRADO\b", "POSTRADOS"),
    (r"(?i)\bGES\b", "GES"),
    (r"(?i)\bPERCAP\b", "PER CAPITA"),
    (r"(?i)\bPER\s*C[AÁ]PITA\b", "PER CAPITA"),
    (r"(?i)\bSUBVENCI[OÓ]N\b", "SUBVENCION"),
    (r"(?i)\bPROGRAMA\s+DROGAS\b", "DROGAS"),
    (r"(?i)\bSENDA\b", "SENDA"),
    (r"(?i)\bPROGRAMA\s+VIH\b", "VIH"),
    (r"(?i)\bTBC\b", "TBC"),
    (r"(?i)\bHOSPICIO\b", "HOSPICIO"),
    (r"(?i)\bLEY\s*SEP\b", "LEY SEP"),
    (r"(?i)\bFLEXIFOND[OI]\b", "FLEXIFONDO"),
    (r"(?i)\bRESOLUCI[OÓ]N\b", "RESOLUCION"),
    (r"(?i)\bCONVENIO\s+(.+?)(?:\.|$)", None),  # Generic "Convenio X" -> X
]

_compiled_patterns = [(re.compile(p), name) for p, name in CONVENIO_PATTERNS]


def derive_convenio(observaciones: str) -> Optional[str]:
    """Extract convenio from observaciones text using pattern matching."""
    if not observaciones:
        return None

    text = observaciones.strip()
    if not text:
        return None

    for pattern, name in _compiled_patterns:
        match = pattern.search(text)
        if match:
            if name is None:
                # Generic "Convenio X" pattern
                extracted = match.group(1).strip().upper()
                return extracted[:200] if extracted else None
            return name

    return None
