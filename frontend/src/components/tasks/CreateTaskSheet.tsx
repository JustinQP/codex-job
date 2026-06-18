import { useState } from "react";

import type { Project, Runner, TaskTemplate, TaskType } from "../../api/types";
import { Button } from "../common/Button";

type CreateTaskSheetProps = {
  projects: Project[];
  runners: Runner[];
  templates: TaskTemplate[];
  onSubmit: (payload: {
    project_id: number;
    prompt: string;
    timeout_seconds: number;
    task_type: TaskType;
    assigned_runner_id?: string | null;
    model?: string | null;
    reasoning_effort?: string | null;
    sandbox?: string | null;
  }) => Promise<void>;
};

export function CreateTaskSheet({
  projects,
  runners,
  templates,
  onSubmit
}: CreateTaskSheetProps) {
  const [projectId, setProjectId] = useState(projects[0]?.id ?? 0);
  const [prompt, setPrompt] = useState("");
  const [taskType, setTaskType] = useState<TaskType>("IMPLEMENT");
  const [runnerId, setRunnerId] = useState("");
  const [timeoutSeconds, setTimeoutSeconds] = useState(7200);
  const [model, setModel] = useState("");
  const [reasoningEffort, setReasoningEffort] = useState("");
  const [sandbox, setSandbox] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const selectedProject = projects.find((project) => project.id === projectId);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!projectId || !prompt.trim()) return;
    setSubmitting(true);
    try {
      await onSubmit({
        project_id: projectId,
        prompt: prompt.trim(),
        timeout_seconds: timeoutSeconds,
        task_type: taskType,
        assigned_runner_id: runnerId || selectedProject?.default_runner_id || null,
        model: model || selectedProject?.default_model || null,
        reasoning_effort: reasoningEffort || selectedProject?.default_reasoning_effort || null,
        sandbox: sandbox || selectedProject?.default_sandbox || null
      });
      setPrompt("");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="task-form-sheet" onSubmit={handleSubmit}>
      <label>
        项目
        <select value={projectId} onChange={(event) => setProjectId(Number(event.target.value))}>
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        任务类型
        <select value={taskType} onChange={(event) => setTaskType(event.target.value as TaskType)}>
          {(templates.length ? templates : [{ task_type: "IMPLEMENT" as TaskType, title: "实现", template: "" }]).map((template) => (
            <option key={template.task_type} value={template.task_type}>
              {template.task_type} {template.title}
            </option>
          ))}
        </select>
      </label>
      <label>
        Prompt
        <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} />
      </label>
      <label>
        Runner
        <select value={runnerId} onChange={(event) => setRunnerId(event.target.value)}>
          <option value="">项目默认 / 自动分配</option>
          {runners.map((runner) => (
            <option key={runner.runner_id} value={runner.runner_id}>
              {runner.runner_id} · {runner.status}
            </option>
          ))}
        </select>
      </label>
      <label>
        超时秒数
        <input
          min={30}
          max={21600}
          type="number"
          value={timeoutSeconds}
          onChange={(event) => setTimeoutSeconds(Number(event.target.value))}
        />
      </label>
      <details>
        <summary>高级参数</summary>
        <label>
          model
          <input value={model} onChange={(event) => setModel(event.target.value)} />
        </label>
        <label>
          reasoning_effort
          <input value={reasoningEffort} onChange={(event) => setReasoningEffort(event.target.value)} />
        </label>
        <label>
          sandbox
          <input value={sandbox} onChange={(event) => setSandbox(event.target.value)} />
        </label>
      </details>
      <Button disabled={!prompt.trim() || !projectId || submitting} type="submit" variant="primary">
        {submitting ? "提交中" : "创建任务"}
      </Button>
    </form>
  );
}
