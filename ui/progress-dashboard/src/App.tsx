import {
  AnimatePresence,
  LayoutGroup,
  animate,
  motion,
  useMotionValue,
  useMotionValueEvent,
} from "motion/react";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import type {
  EpicProgress,
  HealthStatus,
  PhaseKey,
  PhaseStatus,
  ProgressProjection,
  SafeAction,
} from "./contract";
import styles from "./App.module.css";

const healthLabels: Record<HealthStatus, string> = {
  healthy: "Healthy",
  recovering: "Recovering",
  needs_user: "Needs you",
};

const phaseLabels: Record<PhaseKey, string> = {
  prepare: "Prepare",
  build: "Build",
  integrate: "Integrate",
  final_verify: "Verify",
  ship: "Ship",
};

const phaseStatusLabels: Record<PhaseStatus, string> = {
  waiting: "Waiting",
  active: "Active",
  complete: "Complete",
  invalidated: "Invalidated",
};

type IconName = "agents" | "tokens" | "cost" | "arrow" | "check" | "sol" | "terra" | "luna";

function Icon({ name }: { name: IconName }) {
  const common = {
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.7,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };

  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" {...common}>
      {name === "agents" && (
        <>
          <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
          <circle cx="9" cy="7" r="4" />
          <path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
        </>
      )}
      {name === "tokens" && (
        <>
          <ellipse cx="12" cy="5" rx="7.5" ry="3" />
          <path d="M4.5 5v5c0 1.66 3.36 3 7.5 3s7.5-1.34 7.5-3V5" />
          <path d="M4.5 10v5c0 1.66 3.36 3 7.5 3s7.5-1.34 7.5-3v-5" />
          <path d="M4.5 15v4c0 1.66 3.36 3 7.5 3s7.5-1.34 7.5-3v-4" />
        </>
      )}
      {name === "cost" && (
        <>
          <rect x="2.5" y="5" width="19" height="14" rx="2.5" />
          <path d="M2.5 9h19M6 15h4" />
        </>
      )}
      {name === "arrow" && <path d="M5 12h13M13 7l5 5-5 5" />}
      {name === "check" && <path d="m6 12 4 4 8-9" />}
      {name === "sol" && (
        <>
          <circle cx="12" cy="12" r="3.5" />
          <path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M18.7 5.3l-2.1 2.1M7.4 16.6l-2.1 2.1" />
        </>
      )}
      {name === "terra" && (
        <>
          <circle cx="12" cy="12" r="8.5" />
          <path d="M3.5 12h17M12 3.5c2.4 2.3 3.7 5.1 3.7 8.5S14.4 18.2 12 20.5M12 3.5C9.6 5.8 8.3 8.6 8.3 12s1.3 6.2 3.7 8.5" />
        </>
      )}
      {name === "luna" && <path d="M19.5 15.2A8.5 8.5 0 0 1 8.8 4.5a8.5 8.5 0 1 0 10.7 10.7Z" />}
    </svg>
  );
}

function formatTokens(value: number) {
  if (value >= 10_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 100_000) return `${Math.round(value / 1_000)}K`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return Math.round(value).toLocaleString();
}

function AnimatedNumber({
  value,
  format,
}: {
  value: number;
  format: (next: number) => string;
}) {
  const motionValue = useMotionValue(value);
  const [display, setDisplay] = useState(value);

  useMotionValueEvent(motionValue, "change", setDisplay);
  useEffect(() => {
    const controls = animate(motionValue, value, {
      duration: 0.48,
      ease: [0.22, 1, 0.36, 1],
    });
    return () => controls.stop();
  }, [motionValue, value]);

  return <span>{format(display)}</span>;
}

function useCurrentTime(fallback: string) {
  const [current, setCurrent] = useState(() => formatLocalTime(new Date()) || fallback);

  useEffect(() => {
    const update = () => setCurrent(formatLocalTime(new Date()) || fallback);
    update();
    const timer = window.setInterval(update, 15_000);
    return () => window.clearInterval(timer);
  }, [fallback]);

  return current;
}

function formatLocalTime(value: Date) {
  if (Number.isNaN(value.valueOf())) return "";
  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
  }).format(value);
}

interface FocusSnapshot {
  epicId: string;
  transitionId: string;
  checkedAt: string;
  health: HealthStatus;
  phases: Array<{ key: PhaseKey; status: PhaseStatus }>;
  now: string;
  next: string | null;
}

export interface FocusDelta {
  since: string;
  changes: string;
}

function toFocusSnapshot(epic: EpicProgress): FocusSnapshot {
  return {
    epicId: epic.identity.epicId,
    transitionId: epic.presentation.transitionId,
    checkedAt: new Date().toISOString(),
    health: epic.health.status,
    phases: epic.phases.map(({ key, status }) => ({ key, status })),
    now: epic.now.label,
    next: epic.next?.label ?? null,
  };
}

export function describeMaterialDelta(
  previous: FocusSnapshot,
  current: FocusSnapshot,
): FocusDelta | null {
  if (
    previous.epicId !== current.epicId ||
    previous.transitionId === current.transitionId
  ) {
    return null;
  }

  const changes: string[] = [];
  const oldPhases = new Map(previous.phases.map((phase) => [phase.key, phase.status]));

  for (const phase of current.phases) {
    const previousStatus = oldPhases.get(phase.key);
    if (phase.status === "complete" && previousStatus !== "complete") {
      changes.push(`${phaseLabels[phase.key]} completed`);
    } else if (phase.status === "active" && previousStatus !== "active") {
      changes.push(`${phaseLabels[phase.key]} started`);
    } else if (phase.status === "invalidated" && previousStatus !== "invalidated") {
      changes.push(`${phaseLabels[phase.key]} invalidated`);
    }
  }

  if (previous.health !== current.health) {
    changes.push(`Health is ${healthLabels[current.health].toLowerCase()}`);
  }

  if (changes.length === 0 && previous.now !== current.now) changes.push(current.now);
  if (changes.length === 0 && previous.next !== current.next && current.next) {
    changes.push(`Next: ${current.next}`);
  }
  if (changes.length === 0) return null;

  return {
    since: formatLocalTime(new Date(previous.checkedAt)),
    changes: changes.slice(0, 2).join(" · "),
  };
}

function useFocusDelta(epic: EpicProgress) {
  const storageKey = `gauntlet-progress:${epic.identity.launchId}:${epic.identity.epicId}`;
  const latest = useRef(epic);
  const [delta, setDelta] = useState<FocusDelta | null>(null);

  useEffect(() => {
    latest.current = epic;
  }, [epic]);

  useEffect(() => {
    const onVisibilityChange = () => {
      if (document.visibilityState === "hidden") {
        try {
          localStorage.setItem(storageKey, JSON.stringify(toFocusSnapshot(latest.current)));
        } catch {
          // Continuity is optional presentation state; storage failure changes no run truth.
        }
        return;
      }

      try {
        const saved = localStorage.getItem(storageKey);
        if (!saved) return;
        const previous = JSON.parse(saved) as FocusSnapshot;
        const nextDelta = describeMaterialDelta(previous, toFocusSnapshot(latest.current));
        localStorage.removeItem(storageKey);
        if (nextDelta) setDelta(nextDelta);
      } catch {
        localStorage.removeItem(storageKey);
      }
    };

    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => document.removeEventListener("visibilitychange", onVisibilityChange);
  }, [storageKey]);

  useEffect(() => {
    if (!delta) return;
    const timer = window.setTimeout(() => setDelta(null), 7_000);
    return () => window.clearTimeout(timer);
  }, [delta]);

  return delta;
}

function PhaseRail({ epic }: { epic: EpicProgress }) {
  const ambient =
    epic.health.status === "healthy" &&
    !epic.freshness.stale &&
    epic.freshness.coverage !== "unavailable";
  const phaseColumns = epic.phases
    .map((phase, index) => (
      index === 0
        ? `minmax(64px, ${phase.policyShare}fr)`
        : `minmax(0, ${phase.policyShare}fr)`
    ))
    .join(" ");

  return (
    <section className={styles.phaseSection} aria-label="Planned execution progress">
      <div className={styles.rail} style={{ gridTemplateColumns: phaseColumns }} aria-hidden="true">
        {epic.phases.map((phase) => (
          <div
            key={phase.key}
            className={`${styles.segment} ${styles[phase.status]} ${styles[epic.health.status]}`}
          >
            <motion.div
              className={styles.segmentFill}
              initial={false}
              animate={{ scaleX: Math.max(0, Math.min(1, phase.provedShare)) }}
              transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
            />
            {phase.status === "active" && ambient && <span className={styles.tonalCurrent} />}
          </div>
        ))}
      </div>
      <ol className={styles.phaseLabels} style={{ gridTemplateColumns: phaseColumns }}>
        {epic.phases.map((phase) => (
          <li key={phase.key} aria-label={phase.accessibleLabel}>
            <motion.span
              className={`${styles.phaseMarker} ${styles[phase.status]} ${styles[epic.health.status]}`}
              initial={false}
              animate={{ opacity: 1, scale: phase.status === "complete" ? 1 : 0.94 }}
              transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
              aria-hidden="true"
            >
              {phase.status === "complete" ? <Icon name="check" /> : <span />}
            </motion.span>
            <span>{phase.label}</span>
            <span className={styles.srOnly}>{phaseStatusLabels[phase.status]}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

function safeActionFor(epic: EpicProgress): SafeAction | null {
  const actionId = epic.next?.actionId;
  if (!actionId) return null;
  const action = epic.actions.find((candidate) => candidate.id === actionId);
  if (!action || !/^(\/|#)/.test(action.href) || action.href.startsWith("//")) return null;
  return action;
}

const modelPresentation: Record<string, { label: string; icon: "sol" | "terra" | "luna"; order: number }> = {
  "gpt-5.6-sol": { label: "Sol", icon: "sol", order: 0 },
  "gpt-5.6-terra": { label: "Terra", icon: "terra", order: 1 },
  "gpt-5.6-luna": { label: "Luna", icon: "luna", order: 2 },
};

function UsageDetails({ epic }: { epic: EpicProgress }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const models = [...epic.usage.models]
    .filter((model) => modelPresentation[model.model])
    .sort((left, right) => modelPresentation[left.model].order - modelPresentation[right.model].order);
  const total = epic.usage.totalTokens;

  return (
    <details
      className={styles.details}
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary aria-controls={id}>
        Usage details <Icon name="arrow" />
      </summary>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id={id}
            className={styles.detailsBody}
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
          >
            <section className={styles.modelUsage}>
              <h3>Model usage</h3>
              {models.length > 0 ? (
                <>
                <ul>
                  {models.map((model) => {
                    const presentation = modelPresentation[model.model];
                    const share = total > 0 ? `${((model.tokens / total) * 100).toFixed(1)}%` : "—";
                    return (
                    <li key={model.model}>
                      <span className={styles.modelIdentity}>
                        <span className={styles.modelIcon} data-model-icon={presentation.icon}>
                          <Icon name={presentation.icon} />
                        </span>
                        {presentation.label}
                      </span>
                      <strong>{formatTokens(model.tokens)}</strong>
                      <small>{share}</small>
                    </li>
                    );
                  })}
                </ul>
                <div className={styles.modelTotal}>
                  <span>Total</span>
                  <strong>{formatTokens(total)}</strong>
                  <small>{total > 0 ? "100%" : "—"}</small>
                </div>
                </>
              ) : (
                <p className={styles.usageUnavailable}>Model usage is unavailable.</p>
              )}
            </section>
          </motion.div>
        )}
      </AnimatePresence>
    </details>
  );
}

export function ProgressCard({ epic }: { epic: EpicProgress }) {
  const headingId = useId();
  const currentTime = useCurrentTime(epic.time.current);
  const focusDelta = useFocusDelta(epic);
  const action = safeActionFor(epic);
  const complete = epic.identity.terminalOutcome === "succeeded";
  const terminalLabel =
    epic.identity.terminalOutcome === "failed" ? "Failed" :
    epic.identity.terminalOutcome === "stopped" ? "Stopped" :
    complete ? "Complete" : null;
  const milestone =
    epic.presentation.state === "ready_to_merge" ||
    epic.presentation.state === "ready_to_deploy";

  const cardClasses = [
    styles.card,
    complete ? styles.complete : "",
    milestone ? styles.milestone : "",
    epic.freshness.stale ? styles.stale : "",
  ].filter(Boolean).join(" ");

  return (
    <motion.article
      layout
      className={cardClasses}
      aria-labelledby={headingId}
      data-presentation={epic.presentation.state}
      transition={{ layout: { duration: 0.32, ease: [0.22, 1, 0.36, 1] } }}
    >
      <AnimatePresence initial={false}>
        {complete && (
          <motion.div
            className={styles.completionWash}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          />
        )}
      </AnimatePresence>

      <div className={styles.cardBody}>
        <header className={styles.header}>
          <div className={styles.identity}>
            <motion.h1 id={headingId} layout="position">{epic.identity.title}</motion.h1>
            <dl className={styles.timeRow}>
              <div><dt>Started</dt><dd>{epic.time.started}</dd></div>
              <div><dt>Current</dt><dd>{currentTime}</dd></div>
              <div><dt>Elapsed</dt><dd>{epic.time.elapsed}</dd></div>
            </dl>
          </div>

          <div className={styles.statusCluster}>
            <div className={`${styles.health} ${styles[epic.health.status]}`} aria-live="polite">
              <span className={styles.healthDot} aria-hidden="true" />
              {terminalLabel ?? healthLabels[epic.health.status]}
            </div>
            <span className={`${styles.freshness} ${epic.freshness.stale ? styles.freshnessStale : ""}`}>
              {epic.freshness.label}
            </span>
          </div>
        </header>

        <AnimatePresence initial={false}>
          {focusDelta && (
            <motion.div
              className={styles.returnUpdate}
              role="status"
              initial={{ opacity: 0, filter: "blur(2px)", y: -4 }}
              animate={{ opacity: 1, filter: "blur(0px)", y: 0 }}
              exit={{ opacity: 0, filter: "blur(1px)", y: -4 }}
              transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
            >
              <span>Since you last checked at {focusDelta.since}</span>
              <strong>{focusDelta.changes}</strong>
            </motion.div>
          )}
        </AnimatePresence>

        <PhaseRail epic={epic} />

        <div className={styles.workRows}>
          <div className={styles.workRow}>
            <span>Now</span>
            <AnimatePresence mode="wait" initial={false}>
              <motion.strong
                key={epic.now.label}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -3 }}
                transition={{ duration: 0.2 }}
              >
                {epic.now.label}
              </motion.strong>
            </AnimatePresence>
          </div>
          <AnimatePresence mode="popLayout" initial={false}>
            {epic.next && (
              <motion.div
                className={styles.workRow}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.22 }}
              >
                <span>Next</span>
                <strong>{epic.next.label}</strong>
                {action && (
                  <a className={styles.action} href={action.href}>
                    {action.label} <Icon name="arrow" />
                  </a>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {complete && (
          <motion.div
            className={styles.finalCheck}
            initial={{ scale: 0.88, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
            aria-hidden="true"
          >
            <Icon name="check" />
          </motion.div>
        )}
      </div>

      <footer className={styles.usage}>
        <span className={styles.usageLabel}>Usage</span>
        <div className={styles.usageMetrics}>
          <div className={styles.agentMetric}>
            <span className={styles.metricIcon}><Icon name="agents" /></span>
            <div>
              <strong>
                {epic.agents.activeCount} {epic.agents.activeCount === 1 ? "agent" : "agents"} active
              </strong>
              <small>{epic.agents.summary}</small>
            </div>
          </div>
          <i className={styles.divider} aria-hidden="true" />
          <div className={styles.metric}>
            <span className={styles.metricIcon}><Icon name="tokens" /></span>
            <strong>
              {epic.usage.coverage === "unavailable" ? (
                epic.usage.totalLabel
              ) : (
                <>
                  <AnimatedNumber value={epic.usage.totalTokens} format={formatTokens} />
                  <span> tokens used</span>
                </>
              )}
            </strong>
            <small>{epic.usage.coverage === "complete" ? epic.usage.freshness : `${epic.usage.coverage} coverage · ${epic.usage.freshness}`}</small>
          </div>
          <i className={styles.divider} aria-hidden="true" />
          <div className={`${styles.metric} ${styles.costMetric}`}>
            <span className={styles.metricIcon}><Icon name="cost" /></span>
            <strong>
              {epic.pricing.status === "unavailable" || epic.pricing.amountUsd == null ? (
                epic.pricing.amountLabel
              ) : (
                <>
                  {epic.pricing.status === "lower_bound" ? "Priced token subtotal ≥$" : "API equivalent ~$"}
                  <AnimatedNumber value={epic.pricing.amountUsd} format={(value) => value.toFixed(2)} />
                </>
              )}
            </strong>
            <small>{epic.pricing.disclaimer}</small>
          </div>
        </div>
        <UsageDetails epic={epic} />
      </footer>
    </motion.article>
  );
}

export default function App({ projection }: { projection: ProgressProjection }) {
  const epics = useMemo(() => projection.epics, [projection]);
  return (
    <main className={styles.page} aria-label="Epic progress">
      <LayoutGroup>
        {epics.map((epic) => (
          <ProgressCard
            key={`${epic.identity.launchId}:${epic.identity.epicId}`}
            epic={epic}
          />
        ))}
      </LayoutGroup>
    </main>
  );
}
