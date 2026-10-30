"""Contratos de datos compartidos por el caso acumulativo."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class EvidenceSource(BaseModel):
    """Origen verificable de una evidencia."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    kind: Literal["public_web", "synthetic_audio", "synthetic_record", "policy_document"]
    uri: str
    collected_at: datetime
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    terms_reviewed: bool = False
    notes: str | None = None


class PublicAlert(BaseModel):
    """Registro normalizado extraído de una fuente pública."""

    model_config = ConfigDict(extra="forbid")

    published_date: date
    title: str = Field(min_length=5)
    url: HttpUrl
    source_id: str
    collected_at: datetime


class AuditArtifact(BaseModel):
    """Salida reproducible de una sesión."""

    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    session: int = Field(ge=1, le=11)
    path: str
    created_at: datetime
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    input_source_ids: list[str] = Field(default_factory=list)


class AuditCase(BaseModel):
    """Expediente que crecerá a lo largo del curso."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    title: str
    audit_objective: str
    status: Literal["collecting", "analysing", "draft", "reviewed"] = "collecting"
    hypothesis: str | None = None
    sources: list[EvidenceSource] = Field(default_factory=list)
    artifacts: list[AuditArtifact] = Field(default_factory=list)
