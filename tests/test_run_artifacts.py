from __future__ import annotations

import hashlib

from agent.artifact_uploader import RunArtifactUploader, build_run_artifact_manifest
from backend import db
from backend.services import run_service
from tests.test_run_log_chunks import auth_headers, create_bound_run
from tests.test_runs_api import make_client


def isolate_jobs_dir(monkeypatch, tmp_path) -> None:
    jobs_dir = tmp_path / "jobs"
    monkeypatch.setattr(db, "JOBS_DIR", jobs_dir)
    monkeypatch.setattr(run_service, "JOBS_DIR", jobs_dir)


def artifact_body(run: dict, artifact_type: str, filename: str, content: str, *, sequence: int = 1) -> dict:
    content_bytes = content.encode("utf-8")
    return {
        "device_id": run["device_id"],
        "command_id": run["command_id"],
        "artifact_type": artifact_type,
        "filename": filename,
        "sequence": sequence,
        "size_bytes": len(content_bytes),
        "sha256": hashlib.sha256(content_bytes).hexdigest(),
        "content": content,
    }


def test_run_artifacts_upload_and_run_read_apis_work(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    isolate_jobs_dir(monkeypatch, tmp_path)
    for client, session in make_client():
        run = create_bound_run(client, session)

        result = client.post(
            f"/agent/runs/{run['id']}/artifacts",
            headers=auth_headers(),
            json=artifact_body(run, "result", "result.md", "result text"),
        )
        diff = client.post(
            f"/agent/runs/{run['id']}/artifacts",
            headers=auth_headers(),
            json=artifact_body(run, "diff", "diff.patch", "diff text", sequence=2),
        )
        status = client.post(
            f"/agent/runs/{run['id']}/artifacts",
            headers=auth_headers(),
            json=artifact_body(run, "git_status", "git-status.txt", " M file.py", sequence=3),
        )
        report = client.post(
            f"/agent/runs/{run['id']}/artifacts",
            headers=auth_headers(),
            json=artifact_body(run, "run_report", "run-report.md", "report", sequence=4),
        )

        assert result.status_code == 200
        assert diff.status_code == 200
        assert status.status_code == 200
        assert report.status_code == 200
        assert client.get(f"/runs/{run['id']}/result").text == "result text"
        assert client.get(f"/runs/{run['id']}/diff").text == "diff text"
        assert client.get(f"/runs/{run['id']}/artifacts/git-status").text == " M file.py"
        assert client.get(f"/runs/{run['id']}/artifacts/report").text == "report"


def test_run_artifact_replay_same_hash_is_idempotent(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    isolate_jobs_dir(monkeypatch, tmp_path)
    for client, session in make_client():
        run = create_bound_run(client, session)
        body = artifact_body(run, "result", "result.md", "same")

        first = client.post(f"/agent/runs/{run['id']}/artifacts", headers=auth_headers(), json=body)
        replay = client.post(f"/agent/runs/{run['id']}/artifacts", headers=auth_headers(), json=body)

        assert first.status_code == 200
        assert replay.status_code == 200
        assert replay.json()["duplicate"] is True
        assert client.get(f"/runs/{run['id']}/result").text == "same"


def test_run_artifact_conflicting_reupload_is_rejected(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    isolate_jobs_dir(monkeypatch, tmp_path)
    for client, session in make_client():
        run = create_bound_run(client, session)

        first = client.post(
            f"/agent/runs/{run['id']}/artifacts",
            headers=auth_headers(),
            json=artifact_body(run, "result", "result.md", "same"),
        )
        conflict = client.post(
            f"/agent/runs/{run['id']}/artifacts",
            headers=auth_headers(),
            json=artifact_body(run, "result", "result.md", "different"),
        )

        assert first.status_code == 200
        assert conflict.status_code == 409
        assert conflict.json()["detail"]["code"] == "run_artifact_hash_conflict"


def test_run_artifact_rejects_illegal_type_filename_size_hash_and_binding(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    isolate_jobs_dir(monkeypatch, tmp_path)
    for client, session in make_client():
        run = create_bound_run(client, session)
        illegal_type = artifact_body(run, "secret", "secret.txt", "x")
        illegal_filename = artifact_body(run, "result", "../result.md", "x")
        wrong_size = artifact_body(run, "result", "result.md", "x")
        wrong_size["size_bytes"] = 999
        wrong_hash = artifact_body(run, "result", "result.md", "x")
        wrong_hash["sha256"] = "0" * 64
        wrong_device = artifact_body(run, "result", "result.md", "x")
        wrong_device["device_id"] = "other-device"

        responses = [
            client.post(f"/agent/runs/{run['id']}/artifacts", headers=auth_headers(), json=illegal_type),
            client.post(f"/agent/runs/{run['id']}/artifacts", headers=auth_headers(), json=illegal_filename),
            client.post(f"/agent/runs/{run['id']}/artifacts", headers=auth_headers(), json=wrong_size),
            client.post(f"/agent/runs/{run['id']}/artifacts", headers=auth_headers(), json=wrong_hash),
            client.post(f"/agent/runs/{run['id']}/artifacts", headers=auth_headers(), json=wrong_device),
        ]

        assert [response.status_code for response in responses] == [400, 400, 400, 400, 403]
        assert responses[0].json()["detail"]["code"] == "run_artifact_type_not_allowed"
        assert responses[1].json()["detail"]["code"] == "run_artifact_filename_not_allowed"
        assert responses[2].json()["detail"]["code"] == "run_artifact_size_mismatch"
        assert responses[3].json()["detail"]["code"] == "run_artifact_hash_mismatch"
        assert responses[4].json()["detail"]["code"] == "run_artifact_binding_mismatch"


def test_run_artifact_size_limits(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    monkeypatch.setenv("RUN_ARTIFACT_MAX_FILE_BYTES", "3")
    monkeypatch.setenv("RUN_ARTIFACT_MAX_TOTAL_BYTES", "5")
    isolate_jobs_dir(monkeypatch, tmp_path)
    for client, session in make_client():
        run = create_bound_run(client, session)

        too_large_file = client.post(
            f"/agent/runs/{run['id']}/artifacts",
            headers=auth_headers(),
            json=artifact_body(run, "result", "result.md", "abcd"),
        )
        accepted = client.post(
            f"/agent/runs/{run['id']}/artifacts",
            headers=auth_headers(),
            json=artifact_body(run, "result", "result.md", "abc"),
        )
        too_large_total = client.post(
            f"/agent/runs/{run['id']}/artifacts",
            headers=auth_headers(),
            json=artifact_body(run, "diff", "diff.patch", "abc", sequence=2),
        )

        assert too_large_file.status_code == 413
        assert too_large_file.json()["detail"]["code"] == "run_artifact_file_too_large"
        assert accepted.status_code == 200
        assert too_large_total.status_code == 413
        assert too_large_total.json()["detail"]["code"] == "run_artifacts_total_too_large"


def test_run_artifact_uploader_builds_manifest_and_uploads(tmp_path) -> None:
    class FakeClient:
        def __init__(self):
            self.uploads = []

        def upload_run_artifact(self, run_id, payload):
            self.uploads.append((run_id, payload.artifact_type, payload.filename, payload.sequence))
            return {"accepted": True, "artifact_type": payload.artifact_type}

    job_dir = tmp_path / "job"
    job_dir.mkdir()
    (job_dir / "result.md").write_text("result", encoding="utf-8")
    (job_dir / "diff.patch").write_text("diff", encoding="utf-8")
    (job_dir / "ignored.txt").write_text("ignored", encoding="utf-8")

    manifest = build_run_artifact_manifest(job_dir)
    client = FakeClient()
    responses = RunArtifactUploader(client=client).upload_manifest(
        run_id=1,
        device_id="device-a",
        command_id="cmd-1",
        manifest=manifest,
    )

    assert [(item.artifact_type, item.filename, item.sequence) for item in manifest] == [
        ("result", "result.md", 1),
        ("diff", "diff.patch", 2),
    ]
    assert client.uploads == [
        (1, "result", "result.md", 1),
        (1, "diff", "diff.patch", 2),
    ]
    assert responses == [
        {"accepted": True, "artifact_type": "result"},
        {"accepted": True, "artifact_type": "diff"},
    ]


def test_run_artifact_manifest_hashes_normalized_utf8_content(tmp_path) -> None:
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    (job_dir / "result.md").write_bytes(b"\xffabc")

    manifest = build_run_artifact_manifest(job_dir)

    assert len(manifest) == 1
    item = manifest[0]
    expected_content = "\ufffdabc"
    expected_bytes = expected_content.encode("utf-8")
    assert item.content == expected_content
    assert item.size_bytes == len(expected_bytes)
    assert item.sha256 == hashlib.sha256(expected_bytes).hexdigest()
