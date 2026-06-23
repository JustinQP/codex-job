from __future__ import annotations

from agent.log_uploader import RunLogUploader, RunLogUploadTracker
from backend import db
from backend.services import run_service
from tests.test_runs_api import add_device, add_project, add_workspace, make_client


def auth_headers() -> dict[str, str]:
    return {"X-Agent-Token": "agent-secret"}


def isolate_jobs_dir(monkeypatch, tmp_path) -> None:
    jobs_dir = tmp_path / "jobs"
    monkeypatch.setattr(db, "JOBS_DIR", jobs_dir)
    monkeypatch.setattr(run_service, "JOBS_DIR", jobs_dir)


def create_bound_run(client, session):
    project = add_project(session)
    add_device(session, "device-a")
    workspace = add_workspace(session, "device-a")
    response = client.post(
        "/runs",
        json={
            "project_id": project.id,
            "workspace_id": workspace.id,
            "prompt": "write logs",
            "client_request_id": "log-run-1",
        },
    )
    assert response.status_code == 200
    return response.json()


def test_run_log_chunks_append_incrementally_and_run_log_api_reads(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    isolate_jobs_dir(monkeypatch, tmp_path)
    for client, session in make_client():
        run = create_bound_run(client, session)

        first = client.post(
            f"/agent/runs/{run['id']}/log-chunks",
            headers=auth_headers(),
            json={
                "device_id": run["device_id"],
                "command_id": run["command_id"],
                "offset": 0,
                "content": "one\n",
            },
        )
        second = client.post(
            f"/agent/runs/{run['id']}/log-chunks",
            headers=auth_headers(),
            json={
                "device_id": run["device_id"],
                "command_id": run["command_id"],
                "offset": first.json()["current_offset"],
                "content": "two\n",
            },
        )

        assert first.status_code == 200
        assert first.json()["current_offset"] == 4
        assert second.status_code == 200
        assert second.json()["current_offset"] == 8
        assert client.get(f"/runs/{run['id']}/log").text == "one\ntwo\n"


def test_replayed_log_chunk_is_idempotent(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    isolate_jobs_dir(monkeypatch, tmp_path)
    for client, session in make_client():
        run = create_bound_run(client, session)
        body = {
            "device_id": run["device_id"],
            "command_id": run["command_id"],
            "offset": 0,
            "content": "same\n",
        }

        first = client.post(f"/agent/runs/{run['id']}/log-chunks", headers=auth_headers(), json=body)
        replay = client.post(f"/agent/runs/{run['id']}/log-chunks", headers=auth_headers(), json=body)

        assert first.status_code == 200
        assert replay.status_code == 200
        assert replay.json()["duplicate"] is True
        assert client.get(f"/runs/{run['id']}/log").text == "same\n"


def test_log_offset_gap_returns_current_offset(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    isolate_jobs_dir(monkeypatch, tmp_path)
    for client, session in make_client():
        run = create_bound_run(client, session)

        response = client.post(
            f"/agent/runs/{run['id']}/log-chunks",
            headers=auth_headers(),
            json={
                "device_id": run["device_id"],
                "command_id": run["command_id"],
                "offset": 10,
                "content": "gap",
            },
        )

        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "run_log_offset_mismatch"
        assert response.json()["detail"]["current_offset"] == 0


def test_run_log_uploader_sends_only_new_content(tmp_path) -> None:
    class FakeClient:
        def __init__(self):
            self.uploads = []

        def upload_run_log_chunk(self, run_id, payload):
            self.uploads.append((run_id, payload.offset, payload.content))
            return {"current_offset": payload.offset + len(payload.content.encode("utf-8"))}

    log_file = tmp_path / "run.log"
    tracker = RunLogUploadTracker(log_file)
    client = FakeClient()
    uploader = RunLogUploader(client=client, tracker=tracker)

    for text in ("one\n", "two\n", "three\n"):
        with log_file.open("ab") as handle:
            handle.write(text.encode("utf-8"))
        uploader.upload_new_content(run_id=1, device_id="device-a", command_id="cmd-1")

    assert client.uploads == [
        (1, 0, "one\n"),
        (1, 4, "two\n"),
        (1, 8, "three\n"),
    ]
