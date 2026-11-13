"""File-type allowlist: the extension AND the magic bytes / container layout must agree."""

from __future__ import annotations

import io
import zipfile

from .types import ExtractionError, Limits
from .zipguard import check_zip

TEXT_KINDS = {"txt", "md", "csv", "html"}
OOXML_MARKERS = {
    "docx": "word/document.xml",
    "pptx": "ppt/presentation.xml",
    "xlsx": "xl/workbook.xml",
}
EXTENSIONS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".pptx": "pptx",
    ".xlsx": "xlsx",
    ".csv": "csv",
    ".txt": "txt",
    ".md": "md",
    ".markdown": "md",
    ".html": "html",
    ".htm": "html",
    ".rtf": "rtf",
    ".png": "png",
    ".jpg": "jpg",
    ".jpeg": "jpg",
}
LEGACY = {".doc", ".ppt", ".xls", ".docm", ".pptm", ".xlsm", ".dotm"}
_BINARY_MAGIC = (b"PK\x03\x04", b"%PDF", b"MZ", b"\x7fELF", b"\xd0\xcf\x11\xe0", b"\x89PNG", b"\xff\xd8\xff")


def allowed_extensions(feature_ocr: bool) -> list[str]:
    return [e for e, k in EXTENSIONS.items() if feature_ocr or k not in ("png", "jpg")]


def detect_kind(filename: str, data: bytes, limits: Limits) -> str:
    name = filename.lower()
    ext = "." + name.rsplit(".", 1)[-1] if "." in name else ""
    if ext in LEGACY:
        raise ExtractionError(
            "unsupported_type",
            f"{filename}: legacy or macro-enabled Office formats ({ext}) are not accepted. "
            "Save the file as .docx, .pptx or .xlsx and upload it again.",
        )
    kind = EXTENSIONS.get(ext)
    if kind is None:
        raise ExtractionError("unsupported_type", f"{filename}: file type '{ext or 'none'}' is not allowed.")
    if kind in ("png", "jpg") and not limits.feature_ocr:
        raise ExtractionError("ocr_disabled", f"{filename}: image uploads are disabled (OCR feature is off).")
    if not data:
        raise ExtractionError("empty", f"{filename}: the file is empty.")
    if len(data) > limits.max_file_bytes:
        raise ExtractionError(
            "too_large",
            f"{filename}: {len(data) // (1024 * 1024)} MB exceeds the per-file limit of "
            f"{limits.max_file_bytes // (1024 * 1024)} MB.",
        )

    head = data[:2048]
    mismatch = ExtractionError("type_mismatch", f"{filename}: the content does not match the '{ext}' extension.")
    if kind == "pdf":
        if b"%PDF-" not in data[:1024]:
            raise mismatch
    elif kind in OOXML_MARKERS:
        if not data.startswith(b"PK\x03\x04"):
            if data.startswith(b"\xd0\xcf\x11\xe0"):
                raise ExtractionError(
                    "encrypted",
                    f"{filename}: the file is password-protected or in a legacy format. "
                    "Remove the password and upload it again.",
                )
            raise mismatch
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as exc:
            raise ExtractionError("corrupt", f"{filename}: the file is corrupt (not a valid archive).") from exc
        with zf:
            check_zip(zf, filename, limits)
            names = set(zf.namelist())
            if "[Content_Types].xml" not in names or OOXML_MARKERS[kind] not in names:
                raise mismatch
    elif kind == "rtf":
        if not data.lstrip()[:5] == b"{\\rtf":
            raise mismatch
    elif kind == "png":
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise mismatch
    elif kind == "jpg":
        if not data.startswith(b"\xff\xd8\xff"):
            raise mismatch
    elif kind in TEXT_KINDS:
        if head.startswith(_BINARY_MAGIC) or b"\x00" in data[:8192]:
            raise mismatch
    return kind


def decode_text(data: bytes) -> tuple[str, list[str]]:
    warnings: list[str] = []
    for enc in ("utf-8-sig", "utf-16") if data[:2] in (b"\xff\xfe", b"\xfe\xff") else ("utf-8-sig",):
        try:
            return data.decode(enc), warnings
        except UnicodeDecodeError:
            continue
    warnings.append("Text was not valid UTF-8; decoded as Windows-1252, some characters may be wrong.")
    return data.decode("cp1252", errors="replace"), warnings
