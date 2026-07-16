import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { dirname, extname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const project = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const assets = resolve(project, "../../templates/progress-dashboard");
const port = 4175;
const phaseKeys = ["prepare", "build", "integrate", "final_verify", "ship"];
const phaseLabels = ["Prepare", "Build", "Integrate", "Final verify", "Ship"];
const phaseStatuses = ["complete", "active", "active", "active", "waiting"];
const phases = phaseKeys.map((key, index) => ({
  key,
  label: phaseLabels[index],
  status: phaseStatuses[index],
  policyShare: [0.05, 0.35, 0.25, 0.2, 0.15][index],
  provedShare: [1, 0.82, 0.54, 0.22, 0][index],
  accessibleLabel: `${phaseLabels[index]}: ${phaseStatuses[index]}`,
}));

const projection = {
  schema: "gauntlet/live-epic-progress/v1",
  generatedAt: "2030-01-02T16:15:00Z",
  launch: { id: "visual-check" },
  epics: [{
    identity: { launchId: "visual-check", epicId: "EPIC-CHECK", runId: "run-check", title: "Autonomous Epic execution", terminalOutcome: null },
    time: { startedAt: "2030-01-02T15:00:00Z", currentAt: "2030-01-02T16:15:00Z", updatedAt: "2030-01-02T16:14:55Z", terminalAt: null, started: "10:00 AM", current: "11:15 AM", elapsed: "1h 15m", updated: "Updated just now" },
    presentation: { state: "parallel_work", transitionId: "visual-check-1" },
    health: { status: "healthy", reason: "controller_observation", actionRequired: false },
    freshness: { observedAt: "2030-01-02T16:14:55Z", coverage: "complete", stale: false, label: "Updated just now" },
    phases,
    now: { reason: "current_operation", label: "Building + integrating" },
    next: { reason: "critical_path", label: "Complete final verification", actionId: null },
    agents: {
      activeCount: 11,
      summary: "4 building · 3 integrating · 4 verifying",
      byPhase: [{ phase: "build", count: 4 }, { phase: "integrate", count: 3 }, { phase: "final_verify", count: 4 }],
      details: Array.from({ length: 11 }, (_, index) => ({ id: `agent-${index + 1}`, label: `Agent ${String(index + 1).padStart(2, "0")}`, phase: index < 4 ? "build" : index < 7 ? "integrate" : "final_verify", phaseLabel: index < 4 ? "Building" : index < 7 ? "Integrating" : "Verifying", status: "active", elapsed: `${index + 2}m`, modelUsage: index % 2 ? "Terra · 140K" : "Sol · 220K" })),
    },
    eta: { status: "available", likelyFinishAt: "2030-01-02T16:45:00Z", remainingSeconds: 1800, confidence: "medium", estimatorVersion: "eta-v1", label: "Likely done 11:45 AM", detail: "~30 min left · medium confidence" },
    usage: { totalTokens: 1840000, totalLabel: "1.84M", observedThrough: "request-cursor", freshness: "Observed just now", coverage: "complete", models: [{ model: "Sol", tokens: 1340000, label: "1.34M" }, { model: "Terra", tokens: 500000, label: "500K" }] },
    pricing: { status: "complete", registryVersion: "pricing-v1", effectiveDate: "2030-01-01", amountUsd: 18.76, amountLabel: "API equivalent ~$18.76", disclaimer: "comparison only — not your bill or savings", components: [{ label: "Registry", value: "pricing-v1" }, { label: "Coverage", value: "Complete" }], unpricedReasons: [] },
    details: { progressPolicy: "fixed-v1", denominatorDigest: "sha256:visual", plannedProgress: "52%", units: [{ id: "unit-1", label: "Integrate change", phase: "integrate", status: "running" }, { id: "unit-2", label: "Final verification", phase: "final_verify", status: "running" }], timing: [{ label: "Estimator", value: "eta-v1" }], coverage: [{ label: "Lineage", value: "Complete" }, { label: "Requests", value: "Complete" }], recovery: [] },
    actions: [],
  }],
};

const routes = new Map([
  ["/", "index.html"],
  ["/assets/app.js", "assets/app.js"],
  ["/assets/app.css", "assets/app.css"],
]);
const contentTypes = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8" };

createServer(async (request, response) => {
  if (request.url === "/api/progress") {
    if (request.headers.authorization !== "Bearer visual-check") {
      response.writeHead(401, { "Cache-Control": "no-store" });
      response.end();
      return;
    }
    response.writeHead(200, { "Content-Type": "application/json", "Cache-Control": "no-store", ETag: '"visual-check-1"' });
    response.end(JSON.stringify(projection));
    return;
  }
  const file = routes.get(request.url ?? "");
  if (!file) {
    response.writeHead(404);
    response.end();
    return;
  }
  const body = await readFile(resolve(assets, file));
  response.writeHead(200, { "Content-Type": contentTypes[extname(file)], "Cache-Control": "no-store" });
  response.end(body);
}).listen(port, "127.0.0.1", () => {
  process.stdout.write(`visual smoke server http://127.0.0.1:${port}/#capability=visual-check\n`);
});
