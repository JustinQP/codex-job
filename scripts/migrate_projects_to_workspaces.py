from __future__ import annotations

from sqlmodel import Session, select
from pathlib import Path

from backend.db import engine, init_db
from backend.models import AppThread, Project, Task, WorkspaceBindingStatus


def main() -> None:
    init_db()
    with Session(engine) as session:
        projects = session.exec(select(Project).order_by(Project.id)).all()
        task_count = len(session.exec(select(Task)).all())
        app_thread_count = len(session.exec(select(AppThread)).all())
        bound = [
            project
            for project in projects
            if project.workspace_binding_status == WorkspaceBindingStatus.BOUND
        ]
        unbound = [
            project
            for project in projects
            if project.workspace_binding_status == WorkspaceBindingStatus.UNBOUND
        ]

        print(f"projects_total={len(projects)}")
        print(f"projects_bound={len(bound)}")
        print(f"projects_unbound={len(unbound)}")
        print(f"tasks_total={task_count}")
        print(f"app_threads_total={app_thread_count}")
        if unbound:
            print("unbound_projects:")
            for project in unbound:
                print(
                    f"- id={project.id} name={project.name!r} "
                    f"path_label={Path(project.path).name!r} "
                    f"default_runner_id={project.default_runner_id or ''}"
                )


if __name__ == "__main__":
    main()
