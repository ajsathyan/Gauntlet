import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import App, { describeMaterialDelta } from "./App";
import {
  PROJECTION_SCHEMA,
  type EpicProgress,
  type PhaseKey,
  type PhaseStatus,
  type PresentationState,
  type ProgressProjection,
} from "./contract";

const phaseOrder: PhaseKey[] = ["prepare", "build", "integrate", "final_verify", "ship"];
const phaseNames = ["Prepare", "Build", "Integrate", "Final verify", "Ship"];

function phases(statuses: PhaseStatus[]) {
  return phaseOrder.map((key, index) => ({
    key,
    label: phaseNames[index],
    status: statuses[index],
    policyShare: [0.05, 0.35, 0.25, 0.2, 0.15][index],
    provedShare: statuses[index] === "complete" ? 1 : statuses[index] === "active" ? 0.5 : 0,
    accessibleLabel: `${phaseNames[index]}: ${statuses[index]}`,
  }));
}

const presentationCases: Array<{
  state: PresentationState;
  statuses: PhaseStatus[];
  health: EpicProgress["health"]["status"];
}> = [
  { state: "starting", statuses: ["active", "waiting", "waiting", "waiting", "waiting"], health: "healthy" },
  { state: "healthy_build", statuses: ["complete", "active", "waiting", "waiting", "waiting"], health: "healthy" },
  { state: "parallel_work", statuses: ["complete", "active", "active", "active", "waiting"], health: "healthy" },
  { state: "return_update", statuses: ["complete", "complete", "active", "active", "waiting"], health: "healthy" },
  { state: "recovering", statuses: ["complete", "complete", "active", "waiting", "waiting"], health: "recovering" },
  { state: "needs_user", statuses: ["complete", "complete", "complete", "active", "waiting"], health: "needs_user" },
  { state: "ready_to_merge", statuses: ["complete", "complete", "complete", "complete", "active"], health: "healthy" },
  { state: "ready_to_deploy", statuses: ["complete", "complete", "complete", "complete", "active"], health: "healthy" },
  { state: "shipped", statuses: ["complete", "complete", "complete", "complete", "complete"], health: "healthy" },
];

function makeProjection(
  state: PresentationState = "parallel_work",
  activeAgents = 11,
): ProgressProjection {
  const presentation = presentationCases.find((item) => item.state === state)!;
  return {
    schema: PROJECTION_SCHEMA,
    generatedAt: "2030-01-02T16:15:00Z",
    launch: { id: "launch-test" },
    epics: [{
      identity: {
        launchId: "launch-test",
        epicId: "EPIC-TEST",
        runId: "run-test",
        title: "Verified release workflow",
        terminalOutcome: state === "shipped" ? "succeeded" : null,
      },
      time: {
        startedAt: "2030-01-02T15:00:00Z",
        currentAt: "2030-01-02T16:15:00Z",
        updatedAt: "2030-01-02T16:14:55Z",
        terminalAt: state === "shipped" ? "2030-01-02T16:15:00Z" : null,
        started: "10:00 AM",
        current: "11:15 AM",
        elapsed: "1h 15m",
        updated: "Updated just now",
      },
      presentation: { state, transitionId: `transition-${state}` },
      health: {
        status: presentation.health,
        reason: "controller_observation",
        actionRequired: presentation.health === "needs_user",
      },
      freshness: {
        observedAt: "2030-01-02T16:14:55Z",
        coverage: "complete",
        stale: false,
        label: "Updated just now",
      },
      phases: phases(presentation.statuses),
      now: { reason: "current_operation", label: "Integrating verified changes" },
      next: { reason: "critical_path", label: "Complete final verification", actionId: null },
      agents: {
        activeCount: activeAgents,
        summary: "4 building · 3 integrating · 4 verifying",
        byPhase: [
          { phase: "build", count: 4 },
          { phase: "integrate", count: 3 },
          { phase: "final_verify", count: 4 },
        ],
        details: Array.from({ length: activeAgents }, (_, index) => ({
          id: `agent-${index + 1}`,
          label: `Worker ${index + 1}`,
          phase: index < 4 ? "build" : index < 7 ? "integrate" : "final_verify",
          phaseLabel: index < 4 ? "Building" : index < 7 ? "Integrating" : "Verifying",
          status: "active" as const,
          elapsed: `${index + 2}m`,
          modelUsage: "Model usage observed",
        })),
      },
      eta: {
        status: presentation.health === "needs_user" ? "waiting_on_user" : "available",
        likelyFinishAt: "2030-01-02T16:45:00Z",
        remainingSeconds: 1800,
        confidence: "medium",
        estimatorVersion: "eta-v1",
        label: presentation.health === "needs_user" ? "Waiting on you" : "Likely done 11:45 AM",
        detail: presentation.health === "needs_user" ? null : "~30 min left · medium confidence",
      },
      usage: {
        totalTokens: 1357900,
        totalLabel: "1.36M",
        observedThrough: "request-cursor",
        freshness: "Observed just now",
        coverage: "complete",
        models: [{
          model: "model-alpha",
          tokens: 1357900,
          label: "1.36M",
          inputTokens: 1000000,
          cachedInputTokens: 200000,
          outputTokens: 357900,
          reasoningOutputTokens: 157900,
        }],
      },
      pricing: {
        status: "complete",
        registryVersion: "pricing-v1",
        effectiveDate: "2030-01-01",
        amountUsd: 17.25,
        amountLabel: "API equivalent ~$17.25",
        disclaimer: "comparison only — not your bill or savings",
        components: [{ label: "Registry", value: "pricing-v1" }],
        unpricedReasons: [],
      },
      details: {
        progressPolicy: "fixed-v1",
        denominatorDigest: "sha256:test",
        plannedProgress: "52%",
        units: [{ id: "unit-1", label: "Integrate change", phase: "integrate", status: "running" }],
        timing: [{ label: "Estimator", value: "eta-v1" }],
        coverage: [{ label: "Lineage", value: "Complete" }],
        recovery: [],
      },
      actions: [],
    }],
  };
}

describe("production progress experience", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    localStorage.clear();
  });

  async function render(projection: ProgressProjection) {
    await act(async () => root.render(<App projection={projection} />));
  }

  it.each(presentationCases)("renders $state from projection props", async ({ state }) => {
    await render(makeProjection(state));
    const card = container.querySelector("article");
    expect(card?.getAttribute("data-presentation")).toBe(state);
    expect(container.querySelector("h1")?.textContent).toBe("Verified release workflow");
    expect(container.querySelectorAll("ol li")).toHaveLength(5);
    expect(container.textContent).toContain("Integrating verified changes");
    expect(container.textContent).toContain("Complete final verification");
  });

  it("keeps the default card aggregate and discloses individual agents on demand", async () => {
    await render(makeProjection("parallel_work", 11));
    expect(container.textContent).toContain("11 agents active");
    expect(container.textContent).not.toContain("Worker 11");
    expect(container.textContent).not.toContain("52%");

    const details = container.querySelector("details")!;
    await act(async () => {
      details.open = true;
      details.dispatchEvent(new Event("toggle"));
    });
    expect(container.textContent).toContain("Worker 11");
    expect(container.textContent).toContain("52%");
  });

  it("contains no preview controls or fixture shell copy", async () => {
    await render(makeProjection());
    const text = container.textContent ?? "";
    for (const forbidden of [
      "Play all",
      "Pause sequence",
      "Choose a state",
      "Working prototype",
      "Preview a progress state",
      " / 09",
    ]) {
      expect(text.toLowerCase()).not.toContain(forbidden.toLowerCase());
    }
    expect(container.querySelector("nav")).toBeNull();
    expect(container.querySelector("select")).toBeNull();
  });

  it("derives return continuity only from a material transition", () => {
    const previous = {
      epicId: "EPIC-TEST",
      transitionId: "transition-a",
      checkedAt: "2030-01-02T16:00:00Z",
      health: "healthy" as const,
      phases: [
        { key: "build" as const, status: "active" as const },
        { key: "integrate" as const, status: "waiting" as const },
      ],
      now: "Building",
      next: "Integrate",
    };
    expect(describeMaterialDelta(previous, previous)).toBeNull();
    expect(describeMaterialDelta(previous, {
      ...previous,
      transitionId: "transition-b",
      phases: [
        { key: "build", status: "complete" },
        { key: "integrate", status: "active" },
      ],
    })?.changes).toBe("Build completed · Integrate started");
  });
});
