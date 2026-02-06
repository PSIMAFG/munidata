"""Configurable rules to derive 'convenio' from Observaciones field.

The portal's Observaciones column for honorarios uses a consistent pattern:
    "Honorarios {CONVENIO/PROGRAMA NAME}"
Examples:
    "Honorarios AIDIA"
    "Honorarios Sapu Barrancas"
    "Honorarios Convenio Programa Estrategias de Salud Bucal"
    "Honorarios COSAM"
    "Honorarios Per Cápita"

Strategy:
  1. Try specific keyword matches first (highest confidence)
  2. Then try the generic "Honorarios {X}" pattern to capture anything
  3. Then try "Convenio {X}" as final fallback
"""
import re
from typing import Optional

# Ordered rules: first match wins. Specific patterns before generic ones.
CONVENIO_PATTERNS: list[tuple[str, str | None]] = [
    # --- Specific programs/conventions (exact keyword match) ---
    (r"(?i)\bSENAMEF\b", "SENAMEF"),
    (r"(?i)\bSENAME\b", "SENAME"),
    (r"(?i)\bMEJOR\s*NI[ÑN]EZ\b", "MEJOR NIÑEZ"),
    (r"(?i)\bCHILE\s*CRECE\b", "CHILE CRECE CONTIGO"),
    (r"(?i)\bSEPJ\b", "SEPJ"),
    (r"(?i)\bCOSAM\b", "COSAM"),
    (r"(?i)\bCECOF\b", "CECOF"),
    (r"(?i)\bCESFAM\b", "CESFAM"),
    (r"(?i)\bSAR\b", "SAR"),
    (r"(?i)\bSAPU\b", "SAPU"),
    (r"(?i)\bAIDIA\b", "AIDIA"),
    (r"(?i)\bPROGRAMA\s+DE\s+SALUD\s+MENTAL\b", "SALUD MENTAL"),
    (r"(?i)\bSALUD\s*MENTAL\b", "SALUD MENTAL"),
    (r"(?i)\bSSR\b", "SSR"),
    (r"(?i)\bPROGRAMA\s+CARDIOVASCULAR\b", "CARDIOVASCULAR"),
    (r"(?i)\bCARDIOVASCULAR\b", "CARDIOVASCULAR"),
    (r"(?i)\bPROGRAMA\s+ODONTOL[ÓO]GICO\b", "ODONTOLOGICO"),
    (r"(?i)\bSALUD\s*BUCAL\b", "SALUD BUCAL"),
    (r"(?i)\bESTRATEGIA[S]?\s+DE\s+SALUD\s+BUCAL\b", "SALUD BUCAL"),
    (r"(?i)\bPROGRAMA\s+RESPIRATORIO\b", "RESPIRATORIO"),
    (r"(?i)\bIRA[\s/-]*ERA\b", "IRA-ERA"),
    (r"(?i)\bPROGRAMA\s+EPILEPSIA\b", "EPILEPSIA"),
    (r"(?i)\bEPILEPSIA\b", "EPILEPSIA"),
    (r"(?i)\bPROGRAMA\s+POSTRADO\b", "POSTRADOS"),
    (r"(?i)\bPOSTRADO[S]?\b", "POSTRADOS"),
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
    (r"(?i)\bRESIDENCIA\b", "RESIDENCIA"),
    (r"(?i)\bDEPENDENCIA\b", "DEPENDENCIA"),
    (r"(?i)\bREHABILITACI[OÓ]N\b", "REHABILITACION"),
    (r"(?i)\bPALIATIVO[S]?\b", "PALIATIVOS"),
    (r"(?i)\bURGENCIA\b", "URGENCIA"),
    (r"(?i)\bPROGRAMA\s+PRAIS\b", "PRAIS"),
    (r"(?i)\bPRAIS\b", "PRAIS"),
    (r"(?i)\bPESPI\b", "PESPI"),
    (r"(?i)\bRESOLUCI[OÓ]N\b", "RESOLUCION"),
    # --- Generic "Honorarios {X}" pattern (catches remaining conventions) ---
    # Match "Honorarios Convenio Programa X" -> "PROGRAMA X"
    (r"(?i)\bHonorarios\s+Convenio\s+Programa\s+(.+?)$", None),
    # Match "Honorarios Convenio X" -> "X"
    (r"(?i)\bHonorarios\s+Convenio\s+(.+?)$", None),
    # Match "Honorarios Programa X" -> "PROGRAMA X"
    (r"(?i)\bHonorarios\s+Programa\s+(.+?)$", None),
    # Match "Honorarios X" -> "X" (most generic, catches "Honorarios AIDIA", etc.)
    (r"(?i)\bHonorarios\s+(.+?)$", None),
    # Match "Convenio X" without "Honorarios" prefix
    (r"(?i)\bConvenio\s+(.+?)(?:\.|$)", None),
]

_compiled_patterns = [(re.compile(p), name) for p, name in CONVENIO_PATTERNS]


def derive_convenio(observaciones: str) -> Optional[str]:
    """Extract convenio from observaciones text using pattern matching.

    The portal uses "Honorarios {NAME}" as the standard format.
    Returns the normalized convention/program name or None.
    """
    if not observaciones:
        return None

    text = observaciones.strip()
    if not text:
        return None

    for pattern, name in _compiled_patterns:
        match = pattern.search(text)
        if match:
            if name is None:
                # Generic capture group pattern
                extracted = match.group(1).strip()
                # Clean up and normalize
                extracted = re.sub(r'\s+', ' ', extracted).strip().upper()
                # Remove trailing punctuation
                extracted = extracted.rstrip('.,;:')
                return extracted[:200] if extracted else None
            return name

    return None
