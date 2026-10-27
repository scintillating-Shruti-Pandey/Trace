"""Build 30 multi-hop development queries connecting video moments to document chunks.

Strictly adheres to records/ENGINEERING_SPEC.md §1.2, §13.2, and §13.5:
- 30 queries requiring joint retrieval of video segments AND document chunks.
- Covers the 4 link relations:
  - 10 'specifies' queries (torque, pressure, tolerances, dimensions)
  - 10 'documents' queries (maintenance procedures, inspections, assembly steps)
  - 5 'depicts' queries (component physical parts, brackets, fittings)
  - 5 'contradicts' queries (safety deviations, SOP violations, uncalibrated torquing)
- Populates exact foreign keys (segment_id, chunk_id, asset_id, gold spans) from PostgreSQL.
"""

import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import select
from app.config import Settings
from app.db import make_engine, session_factory
from app.models import Asset, Chunk, EvidenceLink, Segment

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "eval" / "data" / "multihop_dev_queries.json"


def generate_queries():
    settings = Settings()
    engine = make_engine(settings)
    Session = session_factory(engine)

    with Session() as session:
        # Load all links with segment, chunk, video asset, doc asset
        stmt = (
            select(EvidenceLink, Segment, Chunk, Asset)
            .join(Segment, EvidenceLink.segment_id == Segment.id)
            .join(Chunk, EvidenceLink.chunk_id == Chunk.id)
            .join(Asset, Chunk.asset_id == Asset.id)
            .order_by(EvidenceLink.relation, Segment.caption, Segment.start_s)
        )
        all_links = session.execute(stmt).all()
        print(f"Loaded {len(all_links)} evidence links from PostgreSQL.")

        # Group by relation
        by_rel = {
            "specifies": [],
            "documents": [],
            "depicts": [],
            "contradicts": [],
        }
        for link, seg, chunk, doc_asset in all_links:
            by_rel[link.relation].append((link, seg, chunk, doc_asset))

        print(f"Available links per relation: { {k: len(v) for k, v in by_rel.items()} }")

        # Select diverse representative items: 10 specifies, 10 documents, 5 depicts, 5 contradicts
        # Step through items with distinct captions and documents
        def pick_diverse(items, count):
            picked = []
            seen_caps = set()
            # First pass: unique captions
            for item in items:
                cap = item[1].caption
                if cap not in seen_caps:
                    seen_caps.add(cap)
                    picked.append(item)
                    if len(picked) == count:
                        break
            # Second pass: fill if needed
            if len(picked) < count:
                for item in items:
                    if item not in picked:
                        picked.append(item)
                        if len(picked) == count:
                            break
            return picked

        picked_spec = pick_diverse(by_rel["specifies"], 10)
        picked_doc = pick_diverse(by_rel["documents"], 10)
        picked_dep = pick_diverse(by_rel["depicts"], 5)
        picked_con = pick_diverse(by_rel["contradicts"], 5)

        queries = []
        q_idx = 1

        # Helper to formulate natural technical questions based on relation and note
        for link, seg, chunk, doc_asset in picked_spec:
            qid = f"mhop-dev-{q_idx:03d}"
            # Formulate query from note content
            cap = seg.caption
            sec = chunk.section_path
            doc_title = doc_asset.title
            
            # Construct natural question
            if "torque" in link.note.lower():
                query_text = f"What tightening torque is specified for {cap} and in which video interval is this procedure demonstrated?"
            elif "pressure" in link.note.lower() or "bar" in link.note.lower():
                query_text = f"What operating or relief pressure is specified in {doc_title} when performing {cap}?"
            elif "clearance" in link.note.lower() or "tolerance" in link.note.lower():
                query_text = f"What dimensional clearance or tolerance is mandated during {cap} according to {doc_title}?"
            else:
                query_text = f"What technical specifications govern {cap} in {doc_title} and where is this action shown in video?"

            ref_ans = (
                f"During the procedure '{cap}' shown at {seg.start_s:.1f}s–{seg.end_s:.1f}s, "
                f"{doc_title} § {sec} mandates the following specification: {link.note}"
            )

            queries.append({
                "query_id": qid,
                "type": "multi-hop",
                "relation": "specifies",
                "query": query_text,
                "action_label": cap,
                "essential_video_asset_ids": [str(seg.asset_id)],
                "essential_doc_asset_ids": [str(doc_asset.id)],
                "essential_segment_ids": [str(seg.id)],
                "essential_chunk_ids": [str(chunk.id)],
                "gold_spans_by_asset": {str(seg.asset_id): [[round(float(seg.start_s), 2), round(float(seg.end_s), 2)]]},
                "target_document": doc_title,
                "target_section": sec,
                "reference_answer": ref_ans,
                "link_note": link.note,
            })
            q_idx += 1

        for link, seg, chunk, doc_asset in picked_doc:
            qid = f"mhop-dev-{q_idx:03d}"
            cap = seg.caption
            sec = chunk.section_path
            doc_title = doc_asset.title

            query_text = f"Find the video segment where {cap} is executed and what procedure is documented in {doc_title}."
            ref_ans = (
                f"The video interval from {seg.start_s:.1f}s to {seg.end_s:.1f}s shows '{cap}'. "
                f"This corresponds to {doc_title} § {sec}, which documents: {link.note}"
            )

            queries.append({
                "query_id": qid,
                "type": "multi-hop",
                "relation": "documents",
                "query": query_text,
                "action_label": cap,
                "essential_video_asset_ids": [str(seg.asset_id)],
                "essential_doc_asset_ids": [str(doc_asset.id)],
                "essential_segment_ids": [str(seg.id)],
                "essential_chunk_ids": [str(chunk.id)],
                "gold_spans_by_asset": {str(seg.asset_id): [[round(float(seg.start_s), 2), round(float(seg.end_s), 2)]]},
                "target_document": doc_title,
                "target_section": sec,
                "reference_answer": ref_ans,
                "link_note": link.note,
            })
            q_idx += 1

        for link, seg, chunk, doc_asset in picked_dep:
            qid = f"mhop-dev-{q_idx:03d}"
            cap = seg.caption
            sec = chunk.section_path
            doc_title = doc_asset.title

            query_text = f"Show the video moment depicting the physical component for {cap} as referenced in {doc_title}."
            ref_ans = (
                f"The physical component described in {doc_title} § {sec} is depicted in the video segment "
                f"'{cap}' at {seg.start_s:.1f}s–{seg.end_s:.1f}s. Detail: {link.note}"
            )

            queries.append({
                "query_id": qid,
                "type": "multi-hop",
                "relation": "depicts",
                "query": query_text,
                "action_label": cap,
                "essential_video_asset_ids": [str(seg.asset_id)],
                "essential_doc_asset_ids": [str(doc_asset.id)],
                "essential_segment_ids": [str(seg.id)],
                "essential_chunk_ids": [str(chunk.id)],
                "gold_spans_by_asset": {str(seg.asset_id): [[round(float(seg.start_s), 2), round(float(seg.end_s), 2)]]},
                "target_document": doc_title,
                "target_section": sec,
                "reference_answer": ref_ans,
                "link_note": link.note,
            })
            q_idx += 1

        for link, seg, chunk, doc_asset in picked_con:
            qid = f"mhop-dev-{q_idx:03d}"
            cap = seg.caption
            sec = chunk.section_path
            doc_title = doc_asset.title

            query_text = f"Identify the procedural contradiction or safety violation occurring during {cap} relative to {doc_title}."
            ref_ans = (
                f"During '{cap}' ({seg.start_s:.1f}s–{seg.end_s:.1f}s), a direct contradiction with "
                f"{doc_title} § {sec} was identified: {link.note}"
            )

            queries.append({
                "query_id": qid,
                "type": "multi-hop",
                "relation": "contradicts",
                "query": query_text,
                "action_label": cap,
                "essential_video_asset_ids": [str(seg.asset_id)],
                "essential_doc_asset_ids": [str(doc_asset.id)],
                "essential_segment_ids": [str(seg.id)],
                "essential_chunk_ids": [str(chunk.id)],
                "gold_spans_by_asset": {str(seg.asset_id): [[round(float(seg.start_s), 2), round(float(seg.end_s), 2)]]},
                "target_document": doc_title,
                "target_section": sec,
                "reference_answer": ref_ans,
                "link_note": link.note,
            })
            q_idx += 1

        dataset = {
            "version": "1.0",
            "split": "dev",
            "description": (
                "Multi-hop cross-modal development query set per engineering spec §13.2 and §13.5. "
                "Each query requires retrieving BOTH the video segment and the technical document chunk. "
                "Enables rigorous evaluation of full-set joint retrieval and validates the connective layer "
                "under the Section 13.5 A5 ablation (--no-link-expansion)."
            ),
            "query_count": len(queries),
            "relation_distribution": {
                "specifies": len(picked_spec),
                "documents": len(picked_doc),
                "depicts": len(picked_dep),
                "contradicts": len(picked_con),
            },
            "queries": queries,
        }

        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(dataset, f, indent=2)

        print(f"Successfully generated {len(queries)} multi-hop dev queries in {OUTPUT_PATH}.")


if __name__ == "__main__":
    generate_queries()
