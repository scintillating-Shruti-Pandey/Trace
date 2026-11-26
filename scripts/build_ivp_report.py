"""Build the standalone TRACE Image and Video Processing project report.

Uses only Python's standard library to emit a small Open XML Word document.
Run from the repository root with any Python 3 interpreter.
"""

from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "TRACE_IVP_Project_Report.docx"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
XML = "http://www.w3.org/XML/1998/namespace"
ET.register_namespace("w", W)
ET.register_namespace("r", R)


def tag(ns: str, name: str) -> str:
    return f"{{{ns}}}{name}"


def element(parent: ET.Element, ns: str, name: str, attrs: dict[str, str] | None = None) -> ET.Element:
    return ET.SubElement(parent, tag(ns, name), attrs or {})


body = ET.Element(tag(W, "document"))
content = element(body, W, "body")


def paragraph(
    text: str = "",
    *,
    style: str = "Normal",
    bold: bool = False,
    italic: bool = False,
    color: str | None = None,
    size: int | None = None,
    before: int | None = None,
    after: int | None = None,
    page_break: bool = False,
) -> ET.Element:
    p = element(content, W, "p")
    ppr = element(p, W, "pPr")
    element(ppr, W, "pStyle", {tag(W, "val"): style})
    if before is not None or after is not None:
        spacing = {}
        if before is not None:
            spacing[tag(W, "before")] = str(before)
        if after is not None:
            spacing[tag(W, "after")] = str(after)
        element(ppr, W, "spacing", spacing)
    if page_break:
        run = element(p, W, "r")
        element(run, W, "br", {tag(W, "type"): "page"})
    if text:
        run = element(p, W, "r")
        rpr = element(run, W, "rPr")
        if bold:
            element(rpr, W, "b")
        if italic:
            element(rpr, W, "i")
        if color:
            element(rpr, W, "color", {tag(W, "val"): color})
        if size:
            element(rpr, W, "sz", {tag(W, "val"): str(size)})
            element(rpr, W, "szCs", {tag(W, "val"): str(size)})
        t = element(run, W, "t")
        if text[:1].isspace() or text[-1:].isspace():
            t.set(tag(XML, "space"), "preserve")
        t.text = text
    return p


def heading(text: str, level: int = 1) -> None:
    paragraph(text, style=f"Heading{level}")


def bullet(text: str) -> None:
    paragraph(f"•  {text}", style="Normal", after=100)


def table(rows: list[list[str]], widths: list[int], header: bool = True) -> None:
    tbl = element(content, W, "tbl")
    pr = element(tbl, W, "tblPr")
    element(pr, W, "tblW", {tag(W, "w"): "9000", tag(W, "type"): "dxa"})
    borders = element(pr, W, "tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element(borders, W, side, {tag(W, "val"): "single", tag(W, "sz"): "4", tag(W, "color"): "CBD5E1"})
    margins = element(pr, W, "tblCellMar")
    for side, value in (("top", "100"), ("start", "120"), ("bottom", "100"), ("end", "120")):
        element(margins, W, side, {tag(W, "w"): value, tag(W, "type"): "dxa"})
    grid = element(tbl, W, "tblGrid")
    for width in widths:
        element(grid, W, "gridCol", {tag(W, "w"): str(width)})
    for ri, row_values in enumerate(rows):
        tr = element(tbl, W, "tr")
        if header and ri == 0:
            trpr = element(tr, W, "trPr")
            element(trpr, W, "tblHeader")
        for ci, value in enumerate(row_values):
            tc = element(tr, W, "tc")
            tcpr = element(tc, W, "tcPr")
            element(tcpr, W, "tcW", {tag(W, "w"): str(widths[ci]), tag(W, "type"): "dxa"})
            if header and ri == 0:
                element(tcpr, W, "shd", {tag(W, "fill"): "12304A", tag(W, "val"): "clear"})
            p = element(tc, W, "p")
            ppr = element(p, W, "pPr")
            element(ppr, W, "pStyle", {tag(W, "val"): "TableText"})
            run = element(p, W, "r")
            rpr = element(run, W, "rPr")
            if header and ri == 0:
                element(rpr, W, "b")
                element(rpr, W, "color", {tag(W, "val"): "FFFFFF"})
            t = element(run, W, "t")
            t.text = value


paragraph("TRACE  /  IMAGE & VIDEO PROCESSING", style="Eyebrow", color="147D92", bold=True, size=18, after=300)
paragraph("Real-Video Image and\nVideo Processing", style="Title", color="12304A", size=38, after=220)
paragraph("An interactive classical-computer-vision module over the IndEgo manufacturing video dataset", style="Subtitle", color="486581", size=22, after=900)
paragraph("PROJECT REPORT", style="Eyebrow", color="147D92", bold=True, size=15, before=800, after=150)
paragraph("TRACE — Multimodal Manufacturing Intelligence & Video Search", style="Normal", bold=True, size=18, after=110)
paragraph("Prepared 26 November 2026  |  Image and Video Processing presentation", style="Normal", color="627D98", size=15, after=250)
paragraph("Scope note: this report documents the verified real-video IVP demonstration. AI-generated captioning and transcription are described only as prepared, untested extensions.", style="Normal", italic=True, color="52606D", size=13, after=300)
paragraph(page_break=True)

heading("Abstract")
paragraph(
    "TRACE includes an interactive Image and Video Processing (IVP) studio that operates on real frames from the IndEgo manufacturing-video dataset. A user selects a source video and time, views the decoded frame, and runs classical image-processing analyses. For short video windows, the system samples consecutive frames, selects candidate keyframes using inter-frame change, and estimates motion using optical flow. Media decoding and analysis use bounded in-memory buffers; the inspected routes do not save decoded video or frames as dataset files. A live diagnostic on one source frame returned eight technique outputs in 234.9 ms, while one eight-second source interval sampled 16 frames, selected three keyframes, and returned motion visualizations. These are single-case demonstrations, not accuracy benchmarks. Optional local AI captioning and speech transcription code is disabled and has not produced results; no AI-generated caption or transcript is claimed in this report."
)
paragraph("Keywords: image processing, video processing, keyframe extraction, optical flow, OpenCV, IndEgo, manufacturing", style="Normal", italic=True, color="486581", after=240)

heading("1. Project scope")
paragraph(
    "This report presents TRACE from an IVP perspective. The focus is the implemented path from a real remote video to visible frame-level and short-window analyses in the web application. The work demonstrates classical computer-vision operations and an interactive way to inspect their outputs. TRACE's broader retrieval and question-answering system is outside the measured results reported here."
)
paragraph(
    "The target use is exploratory inspection of manufacturing footage: expose color and contrast, edges and local structure, candidate visual features, frame-to-frame changes, and motion. These outputs can help a person inspect a video segment; they do not by themselves identify a defect, certify a process, or establish the meaning of an action."
)

heading("2. Dataset and media provenance")
paragraph(
    "The module uses the Fraunhofer IPK IndEgo dataset, a collection of manufacturing and assembly videos. The application manifest pins the dataset to revision c822468b5e0c9c42ebbf2939d3be936c2b203704 and records the source license as Creative Commons Attribution 4.0 (CC BY 4.0). The manifest lists 25 videos totaling 16,557.88 seconds (approximately 4.60 hours); a live catalogue check reported all 25 entries. These catalogue counts indicate availability in the manifest and do not mean that every video was processed during the IVP demonstration. [1, 2]"
)
paragraph(
    "The media path is remote and range-capable: the browser requests media through TRACE's proxy, and the frame reader decodes selected source times. A live check received HTTP 206 for a 1,024-byte range from a pinned MP4 whose full size was reported as 43,477,513 bytes. The tested frame endpoint returned a real 480-pixel-wide frame at 23.76 seconds as a 233,400-byte PNG, with IndEgo source provenance and Cache-Control: no-store. No complete video was copied into the project for this demonstration. [2]"
)

heading("3. Processing pipeline")
table([
    ["Stage", "Implemented behavior"],
    ["1. Select source", "The IVP page loads the IndEgo catalogue and lets the user choose a video and timestamp."],
    ["2. Read media", "TRACE's media proxy provides source bytes; FFmpeg decodes a bounded set of frames into memory."],
    ["3. Analyze", "OpenCV and NumPy compute spatial image descriptors and transformations; short-window analysis adds keyframe selection and motion."],
    ["4. Present", "The page displays the real source frame, processed outputs, selected keyframes, timestamps, and motion visualizations."],
], [1500, 7500])
paragraph(
    "The interval analyzer caps a request at 90 seconds and 24 sampled frames, and clamps the requested sampling rate to 0.25–4 frames per second. The current experiment used a much shorter eight-second window. Results are returned to the caller; the IVP analysis path is designed to keep decoded media in memory rather than create a local media corpus. [3]"
)

heading("4. Image and video techniques")
table([
    ["Technique", "What the implementation computes"],
    ["Color spaces", "RGB, grayscale, HSV, and CIELAB representations with channel statistics."],
    ["Histograms and contrast", "Per-channel intensity histograms, global grayscale equalization, and CLAHE on the LAB lightness channel."],
    ["Filtering and derivatives", "Gaussian smoothing at multiple kernel sizes, sharpening, emboss filtering, and Laplacian response."],
    ["Edges", "Sobel x/y gradients, magnitude and direction, plus Canny edge maps."],
    ["Morphology", "Thresholding and standard erosion, dilation, opening, closing, gradient, top-hat, and black-hat operations."],
    ["Local features", "SIFT and ORB keypoint/descriptor visualization."],
    ["Shape descriptor", "Histogram of Oriented Gradients (HOG) visualization."],
    ["Keyframes", "Grayscale inter-frame mean absolute difference with a configurable threshold and minimum time gap; selected frames also report edge density and Laplacian-variance sharpness."],
    ["Motion", "Sparse Lucas–Kanade and dense Farneback optical-flow analysis on consecutive frames."],
], [2200, 6800])
paragraph(
    "A single-frame request returns the spatial analyses. The underlying single-frame pipeline also has a translated companion-frame option for illustrating optical flow, but that synthetic flow is omitted from the IVP page. Motion shown for a video interval is computed from actual consecutive source frames, which is the appropriate output to use when discussing observed video motion. [3]"
)

heading("5. Demonstration evidence")
table([
    ["Check", "Observed result", "Interpretation"],
    ["IVP page and endpoints", "HTTP 200 for /ivp; live catalogue, frame, and both analysis endpoints responded.", "Service-level checks passed; browser button interaction was not separately exercised."],
    ["Dataset catalogue", "25 IndEgo videos listed.", "Catalogue availability, not full-corpus processing."],
    ["Real frame", "480 px wide; timestamp 23.76 s; 233,400-byte PNG.", "A real dataset frame was decoded and returned with source/no-store metadata."],
    ["Single-frame analysis", "Eight technique outputs; 234.9 ms on the selected frame.", "One diagnostic request only; not a latency distribution or p95."],
    ["Video-window analysis", "One 8 s interval; 16 sampled source frames; 3 selected keyframes; optical-flow images and motion metrics returned.", "A short illustrative run, not a corpus-wide quality or accuracy evaluation."],
], [1800, 3700, 3500])
paragraph(
    "The values above are the recorded live-check results for the selected example. The report does not infer processing speed for other resolutions, videos, hardware states, or concurrent users. No ground-truth keyframe labels or motion annotations were used to calculate precision, recall, or tracking accuracy. [2]"
)

heading("6. Web demonstration workflow")
bullet("Open the TRACE IVP page at /ivp.")
bullet("Choose an IndEgo video and a timestamp to display a real source frame.")
bullet("Run the single-frame analyses to compare color, contrast, filtering, edges, morphology, keypoints, and HOG outputs.")
bullet("Choose a short time window to view sampled keyframes, their timestamps, and motion visualizations from adjacent source frames.")
paragraph(
    "The standalone page makes the operations inspectable without requiring the user to run the temporary notebook. It is a visual demonstration surface, not a claim that all IVP analysis is performed in real time on a live camera. The service analyzes requested source intervals on demand."
)

heading("7. Limitations and claim boundaries")
bullet("The live IVP evidence covers one selected frame and one short video window. It is not a dataset-wide evaluation.")
bullet("Keyframe selection is threshold-based inter-frame change. It is not a learned event detector and has no reported ground-truth accuracy.")
bullet("Optical flow estimates apparent pixel motion. It does not identify objects or infer action semantics.")
bullet("Classical image transformations may make visual structure easier to inspect, but they do not validate component condition or safety compliance.")
bullet("The live check verified HTTP responses; browser-side visual rendering and button interaction were not separately exercised in that verification record.")
bullet("Optional local captioning and ASR code remains disabled. Qwen vision and Whisper weights were not acquired or run; no generated captions, transcripts, or word timestamps are available as pilot results.")
bullet("A user-provided Windows Task Manager screenshot shows Intel Iris Xe integrated graphics with shared GPU memory (1.7/7.8 GB in use) and system memory at 14.4/15.6 GB. This differs from the project plan's earlier RTX 4050 hardware assumption. The current WSL Docker runtime reported no GPU adapter, so the integrated GPU is not available to that container; available RAM was about 1.1 GiB at the host check. AI-model inference remains paused for resource safety. This does not affect the recorded classical IVP results.")
bullet("IndEgo human keystep annotations are dataset annotations; they must not be presented as machine-generated captions or speech transcripts.")

heading("8. Conclusion and next work")
paragraph(
    "TRACE can demonstrate core image and video processing on real manufacturing footage rather than a CAD reconstruction. Its current IVP contribution is a web workflow for source-frame inspection, classical image analysis, threshold-based keyframe selection, and optical-flow visualization. The strongest defensible presentation is therefore a practical, interactive IVP demonstration supported by a small number of live checks—not a claim of AI captioning or corpus-scale CV performance."
)
paragraph(
    "Next, validate the complete browser interaction on a fresh run and collect results over a declared sample of videos and intervals. For any accuracy claim, define ground truth and report the evaluation method. Resume local AI captioning/transcription only after the execution environment exposes usable GPU capacity or sufficient RAM, then report model provenance, runtime, failure rate, and output quality separately. Keep generated outputs in memory until persistence and indexing are explicitly approved."
)

heading("References and attribution")
paragraph("[1] Fraunhofer IPK, IndEgo dataset, Hugging Face Datasets, pinned revision c822468b5e0c9c42ebbf2939d3be936c2b203704. Dataset license recorded in the project manifest: CC BY 4.0.")
paragraph("[2] TRACE project verification record, docs/build-status.md, entry “Visual Intelligence Studio extension (2026-11-26).” Contains the live HTTP, media-range, real-frame, single-frame, and video-window observations summarized in this report.")
paragraph("[3] TRACE implementation: backend/app/ivp/manifest.py, frames.py, service.py, processing.py; backend/app/main.py; and backend/app/static/ivp_lab.html.")
paragraph("[4] TRACE engineering context: records/ENGINEERING_SPEC.md. This report narrows its scope to the implemented IVP demonstration and does not restate broader retrieval acceptance results.")
paragraph("Dataset attribution: Fraunhofer IPK, IndEgo, CC BY 4.0. Any redistribution or public presentation of dataset media should preserve the applicable attribution and license terms.", italic=True, color="52606D", size=12, before=180)

sect = element(content, W, "sectPr")
element(sect, W, "headerReference", {tag(W, "type"): "default", tag(R, "id"): "rId2"})
element(sect, W, "footerReference", {tag(W, "type"): "default", tag(R, "id"): "rId3"})
element(sect, W, "pgSz", {tag(W, "w"): "11906", tag(W, "h"): "16838"})
element(sect, W, "pgMar", {tag(W, "top"): "1200", tag(W, "right"): "1440", tag(W, "bottom"): "1200", tag(W, "left"): "1440", tag(W, "header"): "600", tag(W, "footer"): "600", tag(W, "gutter"): "0"})


def styles_xml() -> bytes:
    root = ET.Element(tag(W, "styles"))

    def style(style_id: str, name: str, *, based: str = "Normal", size: int = 22, color: str = "243B53", bold: bool = False, before: int = 0, after: int = 120, font: str = "Aptos") -> ET.Element:
        s = element(root, W, "style", {tag(W, "type"): "paragraph", tag(W, "styleId"): style_id})
        element(s, W, "name", {tag(W, "val"): name})
        if style_id != "Normal":
            element(s, W, "basedOn", {tag(W, "val"): based})
        ppr = element(s, W, "pPr")
        element(ppr, W, "spacing", {tag(W, "before"): str(before), tag(W, "after"): str(after), tag(W, "line"): "276"})
        rpr = element(s, W, "rPr")
        element(rpr, W, "rFonts", {tag(W, "ascii"): font, tag(W, "hAnsi"): font})
        element(rpr, W, "color", {tag(W, "val"): color})
        element(rpr, W, "sz", {tag(W, "val"): str(size)})
        if bold:
            element(rpr, W, "b")
        return s

    style("Normal", "Normal", size=21, after=140)
    style("Title", "Title", size=38, color="12304A", bold=True, after=180)
    style("Subtitle", "Subtitle", size=23, color="486581", after=280)
    style("Eyebrow", "Eyebrow", size=15, color="147D92", bold=True, after=100)
    style("Heading1", "Heading 1", size=27, color="12304A", bold=True, before=280, after=120)
    style("Heading2", "Heading 2", size=23, color="147D92", bold=True, before=220, after=100)
    style("TableText", "Table Text", size=17, color="243B53", after=50)
    styles = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return styles


def header_xml() -> bytes:
    root = ET.Element(tag(W, "hdr"))
    p = element(root, W, "p")
    ppr = element(p, W, "pPr")
    element(ppr, W, "pBdr")
    run = element(p, W, "r")
    rpr = element(run, W, "rPr")
    element(rpr, W, "color", {tag(W, "val"): "147D92"})
    element(rpr, W, "sz", {tag(W, "val"): "16"})
    element(run, W, "t").text = "TRACE   /   IMAGE & VIDEO PROCESSING"
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def footer_xml() -> bytes:
    root = ET.Element(tag(W, "ftr"))
    p = element(root, W, "p")
    ppr = element(p, W, "pPr")
    element(ppr, W, "jc", {tag(W, "val"): "right"})
    r = element(p, W, "r")
    element(r, W, "t").text = "Project report  •  Page "
    field = element(p, W, "fldSimple", {tag(W, "instr"): "PAGE"})
    fr = element(field, W, "r")
    element(fr, W, "t").text = "1"
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def write_docx() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    content_types = ET.Element(tag(CT, "Types"))
    element(content_types, CT, "Default", {"Extension": "rels", "ContentType": "application/vnd.openxmlformats-package.relationships+xml"})
    element(content_types, CT, "Default", {"Extension": "xml", "ContentType": "application/xml"})
    element(content_types, CT, "Override", {"PartName": "/word/document.xml", "ContentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"})
    element(content_types, CT, "Override", {"PartName": "/word/styles.xml", "ContentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"})
    element(content_types, CT, "Override", {"PartName": "/word/header1.xml", "ContentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"})
    element(content_types, CT, "Override", {"PartName": "/word/footer1.xml", "ContentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"})
    root_rels = ET.Element(tag(REL, "Relationships"))
    element(root_rels, REL, "Relationship", {"Id": "rId1", "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument", "Target": "word/document.xml"})
    doc_rels = ET.Element(tag(REL, "Relationships"))
    element(doc_rels, REL, "Relationship", {"Id": "rId1", "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles", "Target": "styles.xml"})
    element(doc_rels, REL, "Relationship", {"Id": "rId2", "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/header", "Target": "header1.xml"})
    element(doc_rels, REL, "Relationship", {"Id": "rId3", "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer", "Target": "footer1.xml"})
    with ZipFile(OUTPUT, "w", ZIP_DEFLATED) as docx:
        docx.writestr("[Content_Types].xml", ET.tostring(content_types, encoding="utf-8", xml_declaration=True))
        docx.writestr("_rels/.rels", ET.tostring(root_rels, encoding="utf-8", xml_declaration=True))
        docx.writestr("word/document.xml", ET.tostring(body, encoding="utf-8", xml_declaration=True))
        docx.writestr("word/_rels/document.xml.rels", ET.tostring(doc_rels, encoding="utf-8", xml_declaration=True))
        docx.writestr("word/styles.xml", styles_xml())
        docx.writestr("word/header1.xml", header_xml())
        docx.writestr("word/footer1.xml", footer_xml())
    print(f"Created {OUTPUT} ({OUTPUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    write_docx()
