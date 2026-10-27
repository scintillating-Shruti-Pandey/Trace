"""Unit tests for Grounded Answer Generation & Citation Validation (Spec §7.2, §8.8, §16.6)."""

import pytest
from app.generation import (
    CitationValidationError,
    EvidenceItem,
    GenerationResult,
    GroundedAnswerGenerator,
    assemble_evidence,
    validate_citations,
)


def test_validate_citations_success():
    answer = "The camera mounting plate is secured at 25.0s [E1]. The torque spec is 9.5 Nm [E2]."
    valid, invalid = validate_citations(answer, {"E1", "E2", "E3"})
    assert valid is True
    assert invalid == []


def test_validate_citations_detects_non_retrieved_evidence():
    # Contract §16.6: No answer ever cites non-retrieved evidence
    answer = "The hydraulic valve clearance is 0.045 mm [E1], verified in [E99]."
    valid, invalid = validate_citations(answer, {"E1", "E2"})
    assert valid is False
    assert invalid == ["E99"]


def test_assemble_evidence_orders_and_numbers():
    multimodal_results = {
        "video_segments": [
            {
                "segment_id": "seg-1",
                "asset_id": "vid-1",
                "asset_title": "Video 1",
                "start_s": 10.0,
                "end_s": 25.0,
                "seek_to_s": 8.0,
                "caption": "assemble lower hinge",
                "score": 0.85,
            }
        ],
        "document_chunks": [
            {
                "chunk_id": "chk-1",
                "asset_id": "doc-1",
                "asset_title": "SOP Manual",
                "section_path": "4.1 Hinge Assembly",
                "page_from": 5,
                "page_to": 5,
                "text": "Tighten hinge bolts to 9.5 Nm with calibrated torque wrench.",
                "score": 0.80,
                "relation": "specifies",
            }
        ],
        "images": [
            {
                "image_id": "img-1",
                "asset_id": "vid-1",
                "asset_title": "Video 1",
                "storage_key": "keyframes/seg-1.jpg",
                "caption": "assembled lower hinge",
                "score": 0.75,
            }
        ],
    }

    evidence = assemble_evidence(multimodal_results, top_k=8)
    assert len(evidence) == 3
    assert evidence[0].citation_id == "E1"
    assert evidence[0].kind == "video"
    assert evidence[0].seek_to_s == 8.0
    assert evidence[1].citation_id == "E2"
    assert evidence[1].kind == "document"
    assert "Section" in evidence[1].locator or "Hinge Assembly" in evidence[1].locator
    assert evidence[2].citation_id == "E3"
    assert evidence[2].kind == "image"


def test_generate_grounded_answer():
    generator = GroundedAnswerGenerator()
    evidence = [
        EvidenceItem(
            citation_id="E1",
            kind="video",
            source_id="seg-1",
            asset_id="vid-1",
            title="IndEgo Workstation Assembly",
            locator="10.0s – 25.0s (seek: 8.0s)",
            text="assemble lower hinge bracket with pivot pin",
            score=0.85,
            start_s=10.0,
            end_s=25.0,
            seek_to_s=8.0,
        ),
        EvidenceItem(
            citation_id="E2",
            kind="document",
            source_id="chk-1",
            asset_id="doc-1",
            title="Workstation SOP",
            locator="Section 3.2 Hinge Mounting, p. 7",
            text="Lower hinge pivot pin must be lubricated with grease before fastening.",
            score=0.80,
            relation="specifies",
        ),
    ]

    res = generator.generate("How to assemble the lower hinge?", evidence)
    assert res.abstained is False
    assert "[E1]" in res.answer
    assert "[E2]" in res.answer
    assert "IndEgo Workstation Assembly" in res.answer
    assert "Workstation SOP" in res.answer
    # Validate citations
    valid, invalid = validate_citations(res.answer, {"E1", "E2"})
    assert valid is True
    assert invalid == []


def test_generate_surfaces_contradiction_conflict():
    generator = GroundedAnswerGenerator()
    evidence = [
        EvidenceItem(
            citation_id="E1",
            kind="video",
            source_id="seg-1",
            asset_id="vid-1",
            title="Assembly Video",
            locator="10.0s – 25.0s",
            text="Operator torquing bolt without threadlocker",
            score=0.85,
            start_s=10.0,
            end_s=25.0,
        ),
        EvidenceItem(
            citation_id="E2",
            kind="document",
            source_id="chk-1",
            asset_id="doc-1",
            title="Assembly SOP",
            locator="Section 2.1",
            text="Apply medium-strength threadlocker before torquing.",
            score=0.80,
            relation="contradicts",
            metadata={"note": "Fastener torqued dry without threadlocker specified in SOP"},
        ),
    ]

    res = generator.generate("Check fastener procedure", evidence)
    assert res.abstained is False
    assert "deviation" in res.answer.lower() or "contradiction" in res.answer.lower()
    assert "[E2]" in res.answer


def test_generate_abstains_on_unanswerable():
    generator = GroundedAnswerGenerator()
    evidence = [
        EvidenceItem(
            citation_id="E1",
            kind="video",
            source_id="seg-1",
            asset_id="vid-1",
            title="Video 1",
            locator="10.0s – 25.0s",
            text="assemble table frame",
            score=0.02,
            start_s=10.0,
            end_s=25.0,
        )
    ]

    res = generator.generate(
        "What is the curing time for underwater epoxy on deep-sea pipeline flanges?",
        evidence,
    )
    assert res.abstained is True
    assert "cannot answer" in res.answer.lower()
    assert "deep-sea" in res.answer.lower() or "epoxy" in res.answer.lower()


def test_generate_raises_on_invalid_citation_injection(monkeypatch):
    generator = GroundedAnswerGenerator()
    evidence = [
        EvidenceItem(
            citation_id="E1",
            kind="video",
            source_id="seg-1",
            asset_id="vid-1",
            title="Video 1",
            locator="10.0s – 25.0s",
            text="assemble lower hinge",
            score=0.85,
            start_s=10.0,
            end_s=25.0,
        )
    ]

    # Monkeypatch to simulate an unauthorized injection of non-retrieved citation [E99]
    original_validate = validate_citations

    def fake_validate(ans, allowed):
        return False, ["E99"]

    monkeypatch.setattr("app.generation.validate_citations", fake_validate)

    with pytest.raises(CitationValidationError, match="non-retrieved evidence"):
        generator.generate("How to assemble lower hinge?", evidence)


@pytest.mark.anyio
async def test_stream_generate():
    generator = GroundedAnswerGenerator()
    evidence = [
        EvidenceItem(
            citation_id="E1",
            kind="video",
            source_id="seg-1",
            asset_id="vid-1",
            title="Assembly Video",
            locator="10.0s – 25.0s",
            text="attach camera and plate",
            score=0.85,
            start_s=10.0,
            end_s=25.0,
        )
    ]

    tokens = []
    done_event = None
    async for event in generator.stream_generate("Where is the camera plate attached?", evidence):
        if event["type"] == "token":
            tokens.append(event["content"])
        elif event["type"] == "done":
            done_event = event

    assert len(tokens) > 0
    assert done_event is not None
    assert done_event["abstained"] is False
    assert len(done_event["citations"]) == 1
    assert done_event["citations"][0]["citation_id"] == "E1"
