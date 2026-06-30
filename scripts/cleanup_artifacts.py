from __future__ import annotations

import argparse
import shutil
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_JOBS_DIR = ROOT_DIR / "data" / "jobs"


def cleanup_artifacts(jobs_dir: Path, *, keep_run_ids: set[int], apply: bool = False) -> dict:
    jobs_dir = jobs_dir.expanduser().resolve()
    if not jobs_dir.exists():
        return {"jobs_dir": str(jobs_dir), "matched_count": 0, "deleted_count": 0, "matched_paths": []}
    matched: list[Path] = []
    for child in jobs_dir.iterdir():
        if not child.is_dir():
            continue
        try:
            run_id = int(child.name)
        except ValueError:
            continue
        if run_id not in keep_run_ids:
            matched.append(child)
    deleted_count = 0
    if apply:
        for path in matched:
            shutil.rmtree(path)
            deleted_count += 1
    return {
        "jobs_dir": str(jobs_dir),
        "matched_count": len(matched),
        "deleted_count": deleted_count,
        "matched_paths": [str(path) for path in matched],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Dry-run or delete old run artifact directories.")
    parser.add_argument("--jobs-dir", type=Path, default=DEFAULT_JOBS_DIR)
    parser.add_argument("--keep-run-id", type=int, action="append", default=[])
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    result = cleanup_artifacts(
        args.jobs_dir,
        keep_run_ids=set(args.keep_run_id),
        apply=args.apply,
    )
    print(result)


if __name__ == "__main__":
    main()
