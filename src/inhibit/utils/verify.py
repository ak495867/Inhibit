from __future__ import annotations

import json
from pathlib import Path

from inhibit.utils.artifacts import sha256_file


class ArtifactVerificationError(ValueError):
    pass


def verify_run(run_dir: str | Path, input_path: str | Path | None = None) -> dict[str, object]:
    root = Path(run_dir)
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        raise ArtifactVerificationError(f"manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text())
    failures: list[str] = []
    checked: list[str] = []
    for relative, expected in manifest.get("artifacts", {}).items():
        path = root / relative
        if not path.exists():
            failures.append(f"missing artifact: {relative}")
            continue
        checked.append(relative)
        actual = sha256_file(path)
        if actual != expected.get("sha256"):
            failures.append(f"hash mismatch: {relative}")
        if path.stat().st_size != expected.get("bytes"):
            failures.append(f"size mismatch: {relative}")
    if input_path is not None:
        input_file = Path(input_path)
        expected_input = manifest.get("input", {}).get("sha256")
        if not input_file.exists():
            failures.append(f"missing input: {input_file}")
        elif expected_input and sha256_file(input_file) != expected_input:
            failures.append("input hash mismatch")
    return {"passed": not failures, "checked_artifacts": checked, "failures": failures}
