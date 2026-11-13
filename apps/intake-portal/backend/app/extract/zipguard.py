"""Decompression-bomb limits for OOXML (zip) containers, checked before any parsing."""

from __future__ import annotations

import zipfile

from .types import ExtractionError, Limits


def check_zip(zf: zipfile.ZipFile, filename: str, limits: Limits) -> None:
    infos = zf.infolist()
    if len(infos) > limits.zip_max_entries:
        raise ExtractionError(
            "zip_bomb", f"{filename}: the archive has {len(infos)} entries (limit {limits.zip_max_entries})."
        )
    total = 0
    for info in infos:
        if info.flag_bits & 0x1:
            raise ExtractionError("encrypted", f"{filename}: the archive contains encrypted entries.")
        name = info.filename
        if name.startswith("/") or ".." in name.split("/"):
            raise ExtractionError("corrupt", f"{filename}: the archive contains an unsafe path.")
        total += info.file_size
        if (
            info.compress_size > 0
            and info.file_size / info.compress_size > limits.zip_max_ratio
            and (info.file_size > 1024 * 1024)
        ):
            raise ExtractionError(
                "zip_bomb",
                f"{filename}: an entry expands more than {limits.zip_max_ratio}x (possible decompression bomb).",
            )
    if total > limits.zip_max_uncompressed_bytes:
        raise ExtractionError(
            "zip_bomb",
            f"{filename}: uncompressed size {total // (1024 * 1024)} MB exceeds the limit of "
            f"{limits.zip_max_uncompressed_bytes // (1024 * 1024)} MB.",
        )


def risky_parts(zf: zipfile.ZipFile) -> list[str]:
    """Report active content that is present but never executed or extracted."""
    warnings: list[str] = []
    names = zf.namelist()
    if any(n.lower().endswith("vbaproject.bin") for n in names):
        warnings.append("Macros are present in the file. They were not executed and are ignored.")
    if any("/embeddings/" in n.lower() or "oleobject" in n.lower() for n in names):
        warnings.append("Embedded objects are present. They were not opened and are ignored.")
    if any("activex" in n.lower() for n in names):
        warnings.append("ActiveX controls are present. They were ignored.")
    return warnings
