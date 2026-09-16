"""Verify that the packaged Python code and resources match current sources."""
import hashlib
import types
from pathlib import Path
from PyInstaller.archive.readers import CArchiveReader

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist/TRIGRIX Studio"


def fingerprint(code):
    if isinstance(code, types.CodeType):
        return (code.co_code, code.co_names, code.co_varnames, code.co_freevars,
                tuple(fingerprint(value) for value in code.co_consts))
    return code


def main():
    archive = CArchiveReader(str(DIST / "TRIGRIX Studio.exe"))
    pyz_name = next(name for name in archive.toc if name.endswith(".pyz"))
    pyz = archive.open_embedded_archive(pyz_name)
    mismatches = []
    paths = list((ROOT / "src/trigrix_studio").rglob("*.py"))
    for source in paths:
        relative = source.relative_to(ROOT / "src").with_suffix("")
        name = ".".join(relative.parts).removesuffix(".__init__")
        if name not in pyz.toc:
            continue
        expected = compile(source.read_text(encoding="utf-8"), str(source), "exec")
        if fingerprint(expected) != fingerprint(pyz.extract(name)):
            mismatches.append(str(source.relative_to(ROOT)))
    for source in (ROOT / "resources/i18n").rglob("*.json"):
        bundled = DIST / "_internal" / source.relative_to(ROOT)
        if not bundled.is_file() or hashlib.sha256(source.read_bytes()).digest() != hashlib.sha256(bundled.read_bytes()).digest():
            mismatches.append(str(source.relative_to(ROOT)))
    if mismatches:
        raise SystemExit("Distribution differs from sources:\n" + "\n".join(mismatches))
    print("Packaged Python modules and language catalogs match current sources.")


if __name__ == "__main__":
    main()
