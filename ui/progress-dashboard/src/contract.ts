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
    updated: string;
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
    byPhase: Array<{
      phase: PhaseKey;
      count: number;
    }>;
    details: AgentProgress[];
  };
  eta: EtaProgress;
  usage: UsageProgress;
  pricing: PricingProgress;
  details: {
    progressPolicy: string;
    denominatorDigest?: string | null;
    plannedProgress?: string | null;
    units: ProgressUnit[];
    timing: DetailFact[];
    coverage: DetailFact[];
    recovery: DetailFact[];
  };
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

export interface AgentProgress {
  id: string;
  label: string;
  phase: PhaseKey;
  phaseLabel: string;
  status: "active" | "waiting" | "complete";
  elapsed?: string | null;
  modelUsage?: string | null;
}

export interface EtaProgress {
  status: "settling" | "available" | "waiting_on_user" | "unavailable";
  likelyFinishAt?: string | null;
  remainingSeconds?: number | null;
  confidence?: "low" | "medium" | "high" | null;
  estimatorVersion?: string | null;
  label: string;
  detail?: string | null;
  reason?: string | null;
}

export interface UsageProgress {
  totalTokens: number;
  totalLabel: string;
  observedThrough?: string | null;
  freshness: string;
  coverage: CoverageState;
  models: Array<{
    model: string;
    tokens: number;
    label: string;
    inputTokens?: number | null;
    cachedInputTokens?: number | null;
    outputTokens?: number | null;
    reasoningOutputTokens?: number | null;
  }>;
}

export interface PricingProgress {
  status: "complete" | "lower_bound" | "unavailable";
  registryVersion?: string | null;
  effectiveDate?: string | null;
  amountUsd?: number | null;
  amountLabel: string;
  disclaimer: string;
  components: DetailFact[];
  unpricedReasons: string[];
}

export interface ProgressUnit {
  id: string;
  label: string;
  phase: PhaseKey;
  status: "waiting" | "running" | "passed" | "failed" | "invalidated";
}

export interface DetailFact {
  label: string;
  value: string;
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
