"""
Medical document extraction from PDF files.

Two extraction strategies:
  A) docling (preferred) — layout-aware PDF parsing, table extraction, markdown output
  B) PyMuPDF fallback — simple text extraction if docling is unavailable

Additionally: direct image extraction for multimodal MedGemma calls.
PDF pages containing medical images (lab reports, radiology reports, documents
with embedded images) can be sent DIRECTLY to MedGemma 4B multimodal without
pre-extraction — MedGemma's vision system reads document images natively.

Usage:
    from src.data.document_extractor import extract_document_text, pdf_pages_as_images

    # Extract all text from a PDF (lab report, referral letter, discharge summary)
    text = extract_document_text("path/to/lab_report.pdf")

    # Get pages as PIL images for direct MedGemma multimodal input
    images = pdf_pages_as_images("path/to/report.pdf")

    # Let MedGemma read the document image directly
    from src.models.medgemma.inference import analyze_medical_image
    response = analyze_medical_image(images[0], "Extract all lab values from this document")

WHEN TO USE WHICH APPROACH:
  - Text extraction (docling/PyMuPDF): structured reports, discharge summaries,
    referral letters, FHIR/HL7 documents → feed text to structured_output engine
  - Direct image to MedGemma: scanned PDFs, handwritten notes, forms with checkboxes,
    mixed text+image documents where layout matters
  - Neither guarantees PHI removal — always pass through de-identifier first
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


# ── Strategy A: docling ────────────────────────────────────────────────────────

def _extract_with_docling(pdf_path: str) -> str:
    """
    Extract text from PDF using docling.

    docling provides:
    - Layout-aware parsing (respects document structure)
    - Table extraction with structure
    - Markdown output format (works well as MedGemma context)
    - Handles multi-column layouts

    Returns markdown-formatted text string.
    Raises ImportError if docling is not installed.
    """
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    result = converter.convert(pdf_path)

    # Export as markdown — preserves headers, tables, lists
    markdown_text = result.document.export_to_markdown()
    return markdown_text


# ── Strategy B: PyMuPDF fallback ──────────────────────────────────────────────

def _extract_with_pymupdf(pdf_path: str) -> str:
    """
    Extract text from PDF using PyMuPDF (fitz).

    Simpler than docling — plain text extraction with page breaks.
    Good enough for linear text documents; loses table structure.

    Returns plain text string.
    Raises ImportError if PyMuPDF is not installed.
    """
    import fitz  # PyMuPDF

    doc = fitz.open(pdf_path)
    pages: List[str] = []

    for page_num, page in enumerate(doc, start=1):
        text = page.get_text()
        if text.strip():
            pages.append(f"--- Page {page_num} ---\n{text.strip()}")

    doc.close()
    return "\n\n".join(pages)


# ── Strategy C: pdfplumber fallback ───────────────────────────────────────────

def _extract_with_pdfplumber(pdf_path: str) -> str:
    """
    Extract text using pdfplumber.
    Reasonable table extraction. Fallback if docling and PyMuPDF unavailable.
    """
    import pdfplumber

    pages: List[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            tables = page.extract_tables() or []
            page_content = f"--- Page {page_num} ---\n{text.strip()}"
            if tables:
                for table in tables:
                    rows = [" | ".join(str(cell or "") for cell in row) for row in table]
                    page_content += "\n\nTABLE:\n" + "\n".join(rows)
            if page_content.strip():
                pages.append(page_content)

    return "\n\n".join(pages)


# ── Public API ─────────────────────────────────────────────────────────────────

def extract_document_text(
    pdf_path: str,
    strategy: str = "auto",
) -> str:
    """
    Extract all text from a PDF document.

    Args:
        pdf_path: Path to the PDF file.
        strategy: Extraction strategy:
                  "auto"      — try docling, fallback to PyMuPDF, then pdfplumber
                  "docling"   — docling only (layout-aware, markdown output)
                  "pymupdf"   — PyMuPDF only (plain text)
                  "pdfplumber"— pdfplumber only

    Returns:
        Extracted text string. Empty string if extraction fails entirely.

    Note:
        This function does NOT de-identify PHI.
        Run through src/data/deidentifier.py before any model call.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if path.suffix.lower() != ".pdf":
        logger.warning("document_extractor: file %s is not a .pdf", pdf_path)

    pdf_str = str(path)

    if strategy == "docling":
        return _extract_with_docling(pdf_str)

    if strategy == "pymupdf":
        return _extract_with_pymupdf(pdf_str)

    if strategy == "pdfplumber":
        return _extract_with_pdfplumber(pdf_str)

    # Auto strategy: try in order
    errors = []

    try:
        text = _extract_with_docling(pdf_str)
        if text.strip():
            logger.debug("document_extractor: used docling for %s", path.name)
            return text
    except ImportError:
        logger.debug("docling not installed — trying PyMuPDF")
    except Exception as exc:
        errors.append(f"docling: {exc}")

    try:
        text = _extract_with_pymupdf(pdf_str)
        if text.strip():
            logger.debug("document_extractor: used PyMuPDF for %s", path.name)
            return text
    except ImportError:
        logger.debug("PyMuPDF not installed — trying pdfplumber")
    except Exception as exc:
        errors.append(f"PyMuPDF: {exc}")

    try:
        text = _extract_with_pdfplumber(pdf_str)
        if text.strip():
            logger.debug("document_extractor: used pdfplumber for %s", path.name)
            return text
    except ImportError:
        logger.warning("No PDF extraction library installed. Install: pip install docling or pymupdf")
    except Exception as exc:
        errors.append(f"pdfplumber: {exc}")

    if errors:
        logger.error("document_extractor: all strategies failed for %s — %s", path.name, errors)

    return ""


def pdf_pages_as_images(
    pdf_path: str,
    dpi: int = 150,
    max_pages: Optional[int] = None,
) -> List:
    """
    Render PDF pages as PIL Images for direct MedGemma multimodal input.

    Useful when the PDF contains:
    - Scanned documents or handwritten notes
    - Mixed layout (text + charts + images)
    - Forms with checkboxes or structured layouts
    - Embedded medical images

    MedGemma 4B-IT can read document images directly — this is often more
    accurate than text extraction for complex layouts.

    Args:
        pdf_path:  Path to PDF file.
        dpi:       Rendering resolution. 150 DPI is sufficient for text reading;
                   use 200+ for small text or complex layouts.
        max_pages: Maximum pages to render. None = all pages.

    Returns:
        List of PIL.Image.Image objects, one per page.

    Note:
        Requires PyMuPDF: pip install pymupdf
        Output images must be de-identified before any model call.
    """
    try:
        import fitz  # PyMuPDF
        from PIL import Image
        import io
    except ImportError as exc:
        raise ImportError(
            "pdf_pages_as_images requires PyMuPDF and Pillow: "
            "pip install pymupdf pillow"
        ) from exc

    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = fitz.open(str(path))
    images: List[Image.Image] = []

    n_pages = len(doc)
    if max_pages is not None:
        n_pages = min(n_pages, max_pages)

    for page_num in range(n_pages):
        page = doc[page_num]
        # mat scales pixels per point (72 points/inch default)
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        images.append(img)

    doc.close()
    logger.debug(
        "pdf_pages_as_images: rendered %d pages from %s at %d DPI",
        len(images), path.name, dpi,
    )
    return images


def extract_lab_values_with_medgemma(
    pdf_path: str,
    context: Optional[str] = None,
) -> str:
    """
    Extract structured lab values from a PDF document using MedGemma vision.

    Strategy:
    1. Render first 2 pages as images (most lab reports are 1–2 pages)
    2. Send each page image to MedGemma with a targeted extraction prompt
    3. Return JSON string with extracted lab values

    This is ALWAYS preferable to text extraction for lab PDFs because:
    - Lab reports often have complex table layouts
    - Reference ranges are in adjacent columns
    - Abnormal flags (H/L) are visually positioned next to values
    - Units are often in separate columns

    Args:
        pdf_path:  Path to lab report PDF.
        context:   Optional patient context to help MedGemma interpret values.

    Returns:
        JSON string with extracted lab values, or empty string on failure.
        Parse with json.loads() if needed.
    """
    from src.models.medgemma.inference import analyze_medical_image

    try:
        images = pdf_pages_as_images(pdf_path, dpi=150, max_pages=3)
    except Exception as exc:
        logger.error("extract_lab_values_with_medgemma: failed to render pages: %s", exc)
        return ""

    if not images:
        return ""

    all_results: List[str] = []
    for i, img in enumerate(images, start=1):
        patient_context = f"\n\nPatient context: {context}" if context else ""
        prompt = (
            f"Extract all laboratory values from this lab report page {i}. "
            "Return a JSON array where each item has: "
            "{\"test_name\": str, \"value\": str, \"unit\": str, "
            "\"reference_range\": str, \"flag\": \"H\" | \"L\" | \"N\" | null, "
            "\"date\": str | null}. "
            "Include ALL tests visible on this page. "
            f"Output JSON only.{patient_context}"
        )
        try:
            result = analyze_medical_image(img, prompt, max_new_tokens=1024)
            if result.strip():
                all_results.append(result)
        except Exception as exc:
            logger.warning(
                "extract_lab_values_with_medgemma: MedGemma failed on page %d: %s", i, exc
            )

    if not all_results:
        return ""

    # If multiple pages, combine into a single list
    if len(all_results) == 1:
        return all_results[0]

    # Merge multi-page results
    import json
    import re
    combined: List[dict] = []
    for res in all_results:
        # Extract JSON array from each result
        m = re.search(r"\[.*\]", res, re.DOTALL)
        if m:
            try:
                page_labs = json.loads(m.group())
                if isinstance(page_labs, list):
                    combined.extend(page_labs)
            except json.JSONDecodeError:
                pass

    return json.dumps(combined, indent=2) if combined else ""


def classify_document_type(pdf_path: str) -> str:
    """
    Classify a PDF document type from its first page text.

    Returns one of: lab_report | discharge_summary | referral_letter |
                    radiology_report | prescription | unknown

    Useful for routing to the appropriate extraction strategy.
    """
    # Use text extraction for classification — quick and cheap
    try:
        text_snippet = extract_document_text(pdf_path)[:500].lower()
    except Exception:
        return "unknown"

    if any(kw in text_snippet for kw in ["haemoglobin", "creatinine", "glucose", "result", "reference range", "hba1c"]):
        return "lab_report"
    if any(kw in text_snippet for kw in ["discharge summary", "admission", "ward", "inpatient"]):
        return "discharge_summary"
    if any(kw in text_snippet for kw in ["referral", "dear doctor", "dear dr", "gp letter"]):
        return "referral_letter"
    if any(kw in text_snippet for kw in ["findings", "impression", "technique", "x-ray", "ct scan", "mri"]):
        return "radiology_report"
    if any(kw in text_snippet for kw in ["prescription", "dispense", "sig:", "quantity"]):
        return "prescription"

    return "unknown"
