import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App, { describeMaterialDelta } from "./App";
import { ProgressRoot } from "./main";
import {
  PROJECTION_SCHEMA,
  type EpicProgress,
  type PhaseKey,
  type PhaseStatus,
  type PresentationState,
  type ProgressProjection,
} from "./contract";

const phaseOrder: PhaseKey[] = ["prepare", "build", "integrate", "final_verify", "ship"];
const phaseNames = ["Prepare", "Build", "Integrate", "Verify", "Ship"];

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
      },
      usage: {
        totalTokens: 1357900,
        totalLabel: "1.36M",
        freshness: "Observed just now",
        coverage: "complete",
        models: [
          { model: "gpt-5.6-sol", tokens: 925000 },
          { model: "gpt-5.6-terra", tokens: 340000 },
          { model: "gpt-5.6-luna", tokens: 92900 },
        ],
      },
      pricing: {
        status: "complete",
        amountUsd: 17.25,
        amountLabel: "API equivalent ~$17.25",
        disclaimer: "comparison only — not your bill or savings",
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
    vi.unstubAllGlobals();
    vi.useRealTimers();
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

  it("keeps agent usage aggregate and never discloses individual agents", async () => {
    await render(makeProjection("parallel_work", 11));
    expect(container.textContent).toContain("11 agents active");
    expect(container.textContent).not.toContain("Worker 11");
    expect(container.textContent).not.toContain("Sol");

    const details = container.querySelector("details")!;
    await act(async () => {
      details.open = true;
      details.dispatchEvent(new Event("toggle"));
    });
    expect(container.textContent).not.toContain("Worker 11");
    expect(container.textContent).toContain("Sol");
    expect(container.textContent).toContain("Terra");
    expect(container.textContent).toContain("Luna");
    expect(container.textContent).not.toContain("Lineage");
    expect(container.textContent).not.toContain("Integrate change");
    expect(container.querySelectorAll("[data-model-icon]")).toHaveLength(3);
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
    expect(text).not.toContain("Likely done");
    expect(text).not.toContain("remaining");
  });

  it("uses the phase policy with a readable Prepare minimum", async () => {
    await render(makeProjection());
    const phaseSection = container.querySelector('[aria-label="Planned execution progress"]')!;
    const rail = phaseSection.querySelector("div") as HTMLElement;
    const labels = phaseSection.querySelector("ol") as HTMLElement;
    const expected = "minmax(64px, 0.05fr) minmax(0, 0.35fr) minmax(0, 0.25fr) minmax(0, 0.2fr) minmax(0, 0.15fr)";
    expect(rail.style.gridTemplateColumns).toBe(expected);
    expect(labels.style.gridTemplateColumns).toBe(expected);
  });

  it("does not turn unavailable usage into an observed zero", async () => {
    const projection = makeProjection();
    projection.epics[0].usage = {
      ...projection.epics[0].usage,
      totalTokens: 0,
      totalLabel: "Unavailable",
      coverage: "unavailable",
      freshness: "Unavailable",
    };
    await render(projection);
    expect(container.textContent).toContain("Unavailable");
    expect(container.textContent).not.toContain("0 tokens used");
  });

  it("retains last observed token usage while recovering", async () => {
    const projection = makeProjection("recovering");
    projection.epics[0].usage = {
      ...projection.epics[0].usage,
      coverage: "partial",
      freshness: "Last observed 10:59 AM",
    };
    await render(projection);
    expect(container.textContent).toContain("1.36M tokens used");
    expect(container.textContent).toContain("Last observed 10:59 AM");
    expect(container.textContent).not.toContain("Usage temporarily unavailable");
  });

  it("labels partial pricing as a lower bound", async () => {
    const projection = makeProjection();
    projection.epics[0].pricing = {
      status: "lower_bound",
      amountUsd: 14.2,
      amountLabel: "$14.20",
      disclaimer: "comparison only — not your bill or savings",
    };
    await render(projection);
    expect(container.textContent).toContain("Priced token subtotal ≥$14.20");
    expect(container.textContent).not.toContain("API equivalent ~$14.20");
  });

  it.each(["failed", "stopped"] as const)("shows the exact %s terminal outcome without celebration", async (outcome) => {
    const projection = makeProjection("recovering");
    projection.epics[0].identity.terminalOutcome = outcome;
    projection.epics[0].now.label = outcome === "failed" ? "Implementation failed" : "Implementation stopped";
    await render(projection);
    expect(container.textContent).toContain(outcome === "failed" ? "Failed" : "Stopped");
    expect(container.textContent).toContain(projection.epics[0].now.label);
    expect(container.textContent).not.toContain("CompleteLive and verified");
  });

  it("shows a useful unavailable state when the capability is missing", async () => {
    await act(async () => root.render(<ProgressRoot capability={null} />));
    expect(container.textContent).toContain("Live progress is unavailable");
    expect(container.textContent).toContain("Implementation continues in the main task");
  });

  it("shows a transport failure instead of an indefinitely blank loading surface", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    await act(async () => {
      root.render(<ProgressRoot capability="test-capability" />);
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(container.textContent).toContain("Live progress is unavailable");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_500);
    });
    expect(container.textContent).toContain("Live progress is unavailable");
    expect(container.textContent).not.toContain("Showing the last confirmed update");
    vi.useRealTimers();
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
