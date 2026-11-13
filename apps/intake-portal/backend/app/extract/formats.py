"""Per-format text extractors. All output is Markdown-ish plain text.

Security posture: content is parsed as data only. Macros, scripts, embedded
objects, formulas and links are never executed or followed. Hidden text,
comments and document metadata are dropped where the library makes it feasible,
and the user is told what was removed.
"""

from __future__ import annotations

import csv
import io
import logging
import re
import unicodedata
import zipfile
from collections.abc import Callable, Sequence

from . import injection
from .detect import decode_text, detect_kind
from .types import ExtractionError, ExtractionResult, Limits
from .zipguard import risky_parts

log = logging.getLogger(__name__)

_INVISIBLE = re.compile("[\u200b\u200c\u200d\u2060\ufeff\u202a-\u202e\u2066-\u2069\u00ad]")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)


def _md_cell(value: object) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


def md_table(rows: Sequence[Sequence[object]]) -> str:
    rows = [r for r in rows if any(_md_cell(c) for c in r)]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    norm = [[_md_cell(c) for c in r] + [""] * (width - len(r)) for r in rows]
    out = ["| " + " | ".join(norm[0]) + " |", "|" + "---|" * width]
    out += ["| " + " | ".join(r) + " |" for r in norm[1:]]
    return "\n".join(out)


# --------------------------------------------------------------------------- PDF
def extract_pdf(filename: str, data: bytes, limits: Limits) -> ExtractionResult:
    from pypdf import PdfReader
    from pypdf.errors import DependencyError, FileNotDecryptedError, PdfReadError

    warnings: list[str] = []
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
    except PdfReadError as exc:
        raise ExtractionError("corrupt", f"{filename}: the PDF is corrupt or malformed.") from exc
    if reader.is_encrypted:
        try:
            ok = reader.decrypt("")
        except (NotImplementedError, DependencyError, FileNotDecryptedError) as exc:
            raise ExtractionError("encrypted", f"{filename}: the PDF is password-protected.") from exc
        if not ok:
            raise ExtractionError(
                "encrypted",
                f"{filename}: the PDF is password-protected. Remove the password and upload it again.",
            )
        warnings.append("The PDF had an owner password but no open password; text was extracted.")
    try:
        n = len(reader.pages)
    except (PdfReadError, FileNotDecryptedError) as exc:
        raise ExtractionError("corrupt", f"{filename}: the PDF page tree is unreadable.") from exc
    if n > limits.max_pages:
        raise ExtractionError("too_many_pages", f"{filename}: {n} pages exceeds the limit of {limits.max_pages}.")
    if b"/JavaScript" in data or b"/JS " in data or b"/JS(" in data:
        warnings.append("The PDF contains JavaScript. It was not executed.")
    if b"/EmbeddedFile" in data:
        warnings.append("The PDF contains embedded files. They were not opened.")

    parts: list[str] = []
    text_chars = 0
    failed_pages = 0
    for i, page in enumerate(reader.pages, start=1):
        try:
            txt = page.extract_text() or ""
        except Exception:  # noqa: BLE001 - one bad page must not kill the document
            failed_pages += 1
            txt = ""
        text_chars += len(txt.strip())
        parts.append(f"### Page {i}\n\n{txt.strip()}")
    if failed_pages:
        warnings.append(f"{failed_pages} page(s) could not be read and are empty in the output.")
    if n and text_chars < 20 * n:
        warnings.append(
            "Little or no text layer was found; the PDF looks scanned. OCR is off, so image-only pages produce no text."
        )
    text = "\n\n".join(parts) if text_chars else ""
    return ExtractionResult(filename, "pdf", text, pages=n, warnings=warnings)


# -------------------------------------------------------------------------- DOCX
def extract_docx(filename: str, data: bytes, limits: Limits) -> ExtractionResult:
    from docx import Document
    from docx.oxml.ns import qn

    warnings: list[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        warnings += risky_parts(zf)
        names = set(zf.namelist())
    if "word/comments.xml" in names:
        warnings.append("Document comments were removed.")
    try:
        doc = Document(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001 - python-docx raises many types for bad input
        raise ExtractionError("corrupt", f"{filename}: the DOCX is corrupt or not a valid Word document.") from exc

    style_names = {s.style_id: (s.name or "") for s in doc.styles}
    hidden_runs = 0

    def run_text(p_el) -> str:
        nonlocal hidden_runs
        out: list[str] = []
        for r in p_el.iter(qn("w:r")):
            rpr = r.find(qn("w:rPr"))
            if rpr is not None:
                vanish = rpr.find(qn("w:vanish"))
                if vanish is not None and vanish.get(qn("w:val")) not in ("0", "false"):
                    hidden_runs += 1
                    continue
            for node in r:
                if node.tag == qn("w:t"):
                    out.append(node.text or "")
                elif node.tag == qn("w:tab"):
                    out.append("\t")
                elif node.tag in (qn("w:br"), qn("w:cr")):
                    out.append("\n")
        return "".join(out)

    blocks: list[str] = []
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            text = run_text(child).strip()
            if not text:
                continue
            ppr = child.find(qn("w:pPr"))
            style = ""
            is_list = False
            if ppr is not None:
                ps = ppr.find(qn("w:pStyle"))
                if ps is not None:
                    style = style_names.get(ps.get(qn("w:val")) or "", "")
                is_list = ppr.find(qn("w:numPr")) is not None
            m = re.match(r"(?i)heading\s*(\d)", style)
            if style.lower() == "title":
                blocks.append(f"# {text}")
            elif m:
                blocks.append("#" * min(6, int(m.group(1)) + 1) + " " + text)
            elif is_list or style.lower().startswith("list"):
                blocks.append(f"- {text}")
            else:
                blocks.append(text)
        elif child.tag == qn("w:tbl"):
            rows: list[list[object]] = []
            for tr in child.iter(qn("w:tr")):
                rows.append(
                    [
                        " ".join(run_text(p).strip() for p in tc.iter(qn("w:p")) if run_text(p).strip())
                        for tc in tr.iter(qn("w:tc"))
                    ]
                )
            table = md_table(rows)
            if table:
                blocks.append(table)
    if hidden_runs:
        warnings.append(f"{hidden_runs} run(s) of hidden text were removed.")
    return ExtractionResult(filename, "docx", "\n\n".join(blocks), warnings=warnings)


# -------------------------------------------------------------------------- PPTX
def extract_pptx(filename: str, data: bytes, limits: Limits) -> ExtractionResult:
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    warnings: list[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        warnings += risky_parts(zf)
        if any(n.startswith("ppt/comments/") for n in zf.namelist()):
            warnings.append("Slide comments were removed.")
    try:
        prs = Presentation(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        raise ExtractionError("corrupt", f"{filename}: the PPTX is corrupt or not a valid presentation.") from exc
    n = len(prs.slides)
    if n > limits.max_slides:
        raise ExtractionError("too_many_pages", f"{filename}: {n} slides exceeds the limit of {limits.max_slides}.")

    def shape_lines(shapes, title_id) -> list[str]:
        lines: list[str] = []
        for sh in shapes:
            if sh.shape_type == MSO_SHAPE_TYPE.GROUP:
                lines += shape_lines(sh.shapes, title_id)
                continue
            if getattr(sh, "shape_id", None) == title_id:
                continue
            if getattr(sh, "has_table", False) and sh.has_table:
                lines.append(md_table([[c.text for c in row.cells] for row in sh.table.rows]))
            elif getattr(sh, "has_text_frame", False) and sh.has_text_frame:
                for para in sh.text_frame.paragraphs:
                    t = "".join(r.text for r in para.runs).strip()
                    if t:
                        lines.append(("  " * para.level) + "- " + t)
        return lines

    blocks: list[str] = []
    hidden = 0
    for i, slide in enumerate(prs.slides, start=1):
        if slide._element.get("show") in ("0", "false"):
            hidden += 1
            continue
        title_shape = slide.shapes.title
        title = title_shape.text.strip() if title_shape is not None and title_shape.has_text_frame else ""
        title_id = title_shape.shape_id if title_shape is not None else None
        block = [f"## Slide {i}" + (f": {title}" if title else "")]
        block += shape_lines(slide.shapes, title_id)
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text.strip() if slide.notes_slide.notes_text_frame else ""
            if notes:
                block.append(f"**Speaker notes:** {notes}")
        blocks.append("\n".join(block))
    if hidden:
        warnings.append(f"{hidden} hidden slide(s) were skipped.")
    return ExtractionResult(filename, "pptx", "\n\n".join(blocks), slides=n, warnings=warnings)


# -------------------------------------------------------------------------- XLSX
def extract_xlsx(filename: str, data: bytes, limits: Limits) -> ExtractionResult:
    from openpyxl import load_workbook

    warnings: list[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        warnings += risky_parts(zf)
        if any(n.startswith("xl/externalLinks/") for n in zf.namelist()):
            warnings.append("External workbook links were ignored.")
    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001
        raise ExtractionError("corrupt", f"{filename}: the XLSX is corrupt or not a valid workbook.") from exc
    blocks: list[str] = []
    cells = 0
    hidden = 0
    truncated = False
    try:
        sheets = wb.worksheets
        for ws in sheets:
            if getattr(ws, "sheet_state", "visible") != "visible":
                hidden += 1
                continue
            rows: list[list[object]] = []
            for row in ws.iter_rows(values_only=True):
                cells += len(row)
                if cells > limits.max_sheet_cells:
                    truncated = True
                    break
                rows.append(list(row))
            table = md_table(rows)
            blocks.append(f"## Sheet: {ws.title}\n\n{table or '(empty)'}")
            if truncated:
                break
    finally:
        wb.close()
    if hidden:
        warnings.append(f"{hidden} hidden sheet(s) were skipped.")
    if truncated:
        warnings.append(f"Workbook truncated after {limits.max_sheet_cells} cells.")
    warnings.append("Formulas were not evaluated; cached values were used.")
    return ExtractionResult(filename, "xlsx", "\n\n".join(blocks), sheets=len(sheets), warnings=warnings)


# --------------------------------------------------------------------- CSV / TXT
def extract_csv(filename: str, data: bytes, limits: Limits) -> ExtractionResult:
    text, warnings = decode_text(data)
    try:
        dialect: type[csv.Dialect] | csv.Dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows: list[list[object]] = []
    cells = 0
    try:
        for row in csv.reader(io.StringIO(text), dialect):
            cells += len(row)
            if cells > limits.max_sheet_cells:
                warnings.append(f"CSV truncated after {limits.max_sheet_cells} cells.")
                break
            rows.append(list(row))
    except csv.Error as exc:
        raise ExtractionError("corrupt", f"{filename}: the CSV could not be parsed ({exc}).") from exc
    return ExtractionResult(filename, "csv", md_table(rows), warnings=warnings)


def extract_text(filename: str, data: bytes, limits: Limits, kind: str = "txt") -> ExtractionResult:
    text, warnings = decode_text(data)
    if kind == "md" and _HTML_COMMENT.search(text):
        text = _HTML_COMMENT.sub("", text)
        warnings.append("HTML comments (hidden in rendered Markdown) were removed.")
    return ExtractionResult(filename, kind, text, warnings=warnings)


# -------------------------------------------------------------------------- HTML
def extract_html(filename: str, data: bytes, limits: Limits) -> ExtractionResult:
    from bs4 import BeautifulSoup, Comment

    raw, warnings = decode_text(data)
    soup = BeautifulSoup(raw, "html.parser")
    removed_active = 0
    for tag in soup(
        [
            "script",
            "style",
            "noscript",
            "template",
            "iframe",
            "object",
            "embed",
            "svg",
            "canvas",
            "head",
            "meta",
            "link",
        ]
    ):
        if tag.name in ("script", "iframe", "object", "embed"):
            removed_active += 1
        tag.decompose()
    comments = soup.find_all(string=lambda t: isinstance(t, Comment))
    for c in comments:
        c.extract()
    hidden = 0
    for tag in soup.find_all(True):
        if tag.decomposed:
            continue
        style = str(tag.get("style") or "").replace(" ", "").lower()
        if (
            tag.has_attr("hidden")
            or tag.get("aria-hidden") == "true"
            or "display:none" in style
            or "visibility:hidden" in style
            or "font-size:0" in style
        ):
            hidden += 1
            tag.decompose()
    for table in soup.find_all("table"):
        rows = [[td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])] for tr in table.find_all("tr")]
        table.replace_with(soup.new_string("\n\n" + md_table(rows) + "\n\n"))
    for level in range(1, 7):
        for h in soup.find_all(f"h{level}"):
            h.replace_with(soup.new_string(f"\n\n{'#' * level} {h.get_text(' ', strip=True)}\n\n"))
    for li in soup.find_all("li"):
        li.insert_before(soup.new_string("\n- "))
    for br in soup.find_all("br"):
        br.replace_with(soup.new_string("\n"))
    for blk in soup.find_all(["p", "div", "section", "article", "ul", "ol", "tr", "pre", "blockquote"]):
        blk.insert_after(soup.new_string("\n"))
    text = re.sub(r"\n{3,}", "\n\n", soup.get_text())
    text = "\n".join(line.rstrip() for line in text.splitlines()).strip()
    if removed_active:
        warnings.append(f"{removed_active} script/embedded element(s) were removed and not executed.")
    if comments:
        warnings.append(f"{len(comments)} HTML comment(s) were removed.")
    if hidden:
        warnings.append(f"{hidden} hidden element(s) were removed.")
    return ExtractionResult(filename, "html", text, warnings=warnings)


# --------------------------------------------------------------------------- RTF
def extract_rtf(filename: str, data: bytes, limits: Limits) -> ExtractionResult:
    from striprtf.striprtf import rtf_to_text

    warnings: list[str] = []
    raw = data.decode("latin-1")
    if "\\object" in raw or "\\objdata" in raw:
        warnings.append("Embedded objects in the RTF were ignored.")
    try:
        text = rtf_to_text(raw, errors="replace")
    except Exception as exc:  # noqa: BLE001
        raise ExtractionError("corrupt", f"{filename}: the RTF is corrupt or malformed.") from exc
    return ExtractionResult(filename, "rtf", text, warnings=warnings)


# ------------------------------------------------------------------------- IMAGE
def extract_image(filename: str, data: bytes, limits: Limits, kind: str = "png") -> ExtractionResult:
    if not limits.feature_ocr:
        raise ExtractionError("ocr_disabled", f"{filename}: image uploads are disabled (OCR feature is off).")
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise ExtractionError("ocr_unavailable", f"{filename}: OCR is enabled but no OCR engine is installed.") from exc
    Image.MAX_IMAGE_PIXELS = 50_000_000
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as exc:  # noqa: BLE001 - includes DecompressionBombError
        raise ExtractionError("corrupt", f"{filename}: the image could not be read.") from exc
    text = pytesseract.image_to_string(img, timeout=30)
    return ExtractionResult(filename, kind, text, warnings=["Text was produced by OCR and may contain errors."])


_EXTRACTORS: dict[str, Callable[[str, bytes, Limits], ExtractionResult]] = {
    "pdf": extract_pdf,
    "docx": extract_docx,
    "pptx": extract_pptx,
    "xlsx": extract_xlsx,
    "csv": extract_csv,
    "txt": lambda f, d, lim: extract_text(f, d, lim, "txt"),
    "md": lambda f, d, lim: extract_text(f, d, lim, "md"),
    "html": extract_html,
    "rtf": extract_rtf,
    "png": lambda f, d, lim: extract_image(f, d, lim, "png"),
    "jpg": lambda f, d, lim: extract_image(f, d, lim, "jpg"),
}


def normalise(text: str) -> tuple[str, int]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = unicodedata.normalize("NFC", text)
    invisible = len(_INVISIBLE.findall(text))
    text = _INVISIBLE.sub("", text)
    text = _CONTROL.sub("", text)
    return text.strip(), invisible


def extract_bytes(filename: str, data: bytes, limits: Limits) -> ExtractionResult:
    """Detect, extract and post-process one file. Raises ExtractionError with a clear message."""
    safe_name = re.sub(r"[^\w.\- ()]", "_", filename)[:200] or "file"
    kind = detect_kind(safe_name, data, limits)
    try:
        result = _EXTRACTORS[kind](safe_name, data, limits)
    except ExtractionError:
        raise
    except RecursionError as exc:
        raise ExtractionError("corrupt", f"{safe_name}: the file structure is too deeply nested.") from exc
    except MemoryError as exc:
        raise ExtractionError("too_large", f"{safe_name}: the file needs too much memory to process.") from exc
    except Exception as exc:  # noqa: BLE001 - never crash on malformed input
        log.warning("extractor failure", extra={"fields": {"kind": kind, "error_type": type(exc).__name__}})
        raise ExtractionError("corrupt", f"{safe_name}: the file could not be read; it may be corrupt.") from exc

    result.text, invisible = normalise(result.text)
    if invisible:
        result.warnings.append(f"{invisible} invisible formatting character(s) were removed.")
    if len(result.text) > limits.max_extracted_chars:
        result.text = result.text[: limits.max_extracted_chars]
        result.warnings.append(f"Extracted text was truncated at {limits.max_extracted_chars:,} characters.")
    if not result.text.strip():
        result.warnings.append("No text could be extracted from this file.")
    result.injection_flags = injection.scan(result.text)
    if result.injection_flags:
        result.warnings.append(
            f"{len(result.injection_flags)} phrase(s) that look like instructions to an AI were found. "
            "They were left unchanged; AISDLC treats them as data, but please review them."
        )
    return result
