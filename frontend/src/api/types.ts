export type TaskStatus = "PENDING" | "RUNNING" | "SUCCESS" | "FAILED" | "CANCELLED";

export type TaskType = "PLAN" | "IMPLEMENT" | "REVIEW" | "TEST_FIX" | "DOCS" | "COMMIT";

export type Project = {
  id: number;
  name: string;
  path_label: string;
  enabled: boolean;
  test_command?: string | null;
  smoke_check_command?: string | null;
  default_branch?: string | null;
  require_clean_worktree?: boolean | null;
  default_runner_id?: string | null;
  default_model?: string | null;
  default_reasoning_effort?: string | null;
  default_sandbox?: string | null;
  created_at: string;
  updated_at: string;
};

export type Runner = {
  runner_id: string;
  pid: number;
  hostname: string;
  supported_models?: string | null;
  status: string;
  registered_at: string;
  last_heartbeat_at: string;
  lease_expires_at?: string | null;
};

export type Task = {
  id: number;
  project_id: number;
  prompt: string;
  task_type: TaskType;
  status: TaskStatus;
  timeout_seconds: number;
  model?: string | null;
  reasoning_effort?: string | null;
  sandbox?: string | null;
  exit_code?: number | null;
  error_message?: string | null;
  cancel_requested: boolean;
  assigned_runner_id?: string | null;
  runner_id?: string | null;
  runner_pid?: number | null;
  lease_expires_at?: string | null;
  log_url: string;
  result_url: string;
  diff_url: string;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  finished_at?: string | null;
};

export type TaskTemplate = {
  task_type: TaskType;
  title: string;
  template: string;
};

export type AppThread = {
  id: number;
  project_id: number;
  title: string;
  bridge_thread_id?: string | null;
  app_thread_id?: string | null;
  status: string;
  last_error?: string | null;
  latest_assistant_final?: string | null;
  turn_count: number;
  created_at: string;
  updated_at: string;
};

export type AppTurn = {
  id: number;
  app_thread_id: number;
  user_message: string;
  assistant_final?: string | null;
  status: string;
  error_message?: string | null;
  bridge_turn_id?: string | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  duration_seconds?: number | null;
  event_summary?: Record<string, unknown> | null;
};

export type BridgeHealth = {
  status?: string;
  service?: string;
  mode?: string;
  sandbox?: string;
  threads?: number;
  token_required?: boolean;
  idle_timeout_seconds?: number;
  codex_command?: string;
  repo_root?: string;
  [key: string]: unknown;
};

export type AppThreadFinal = {
  app_thread_id: number;
  assistant_final?: string | null;
};

export type AppThreadEvents = {
  app_thread_id: number;
  latest_turn_id?: number | null;
  event_summary?: Record<string, unknown> | null;
};

export type AppTurnRecovery = {
  recovered_count: number;
  recovered_turn_ids: number[];
};

export type AppThreadCleanup = {
  archived_count: number;
  archived_thread_ids: number[];
};
