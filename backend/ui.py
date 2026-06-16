from __future__ import annotations

from html import escape
from typing import Iterable, Optional

from backend.models import Project, Task, TaskStatus, TaskType


def page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; background: #f7f7f5; color: #1f2933; }}
    header {{ background: #1f2933; color: white; padding: 16px 24px; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
    section {{ margin-bottom: 28px; }}
    h1, h2, h3 {{ margin: 0 0 12px; }}
    table {{ width: 100%; border-collapse: collapse; background: white; }}
    th, td {{ border-bottom: 1px solid #e4e7eb; padding: 9px 10px; text-align: left; vertical-align: top; }}
    th {{ background: #f0f2f4; font-weight: 600; }}
    input, select, textarea {{ box-sizing: border-box; width: 100%; padding: 8px; border: 1px solid #cbd2d9; border-radius: 4px; font: inherit; }}
    textarea {{ min-height: 120px; resize: vertical; }}
    button, .button {{ display: inline-block; padding: 7px 12px; border: 0; border-radius: 4px; background: #2563eb; color: white; font: inherit; text-decoration: none; cursor: pointer; }}
    .button.secondary {{ background: #52606d; }}
    .button.danger {{ background: #c2410c; }}
    .grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }}
    .stack {{ display: grid; gap: 10px; }}
    .muted {{ color: #66788a; }}
    .prompt {{ max-width: 420px; white-space: pre-wrap; }}
    .actions {{ display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }}
    @media (max-width: 760px) {{ main {{ padding: 16px; }} .grid {{ grid-template-columns: 1fr; }} table {{ display: block; overflow-x: auto; }} }}
  </style>
</head>
<body>
  <header><h1>Codex Remote Runner</h1></header>
  <main>{body}</main>
</body>
</html>"""


def dashboard(
    *,
    projects: Iterable[Project],
    tasks: Iterable[Task],
    selected_project_id: Optional[int],
    selected_status: Optional[TaskStatus],
    limit: int,
) -> str:
    project_list = list(projects)
    task_list = list(tasks)
    body = "\n".join(
        [
            render_task_form(project_list),
            render_task_filters(
                project_list,
                selected_project_id=selected_project_id,
                selected_status=selected_status,
                limit=limit,
            ),
            render_tasks_table(task_list),
            render_projects_table(project_list),
        ]
    )
    return page("Codex Remote Runner", body)


def render_task_form(projects: list[Project]) -> str:
    options = "\n".join(
        f'<option value="{project.id}">{escape(project.name)}</option>'
        for project in projects
        if project.id is not None and project.enabled
    )
    disabled_note = ""
    if not options:
        disabled_note = '<p class="muted">暂无可用项目。请先通过 API 创建 enabled=true 的项目。</p>'
    task_type_options = "\n".join(
        f'<option value="{task_type.value}">{task_type.value}</option>'
        for task_type in TaskType
    )
    return f"""
<section>
  <h2>创建任务</h2>
  {disabled_note}
  <form class="stack" method="post" action="/ui/tasks">
    <label>项目
      <select name="project_id" required>{options}</select>
    </label>
    <label>任务类型
      <select name="task_type" required>{task_type_options}</select>
    </label>
    <label>Prompt
      <textarea name="prompt" required></textarea>
    </label>
    <label>超时秒数
      <input name="timeout_seconds" type="number" min="30" max="21600" value="7200" required>
    </label>
    <div><button type="submit">创建</button></div>
  </form>
</section>"""


def render_task_filters(
    projects: list[Project],
    *,
    selected_project_id: Optional[int],
    selected_status: Optional[TaskStatus],
    limit: int,
) -> str:
    project_options = ['<option value="">全部项目</option>']
    for project in projects:
        if project.id is None:
            continue
        selected = " selected" if project.id == selected_project_id else ""
        project_options.append(
            f'<option value="{project.id}"{selected}>{escape(project.name)}</option>'
        )

    status_options = ['<option value="">全部状态</option>']
    for status in TaskStatus:
        selected = " selected" if status == selected_status else ""
        status_options.append(
            f'<option value="{status.value}"{selected}>{status.value}</option>'
        )

    return f"""
<section>
  <h2>任务列表</h2>
  <form class="grid" method="get" action="/">
    <label>项目
      <select name="project_id">{"".join(project_options)}</select>
    </label>
    <label>状态
      <select name="status">{"".join(status_options)}</select>
    </label>
    <label>数量
      <input name="limit" type="number" min="1" max="200" value="{limit}">
    </label>
    <div><button type="submit">筛选</button></div>
  </form>
</section>"""


def render_tasks_table(tasks: list[Task]) -> str:
    if not tasks:
        return '<section><p class="muted">暂无任务。</p></section>'
    rows = "\n".join(render_task_row(task) for task in tasks)
    return f"""
<section>
  <table>
    <thead>
      <tr>
        <th>ID</th>
        <th>项目</th>
        <th>类型</th>
        <th>状态</th>
        <th>Prompt</th>
        <th>更新时间</th>
        <th>操作</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</section>"""


def render_task_row(task: Task) -> str:
    task_id = task.id or 0
    return f"""
<tr>
  <td>{task_id}</td>
  <td>{task.project_id}</td>
  <td>{task.task_type.value}</td>
  <td>{task.status.value}</td>
  <td class="prompt">{escape(task.prompt)}</td>
  <td>{escape(task.updated_at.isoformat())}</td>
  <td><a class="button secondary" href="/ui/tasks/{task_id}">详情</a></td>
</tr>"""


def render_projects_table(projects: list[Project]) -> str:
    rows = "\n".join(
        f"""
<tr>
  <td>{project.id}</td>
  <td>{escape(project.name)}</td>
  <td>已配置</td>
  <td>{'是' if project.enabled else '否'}</td>
</tr>"""
        for project in projects
    )
    if not rows:
        rows = '<tr><td colspan="4" class="muted">暂无项目。</td></tr>'
    return f"""
<section>
  <h2>项目列表</h2>
  <table>
    <thead>
      <tr><th>ID</th><th>名称</th><th>路径</th><th>启用</th></tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</section>"""


def task_detail(task: Task) -> str:
    task_id = task.id or 0
    cancel_button = ""
    if task.status in {TaskStatus.PENDING, TaskStatus.RUNNING}:
        cancel_button = f"""
    <form method="post" action="/ui/tasks/{task_id}/cancel">
      <button class="danger" type="submit">取消</button>
    </form>"""
    body = f"""
<section>
  <div class="actions">
    <a class="button secondary" href="/">返回</a>
    <form method="post" action="/ui/tasks/{task_id}/rerun">
      <button type="submit">重跑</button>
    </form>
    {cancel_button}
  </div>
</section>
<section>
  <h2>任务 #{task_id}</h2>
  <table>
    <tbody>
      <tr><th>项目</th><td>{task.project_id}</td></tr>
      <tr><th>类型</th><td>{task.task_type.value}</td></tr>
      <tr><th>状态</th><td>{task.status.value}</td></tr>
      <tr><th>取消请求</th><td>{'是' if task.cancel_requested else '否'}</td></tr>
      <tr><th>Runner PID</th><td>{'' if task.runner_pid is None else task.runner_pid}</td></tr>
      <tr><th>超时</th><td>{task.timeout_seconds}</td></tr>
      <tr><th>退出码</th><td>{'' if task.exit_code is None else task.exit_code}</td></tr>
      <tr><th>错误</th><td>{escape(task.error_message or '')}</td></tr>
      <tr><th>创建时间</th><td>{escape(task.created_at.isoformat())}</td></tr>
      <tr><th>更新时间</th><td>{escape(task.updated_at.isoformat())}</td></tr>
      <tr><th>Prompt</th><td class="prompt">{escape(task.prompt)}</td></tr>
    </tbody>
  </table>
</section>
<section>
  <h2>产物</h2>
  <div class="actions">
    <a class="button secondary" href="/tasks/{task_id}/log">Log</a>
    <a class="button secondary" href="/tasks/{task_id}/result">Result</a>
    <a class="button secondary" href="/tasks/{task_id}/diff">Diff</a>
    <a class="button secondary" href="/tasks/{task_id}/artifacts/git-status">Git Status</a>
    <a class="button secondary" href="/tasks/{task_id}/artifacts/report">Report</a>
  </div>
</section>"""
    return page(f"任务 #{task_id}", body)
