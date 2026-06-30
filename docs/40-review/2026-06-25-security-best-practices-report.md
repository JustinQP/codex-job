# Security Best Practices Review - 2026-06-25

## Executive Summary

本次按 `security-best-practices` 对 `F:\JustinKing\codex-job` 做了主动安全检查，范围覆盖 FastAPI 后端、Device Agent、React/Vite 前端、启动脚本和现有安全测试。

确认问题共 3 项，均已在本次修复中关闭：

- S-1：`API_TOKEN` 未配置时主线业务 API 默认开放。
- S-2：`API_TOKEN` 与 `AGENT_TOKEN` 可配置为相同值，导致控制面和 Agent 面令牌隔离失效。
- S-3：未绑定 Workspace 的本地 Project 路径在未配置 `PROJECT_PATH_WHITELIST` 时可接受任意本机目录。

未发现典型命令注入、SQL 注入、前端 raw HTML/DOM XSS sink、跨域凭据请求、文件读取越过 jobs 目录的确认漏洞。

## Scope And Evidence

技术栈证据：

- 后端：`requirements.txt` 使用 FastAPI、Uvicorn、SQLModel。
- 前端：`frontend/package.json` 使用 React、TypeScript、Vite。
- 控制面 API：`backend/main.py` 注册 `projects`、`runs`、`app_threads`、`devices`、`workspaces`、`agent` 路由。
- Agent 执行：`agent/codex_executor.py` 使用 `subprocess.Popen` 参数列表执行 Codex CLI；Git 命令使用参数列表和超时。

## High Severity

### S-1. Mainline API could run without configured API token

- Rule ID: FASTAPI-AUTH-001
- Severity: High
- Location: `backend/dependencies.py`, `require_api_token`, lines 8-14
- Previous evidence: `require_api_token()` 在 `API_TOKEN` 缺失时直接放行，主线 API 路由如 `backend/routers/projects.py:15-20` 和 `backend/routers/runs.py:20-25` 依赖该函数。
- Impact: 如果后端按 README 示例绑定 `0.0.0.0` 并暴露到可信边界之外，未设置 `API_TOKEN` 会使项目、运行、会话等控制 API 无认证可用。
- Fix applied: `API_TOKEN` 缺失时返回 `503 API token is not configured`，不再默认放行。
- Verification: `tests/test_security_api.py::test_mainline_api_requires_configured_api_token`。

### S-2. API and Agent token separation was not enforced

- Rule ID: FASTAPI-AUTH-001
- Severity: High
- Location: `backend/dependencies.py`, `require_api_token` and `require_agent_token`, lines 15-20 and 35-40
- Previous evidence: 文档要求 `API_TOKEN` 和 `AGENT_TOKEN` 必须不同，但代码只比较各自 header 和环境变量，未拒绝同值配置。
- Impact: 同一个令牌可以同时调用手机控制 API 和 Agent API，破坏控制面与 Agent 面隔离。
- Fix applied: 两个依赖均拒绝同值配置并返回 503；启动脚本也在启动前拒绝同值。
- Verification: `tests/test_security_api.py::test_api_and_agent_tokens_must_be_distinct`。

## Medium Severity

### S-3. Unbound local project paths lacked a mandatory allowlist

- Rule ID: FASTAPI-AUTHZ-001 / FASTAPI-INJECT-002 defense boundary
- Severity: Medium
- Location: `backend/services/project_service.py`, `create_project` and `validate_project_whitelist`, lines 33-40 and 75-94
- Previous evidence: 未绑定 Workspace 的 Project 使用请求体路径解析成本地目录；`PROJECT_PATH_WHITELIST` 未配置时返回 `None`，等同允许任意存在目录。
- Impact: 对于可访问主线 API 的调用者，项目创建可扩大到任意本机目录。后续 Run/Session 通过 Agent 在工作区执行 Codex，路径边界应默认收紧。
- Fix applied: 未绑定 Workspace 的本地路径必须配置 `PROJECT_PATH_WHITELIST`；空白名单和缺失白名单均拒绝。
- Verification: `tests/test_security_api.py::test_unbound_project_creation_requires_path_whitelist` 和既有 `test_project_path_whitelist_rejects_outside_path`。

## Low Severity / Operational Hardening

### S-4. Local app server launcher did not set or validate Agent token

- Rule ID: FASTAPI-AUTH-001 operational config
- Severity: Low
- Location: `scripts/start_app_server_stack.ps1`, lines 1-73
- Evidence: 脚本原先只接受并设置 `ApiToken`，没有设置 `AGENT_TOKEN`；后端 Agent API 在 `AGENT_TOKEN` 缺失时会返回 503。
- Impact: 使用脚本启动时容易形成“主线 API 可用、Agent API 不可用”的半配置状态；如果用户手动设置相同 token，也没有脚本级提示。
- Fix applied: 脚本新增 `-AgentToken`，设置 `$env:AGENT_TOKEN`，并在启动前校验两个 token 非空且不同。
- Verification: `tests/test_windows_agent_install_script.py` 间接覆盖脚本 token 约定；目标安全测试已通过。完整 PowerShell 脚本运行未执行，避免启动长期后台窗口。

## No Confirmed Finding

- CORS：未发现 `CORSMiddleware` 宽松配置。
- Debug：未发现 `FastAPI(debug=True)`。
- OpenAPI/docs：生产是否公开 `/docs` 未在本次修复中处理；该项目文档定位为本地或可信局域网单用户工具，保留为部署边界事项。
- Command injection：`agent/codex_executor.py` 使用参数列表调用 Codex 和 Git，未发现 `shell=True` 处理用户输入。
- File read traversal：`backend/routers/runs.py` 在读取 run artifact 前使用 `path.relative_to(db.JOBS_DIR.resolve())` 做目录边界检查。
- Frontend XSS sinks：`frontend/src` 未发现 `dangerouslySetInnerHTML`、`innerHTML`、`eval`、`postMessage`、`window.location` 等高风险 sink；`localStorage` 仅用于 UI 状态和 API token，风险与当前单用户本地工具定位一致。

## Verification Result

本次修复已执行以下验证：

```powershell
pytest -q tests/test_security_api.py tests/test_projects_api.py tests/test_windows_agent_install_script.py --basetemp data\.pytest-tmp-security-target -o cache_dir=data\.pytest-cache-security-target
python -m compileall backend agent scripts
pytest -q tests --basetemp data\.pytest-tmp-security-fixes -o cache_dir=data\.pytest-cache-security-fixes
cd frontend
npm.cmd run typecheck
npm.cmd run build
```

结果：

- 目标安全测试：10 passed，随后含 docs 的目标复测为 17 passed。
- `python -m compileall backend agent scripts`：通过。
- 全量后端测试：178 passed, 1 skipped。
- 前端 `npm.cmd run typecheck`：通过。
- 前端 `npm.cmd run build`：通过。
- `git diff --check`：无 whitespace error，仅提示 Windows 工作区 LF/CRLF 转换。

## Residual Risk

- 本项目仍是本地或可信局域网单用户工具，不应作为公网多用户控制面部署。
- Token 是工具级共享密钥，不提供用户级授权、轮换、审计或会话管理。
- 浏览器端 API token 存在 `localStorage`，如果前端发生 XSS，token 可被读取；本次未发现 raw HTML sink，但部署时仍应限制网络边界。
