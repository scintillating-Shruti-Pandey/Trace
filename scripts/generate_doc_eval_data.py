"""Generate Document Development Evaluation Queries linked to PostgreSQL Chunk IDs."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.config import Settings
from app.db import make_engine, session_factory
from app.models import Asset, Chunk
from sqlalchemy import select

DEV_DOC_QUERIES_RAW = [
    {
        "query_id": "doc-dev-001",
        "query": "What is the tightening torque for the M8 corner gusset screws on the base frame?",
        "doc_id": "doc-mech-001",
        "section_pattern": "1.0 Base Structure > Frame Rails",
        "difficulty": "easy",
    },
    {
        "query_id": "doc-dev-002",
        "query": "What is the allowable diagonal tolerance between opposite base corners during frame assembly?",
        "doc_id": "doc-mech-001",
        "section_pattern": "1.0 Base Structure > Frame Rails",
        "difficulty": "medium",
    },
    {
        "query_id": "doc-dev-003",
        "query": "How should the composite tabletop be secured to the extrusion frame?",
        "doc_id": "doc-mech-001",
        "section_pattern": "2.0 Tabletop Installation",
        "difficulty": "easy",
    },
    {
        "query_id": "doc-dev-004",
        "query": "What is the required axial clearance between lower hinge leaf and bracket collar?",
        "doc_id": "doc-mech-002",
        "section_pattern": "1.1 Lower Hinge Assembly > Torque & Clearance",
        "difficulty": "easy",
    },
    {
        "query_id": "doc-dev-005",
        "query": "How is the friction resistance adjusted on the middle articulating hinge?",
        "doc_id": "doc-mech-002",
        "section_pattern": "2.0 Middle Hinge Assembly",
        "difficulty": "medium",
    },
    {
        "query_id": "doc-dev-006",
        "query": "What is the part number and dimensions of the camera mounting plate?",
        "doc_id": "doc-mech-003",
        "section_pattern": "2.0 Camera Plate Attachment",
        "difficulty": "easy",
    },
    {
        "query_id": "doc-dev-007",
        "query": "What damping material is placed between the camera plate and vertical collar clamp?",
        "doc_id": "doc-mech-003",
        "section_pattern": "2.0 Camera Plate Attachment",
        "difficulty": "medium",
    },
    {
        "query_id": "doc-dev-008",
        "query": "What corrective action was taken for frame bolt loosening under cyclic vibration?",
        "doc_id": "doc-mech-004",
        "section_pattern": "2.0 Corrective Actions > Retorque",
        "difficulty": "medium",
    },
    {
        "query_id": "doc-dev-009",
        "query": "What tool is required to extract the NDE end-bell on drive motor MOT-AC-3750?",
        "doc_id": "doc-rot-001",
        "section_pattern": "2.0 Disassembly Procedure",
        "difficulty": "easy",
    },
    {
        "query_id": "doc-dev-010",
        "query": "What is the nominal radial air gap between motor rotor and stator bore?",
        "doc_id": "doc-rot-001",
        "section_pattern": "3.0 Rotor & Stator Inspection",
        "difficulty": "medium",
    },
    {
        "query_id": "doc-dev-011",
        "query": "What is the maximum heating temperature for thermal mounting of drive motor bearings?",
        "doc_id": "doc-rot-002",
        "section_pattern": "2.0 Induction Heating",
        "difficulty": "easy",
    },
    {
        "query_id": "doc-dev-012",
        "query": "What type of synthetic grease is specified for open motor bearing relubrication?",
        "doc_id": "doc-rot-002",
        "section_pattern": "3.0 Lubrication",
        "difficulty": "easy",
    },
    {
        "query_id": "doc-dev-013",
        "query": "What is the minimum allowable service length for carbon commutator brushes?",
        "doc_id": "doc-rot-003",
        "section_pattern": "1.0 Brush Inspection",
        "difficulty": "easy",
    },
    {
        "query_id": "doc-dev-014",
        "query": "What vibration frequency identified the outer race bearing fault on motor Unit 02?",
        "doc_id": "doc-rot-004",
        "section_pattern": "1.0 Vibration Analysis",
        "difficulty": "medium",
    },
    {
        "query_id": "doc-dev-015",
        "query": "What is the maximum continuous case drain pressure for hydraulic pump A10VSO45?",
        "doc_id": "doc-hyd-001",
        "section_pattern": "1.0 Specifications > Pressure Ratings",
        "difficulty": "medium",
    },
    {
        "query_id": "doc-dev-016",
        "query": "How is the hydraulic pressure compensator valve adjusted to 180 bar?",
        "doc_id": "doc-hyd-001",
        "section_pattern": "2.0 Pressure Control Valve",
        "difficulty": "easy",
    },
    {
        "query_id": "doc-dev-017",
        "query": "What safety procedure is required before opening the hydraulic filter bowl?",
        "doc_id": "doc-hyd-002",
        "section_pattern": "1.0 Safety Isolation",
        "difficulty": "easy",
    },
    {
        "query_id": "doc-dev-018",
        "query": "What solvent temperature and circulation rate are specified for cooling jacket descaling?",
        "doc_id": "doc-hyd-003",
        "section_pattern": "1.0 Flushing Rig Setup",
        "difficulty": "medium",
    },
    {
        "query_id": "doc-dev-019",
        "query": "What test pressure is required for the hydraulic cooling jacket hydrostatic leak check?",
        "doc_id": "doc-hyd-003",
        "section_pattern": "2.0 Neutralization & Hydrostatic",
        "difficulty": "easy",
    },
    {
        "query_id": "doc-dev-020",
        "query": "What caused the pressure fluctuations and valve chatter on automated clamping Line 3?",
        "doc_id": "doc-hyd-004",
        "section_pattern": "2.0 Root Cause & Teardown",
        "difficulty": "medium",
    },
    {
        "query_id": "doc-dev-021",
        "query": "What are the output ratings of the 24V DC auxiliary bus on PDU-400-24?",
        "doc_id": "doc-elec-001",
        "section_pattern": "1.0 Technical Specs > Power Input",
        "difficulty": "easy",
    },
    {
        "query_id": "doc-dev-022",
        "query": "How quickly do the redundant safety contactors de-energize when an E-stop is pressed?",
        "doc_id": "doc-elec-001",
        "section_pattern": "2.0 Safety Features",
        "difficulty": "easy",
    },
    {
        "query_id": "doc-dev-023",
        "query": "What is the maximum allowable grounding continuity resistance for the display monitor?",
        "doc_id": "doc-elec-002",
        "section_pattern": "2.0 Cable Routing",
        "difficulty": "easy",
    },
    {
        "query_id": "doc-dev-024",
        "query": "What drawbar retention pull force is required for the ISO 40 spindle toolholder?",
        "doc_id": "doc-cnc-001",
        "section_pattern": "1.0 Spindle Design",
        "difficulty": "medium",
    },
    {
        "query_id": "doc-dev-025",
        "query": "What five steps comprise the standard zero energy LOTO protocol?",
        "doc_id": "doc-safe-001",
        "section_pattern": "2.0 Step-by-Step LOTO Protocol",
        "difficulty": "easy",
    },
]

UNANSWERABLE_QUERIES = [
    {
        "query_id": "doc-dev-026",
        "query": "What is the curing time for underwater epoxy on deep-sea pipeline flanges?",
        "difficulty": "hard",
    },
    {
        "query_id": "doc-dev-027",
        "query": "Calibrating the optical pyrometer on the blast furnace nozzle.",
        "difficulty": "hard",
    },
    {
        "query_id": "doc-dev-028",
        "query": "Turbine blade cryogenic coating inspection for supersonic jet engines.",
        "difficulty": "hard",
    },
    {
        "query_id": "doc-dev-029",
        "query": "Fiber optic splice attenuation loss threshold for telecom trunk lines.",
        "difficulty": "hard",
    },
    {
        "query_id": "doc-dev-030",
        "query": "Refueling protocol for heavy water nuclear reactor cooling pools.",
        "difficulty": "hard",
    },
]


def generate_doc_eval_queries():
    settings = Settings()
    engine = make_engine(settings)
    session_maker = session_factory(engine)

    queries = []

    with session_maker() as session:
        for item in DEV_DOC_QUERIES_RAW:
            doc_id = item["doc_id"]
            pattern = item["section_pattern"]

            # Find matching asset
            assets = session.scalars(select(Asset).where(Asset.kind == "document")).all()
            matched_asset = None
            for a in assets:
                if a.meta and a.meta.get("doc_id") == doc_id:
                    matched_asset = a
                    break

            if not matched_asset:
                raise RuntimeError(f"Could not find asset for doc_id {doc_id}")

            # Find matching chunk
            chunks = session.scalars(
                select(Chunk).where(Chunk.asset_id == matched_asset.id)
            ).all()

            matched_chunk = None
            for c in chunks:
                if pattern in c.section_path:
                    matched_chunk = c
                    break

            if not matched_chunk:
                raise RuntimeError(f"Could not find chunk for pattern '{pattern}' in doc {doc_id}")

            queries.append({
                "query_id": item["query_id"],
                "type": "doc-only",
                "query": item["query"],
                "difficulty": item["difficulty"],
                "essential_asset_ids": [matched_asset.id],
                "essential_chunk_ids": [matched_chunk.id],
                "target_section": matched_chunk.section_path,
                "target_document": matched_asset.title,
            })

    # Add unanswerable queries
    for u in UNANSWERABLE_QUERIES:
        queries.append({
            "query_id": u["query_id"],
            "type": "unanswerable",
            "query": u["query"],
            "difficulty": u["difficulty"],
            "essential_asset_ids": [],
            "essential_chunk_ids": [],
        })

    out_data = {
        "version": "1.0",
        "split": "dev",
        "description": "Document-only development query set per engineering spec §16.5.",
        "query_count": len(queries),
        "doc_only_count": len(DEV_DOC_QUERIES_RAW),
        "unanswerable_count": len(UNANSWERABLE_QUERIES),
        "queries": queries,
    }

    out_file = ROOT / "eval" / "data" / "doc_dev_queries.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(out_data, f, indent=2)

    print(f"Generated {len(queries)} doc eval queries ({len(DEV_DOC_QUERIES_RAW)} answerable, {len(UNANSWERABLE_QUERIES)} unanswerable) in {out_file}")


if __name__ == "__main__":
    generate_doc_eval_queries()
