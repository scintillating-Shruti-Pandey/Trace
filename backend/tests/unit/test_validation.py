from uuid import uuid4

import pytest
from app.config import Settings
from app.ingest.probe import incoming_file
from app.schemas import ChunkCreate, LinkCreate, SegmentCreate
from pydantic import ValidationError


def test_no_database_fallback():
    with pytest.raises(ValidationError):
        Settings(database_url="sqlite://")


@pytest.mark.parametrize("start,end", [(10, 10), (-1, 10), (10, 9), (0, float("inf"))])
def test_invalid_spans(start, end):
    with pytest.raises(ValidationError):
        SegmentCreate(start_s=start, end_s=end, human_caption="Observed action", author="Reviewer")


def test_link_requires_two_targets():
    with pytest.raises(ValidationError):
        LinkCreate(segment_id=uuid4(), relation="documents", author="Reviewer")


def test_pages_must_be_a_valid_pair():
    with pytest.raises(ValidationError):
        ChunkCreate(
            doc_type="manual",
            section_path="Section 1",
            text="Text",
            token_count=1,
            page_from=2,
            page_to=1,
        )


def test_incoming_path_is_confined(tmp_path):
    root = tmp_path / "incoming"
    root.mkdir()
    (tmp_path / "private.txt").write_text("outside")
    (root / "real.txt").write_text("inside")
    assert incoming_file(root, "real.txt").name == "real.txt"
    with pytest.raises(ValueError):
        incoming_file(root, "../private.txt")
    with pytest.raises(ValueError):
        incoming_file(root, str(tmp_path / "private.txt"))
