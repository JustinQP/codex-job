import { useCallback, useEffect, useState } from "react";

import { cleanupAppThreads, recoverStaleAppTurns } from "../../api/appThreads";
import { getHealth } from "../../api/health";
import type { Health } from "../../api/types";
import { useLocalStorage } from "../../hooks/useLocalStorage";
import { API_TOKEN_KEY } from "../../state/storage";
import { errorText } from "../../utils/error";
import { Button } from "../common/Button";
import type { PageProps } from "../types";

export function SettingsPage({ showToast }: PageProps) {
  const [token, setToken] = useLocalStorage(API_TOKEN_KEY, "");
  const [draftToken, setDraftToken] = useState(token);
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState("");

  const loadDiagnostics = useCallback(async () => {
    setError("");
    try {
      const healthData = await getHealth();
      setHealth(healthData);
    } catch (err) {
      setError(errorText(err));
    }
  }, []);

  useEffect(() => {
    void loadDiagnostics();
  }, [loadDiagnostics]);

  async function handleRecoverStale() {
    try {
      const result = await recoverStaleAppTurns();
      showToast(`恢复 ${result.recovered_count} 个 turn`, "success");
    } catch (err) {
      showToast(errorText(err), "error");
    }
  }

  async function handleCleanup(status: string) {
    if (!window.confirm(`确认将 ${status} AppThread 标记为 archived？`)) return;
    try {
      const result = await cleanupAppThreads(status);
      showToast(`清理 ${result.archived_count} 个会话`, "success");
    } catch (err) {
      showToast(errorText(err), "error");
    }
  }

  return (
    <section className="page active" id="tab-settings">
      <div className="profile-hero">
        <div className="profile-avatar">我</div>
        <div>
          <h2>移动控制台</h2>
          <p>v2.0.0 multi-device control plane</p>
        </div>
      </div>

      <div className="settings-grid">
        <div className="wechat-form stack">
          <h3>API Token</h3>
          <label>
            Token
            <input
              placeholder="保存后页面请求会携带 X-API-Token"
              type="password"
              value={draftToken}
              onChange={(event) => setDraftToken(event.target.value)}
            />
          </label>
          <div className="task-actions">
            <Button
              onClick={() => {
                setToken(draftToken.trim());
                showToast("Token 已保存", "success");
              }}
              variant="primary"
            >
              保存 Token
            </Button>
            <Button
              onClick={() => {
                setDraftToken("");
                setToken("");
                showToast("Token 已清空", "success");
              }}
              variant="secondary"
            >
              清空
            </Button>
          </div>
          <span className="muted">当前状态：{token ? "configured" : "not configured"}</span>
        </div>

        <div className="wechat-section stack">
          <div className="section-title-row">
            <h3>运行诊断</h3>
            <Button onClick={() => void loadDiagnostics()} variant="secondary">刷新</Button>
          </div>
          {error ? <div className="inline-warning">{error}</div> : null}
          <div className="wechat-list">
            <div className="wechat-row">
              <div className="wechat-avatar">M</div>
              <div className="wechat-row-main">
                <strong>control mode</strong>
                <span>{health?.execution_mode || "-"}</span>
              </div>
            </div>
            <div className="wechat-row">
              <div className="wechat-avatar">A</div>
              <div className="wechat-row-main">
                <strong>session mode</strong>
                <span>{health?.session_mode || "-"}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="wechat-form stack">
          <h3>维护操作</h3>
          <div className="task-actions">
            <Button onClick={handleRecoverStale} variant="secondary">recover stale AppTurn</Button>
            <Button onClick={() => void handleCleanup("CLOSED")} variant="secondary">
              清理 CLOSED
            </Button>
            <Button onClick={() => void handleCleanup("ERROR")} variant="secondary">
              清理 ERROR
            </Button>
          </div>
        </div>

        <div className="wechat-form stack">
          <h3>Smoke 命令</h3>
          <pre className="code-block">$env:API_TOKEN="dev-token"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000</pre>
        </div>

        <div className="wechat-form stack">
          <h3>当前限制</h3>
          <ul>
            <li>不支持审批 UI。</li>
            <li>不支持 diff UI。</li>
            <li>会话与运行统一通过 Device Agent 执行。</li>
          </ul>
        </div>
      </div>
    </section>
  );
}
