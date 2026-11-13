from app.extract import ScanVerdict


def reject_all(filename: str, data: bytes) -> ScanVerdict:
    return ScanVerdict(clean=False, reason="EICAR test signature")


def explode(filename: str, data: bytes) -> ScanVerdict:
    raise RuntimeError("scanner offline")
