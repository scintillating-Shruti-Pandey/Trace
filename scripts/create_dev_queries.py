"""Generate reproducible dev split queries grounded in the IndEgo 25-video corpus.

Adheres strictly to records/ENGINEERING_SPEC.md §13.1 & §13.2:
- video-only queries paired with essential gold manual segment IDs and ground-truth temporal spans.
- unanswerable queries (plausible industrial tasks not in the 25 videos) to evaluate abstention.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.config import Settings
from app.db import make_engine, session_factory
from sqlalchemy import text

OUTPUT_PATH = Path("eval/data/dev_queries.json")

# Natural query templates for specific ground-truth actions
ACTION_QUERY_TEMPLATES = {
    "assemble lower hinge": [
        "How is the lower hinge assembled on the frame?",
        "Show me the segment where the technician installs the lower hinge.",
    ],
    "assemble middle hinge": [
        "What is the step for assembling the middle hinge?",
        "Where is the middle hinge attached?",
    ],
    "assemble upper hinge": [
        "Show the upper hinge assembly procedure.",
        "Demonstrate attaching the upper hinge.",
    ],
    "attach power connection": [
        "Where does the operator attach the power connection?",
    ],
    "attach camera and plate": [
        "Show the video segment attaching the camera and plate.",
        "Mounting the camera plate to the vertical bar.",
    ],
    "attach connector plates": [
        "Locate where the connector plates are secured.",
    ],
    "attach top plate": [
        "Installing the top plate on the assembly.",
    ],
    "attach bottom plate": [
        "Securing the bottom plate to the structure.",
    ],
    "attach tabletop": [
        "How is the tabletop mounted onto the frame?",
    ],
    "connect base": [
        "Assembling and connecting the base frame.",
        "Connecting base components of the structure.",
    ],
    "attach vertical bar": [
        "Where is the vertical bar positioned and fastened?",
    ],
    "attach upper bar": [
        "Mounting the upper bar across the frame.",
    ],
    "inspect and clean": [
        "Where is the component inspected and cleaned for maintenance?",
    ],
    "disassemble": [
        "Show the disassembly of the motor casing and components.",
        "Disassembling the unit for repair inspection.",
    ],
    "repair": [
        "Where is the repair procedure performed on the machine?",
    ],
    "test": [
        "Testing the completed assembly after repair.",
    ],
    "clean up": [
        "Clean up of the workstation and tools after the task.",
    ],
    "plug in": [
        "Plugging in electrical power to the test unit.",
    ],
    "attach monitor": [
        "Attaching the display monitor to the mount.",
    ],
    "turn on": [
        "Powering on and turning on the system.",
    ],
}

# Unanswerable queries (spec §13.2: plausible queries absent from corpus to test abstention)
UNANSWERABLE_QUERIES = [
    "Replacing the hydraulic pump oil filter and seal ring.",
    "Calibrating the optical pyrometer on the furnace nozzle.",
    "Torque specification for high-pressure fuel injectors.",
    "Flushing cooling jacket with glycol solvent.",
    "Replacing cracked carbon commutator brushes.",
]


def create_dev_dataset():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    settings = Settings()
    engine = make_engine(settings)
    session_maker = session_factory(engine)

    queries = []
    q_id = 1

    with session_maker() as session:
        # Load all manual segments grouped by caption
        sql = text(
            """
            SELECT s.id, s.asset_id, a.title, s.caption, s.start_s, s.end_s
            FROM segments s
            JOIN assets a ON a.id = s.asset_id
            WHERE s.method = 'manual'
            ORDER BY a.title, s.idx
            """
        )
        rows = session.execute(sql).mappings().all()

        segments_by_caption = {}
        for r in rows:
            cap = r["caption"].strip().lower()
            segments_by_caption.setdefault(cap, []).append(
                {
                    "segment_id": str(r["id"]),
                    "asset_id": str(r["asset_id"]),
                    "asset_title": r["title"],
                    "start_s": float(r["start_s"]),
                    "end_s": float(r["end_s"]),
                }
            )

        # 1. Answerable video-only queries
        for action, templates in ACTION_QUERY_TEMPLATES.items():
            key = action.lower()
            matching_segs = segments_by_caption.get(key, [])
            if not matching_segs:
                continue

            essential_seg_ids = [s["segment_id"] for s in matching_segs]

            # Map gold spans and essential asset IDs across all matching videos
            gold_spans_by_asset = {}
            seen_assets = []
            for s in matching_segs:
                aid = s["asset_id"]
                if aid not in seen_assets:
                    seen_assets.append(aid)
                gold_spans_by_asset.setdefault(aid, []).append([s["start_s"], s["end_s"]])

            primary_seg = matching_segs[0]

            for tmpl in templates:
                queries.append(
                    {
                        "query_id": f"dev-{q_id:03d}",
                        "type": "video-only",
                        "query": tmpl,
                        "action_label": action,
                        "essential_asset_ids": seen_assets,
                        "essential_segment_ids": essential_seg_ids,
                        "gold_spans_by_asset": gold_spans_by_asset,
                        "primary_asset": primary_seg["asset_title"],
                        "primary_gold_span": [primary_seg["start_s"], primary_seg["end_s"]],
                        "num_gold_videos": len(seen_assets),
                        "num_gold_segments": len(essential_seg_ids),
                    }
                )
                q_id += 1

        # 2. Unanswerable queries (spec §13.2)
        for u_query in UNANSWERABLE_QUERIES:
            queries.append(
                {
                    "query_id": f"dev-{q_id:03d}",
                    "type": "unanswerable",
                    "query": u_query,
                    "action_label": None,
                    "essential_asset_ids": [],
                    "essential_segment_ids": [],
                    "gold_spans_by_asset": {},
                    "primary_asset": None,
                    "primary_gold_span": None,
                    "num_gold_videos": 0,
                    "num_gold_segments": 0,
                }
            )
            q_id += 1

    payload = {
        "version": "1.1",
        "split": "dev",
        "description": (
            "IndEgo 25-video grounded development query set per engineering spec §13. "
            "Evaluates text-to-video retrieval against the 114 human-annotated keysteps. "
            "Caveat: Tests annotation-text semantic alignment; 1,091 secondary windows contain "
            "procedural timestamp captions rather than full multimodal captions."
        ),
        "circularity_disclosure": (
            "Queries are written to reflect procedural operations present in the 114 keysteps. "
            "Locked held-out test split remains separate and unrun until Phase 6."
        ),
        "query_count": len(queries),
        "video_only_count": len([q for q in queries if q["type"] == "video-only"]),
        "unanswerable_count": len([q for q in queries if q["type"] == "unanswerable"]),
        "queries": queries,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(
        f"Generated {len(queries)} dev queries ({payload['video_only_count']} video-only, "
        f"{payload['unanswerable_count']} unanswerable) -> {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    create_dev_dataset()
