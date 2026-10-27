from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Kind = Literal["video", "image", "document"]
Family = Literal["hydraulic", "rotating", "cnc"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class AssetCreate(Input):
    path: NonBlank  # relative to INCOMING_DIR; never an arbitrary server path
    kind: Kind
    title: NonBlank
    source_uri: NonBlank
    license: NonBlank
    redistributable: bool = False
    equipment_family: Family


class SegmentCreate(Input):
    start_s: float = Field(ge=0)
    end_s: float = Field(gt=0)
    human_caption: NonBlank
    author: NonBlank
    human_verified: bool = False
    transcript: str | None = None

    @model_validator(mode="after")
    def span(self):
        if self.end_s <= self.start_s:
            raise ValueError("end_s must be greater than start_s")
        return self


class SegmentPatch(Input):
    human_caption: NonBlank
    human_verified: bool
    author: NonBlank


class ChunkCreate(Input):
    doc_type: Literal["manual", "sop", "report"]
    section_path: NonBlank
    text: NonBlank
    token_count: int = Field(gt=0)  # supplied by the annotation/import tokenizer
    page_from: int | None = Field(default=None, ge=1)
    page_to: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def pages(self):
        if (self.page_from is None) != (self.page_to is None):
            raise ValueError("provide both page_from and page_to, or neither")
        if self.page_from is not None and self.page_to < self.page_from:
            raise ValueError("page_to must be >= page_from")
        return self


class LinkCreate(Input):
    segment_id: UUID | None = None
    chunk_id: UUID | None = None
    image_id: UUID | None = None
    relation: Literal["documents", "specifies", "depicts", "contradicts"]
    confidence: float = Field(default=1, ge=0, le=1)
    author: NonBlank
    note: str | None = None

    @model_validator(mode="after")
    def targets(self):
        if sum(x is not None for x in (self.segment_id, self.chunk_id, self.image_id)) < 2:
            raise ValueError("an evidence link requires at least two targets")
        return self


class SearchQuery(Input):
    query: NonBlank
    modality: Literal["video", "document", "image", "all"] = "all"
    equipment_family: Family | None = None
    limit: int = Field(default=10, ge=1, le=50)
    link_expansion: bool = Field(default=True, description="Enable evidence-link graph expansion (spec §8.5)")


class CitationItem(BaseModel):
    citation_id: str
    kind: Literal["video", "document", "image"]
    source_id: str
    asset_id: str
    title: str
    locator: str
    text_snippet: str
    score: float
    seek_to_s: float | None = None


class GenerateRequest(Input):
    query: NonBlank
    limit: int = Field(default=8, ge=1, le=20)
    equipment_family: Family | None = None
    link_expansion: bool = Field(default=True, description="Enable evidence-link graph expansion (spec §8.5)")


class GenerateResponse(BaseModel):
    query: str
    answer: str
    abstained: bool
    abstention_reason: str | None = None
    citations: list[CitationItem]
    evidence_count: int
