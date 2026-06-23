from __future__ import annotations

from threading import Event, Thread

from agent.api_client import AgentApiClient, AgentApiError
from agent.heartbeat import send_heartbeat
from agent.identity import AgentIdentity


class HeartbeatWorker:
    def __init__(
        self,
        *,
        client: AgentApiClient,
        identity: AgentIdentity,
        interval_seconds: float = 30.0,
    ) -> None:
        self.client = client
        self.identity = identity
        self.interval_seconds = max(1.0, interval_seconds)
        self._stop_event = Event()
        self._thread: Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(target=self._run, name="agent-heartbeat", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop_event.wait(self.interval_seconds):
            try:
                send_heartbeat(self.client, self.identity)
            except AgentApiError:
                continue
