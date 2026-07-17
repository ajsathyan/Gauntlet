export const PROJECTION_SCHEMA = "gauntlet/live-epic-progress/v1" as const;

export type PresentationState =
  | "starting"
  | "healthy_build"
  | "parallel_work"
  | "return_update"
  | "recovering"
  | "needs_user"
  | "ready_to_merge"
  | "ready_to_deploy"
  | "shipped";

export type HealthStatus = "healthy" | "recovering" | "needs_user";
export type PhaseKey = "prepare" | "build" | "integrate" | "final_verify" | "ship";
export type PhaseStatus = "waiting" | "active" | "complete" | "invalidated";
export type CoverageState = "complete" | "partial" | "unavailable";

export interface ProgressProjection {
  schema: typeof PROJECTION_SCHEMA;
  generatedAt: string;
  launch: {
    id: string;
  };
  epics: EpicProgress[];
}

export interface EpicProgress {
  identity: {
    launchId: string;
    epicId: string;
    runId: string;
    title: string;
    terminalOutcome?: "succeeded" | "failed" | "stopped" | null;
  };
  time: {
    startedAt?: string | null;
    currentAt: string;
    updatedAt?: string | null;
    terminalAt?: string | null;
    started: string;
    current: string;
    elapsed: string;
  };
  presentation: {
    state: PresentationState;
    transitionId: string;
  };
  health: {
    status: HealthStatus;
    reason: string;
    actionRequired: boolean;
  };
  freshness: {
    observedAt?: string | null;
    coverage: CoverageState;
    stale: boolean;
    label: string;
  };
  phases: PhaseProgress[];
  now: ProgressCopy;
  next?: ProgressCopy | null;
  agents: {
    activeCount: number;
    summary: string;
  };
  usage: UsageProgress;
  pricing: PricingProgress;
  actions: SafeAction[];
}

export interface PhaseProgress {
  key: PhaseKey;
  label: string;
  status: PhaseStatus;
  policyShare: number;
  provedShare: number;
  accessibleLabel: string;
}

export interface ProgressCopy {
  reason: string;
  label: string;
  actionId?: string | null;
}

export interface UsageProgress {
  totalTokens: number;
  totalLabel: string;
  freshness: string;
  coverage: CoverageState;
  models: Array<{
    model: string;
    tokens: number;
  }>;
}

export interface PricingProgress {
  status: "complete" | "lower_bound" | "unavailable";
  amountUsd?: number | null;
  amountLabel: string;
  disclaimer: string;
}

export interface SafeAction {
  id: string;
  label: string;
  href: string;
}

export function isProgressProjection(value: unknown): value is ProgressProjection {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<ProgressProjection>;
  return (
    candidate.schema === PROJECTION_SCHEMA &&
    typeof candidate.generatedAt === "string" &&
    !!candidate.launch &&
    typeof candidate.launch.id === "string" &&
    Array.isArray(candidate.epics)
  );
}
