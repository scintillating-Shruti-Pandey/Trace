import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import select
from app.config import Settings
from app.db import make_engine, session_factory
from app.models import Asset, Segment

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "eval" / "data" / "visual_dev_queries.json"

# Curated 20 visual queries reflecting visual features of the 114 IndEgo keysteps
VISUAL_QUERY_SPECS = [
    {
        "query_id": "vis-dev-001",
        "query": "black anodized camera mounting plate attached to vertical bar",
        "caption_match": "attach camera and plate",
        "visual_description": "Depicts black anodized aluminum camera mounting plate (CMP-402) secured to vertical extrusion.",
    },
    {
        "query_id": "vis-dev-002",
        "query": "lower hinge bracket and hardened pivot pin mounted on base frame",
        "caption_match": "assemble lower hinge",
        "visual_description": "Depicts lower hinge mounting bracket and hardened pivot pin seated against extrusion channel.",
    },
    {
        "query_id": "vis-dev-003",
        "query": "middle articulation hinge joint with central friction pre-load nut",
        "caption_match": "assemble middle hinge",
        "visual_description": "Depicts middle articulation joint and friction pre-load hex nut assembly.",
    },
    {
        "query_id": "vis-dev-004",
        "query": "upper hinge top pivot and detent latch mechanism",
        "caption_match": "assemble upper hinge",
        "visual_description": "Depicts upper hinge pivot pin and spring detent latch assembly.",
    },
    {
        "query_id": "vis-dev-005",
        "query": "M12 articulated leveling foot threaded into base corner bracket",
        "caption_match": "attach feet",
        "visual_description": "Depicts articulated leveling feet with rubber base threaded into lower corner brackets.",
    },
    {
        "query_id": "vis-dev-006",
        "query": "VESA display monitor mount and articulated support arm",
        "caption_match": "attach monitor",
        "visual_description": "Depicts operator console monitor fastened to VESA mounting bracket and arm.",
    },
    {
        "query_id": "vis-dev-007",
        "query": "aluminum extrusion corner gusset reinforcement plates with M8 fasteners",
        "caption_match": "attach plates",
        "visual_description": "Depicts 90-degree corner gusset reinforcement plates aligning base frame rails.",
    },
    {
        "query_id": "vis-dev-008",
        "query": "overhead horizontal crossbeam mounted across vertical upright bars",
        "caption_match": "attach upper bar",
        "visual_description": "Depicts top horizontal crossbeam bridging left and right upright vertical bars.",
    },
    {
        "query_id": "vis-dev-009",
        "query": "vertical support extrusion bar fastened to base workstation frame",
        "caption_match": "attach vertical bar",
        "visual_description": "Depicts 1100 mm vertical upright bar standing on workstation frame rail.",
    },
    {
        "query_id": "vis-dev-010",
        "query": "composite tabletop secured with perimeter surface clamping plates",
        "caption_match": "attach tabletop",
        "visual_description": "Depicts composite work surface clamped down onto aluminum extrusion perimeter.",
    },
    {
        "query_id": "vis-dev-011",
        "query": "internal data storage drive and SATA power cabling harness",
        "caption_match": "attach hard disk",
        "visual_description": "Depicts hard disk drive installed in chassis and SATA data cable connection.",
    },
    {
        "query_id": "vis-dev-012",
        "query": "electrical power distribution unit terminal block wiring on DIN rail",
        "caption_match": "attach power connection",
        "visual_description": "Depicts power distribution unit with color-coded stranded wires wired to DIN rail.",
    },
    {
        "query_id": "vis-dev-013",
        "query": "disassembly of axial piston hydraulic pump cylinder block and swashplate",
        "caption_match": "disassemble",
        "visual_description": "Depicts technician extracting cylinder block and piston assembly from hydraulic pump casing.",
    },
    {
        "query_id": "vis-dev-014",
        "query": "inspection of hydraulic valve plate and bronze piston shoe surfaces",
        "caption_match": "inspect",
        "visual_description": "Depicts visual inspection of valve plate sealing face and piston shoes for cavitation wear.",
    },
    {
        "query_id": "vis-dev-015",
        "query": "hydraulic pump casing bolt assembly and valve housing reinstallation",
        "caption_match": "assemble",
        "visual_description": "Depicts technician reassembling hydraulic pump end cover bolts.",
    },
    {
        "query_id": "vis-dev-016",
        "query": "adjusting leveling foot height with open-ended wrench",
        "caption_match": "adjust height",
        "visual_description": "Depicts technician turning jam nut on articulated leveling foot to adjust workstation height.",
    },
    {
        "query_id": "vis-dev-017",
        "query": "connecting 45x45 mm aluminum extrusion base rails into rectangular frame",
        "caption_match": "connect base",
        "visual_description": "Depicts four base extrusion rails joined at 90-degree corners to form the base perimeter.",
    },
    {
        "query_id": "vis-dev-018",
        "query": "preparation of tools and mechanical parts on workstation before assembly",
        "caption_match": "preparation",
        "visual_description": "Depicts layout of hand tools, fasteners, and bracket hardware on assembly workbench.",
    },
    {
        "query_id": "vis-dev-019",
        "query": "attaching aluminum connector gusset plates to frame superstructure",
        "caption_match": "attach connector plates",
        "visual_description": "Depicts fastening triangular connector plates with T-slot nuts onto aluminum profiles.",
    },
    {
        "query_id": "vis-dev-020",
        "query": "camera support collar clamp positioned on vertical bar at operational height",
        "caption_match": "attach camera and plate",
        "visual_description": "Depicts clamping camera support collar clamp (CAM-CLR-45) onto the upright extrusion bar.",
    },
]


def build_queries():
    settings = Settings()
    engine = make_engine(settings)
    session_maker = session_factory(engine)

    with session_maker() as session:
        # Load all manual keysteps
        stmt = (
            select(Segment, Asset)
            .join(Asset, Segment.asset_id == Asset.id)
            .where(Segment.method == "manual")
            .order_by(Segment.caption, Segment.start_s)
        )
        segs_and_assets = session.execute(stmt).all()

        queries = []
        for spec in VISUAL_QUERY_SPECS:
            cap_target = spec["caption_match"]
            matching = [
                (s, a) for s, a in segs_and_assets if s.caption == cap_target
            ]
            if not matching:
                print(f"WARNING: No segment found for {cap_target}!")
                continue

            essential_seg_ids = [str(s.id) for s, a in matching]
            essential_asset_ids = list({str(a.id) for s, a in matching})
            gold_spans = {}
            for s, a in matching:
                aid = str(a.id)
                gold_spans.setdefault(aid, []).append([round(float(s.start_s), 2), round(float(s.end_s), 2)])

            queries.append({
                "query_id": spec["query_id"],
                "type": "visual",
                "query": spec["query"],
                "action_label": cap_target,
                "visual_description": spec["visual_description"],
                "essential_asset_ids": essential_asset_ids,
                "essential_segment_ids": essential_seg_ids,
                "gold_spans_by_asset": gold_spans,
                "candidate_segment_count": len(matching),
            })

        dataset = {
            "version": "1.0",
            "split": "dev",
            "description": (
                "Visual development query set for Phase 3 industrial-image retrieval per engineering spec §13.2, §16.4. "
                "Evaluates visual-text retrieval against representative industrial workpiece keyframes extracted from the 114 keysteps. "
                "Exit gate requirement: Visual Recall@5 >= 0.60."
            ),
            "query_count": len(queries),
            "queries": queries,
        }

        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(dataset, f, indent=2)

        print(f"Generated {len(queries)} visual dev queries in {OUTPUT_PATH}.")


if __name__ == "__main__":
    build_queries()
