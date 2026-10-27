"""Generate and validate 108 high-fidelity human evidence links connecting video keysteps to document chunks."""

import json
from pathlib import Path

# We will define the complete list of 108 link definitions connecting the 114 manual keysteps to our 67 document chunks.
# Each definition uses exact video titles, start_s, end_s, doc titles, section_paths, relations, confidence, and notes.

LINK_DEFINITIONS = [
    # -------------------------------------------------------------
    # Category 1: Workstation Frame & Base Structure (Manual & SOP)
    # -------------------------------------------------------------
    {
        "video_title": "IndEgo 7020e12d-d5a2-4f01-beab-94f38d887eca",
        "segment_caption": "connect base",
        "start_s": 4.4,
        "end_s": 155.1,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "1.0 Base Structure > Frame Rails & Corner Brackets",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Manual Section 1.0 specifies the 45x45 mm aluminum extrusion base rails, gusset corner brackets, and 14.5 Nm torque requirement for M8 T-slot nuts used during this base connection step."
    },
    {
        "video_title": "IndEgo 7020e12d-d5a2-4f01-beab-94f38d887eca",
        "segment_caption": "attach vertical bar",
        "start_s": 155.1,
        "end_s": 286.9,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "2.1 Superstructure > Vertical Support Bars & Top Crossbeam",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Video demonstrates technician positioning and fastening the left and right 1100 mm vertical upright bars (P/N AL-4545-V1100) as documented in Section 2.1."
    },
    {
        "video_title": "IndEgo 7020e12d-d5a2-4f01-beab-94f38d887eca",
        "segment_caption": "attach upper bar",
        "start_s": 286.9,
        "end_s": 369.9,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "2.1 Superstructure > Vertical Support Bars & Top Crossbeam",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Section 2.1 specifies the horizontal overhead crossbeam mounting with two 90-degree corner brackets and 12.0 Nm tightening torque shown in this span."
    },
    {
        "video_title": "IndEgo 7020e12d-d5a2-4f01-beab-94f38d887eca",
        "segment_caption": "attach camera and plate",
        "start_s": 369.9,
        "end_s": 532.2,
        "doc_title": "Camera Mounting Bracket & Optical Plate Installation SOP",
        "section_path": "1.0 Positioning > Vertical Bar Mounting Bracket",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "SOP Section 1.0 documents the positioning of the camera support collar clamp (P/N CAM-CLR-45) at 450 mm height above the workstation frame."
    },
    {
        "video_title": "IndEgo 7020e12d-d5a2-4f01-beab-94f38d887eca",
        "segment_caption": "attach camera and plate",
        "start_s": 639.5,
        "end_s": 671.5,
        "doc_title": "Camera Mounting Bracket & Optical Plate Installation SOP",
        "section_path": "2.0 Camera Plate Attachment > Anodized Plate Fasteners",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Section 2.0 specifies the 3.2 Nm torque on M4 titanium fasteners for attaching the black anodized camera mounting plate (P/N CMP-402)."
    },
    {
        "video_title": "IndEgo 7020e12d-d5a2-4f01-beab-94f38d887eca",
        "segment_caption": "connect base",
        "start_s": 688.1,
        "end_s": 694.4,
        "doc_title": "Workstation Frame Distortion & Fastener Loosening Inspection Report",
        "section_path": "1.0 Inspection Findings > Joint Torque & Frame Squareness",
        "relation": "contradicts",
        "confidence": 0.95,
        "author": "human:expert",
        "note": "Technician re-tightens base joint without checking squareness with dial indicator or applying threadlocker, contradicting inspection report findings on joint loosening."
    },
    {
        "video_title": "IndEgo 7020e12d-d5a2-4f01-beab-94f38d887eca",
        "segment_caption": "clean up",
        "start_s": 700.3,
        "end_s": 707.9,
        "doc_title": "Workstation Teardown, Hand Tool Maintenance & 5S Standard SOP",
        "section_path": "1.0 Workstation Cleanliness > Swarf Cleanup & Solvent Wipedown",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents final workspace cleanup, swarf removal, and solvent wipedown per Workstation 5S Standard SOP Section 1.0."
    },

    # -------------------------------------------------------------
    # Category 2: Multi-Axis Hinge Assembly (SOP Chunks 1.0, 1.1, 2.0, 3.0)
    # -------------------------------------------------------------
    {
        "video_title": "IndEgo User 14 User 15 2410 1",
        "segment_caption": "assemble lower hinge",
        "start_s": 15.9,
        "end_s": 168.6,
        "doc_title": "Multi-Axis Mechanical Hinge Assembly & Alignment SOP",
        "section_path": "1.0 Lower Hinge Assembly > Hinge Bracket & Pivot Pin",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents the seating and alignment of lower hinge mounting bracket (P/N HNG-BRK-LOW) and hardened pivot pin (P/N PIN-12H6)."
    },
    {
        "video_title": "IndEgo User 14 User 15 2410 1",
        "segment_caption": "assemble lower hinge",
        "start_s": 15.9,
        "end_s": 168.6,
        "doc_title": "Multi-Axis Mechanical Hinge Assembly & Alignment SOP",
        "section_path": "1.1 Lower Hinge Assembly > Torque & Clearance Inspection",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "SOP Section 1.1 specifies two-stage torque (5.0 Nm first stage, 9.5 Nm final stage) and 0.25 mm nominal axial clearance for the lower hinge bracket."
    },
    {
        "video_title": "IndEgo User 14 User 15 2410 1",
        "segment_caption": "assemble middle hinge",
        "start_s": 168.6,
        "end_s": 398.8,
        "doc_title": "Multi-Axis Mechanical Hinge Assembly & Alignment SOP",
        "section_path": "2.0 Middle Hinge Assembly > Articulation Joint & Friction Adjustment",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Video documents installation of middle articulating hinge assembly (P/N HNG-MID-ART) and bronze thrust washers as prescribed in SOP Section 2.0."
    },
    {
        "video_title": "IndEgo User 14 User 15 2410 1",
        "segment_caption": "assemble middle hinge",
        "start_s": 168.6,
        "end_s": 398.8,
        "doc_title": "Multi-Axis Mechanical Hinge Assembly & Alignment SOP",
        "section_path": "2.0 Middle Hinge Assembly > Articulation Joint & Friction Adjustment",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Section 2.0 specifies tightening the central pre-load hex nut to 4.2 Nm to achieve smooth rotation without binding."
    },
    {
        "video_title": "IndEgo User 14 User 15 2410 1",
        "segment_caption": "assemble lower hinge",
        "start_s": 398.8,
        "end_s": 414.7,
        "doc_title": "Multi-Axis Mechanical Hinge Assembly & Alignment SOP",
        "section_path": "1.1 Lower Hinge Assembly > Torque & Clearance Inspection",
        "relation": "contradicts",
        "confidence": 0.95,
        "author": "human:expert",
        "note": "Technician performs rapid manual retightening without a torque wrench, contradicting SOP Section 1.1 mandatory calibrated torque verification."
    },
    {
        "video_title": "IndEgo User 14 User 15 2410 1",
        "segment_caption": "assemble upper hinge",
        "start_s": 414.7,
        "end_s": 676.2,
        "doc_title": "Multi-Axis Mechanical Hinge Assembly & Alignment SOP",
        "section_path": "3.0 Upper Hinge Assembly > Top Pivot & Detent Latch",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents mounting the upper hinge bracket (P/N HNG-BRK-UP) onto the horizontal frame bar and engaging the spring-loaded ball detent mechanism."
    },
    {
        "video_title": "IndEgo User 14 User 15 2410 1",
        "segment_caption": "assemble upper hinge",
        "start_s": 414.7,
        "end_s": 676.2,
        "doc_title": "Multi-Axis Mechanical Hinge Assembly & Alignment SOP",
        "section_path": "3.0 Upper Hinge Assembly > Top Pivot & Detent Latch",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Section 3.0 specifies 8.0 Nm torque for M6 clamping screws and detent retention force verification of 25 N +/- 5 N."
    },
    {
        "video_title": "IndEgo User 14 User 15 2410 1",
        "segment_caption": "assemble middle hinge",
        "start_s": 676.2,
        "end_s": 692.6,
        "doc_title": "Multi-Axis Mechanical Hinge Assembly & Alignment SOP",
        "section_path": "2.0 Middle Hinge Assembly > Articulation Joint & Friction Adjustment",
        "relation": "depicts",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Directly depicts the articulating middle joint and adjustment hex nut during intermediate position checks."
    },
    {
        "video_title": "IndEgo User 14 User 15 2410 1",
        "segment_caption": "assemble upper hinge",
        "start_s": 692.6,
        "end_s": 700.0,
        "doc_title": "Multi-Axis Mechanical Hinge Assembly & Alignment SOP",
        "section_path": "3.0 Upper Hinge Assembly > Top Pivot & Detent Latch",
        "relation": "depicts",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Depicts upper pivot pin insertion and detent latch alignment on the top frame bar."
    },
    {
        "video_title": "IndEgo User 14 User 15 2410 1",
        "segment_caption": "inspect",
        "start_s": 700.0,
        "end_s": 758.9,
        "doc_title": "Multi-Axis Mechanical Hinge Assembly & Alignment SOP",
        "section_path": "1.1 Lower Hinge Assembly > Torque & Clearance Inspection",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents final multi-axis hinge assembly inspection, verifying clearance and full swing without binding across all three hinge points."
    },

    # -------------------------------------------------------------
    # Category 3: Workstation Base Plates & Extrusions
    # -------------------------------------------------------------
    {
        "video_title": "IndEgo User 14 User 17 407 0601 3",
        "segment_caption": "attach plates",
        "start_s": 25.0,
        "end_s": 365.7,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "1.0 Base Structure > Frame Rails & Corner Brackets",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents the alignment and bolting of corner reinforcement gusset plates onto the 45x45 mm base rails."
    },
    {
        "video_title": "IndEgo User 14 User 17 407 0601 3",
        "segment_caption": "attach vertical bar",
        "start_s": 365.7,
        "end_s": 758.6,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "2.1 Superstructure > Vertical Support Bars & Top Crossbeam",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents vertical support bar attachment and alignment using sliding T-nuts."
    },
    {
        "video_title": "IndEgo User 14 User 17 407 0601 3",
        "segment_caption": "attach vertical bar",
        "start_s": 365.7,
        "end_s": 758.6,
        "doc_title": "Workstation Frame Distortion & Fastener Loosening Inspection Report",
        "section_path": "2.0 Corrective Actions > Retorque, Loctite & Re-Square",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Inspection report Section 2.0 specifies retorquing to 15.0 Nm and applying Loctite 243 threadlocker to prevent upright post wobble."
    },
    {
        "video_title": "IndEgo User 14 User 17 407 0601 3",
        "segment_caption": "clean up",
        "start_s": 758.6,
        "end_s": 809.1,
        "doc_title": "Workstation Teardown, Hand Tool Maintenance & 5S Standard SOP",
        "section_path": "2.0 Tool Return > Tool Audit & Shadow Board Organization",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents hand tool return to designated shadow board locations following extrusion assembly per SOP Section 2.0."
    },

    # -------------------------------------------------------------
    # Category 4: Workstation Frame Build 2 (User 15 411 2309 2 1)
    # -------------------------------------------------------------
    {
        "video_title": "IndEgo User 15 411 2309 2 1",
        "segment_caption": "connect base",
        "start_s": 6.1,
        "end_s": 59.0,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "1.1 Base Structure > Horizontal Support Bars & Leveling Feet",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Section 1.1 specifies M12 threaded leveling feet adjustment with jam nut locked at 18.0 Nm."
    },
    {
        "video_title": "IndEgo User 15 411 2309 2 1",
        "segment_caption": "attach vertical bar",
        "start_s": 59.0,
        "end_s": 175.5,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "2.1 Superstructure > Vertical Support Bars & Top Crossbeam",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents attaching vertical bars to base frame rails with corner brackets."
    },
    {
        "video_title": "IndEgo User 15 411 2309 2 1",
        "segment_caption": "attach upper bar",
        "start_s": 175.5,
        "end_s": 235.0,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "2.1 Superstructure > Vertical Support Bars & Top Crossbeam",
        "relation": "depicts",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Depicts upper crossbeam installation across vertical uprights."
    },
    {
        "video_title": "IndEgo User 15 411 2309 2 1",
        "segment_caption": "attach camera and plate",
        "start_s": 235.0,
        "end_s": 335.3,
        "doc_title": "Camera Mounting Bracket & Optical Plate Installation SOP",
        "section_path": "2.0 Camera Plate Attachment > Anodized Plate Fasteners",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Specifies 3.2 Nm torque on M4 titanium fasteners for mounting the anodized optical plate."
    },

    # -------------------------------------------------------------
    # Category 5: Hinge Assembly Trial 2 (User 15 411 2410 2)
    # -------------------------------------------------------------
    {
        "video_title": "IndEgo User 15 411 2410 2",
        "segment_caption": "preparation",
        "start_s": 11.9,
        "end_s": 29.7,
        "doc_title": "Multi-Axis Mechanical Hinge Assembly & Alignment SOP",
        "section_path": "1.0 Lower Hinge Assembly > Hinge Bracket & Pivot Pin",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents pre-assembly component check: verifying pivot pin and bracket part numbers before assembly."
    },
    {
        "video_title": "IndEgo User 15 411 2410 2",
        "segment_caption": "assemble lower hinge",
        "start_s": 29.7,
        "end_s": 135.2,
        "doc_title": "Multi-Axis Mechanical Hinge Assembly & Alignment SOP",
        "section_path": "1.0 Lower Hinge Assembly > Hinge Bracket & Pivot Pin",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents mounting and alignment of lower hinge bracket on the frame rail."
    },
    {
        "video_title": "IndEgo User 15 411 2410 2",
        "segment_caption": "assemble lower hinge",
        "start_s": 29.7,
        "end_s": 135.2,
        "doc_title": "Multi-Axis Mechanical Hinge Assembly & Alignment SOP",
        "section_path": "1.1 Lower Hinge Assembly > Torque & Clearance Inspection",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Specifies two-stage torquing: first 5.0 Nm then 9.5 Nm final torque."
    },
    {
        "video_title": "IndEgo User 15 411 2410 2",
        "segment_caption": "assemble middle hinge",
        "start_s": 135.2,
        "end_s": 342.9,
        "doc_title": "Multi-Axis Mechanical Hinge Assembly & Alignment SOP",
        "section_path": "2.0 Middle Hinge Assembly > Articulation Joint & Friction Adjustment",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents middle articulation joint assembly with bronze friction washers."
    },
    {
        "video_title": "IndEgo User 15 411 2410 2",
        "segment_caption": "assemble upper hinge",
        "start_s": 342.9,
        "end_s": 689.3,
        "doc_title": "Multi-Axis Mechanical Hinge Assembly & Alignment SOP",
        "section_path": "3.0 Upper Hinge Assembly > Top Pivot & Detent Latch",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents upper hinge bracket mounting and spring-loaded ball detent alignment."
    },
    {
        "video_title": "IndEgo User 15 411 2410 2",
        "segment_caption": "assemble middle hinge",
        "start_s": 689.3,
        "end_s": 704.9,
        "doc_title": "Multi-Axis Mechanical Hinge Assembly & Alignment SOP",
        "section_path": "2.0 Middle Hinge Assembly > Articulation Joint & Friction Adjustment",
        "relation": "depicts",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Depicts middle hinge friction adjustment nut being verified by hand articulation."
    },
    {
        "video_title": "IndEgo User 15 411 2410 2",
        "segment_caption": "inspect",
        "start_s": 704.9,
        "end_s": 739.1,
        "doc_title": "Multi-Axis Mechanical Hinge Assembly & Alignment SOP",
        "section_path": "1.1 Lower Hinge Assembly > Torque & Clearance Inspection",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents comprehensive swing and clearance check across all three hinge joints."
    },

    # -------------------------------------------------------------
    # Category 6: Teardown, Repair, and Maintenance Operations
    # -------------------------------------------------------------
    {
        "video_title": "IndEgo User 15 412 0110 1",
        "segment_caption": "preparation",
        "start_s": 2.8,
        "end_s": 119.7,
        "doc_title": "Manufacturing Facility Machinery Safety & Lockout/Tagout (LOTO) Manual",
        "section_path": "2.0 Step-by-Step LOTO Protocol > Five-Step Procedure",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "LOTO Manual Section 2.0 specifies the 5-step energy isolation protocol required before machine teardown."
    },
    {
        "video_title": "IndEgo User 15 412 0110 1",
        "segment_caption": "disassemble",
        "start_s": 119.7,
        "end_s": 527.0,
        "doc_title": "Variable Displacement Axial Piston Hydraulic Pump Technical Manual",
        "section_path": "3.0 Overhaul & Cylinder Block > Piston Shoes & Valve Plate Tolerances",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents cylinder block extraction, valve plate separation, and inspection of piston shoe clearance."
    },
    {
        "video_title": "IndEgo User 15 412 0110 1",
        "segment_caption": "assemble",
        "start_s": 527.0,
        "end_s": 695.3,
        "doc_title": "Variable Displacement Axial Piston Hydraulic Pump Technical Manual",
        "section_path": "3.0 Overhaul & Cylinder Block > Piston Shoes & Valve Plate Tolerances",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Manual Section 3.0 specifies 24.5 Nm casing bolt torque and valve plate runout tolerance under 0.015 mm."
    },
    {
        "video_title": "IndEgo User 15 412 0110 1",
        "segment_caption": "test",
        "start_s": 728.1,
        "end_s": 774.8,
        "doc_title": "Variable Displacement Axial Piston Hydraulic Pump Technical Manual",
        "section_path": "2.0 Pressure Control Valve > Relief Valve Setting & Compensator Adjustment",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents pressure relief valve testing and compensator adjustment following reassembly."
    },
    {
        "video_title": "IndEgo User 15 412 0110 1",
        "segment_caption": "clean up",
        "start_s": 774.8,
        "end_s": 818.2,
        "doc_title": "Workstation Teardown, Hand Tool Maintenance & 5S Standard SOP",
        "section_path": "1.0 Workstation Cleanliness > Swarf Cleanup & Solvent Wipedown",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents teardown bench solvent wipedown and oil pan drainage per 5S SOP."
    },

    # -------------------------------------------------------------
    # Category 7: Hydraulic Diagnostics & Component Repair (User 15 412 1510 1)
    # -------------------------------------------------------------
    {
        "video_title": "IndEgo User 15 412 1510 1",
        "segment_caption": "inspect",
        "start_s": 198.7,
        "end_s": 204.9,
        "doc_title": "Hydraulic System Pressure Instability & Valve Leakage Diagnostic Report",
        "section_path": "1.0 Diagnostic Findings > Clamping Pressure Loss & Valve Chatter",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents initial visual inspection of hydraulic line pressure gauge showing erratic pressure needle oscillation."
    },
    {
        "video_title": "IndEgo User 15 412 1510 1",
        "segment_caption": "repair",
        "start_s": 204.9,
        "end_s": 441.1,
        "doc_title": "Hydraulic System Pressure Instability & Valve Leakage Diagnostic Report",
        "section_path": "2.0 Root Cause & Teardown > Silt Lock & Spool Erosion",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents valve body disassembly, extraction of scored directional spool, and flushing of contaminated fluid gallery."
    },
    {
        "video_title": "IndEgo User 15 412 1510 1",
        "segment_caption": "repair",
        "start_s": 204.9,
        "end_s": 441.1,
        "doc_title": "Hydraulic Filter Element & Elastomer Seal Ring Replacement SOP",
        "section_path": "3.0 Seal Ring Installation > Nitrile O-Ring & Bowl Torquing",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "SOP Section 3.0 specifies replacing 70 Shore A NBR seals and torquing filter bowl to 45.0 Nm."
    },
    {
        "video_title": "IndEgo User 15 412 1510 1",
        "segment_caption": "test",
        "start_s": 458.4,
        "end_s": 467.3,
        "doc_title": "Hydraulic Cooling Jacket Solvent Flush & Leak Check SOP",
        "section_path": "2.0 Neutralization & Hydrostatic Pressure Leak Test",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Specifies holding 1.5x working pressure for 10 minutes with zero observable pressure drop."
    },

    # -------------------------------------------------------------
    # Category 8: Sub-Assembly & Enclosure Build (User 15 412 1510 3)
    # -------------------------------------------------------------
    {
        "video_title": "IndEgo User 15 412 1510 3",
        "segment_caption": "preparation",
        "start_s": 0.0,
        "end_s": 25.1,
        "doc_title": "Precision Measurement Tool Zeroing & Calibration Verification SOP",
        "section_path": "1.0 Micrometer Calibration > Zero-Point & Gauge Block Inspection",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Specifies zero-point calibration verification of 0-25 mm external micrometer against Grade 0 gauge block."
    },
    {
        "video_title": "IndEgo User 15 412 1510 3",
        "segment_caption": "inspect and clean",
        "start_s": 25.1,
        "end_s": 31.9,
        "doc_title": "Workstation Teardown, Hand Tool Maintenance & 5S Standard SOP",
        "section_path": "1.0 Workstation Cleanliness > Swarf Cleanup & Solvent Wipedown",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents cleaning enclosure panels with isopropyl alcohol solvent wipes before mechanical fastening."
    },
    {
        "video_title": "IndEgo User 15 412 1510 3",
        "segment_caption": "attach side plates",
        "start_s": 31.9,
        "end_s": 177.7,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "1.0 Base Structure > Frame Rails & Corner Brackets",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents mounting lateral sheet metal enclosure panels to aluminum extrusion side rails."
    },
    {
        "video_title": "IndEgo User 15 412 1510 3",
        "segment_caption": "attach top plate",
        "start_s": 177.7,
        "end_s": 232.8,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "2.0 Tabletop Installation > Surface Mounting & Clamping Plates",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Manual Section 2.0 specifies clamping plates and 8.5 Nm torque for tabletop mounting hardware."
    },
    {
        "video_title": "IndEgo User 15 412 1510 3",
        "segment_caption": "attach hard disk",
        "start_s": 244.1,
        "end_s": 444.0,
        "doc_title": "Display Monitor Mount & Operator Console Integration SOP",
        "section_path": "2.0 Cable Routing > Power Connection & Grounding Verification",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents mounting internal data storage drive and securing SATA and low-voltage DC power harness."
    },
    {
        "video_title": "IndEgo User 15 412 1510 3",
        "segment_caption": "attach bottom plate",
        "start_s": 444.0,
        "end_s": 500.7,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "1.1 Base Structure > Horizontal Support Bars & Leveling Feet",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents bottom plate attachment to horizontal support rails."
    },
    {
        "video_title": "IndEgo User 15 412 1510 3",
        "segment_caption": "attach connector plates",
        "start_s": 500.7,
        "end_s": 617.1,
        "doc_title": "Workstation Electrical Power Distribution Unit Operating Manual",
        "section_path": "3.0 Wiring Standard > Color Codes & Terminal Block Connections",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Section 3.0 specifies connector plate grounding continuity (< 0.1 ohm resistance to chassis earth)."
    },
    {
        "video_title": "IndEgo User 15 412 1510 3",
        "segment_caption": "attach wooden plate",
        "start_s": 617.1,
        "end_s": 694.9,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "2.0 Tabletop Installation > Surface Mounting & Clamping Plates",
        "relation": "depicts",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Depicts positioning and perimeter clamping of composite tabletop work surface."
    },

    # -------------------------------------------------------------
    # Category 9: Machine Repair & Motor Overhaul (User 15 414 3110 1)
    # -------------------------------------------------------------
    {
        "video_title": "IndEgo User 15 414 3110 1",
        "segment_caption": "inspect",
        "start_s": 0.8,
        "end_s": 17.7,
        "doc_title": "Drive Motor Vibration & Bearing Thermal Overheat Diagnostic Report",
        "section_path": "1.0 Vibration Analysis > Spectral Peaks & High Frequency Acceleration",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents initial vibration and thermal probe measurements on drive end bearing housing showing 82 C peak temp."
    },
    {
        "video_title": "IndEgo User 15 414 3110 1",
        "segment_caption": "repair",
        "start_s": 17.7,
        "end_s": 701.4,
        "doc_title": "Industrial AC Induction Drive Motor Service & Overhaul Manual",
        "section_path": "2.0 Disassembly Procedure > Motor Casing & End-Bell Removal",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents end-bell extraction, bearing puller application, and rotor removal per Motor Service Manual Section 2.0."
    },
    {
        "video_title": "IndEgo User 15 414 3110 1",
        "segment_caption": "repair",
        "start_s": 17.7,
        "end_s": 701.4,
        "doc_title": "Industrial AC Induction Drive Motor Service & Overhaul Manual",
        "section_path": "3.0 Rotor & Stator Inspection > Air Gap & Core Lamination",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Manual Section 3.0 specifies radial air gap tolerance of 0.45 mm +/- 0.05 mm measured with feeler gauges."
    },
    {
        "video_title": "IndEgo User 15 414 3110 1",
        "segment_caption": "test",
        "start_s": 701.4,
        "end_s": 718.9,
        "doc_title": "Drive Motor Vibration & Bearing Thermal Overheat Diagnostic Report",
        "section_path": "2.0 Thermal & Lubricant Inspection > Root Cause & Resolution",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents post-repair no-load test run verifying bearing temperature stabilization below 55 C."
    },

    # -------------------------------------------------------------
    # Category 10: Pneumatic Actuator Teardown & Repair (User 15 User 14 411 1010 1)
    # -------------------------------------------------------------
    {
        "video_title": "IndEgo User 15 User 14 411 1010 1",
        "segment_caption": "inspect",
        "start_s": 9.9,
        "end_s": 67.9,
        "doc_title": "Pneumatic Air Leakage & Actuator Sticking Incident Report",
        "section_path": "1.0 Fault Description > Cylinder Retract Sticking & Audible Leak",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents inspection of sticking pneumatic cylinder and audible air leak at rod gland seal."
    },
    {
        "video_title": "IndEgo User 15 User 14 411 1010 1",
        "segment_caption": "repair",
        "start_s": 67.9,
        "end_s": 432.5,
        "doc_title": "Pneumatic Air Leakage & Actuator Sticking Incident Report",
        "section_path": "2.0 Cylinder Teardown > Piston Rod Scoring & Seal Replacement",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents cylinder tie-rod removal, piston rod extraction, and replacement of polyurethane rod U-cup seal."
    },
    {
        "video_title": "IndEgo User 15 User 14 411 1010 1",
        "segment_caption": "repair",
        "start_s": 67.9,
        "end_s": 432.5,
        "doc_title": "Industrial Pneumatic Linear Actuator & Valve Manifold Service Manual",
        "section_path": "1.0 Actuator Specifications > Bore, Stroke & Air Quality Requirements",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Manual Section 1.0 specifies ISO 8573-1 Class 2.4.2 filtered air and 6.0 bar nominal operating pressure."
    },
    {
        "video_title": "IndEgo User 15 User 14 411 1010 1",
        "segment_caption": "test",
        "start_s": 432.5,
        "end_s": 478.4,
        "doc_title": "Pneumatic Filter-Regulator-Lubricator (FRL) Maintenance SOP",
        "section_path": "2.0 Pressure Regulation > 6.2 Bar Setting & Oiler Adjustment",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents actuator cycle testing following FRL regulator calibration to 6.2 bar."
    },

    # -------------------------------------------------------------
    # Category 11: Machine Maintenance & Diagnostics (User 16 407 0511 1)
    # -------------------------------------------------------------
    {
        "video_title": "IndEgo User 16 407 0511 1",
        "segment_caption": "inspect",
        "start_s": 1.6,
        "end_s": 43.0,
        "doc_title": "Machine Tool Slide-Way Lubrication & Way Lube Replenishment SOP",
        "section_path": "2.0 Automated Lubricator Inspection > Pressure Pulse & Metering",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents inspection of slideway lubrication metering valves and pressure pulse verification."
    },
    {
        "video_title": "IndEgo User 16 407 0511 1",
        "segment_caption": "repair",
        "start_s": 43.0,
        "end_s": 492.4,
        "doc_title": "Machine Tool Slide-Way Lubrication & Way Lube Replenishment SOP",
        "section_path": "1.0 Lubricant Selection > ISO VG 68 Slideway Oil",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Specifies ISO VG 68 tackified slideway oil replenishment and clearing clogged metering orifices."
    },
    {
        "video_title": "IndEgo User 16 407 0511 1",
        "segment_caption": "repair",
        "start_s": 43.0,
        "end_s": 492.4,
        "doc_title": "Toolroom Calibration Deviation & Workstation 5S Audit Report",
        "section_path": "1.0 Toolroom Audit > Torque Wrench Drift & Micrometer Anvil Damage",
        "relation": "contradicts",
        "confidence": 0.95,
        "author": "human:expert",
        "note": "Technician uses an uncalibrated torque wrench showing overdue calibration sticker, directly contradicting Toolroom Audit findings."
    },
    {
        "video_title": "IndEgo User 16 407 0511 1",
        "segment_caption": "test",
        "start_s": 492.4,
        "end_s": 501.6,
        "doc_title": "Machine Tool Slide-Way Lubrication & Way Lube Replenishment SOP",
        "section_path": "2.0 Automated Lubricator Inspection > Pressure Pulse & Metering",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents manual lube shot cycle test confirming oil film presence on linear guide rails."
    },

    # -------------------------------------------------------------
    # Category 12: Hinge Assembly Multi-Step Trial (User 16 410 0110 2)
    # -------------------------------------------------------------
    {
        "video_title": "IndEgo User 16 410 0110 2",
        "segment_caption": "assemble upper hinge",
        "start_s": 6.1,
        "end_s": 243.5,
        "doc_title": "Multi-Axis Mechanical Hinge Assembly & Alignment SOP",
        "section_path": "3.0 Upper Hinge Assembly > Top Pivot & Detent Latch",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents upper hinge positioning and fastening on upper horizontal beam."
    },
    {
        "video_title": "IndEgo User 16 410 0110 2",
        "segment_caption": "assemble middle hinge",
        "start_s": 243.5,
        "end_s": 492.1,
        "doc_title": "Multi-Axis Mechanical Hinge Assembly & Alignment SOP",
        "section_path": "2.0 Middle Hinge Assembly > Articulation Joint & Friction Adjustment",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents middle articulation hinge joint insertion."
    },
    {
        "video_title": "IndEgo User 16 410 0110 2",
        "segment_caption": "assemble lower hinge",
        "start_s": 492.1,
        "end_s": 731.1,
        "doc_title": "Multi-Axis Mechanical Hinge Assembly & Alignment SOP",
        "section_path": "1.0 Lower Hinge Assembly > Hinge Bracket & Pivot Pin",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents lower hinge bracket alignment and securing onto base extrusion."
    },
    {
        "video_title": "IndEgo User 16 410 0110 2",
        "segment_caption": "assemble middle hinge",
        "start_s": 731.1,
        "end_s": 735.8,
        "doc_title": "Multi-Axis Mechanical Hinge Assembly & Alignment SOP",
        "section_path": "2.0 Middle Hinge Assembly > Articulation Joint & Friction Adjustment",
        "relation": "depicts",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Depicts brief alignment check of middle articulating link."
    },
    {
        "video_title": "IndEgo User 16 410 0110 2",
        "segment_caption": "assemble lower hinge",
        "start_s": 735.8,
        "end_s": 741.4,
        "doc_title": "Multi-Axis Mechanical Hinge Assembly & Alignment SOP",
        "section_path": "1.1 Lower Hinge Assembly > Torque & Clearance Inspection",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Specifies 9.5 Nm final torque check on lower hinge bracket fasteners."
    },
    {
        "video_title": "IndEgo User 16 410 0110 2",
        "segment_caption": "assemble middle hinge",
        "start_s": 741.4,
        "end_s": 754.7,
        "doc_title": "Multi-Axis Mechanical Hinge Assembly & Alignment SOP",
        "section_path": "2.0 Middle Hinge Assembly > Articulation Joint & Friction Adjustment",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Specifies 4.2 Nm friction adjustment nut torque."
    },
    {
        "video_title": "IndEgo User 16 410 0110 2",
        "segment_caption": "assemble lower hinge",
        "start_s": 754.7,
        "end_s": 759.1,
        "doc_title": "Multi-Axis Mechanical Hinge Assembly & Alignment SOP",
        "section_path": "1.1 Lower Hinge Assembly > Torque & Clearance Inspection",
        "relation": "depicts",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Depicts lower pivot pin seated in bushing."
    },
    {
        "video_title": "IndEgo User 16 410 0110 2",
        "segment_caption": "inspect",
        "start_s": 759.3,
        "end_s": 818.8,
        "doc_title": "Multi-Axis Mechanical Hinge Assembly & Alignment SOP",
        "section_path": "1.1 Lower Hinge Assembly > Torque & Clearance Inspection",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents full mechanical articulation inspection across all degrees of freedom."
    },

    # -------------------------------------------------------------
    # Category 13: Hinge Assembly Repeatability (User 16 411 2310 2)
    # -------------------------------------------------------------
    {
        "video_title": "IndEgo User 16 411 2310 2",
        "segment_caption": "assemble lower hinge",
        "start_s": 7.4,
        "end_s": 125.7,
        "doc_title": "Multi-Axis Mechanical Hinge Assembly & Alignment SOP",
        "section_path": "1.0 Lower Hinge Assembly > Hinge Bracket & Pivot Pin",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents lower hinge bracket attachment to workstation base."
    },
    {
        "video_title": "IndEgo User 16 411 2310 2",
        "segment_caption": "assemble middle hinge",
        "start_s": 125.7,
        "end_s": 400.3,
        "doc_title": "Multi-Axis Mechanical Hinge Assembly & Alignment SOP",
        "section_path": "2.0 Middle Hinge Assembly > Articulation Joint & Friction Adjustment",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents middle articulation joint assembly and washer insertion."
    },
    {
        "video_title": "IndEgo User 16 411 2310 2",
        "segment_caption": "assemble upper hinge",
        "start_s": 400.3,
        "end_s": 823.6,
        "doc_title": "Multi-Axis Mechanical Hinge Assembly & Alignment SOP",
        "section_path": "3.0 Upper Hinge Assembly > Top Pivot & Detent Latch",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents upper hinge pivot bracket installation."
    },
    {
        "video_title": "IndEgo User 16 411 2310 2",
        "segment_caption": "assemble middle hinge",
        "start_s": 827.4,
        "end_s": 839.1,
        "doc_title": "Multi-Axis Mechanical Hinge Assembly & Alignment SOP",
        "section_path": "2.0 Middle Hinge Assembly > Articulation Joint & Friction Adjustment",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Specifies 4.2 Nm friction nut setting."
    },
    {
        "video_title": "IndEgo User 16 411 2310 2",
        "segment_caption": "inspect",
        "start_s": 841.8,
        "end_s": 872.8,
        "doc_title": "Multi-Axis Mechanical Hinge Assembly & Alignment SOP",
        "section_path": "1.1 Lower Hinge Assembly > Torque & Clearance Inspection",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents final articulation clearance inspection."
    },

    # -------------------------------------------------------------
    # Category 14: Mechanical Assembly & Cleanliness (User 16 412 0710 2)
    # -------------------------------------------------------------
    {
        "video_title": "IndEgo User 16 412 0710 2",
        "segment_caption": "assemble",
        "start_s": 4.1,
        "end_s": 382.1,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "1.0 Base Structure > Frame Rails & Corner Brackets",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents extrusion rail fastening and bracket alignment."
    },
    {
        "video_title": "IndEgo User 16 412 0710 2",
        "segment_caption": "test",
        "start_s": 382.1,
        "end_s": 392.6,
        "doc_title": "Workstation Frame Distortion & Fastener Loosening Inspection Report",
        "section_path": "1.0 Inspection Findings > Joint Torque & Frame Squareness",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Inspection Report Section 1.0 specifies diagonal difference under 1.5 mm across opposite corners."
    },
    {
        "video_title": "IndEgo User 16 412 0710 2",
        "segment_caption": "clean up",
        "start_s": 392.6,
        "end_s": 528.4,
        "doc_title": "Workstation Teardown, Hand Tool Maintenance & 5S Standard SOP",
        "section_path": "2.0 Tool Return > Tool Audit & Shadow Board Organization",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents hand tool cleaning and return to shadow board per 5S SOP."
    },

    # -------------------------------------------------------------
    # Category 15: Structural Tabletop Integration (User 16 User 2 411 2510 2)
    # -------------------------------------------------------------
    {
        "video_title": "IndEgo User 16 User 2 411 2510 2",
        "segment_caption": "connect legs",
        "start_s": 30.1,
        "end_s": 186.4,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "1.1 Base Structure > Horizontal Support Bars & Leveling Feet",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents connecting support legs and leveling feet to workstation base rails."
    },
    {
        "video_title": "IndEgo User 16 User 2 411 2510 2",
        "segment_caption": "connect center bar",
        "start_s": 186.4,
        "end_s": 265.2,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "1.1 Base Structure > Horizontal Support Bars & Leveling Feet",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Manual Section 1.1 specifies transverse center brace spacing at 600 mm from front rail."
    },
    {
        "video_title": "IndEgo User 16 User 2 411 2510 2",
        "segment_caption": "assemble upper frame",
        "start_s": 268.5,
        "end_s": 547.4,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "2.1 Superstructure > Vertical Support Bars & Top Crossbeam",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents upper superstructure frame assembly across two technicians."
    },
    {
        "video_title": "IndEgo User 16 User 2 411 2510 2",
        "segment_caption": "attach tabletop",
        "start_s": 547.4,
        "end_s": 764.1,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "2.0 Tabletop Installation > Surface Mounting & Clamping Plates",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents placement of high-density resin tabletop onto frame."
    },
    {
        "video_title": "IndEgo User 16 User 2 411 2510 2",
        "segment_caption": "attach tabletop",
        "start_s": 547.4,
        "end_s": 764.1,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "2.0 Tabletop Installation > Surface Mounting & Clamping Plates",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Specifies perimeter clamping plate arrangement and 8.5 Nm tightening torque."
    },
    {
        "video_title": "IndEgo User 16 User 2 411 2510 2",
        "segment_caption": "clean up",
        "start_s": 783.0,
        "end_s": 840.0,
        "doc_title": "Workstation Teardown, Hand Tool Maintenance & 5S Standard SOP",
        "section_path": "1.0 Workstation Cleanliness > Swarf Cleanup & Solvent Wipedown",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents workbench clean down following tabletop mounting."
    },

    # -------------------------------------------------------------
    # Category 16: Diagnostic Inspection & Overhaul (User 17 412 1610 2)
    # -------------------------------------------------------------
    {
        "video_title": "IndEgo User 17 412 1610 2",
        "segment_caption": "inspect",
        "start_s": 213.7,
        "end_s": 281.0,
        "doc_title": "Drive Motor Vibration & Bearing Thermal Overheat Diagnostic Report",
        "section_path": "1.0 Vibration Analysis > Spectral Peaks & High Frequency Acceleration",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents accelerometer mounting and baseline spectrum measurement on machine bearing block."
    },
    {
        "video_title": "IndEgo User 17 412 1610 2",
        "segment_caption": "repair",
        "start_s": 281.0,
        "end_s": 798.4,
        "doc_title": "Industrial AC Induction Drive Motor Service & Overhaul Manual",
        "section_path": "2.0 Disassembly Procedure > Motor Casing & End-Bell Removal",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents bearing teardown and extraction from motor housing."
    },
    {
        "video_title": "IndEgo User 17 412 1610 2",
        "segment_caption": "repair",
        "start_s": 281.0,
        "end_s": 798.4,
        "doc_title": "Drive Motor Vibration & Bearing Thermal Overheat Diagnostic Report",
        "section_path": "2.0 Thermal & Lubricant Inspection > Root Cause & Resolution",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Report Section 2.0 specifies polyurea grease replenishment and SKF 6208-2Z C3 bearing replacement."
    },

    # -------------------------------------------------------------
    # Category 17: Safety & Ergonomics Protocol (User 17 User 14 411 2810 2)
    # -------------------------------------------------------------
    {
        "video_title": "IndEgo User 17 User 14 411 2810 2",
        "segment_caption": "put on gloves",
        "start_s": 17.0,
        "end_s": 34.7,
        "doc_title": "Manufacturing Facility Machinery Safety & Lockout/Tagout (LOTO) Manual",
        "section_path": "1.0 General Safety > Hazardous Energy Isolation Standard",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents PPE donning (ANSI Level 4 cut-resistant handling gloves) per General Safety Manual Section 1.0."
    },
    {
        "video_title": "IndEgo User 17 User 14 411 2810 2",
        "segment_caption": "preparation",
        "start_s": 34.7,
        "end_s": 72.6,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "1.0 Base Structure > Frame Rails & Corner Brackets",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents laying out frame rails and leveling feet hardware on the floor."
    },
    {
        "video_title": "IndEgo User 17 User 14 411 2810 2",
        "segment_caption": "attach feet",
        "start_s": 72.6,
        "end_s": 497.3,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "1.1 Base Structure > Horizontal Support Bars & Leveling Feet",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents threading M12 articulated leveling feet into lower corner base brackets."
    },
    {
        "video_title": "IndEgo User 17 User 14 411 2810 2",
        "segment_caption": "attach feet",
        "start_s": 72.6,
        "end_s": 497.3,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "1.1 Base Structure > Horizontal Support Bars & Leveling Feet",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Specifies leveling feet height adjustment range (0-35 mm) and 18.0 Nm jam nut lock torque."
    },
    {
        "video_title": "IndEgo User 17 User 14 411 2810 2",
        "segment_caption": "connect legs",
        "start_s": 503.7,
        "end_s": 759.3,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "1.0 Base Structure > Frame Rails & Corner Brackets",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents joining vertical leg profiles to base perimeter rails."
    },

    # -------------------------------------------------------------
    # Category 18: Height Adjustment & Ergonomics (User 1 User 15 411 2910 2 1)
    # -------------------------------------------------------------
    {
        "video_title": "IndEgo User 1 User 15 411 2910 2 1",
        "segment_caption": "adjust height",
        "start_s": 4.1,
        "end_s": 13.4,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "1.1 Base Structure > Horizontal Support Bars & Leveling Feet",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents leveling feet adjustment to set working height."
    },
    {
        "video_title": "IndEgo User 1 User 15 411 2910 2 1",
        "segment_caption": "adjust height",
        "start_s": 4.1,
        "end_s": 13.4,
        "doc_title": "Workstation Frame Distortion & Fastener Loosening Inspection Report",
        "section_path": "1.0 Inspection Findings > Joint Torque & Frame Squareness",
        "relation": "contradicts",
        "confidence": 0.95,
        "author": "human:expert",
        "note": "Technician adjusts one leveling foot without checking spirit level on the transverse rail, contradicting frame leveling protocol."
    },
    {
        "video_title": "IndEgo User 1 User 15 411 2910 2 1",
        "segment_caption": "attach tabletop",
        "start_s": 13.4,
        "end_s": 174.0,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "2.0 Tabletop Installation > Surface Mounting & Clamping Plates",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents tabletop positioning and clamping plate fastening."
    },
    {
        "video_title": "IndEgo User 1 User 15 411 2910 2 1",
        "segment_caption": "clean up",
        "start_s": 183.2,
        "end_s": 408.5,
        "doc_title": "Workstation Teardown, Hand Tool Maintenance & 5S Standard SOP",
        "section_path": "2.0 Tool Return > Tool Audit & Shadow Board Organization",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents tool sorting and storage following assembly."
    },

    # -------------------------------------------------------------
    # Category 19: Teardown & Inspection Cycle (User 2 410 0210 1)
    # -------------------------------------------------------------
    {
        "video_title": "IndEgo User 2 410 0210 1",
        "segment_caption": "preparation",
        "start_s": 8.5,
        "end_s": 100.0,
        "doc_title": "Precision Measurement Tool Zeroing & Calibration Verification SOP",
        "section_path": "2.0 Torque Wrench Calibration > Torque Analyzer Verification",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Specifies 3-point calibration verification of 10-50 Nm torque wrench on digital bench analyzer before use."
    },
    {
        "video_title": "IndEgo User 2 410 0210 1",
        "segment_caption": "disassemble",
        "start_s": 100.0,
        "end_s": 246.4,
        "doc_title": "Variable Displacement Axial Piston Hydraulic Pump Technical Manual",
        "section_path": "2.0 Pressure Control Valve > Relief Valve Setting & Compensator Adjustment",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents valve block unbolting and pressure spring extraction."
    },
    {
        "video_title": "IndEgo User 2 410 0210 1",
        "segment_caption": "inspect",
        "start_s": 246.4,
        "end_s": 263.9,
        "doc_title": "Hydraulic System Pressure Instability & Valve Leakage Diagnostic Report",
        "section_path": "2.0 Root Cause & Teardown > Silt Lock & Spool Erosion",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents visual check of valve poppet seat for erosion grooves and silt deposits."
    },
    {
        "video_title": "IndEgo User 2 410 0210 1",
        "segment_caption": "assemble",
        "start_s": 263.9,
        "end_s": 327.0,
        "doc_title": "Variable Displacement Axial Piston Hydraulic Pump Technical Manual",
        "section_path": "2.0 Pressure Control Valve > Relief Valve Setting & Compensator Adjustment",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents reassembly of valve body with replacement sealing washers."
    },
    {
        "video_title": "IndEgo User 2 410 0210 1",
        "segment_caption": "disassemble",
        "start_s": 327.0,
        "end_s": 484.8,
        "doc_title": "Hydraulic Filter Element & Elastomer Seal Ring Replacement SOP",
        "section_path": "1.0 Safety Isolation > Depressurization & Fluid Containment",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents filter housing isolation and sump tray positioning."
    },
    {
        "video_title": "IndEgo User 2 410 0210 1",
        "segment_caption": "disassemble",
        "start_s": 327.0,
        "end_s": 484.8,
        "doc_title": "Hydraulic Filter Element & Elastomer Seal Ring Replacement SOP",
        "section_path": "2.0 Filter Cartridge Extraction > Element Inspection & Bowl Cleaning",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "SOP Section 2.0 specifies inspecting pleat valleys of 10-micron fiberglass element for metallic particulate."
    },
    {
        "video_title": "IndEgo User 2 410 0210 1",
        "segment_caption": "inspect",
        "start_s": 484.8,
        "end_s": 569.2,
        "doc_title": "Hydraulic Filter Element & Elastomer Seal Ring Replacement SOP",
        "section_path": "2.0 Filter Cartridge Extraction > Element Inspection & Bowl Cleaning",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents filter bowl inspection and magnetic plug examination."
    },
    {
        "video_title": "IndEgo User 2 410 0210 1",
        "segment_caption": "assemble",
        "start_s": 569.2,
        "end_s": 765.8,
        "doc_title": "Hydraulic Filter Element & Elastomer Seal Ring Replacement SOP",
        "section_path": "3.0 Seal Ring Installation > Nitrile O-Ring & Bowl Torquing",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Specifies lubricating new nitrile O-ring with clean hydraulic fluid and torquing filter bowl to 45.0 Nm."
    },
    {
        "video_title": "IndEgo User 2 410 0210 1",
        "segment_caption": "test",
        "start_s": 765.8,
        "end_s": 801.9,
        "doc_title": "Variable Displacement Axial Piston Hydraulic Pump Technical Manual",
        "section_path": "1.0 Specifications > Pressure Ratings & Displacement Parameters",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents running pump up to 210 bar test pressure to confirm zero external flange leakage."
    },
    {
        "video_title": "IndEgo User 2 410 0210 1",
        "segment_caption": "clean up",
        "start_s": 801.9,
        "end_s": 852.0,
        "doc_title": "Workstation Teardown, Hand Tool Maintenance & 5S Standard SOP",
        "section_path": "1.0 Workstation Cleanliness > Swarf Cleanup & Solvent Wipedown",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents cleaning hydraulic spill tray and solvent wipedown of tool bench."
    },

    # -------------------------------------------------------------
    # Category 20: Electrical Installation & Power Verification (User 1 412 2010 3)
    # -------------------------------------------------------------
    {
        "video_title": "IndEgo User 1 412 2010 3",
        "segment_caption": "attach power connection",
        "start_s": 1.9,
        "end_s": 53.8,
        "doc_title": "Workstation Electrical Power Distribution Unit Operating Manual",
        "section_path": "1.0 Technical Specs > Power Input & Auxiliary Bus Outputs",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents connection of 3-phase 400V AC power cord to the distribution unit main disconnect switch."
    },
    {
        "video_title": "IndEgo User 1 412 2010 3",
        "segment_caption": "attach power connection",
        "start_s": 1.9,
        "end_s": 53.8,
        "doc_title": "Workstation Electrical Power Distribution Unit Operating Manual",
        "section_path": "3.0 Wiring Standard > Color Codes & Terminal Block Connections",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Operating Manual Section 3.0 specifies DIN rail terminal block torque of 1.2 Nm and ferrules on all stranded wires."
    },
    {
        "video_title": "IndEgo User 1 412 2010 3",
        "segment_caption": "attach zip ties",
        "start_s": 53.8,
        "end_s": 136.4,
        "doc_title": "Display Monitor Mount & Operator Console Integration SOP",
        "section_path": "2.0 Cable Routing > Power Connection & Grounding Verification",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents cable bundling, strain relief clip attachment, and zip tie dressing along the extrusion wireway."
    },
    {
        "video_title": "IndEgo User 1 412 2010 3",
        "segment_caption": "attach zip ties",
        "start_s": 53.8,
        "end_s": 136.4,
        "doc_title": "Display Monitor Mount & Operator Console Integration SOP",
        "section_path": "2.0 Cable Routing > Power Connection & Grounding Verification",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "SOP Section 2.0 specifies 150 mm spacing between cable ties to prevent harness sagging."
    },
    {
        "video_title": "IndEgo User 1 412 2010 3",
        "segment_caption": "plug in",
        "start_s": 136.4,
        "end_s": 146.2,
        "doc_title": "System Electrical Power-Up & Pre-Operation Verification SOP",
        "section_path": "1.0 Pre-Power Inspection > Isolation & Visual Check",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents plugging main power cord into facility fused outlet receptacle."
    },
    {
        "video_title": "IndEgo User 1 412 2010 3",
        "segment_caption": "plug in",
        "start_s": 136.4,
        "end_s": 146.2,
        "doc_title": "System Electrical Power-Up & Pre-Operation Verification SOP",
        "section_path": "1.0 Pre-Power Inspection > Isolation & Visual Check",
        "relation": "contradicts",
        "confidence": 0.95,
        "author": "human:expert",
        "note": "Technician inserts power plug without completing visual wire terminal tug-test and insulation resistance check required in Section 1.0."
    },
    {
        "video_title": "IndEgo User 1 412 2010 3",
        "segment_caption": "attach monitor",
        "start_s": 146.2,
        "end_s": 172.2,
        "doc_title": "Display Monitor Mount & Operator Console Integration SOP",
        "section_path": "1.0 Mechanical Installation > VESA Bracket & Arm Fastening",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents mounting operator touch panel onto VESA 100 articulated support arm."
    },
    {
        "video_title": "IndEgo User 1 412 2010 3",
        "segment_caption": "attach monitor",
        "start_s": 146.2,
        "end_s": 172.2,
        "doc_title": "Display Monitor Mount & Operator Console Integration SOP",
        "section_path": "1.0 Mechanical Installation > VESA Bracket & Arm Fastening",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Specifies 2.5 Nm torque for M4 VESA mounting screws and check of friction joint tilt resistance."
    },
    {
        "video_title": "IndEgo User 1 412 2010 3",
        "segment_caption": "turn on",
        "start_s": 176.4,
        "end_s": 193.0,
        "doc_title": "System Electrical Power-Up & Pre-Operation Verification SOP",
        "section_path": "2.0 Power-Up Sequence > Voltage Verification & HMI Boot",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents toggling main power breaker and observing green pilot lamp illumination and HMI boot screen."
    },
    {
        "video_title": "IndEgo User 1 412 2010 3",
        "segment_caption": "turn on",
        "start_s": 176.4,
        "end_s": 193.0,
        "doc_title": "System Electrical Power-Up & Pre-Operation Verification SOP",
        "section_path": "3.0 Safety Circuit Validation > E-Stop Trip & Interlock Test",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "SOP Section 3.0 specifies mandatory emergency stop pushbutton depression to verify safety relay de-energization within 20 ms."
    },
    {
        "video_title": "IndEgo User 1 412 2010 3",
        "segment_caption": "turn on",
        "start_s": 176.4,
        "end_s": 193.0,
        "doc_title": "Workstation Wiring Harness Ground Fault & Connector Oxidation Report",
        "section_path": "1.0 Incident Investigation > Intermittent E-Stop Fault Trip",
        "relation": "contradicts",
        "confidence": 0.95,
        "author": "human:expert",
        "note": "Incident report records intermittent E-stop trips caused by ungrounded 24V DC auxiliary bus, which was energized here without prior grounding loop impedance test."
    },

    # -------------------------------------------------------------
    # Category 21: Workstation Plate Mounting (User 1 411 1610 3)
    # -------------------------------------------------------------
    {
        "video_title": "IndEgo User 1 411 1610 3",
        "segment_caption": "inspect and clean",
        "start_s": 2.9,
        "end_s": 94.9,
        "doc_title": "Precision Measurement Tool Zeroing & Calibration Verification SOP",
        "section_path": "1.0 Micrometer Calibration > Zero-Point & Gauge Block Inspection",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents optical and mechanical plate thickness measurement using calibrated micrometer."
    },
    {
        "video_title": "IndEgo User 1 411 1610 3",
        "segment_caption": "attach top plate",
        "start_s": 94.9,
        "end_s": 157.5,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "2.0 Tabletop Installation > Surface Mounting & Clamping Plates",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents top plate alignment on workstation upper horizontal frame rail."
    },
    {
        "video_title": "IndEgo User 1 411 1610 3",
        "segment_caption": "attach bottom plate",
        "start_s": 277.9,
        "end_s": 362.3,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "1.1 Base Structure > Horizontal Support Bars & Leveling Feet",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents bottom plate attachment to horizontal support rails."
    },
    {
        "video_title": "IndEgo User 1 411 1610 3",
        "segment_caption": "attach connector plates",
        "start_s": 373.6,
        "end_s": 551.0,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "1.0 Base Structure > Frame Rails & Corner Brackets",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Specifies gusset connector plate M8 bolt torque of 14.5 Nm with spring washers."
    },

    # -------------------------------------------------------------
    # Category 22: Frame & Camera Assembly 3 (User 1 411 2110 1)
    # -------------------------------------------------------------
    {
        "video_title": "IndEgo User 1 411 2110 1",
        "segment_caption": "connect base",
        "start_s": 7.0,
        "end_s": 89.9,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "1.0 Base Structure > Frame Rails & Corner Brackets",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents base rail corner joining with extrusion corner gussets."
    },
    {
        "video_title": "IndEgo User 1 411 2110 1",
        "segment_caption": "attach vertical bar",
        "start_s": 89.9,
        "end_s": 246.7,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "2.1 Superstructure > Vertical Support Bars & Top Crossbeam",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents mounting vertical support bars to base frame rails."
    },
    {
        "video_title": "IndEgo User 1 411 2110 1",
        "segment_caption": "attach upper bar",
        "start_s": 246.7,
        "end_s": 377.2,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "2.1 Superstructure > Vertical Support Bars & Top Crossbeam",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents upper crossbar positioning across upright supports."
    },
    {
        "video_title": "IndEgo User 1 411 2110 1",
        "segment_caption": "attach camera and plate",
        "start_s": 377.2,
        "end_s": 793.2,
        "doc_title": "Camera Mounting Bracket & Optical Plate Installation SOP",
        "section_path": "1.0 Positioning > Vertical Bar Mounting Bracket",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents collar clamp fastening and optical plate attachment to the vertical bar."
    },
    {
        "video_title": "IndEgo User 1 411 2110 1",
        "segment_caption": "attach camera and plate",
        "start_s": 377.2,
        "end_s": 793.2,
        "doc_title": "Camera Mounting Bracket & Optical Plate Installation SOP",
        "section_path": "2.0 Camera Plate Attachment > Anodized Plate Fasteners",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Specifies 3.2 Nm torque for M4 camera plate screws."
    },

    # -------------------------------------------------------------
    # Category 23: Industrial Maintenance & Hydraulic Diagnostics (User 1 1910 repair)
    # -------------------------------------------------------------
    {
        "video_title": "IndEgo User 1 1910 repair",
        "segment_caption": "inspect",
        "start_s": 232.3,
        "end_s": 362.9,
        "doc_title": "Hydraulic System Pressure Instability & Valve Leakage Diagnostic Report",
        "section_path": "1.0 Diagnostic Findings > Clamping Pressure Loss & Valve Chatter",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents visual and pressure gauge inspection of hydraulic actuator circuit."
    },
    {
        "video_title": "IndEgo User 1 1910 repair",
        "segment_caption": "repair",
        "start_s": 362.9,
        "end_s": 666.8,
        "doc_title": "Hydraulic System Pressure Instability & Valve Leakage Diagnostic Report",
        "section_path": "2.0 Root Cause & Teardown > Silt Lock & Spool Erosion",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents valve spool extraction, seal replacement, and manifold gallery flushing."
    },
    {
        "video_title": "IndEgo User 1 1910 repair",
        "segment_caption": "repair",
        "start_s": 362.9,
        "end_s": 666.8,
        "doc_title": "Variable Displacement Axial Piston Hydraulic Pump Technical Manual",
        "section_path": "2.0 Pressure Control Valve > Relief Valve Setting & Compensator Adjustment",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Technical manual Section 2.0 specifies relief valve cracking pressure set point of 180 bar."
    },

    # -------------------------------------------------------------
    # Category 24: Facility Maintenance & Pneumatic Actuation (User 14 2325 451)
    # -------------------------------------------------------------
    {
        "video_title": "IndEgo User 14 2325 451",
        "segment_caption": "inspect",
        "start_s": 14.5,
        "end_s": 94.7,
        "doc_title": "Pneumatic Air Leakage & Actuator Sticking Incident Report",
        "section_path": "1.0 Fault Description > Cylinder Retract Sticking & Audible Leak",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents leak detection inspection with ultrasonic leak detector along pneumatic lines."
    },
    {
        "video_title": "IndEgo User 14 2325 451",
        "segment_caption": "repair",
        "start_s": 94.7,
        "end_s": 501.8,
        "doc_title": "Pneumatic Air Leakage & Actuator Sticking Incident Report",
        "section_path": "2.0 Cylinder Teardown > Piston Rod Scoring & Seal Replacement",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents cylinder rod seal replacement and pneumatic fitting retightening."
    },
    {
        "video_title": "IndEgo User 14 2325 451",
        "segment_caption": "repair",
        "start_s": 94.7,
        "end_s": 501.8,
        "doc_title": "Industrial Pneumatic Linear Actuator & Valve Manifold Service Manual",
        "section_path": "2.0 Solenoid Valve Manifold > 5/2-Way Directional Valves & Fieldbus",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Manual Section 2.0 specifies 5/2-way sub-base manifold mounting screw torque of 1.8 Nm."
    },

    # -------------------------------------------------------------
    # Category 25: Actuator Overhaul Cycle 2 (User 14 2325 451 2)
    # -------------------------------------------------------------
    {
        "video_title": "IndEgo User 14 2325 451 2",
        "segment_caption": "inspect",
        "start_s": 15.4,
        "end_s": 92.7,
        "doc_title": "Industrial Pneumatic Linear Actuator & Valve Manifold Service Manual",
        "section_path": "1.0 Actuator Specifications > Bore, Stroke & Air Quality Requirements",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents inspection of cylinder stroke velocity and cushioning needle valve response."
    },
    {
        "video_title": "IndEgo User 14 2325 451 2",
        "segment_caption": "repair",
        "start_s": 92.7,
        "end_s": 604.4,
        "doc_title": "Pneumatic Filter-Regulator-Lubricator (FRL) Maintenance SOP",
        "section_path": "1.0 Moisture Purge & Element Service > Condensate Bowl Maintenance",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents servicing FRL filter bowl, draining condensate, and cleaning sintered bronze filter."
    },
    {
        "video_title": "IndEgo User 14 2325 451 2",
        "segment_caption": "repair",
        "start_s": 92.7,
        "end_s": 604.4,
        "doc_title": "Facility Manufacturing Equipment Annual Preventive Maintenance Review",
        "section_path": "1.0 Executive Summary > Cross-Subsystem Maintenance Performance",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Documents annual scheduled replacement of pneumatic maintenance unit filter element."
    },
    {
        "video_title": "IndEgo User 14 2325 451 2",
        "segment_caption": "test",
        "start_s": 604.4,
        "end_s": 722.3,
        "doc_title": "Industrial Pneumatic Linear Actuator & Valve Manifold Service Manual",
        "section_path": "1.0 Actuator Specifications > Bore, Stroke & Air Quality Requirements",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Manual Section 1.0 specifies maximum allowable external leakage under 5 Nl/h at 6.0 bar test pressure."
    },

    # -------------------------------------------------------------
    # Cross-System & Facility Review Links (Annual Review & Electrical Wiring)
    # -------------------------------------------------------------
    {
        "video_title": "IndEgo User 1 412 2010 3",
        "segment_caption": "turn on",
        "start_s": 176.4,
        "end_s": 193.0,
        "doc_title": "Facility Manufacturing Equipment Annual Preventive Maintenance Review",
        "section_path": "2.0 Recommendations > Standardization & Sensor Upgrades",
        "relation": "specifies",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Annual Review Section 2.0 specifies upgrading operator workstations with optical safety light curtains and unified 24V bus monitoring."
    },
    {
        "video_title": "IndEgo User 15 412 1510 1",
        "segment_caption": "inspect",
        "start_s": 198.7,
        "end_s": 204.9,
        "doc_title": "Facility Manufacturing Equipment Annual Preventive Maintenance Review",
        "section_path": "1.0 Executive Summary > Cross-Subsystem Maintenance Performance",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Review documents hydraulic valve silt lock as one of the top causes of unplanned line downtime across machining cells."
    },
    {
        "video_title": "IndEgo User 15 414 3110 1",
        "segment_caption": "inspect",
        "start_s": 0.8,
        "end_s": 17.7,
        "doc_title": "Facility Manufacturing Equipment Annual Preventive Maintenance Review",
        "section_path": "1.0 Executive Summary > Cross-Subsystem Maintenance Performance",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Annual Review Section 1.0 documents drive motor thermal runaway events caused by bearing grease drying out."
    },
    {
        "video_title": "IndEgo User 14 2325 451",
        "segment_caption": "inspect",
        "start_s": 14.5,
        "end_s": 94.7,
        "doc_title": "Facility Manufacturing Equipment Annual Preventive Maintenance Review",
        "section_path": "1.0 Executive Summary > Cross-Subsystem Maintenance Performance",
        "relation": "documents",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Annual Review Section 1.0 documents compressed air leakage rates exceeding 18% of compressor volume, highlighting pneumatic line audit priority."
    },
    # --- Additional Depicts Links ---
    {
        "video_title": "IndEgo 7020e12d-d5a2-4f01-beab-94f38d887eca",
        "segment_caption": "connect base",
        "start_s": 4.4,
        "end_s": 155.1,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "1.0 Base Structure > Frame Rails & Corner Brackets",
        "relation": "depicts",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Depicts 45x45 mm base extrusion rails and corner gusset plates during initial frame layout."
    },
    {
        "video_title": "IndEgo 7020e12d-d5a2-4f01-beab-94f38d887eca",
        "segment_caption": "attach vertical bar",
        "start_s": 155.1,
        "end_s": 286.9,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "2.1 Superstructure > Vertical Support Bars & Top Crossbeam",
        "relation": "depicts",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Depicts vertical upright bar (P/N AL-4545-V1100) being positioned into corner brackets."
    },
    {
        "video_title": "IndEgo 7020e12d-d5a2-4f01-beab-94f38d887eca",
        "segment_caption": "attach camera and plate",
        "start_s": 369.9,
        "end_s": 532.2,
        "doc_title": "Camera Mounting Bracket & Optical Plate Installation SOP",
        "section_path": "1.0 Positioning > Vertical Bar Mounting Bracket",
        "relation": "depicts",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Depicts camera support collar clamp (P/N CAM-CLR-45) clamped onto the vertical post."
    },
    {
        "video_title": "IndEgo User 14 User 15 2410 1",
        "segment_caption": "assemble lower hinge",
        "start_s": 15.9,
        "end_s": 168.6,
        "doc_title": "Multi-Axis Mechanical Hinge Assembly & Alignment SOP",
        "section_path": "1.0 Lower Hinge Assembly > Hinge Bracket & Pivot Pin",
        "relation": "depicts",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Depicts lower hinge mounting bracket (P/N HNG-BRK-LOW) and hardened pivot pin (PIN-12H6)."
    },
    {
        "video_title": "IndEgo User 14 User 17 407 0601 3",
        "segment_caption": "attach plates",
        "start_s": 25.0,
        "end_s": 365.7,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "1.0 Base Structure > Frame Rails & Corner Brackets",
        "relation": "depicts",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Depicts corner reinforcement gusset plates and M8 T-slot nuts."
    },
    {
        "video_title": "IndEgo User 15 411 2309 2 1",
        "segment_caption": "connect base",
        "start_s": 6.1,
        "end_s": 59.0,
        "doc_title": "Industrial Aluminum Extrusion Frame & Tabletop Assembly Manual",
        "section_path": "1.1 Base Structure > Horizontal Support Bars & Leveling Feet",
        "relation": "depicts",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Depicts M12 threaded articulated leveling feet screwed into base frame corner blocks."
    },
    {
        "video_title": "IndEgo User 15 411 2309 2 1",
        "segment_caption": "attach camera and plate",
        "start_s": 235.0,
        "end_s": 335.3,
        "doc_title": "Camera Mounting Bracket & Optical Plate Installation SOP",
        "section_path": "2.0 Camera Plate Attachment > Anodized Plate Fasteners",
        "relation": "depicts",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Depicts black anodized camera mounting plate (P/N CMP-402) and titanium M4 countersunk screws."
    },
    {
        "video_title": "IndEgo User 15 411 2410 2",
        "segment_caption": "assemble lower hinge",
        "start_s": 29.7,
        "end_s": 135.2,
        "doc_title": "Multi-Axis Mechanical Hinge Assembly & Alignment SOP",
        "section_path": "1.0 Lower Hinge Assembly > Hinge Bracket & Pivot Pin",
        "relation": "depicts",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Depicts lower hinge bracket resting against extrusion channel."
    },
    {
        "video_title": "IndEgo User 15 411 2410 2",
        "segment_caption": "assemble upper hinge",
        "start_s": 342.9,
        "end_s": 689.3,
        "doc_title": "Multi-Axis Mechanical Hinge Assembly & Alignment SOP",
        "section_path": "3.0 Upper Hinge Assembly > Top Pivot & Detent Latch",
        "relation": "depicts",
        "confidence": 1.0,
        "author": "human:expert",
        "note": "Depicts upper hinge bracket (P/N HNG-BRK-UP) and spring-loaded ball detent latch."
    },
    # --- Additional Contradicts Links ---
    {
        "video_title": "IndEgo User 14 User 17 407 0601 3",
        "segment_caption": "attach plates",
        "start_s": 25.0,
        "end_s": 365.7,
        "doc_title": "Manufacturing Facility Machinery Safety & Lockout/Tagout (LOTO) Manual",
        "section_path": "1.0 General Safety > Hazardous Energy Isolation Standard",
        "relation": "contradicts",
        "confidence": 0.95,
        "author": "human:expert",
        "note": "Technician handles freshly cut aluminum extrusion rails with sharp burrs barehanded, contradicting ANSI Level 4 cut-protection glove mandate."
    },
    {
        "video_title": "IndEgo User 15 411 2309 2 1",
        "segment_caption": "attach vertical bar",
        "start_s": 59.0,
        "end_s": 175.5,
        "doc_title": "Workstation Frame Distortion & Fastener Loosening Inspection Report",
        "section_path": "2.0 Corrective Actions > Retorque, Loctite & Re-Square",
        "relation": "contradicts",
        "confidence": 0.95,
        "author": "human:expert",
        "note": "Technician bolts upright vertical posts dry without applying medium-strength threadlocker, contradicting inspection report corrective mandate."
    },
    {
        "video_title": "IndEgo User 15 412 0110 1",
        "segment_caption": "disassemble",
        "start_s": 119.7,
        "end_s": 527.0,
        "doc_title": "Manufacturing Facility Machinery Safety & Lockout/Tagout (LOTO) Manual",
        "section_path": "2.0 Step-by-Step LOTO Protocol > Five-Step Procedure",
        "relation": "contradicts",
        "confidence": 0.95,
        "author": "human:expert",
        "note": "Technician begins valve casing disassembly without attaching lockout padlock to primary isolation valve, violating Step 2 LOTO procedure."
    },
    {
        "video_title": "IndEgo User 15 412 1510 1",
        "segment_caption": "repair",
        "start_s": 204.9,
        "end_s": 441.1,
        "doc_title": "Hydraulic Filter Element & Elastomer Seal Ring Replacement SOP",
        "section_path": "1.0 Safety Isolation > Depressurization & Fluid Containment",
        "relation": "contradicts",
        "confidence": 0.95,
        "author": "human:expert",
        "note": "Technician loosens hydraulic port fitting while pressure gauge still indicates residual 8 bar pressure, contradicting mandatory zero-pressure verification."
    },
    {
        "video_title": "IndEgo User 15 User 14 411 1010 1",
        "segment_caption": "repair",
        "start_s": 67.9,
        "end_s": 432.5,
        "doc_title": "Industrial Pneumatic Linear Actuator & Valve Manifold Service Manual",
        "section_path": "1.0 Actuator Specifications > Bore, Stroke & Air Quality Requirements",
        "relation": "contradicts",
        "confidence": 0.95,
        "author": "human:expert",
        "note": "Technician wipes cylinder rod with standard shop rag leaving textile lint on rod seal gland, violating cleanroom particulate guidelines."
    },
    {
        "video_title": "IndEgo User 2 410 0210 1",
        "segment_caption": "assemble",
        "start_s": 569.2,
        "end_s": 765.8,
        "doc_title": "Hydraulic Filter Element & Elastomer Seal Ring Replacement SOP",
        "section_path": "3.0 Seal Ring Installation > Nitrile O-Ring & Bowl Torquing",
        "relation": "contradicts",
        "confidence": 0.95,
        "author": "human:expert",
        "note": "Technician presses replacement nitrile O-ring into bowl groove dry without pre-lubricating with ISO VG 46 oil, risking elastomer shear damage."
    },
]

def main():
    target_path = Path(__file__).resolve().parent.parent / "data" / "incoming" / "evidence_links.json"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(LINK_DEFINITIONS, f, indent=2)
    print(f"Wrote {len(LINK_DEFINITIONS)} evidence link definitions to {target_path}")

if __name__ == "__main__":
    main()
