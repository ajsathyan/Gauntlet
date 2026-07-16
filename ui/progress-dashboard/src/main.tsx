import { MotionConfig } from "motion/react";
import { StrictMode, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { isProgressProjection, type ProgressProjection } from "./contract";
import "./index.css";

const PROJECTION_ROUTE = "/api/progress";
const POLL_INTERVAL_MS = 2_500;
type TransportStatus = "loading" | "connected" | "reconnecting" | "unavailable";

function takeCapability() {
  const fragment = window.location.hash.slice(1);
  const params = new URLSearchParams(fragment);
  const capability = params.get("capability") ?? (fragment.includes("=") ? null : fragment);
  window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
  return capability;
}

function TransportNotice({ status }: { status: Exclude<TransportStatus, "connected"> }) {
  const copy = {
    loading: ["Connecting to live progress…", "Implementation continues in the main task."],
    reconnecting: ["Reconnecting to live progress", "Showing the last confirmed update."],
    unavailable: ["Live progress is unavailable", "Implementation continues in the main task."],
  }[status];
  return (
    <div className={`transportNotice transport-${status}`} role="status" aria-live="polite">
      <strong>{copy[0]}</strong>
      <span>{copy[1]}</span>
    </div>
  );
}

export function ProgressRoot({ capability }: { capability: string | null }) {
  const [projection, setProjection] = useState<ProgressProjection | null>(null);
  const [transport, setTransport] = useState<TransportStatus>(capability ? "loading" : "unavailable");
  const etag = useRef<string | null>(null);
  const confirmed = useRef(false);

  useEffect(() => {
    if (!capability) {
      setTransport("unavailable");
      return;
    }
    let stopped = false;
    let timer: number | undefined;

    const poll = async () => {
      try {
        const headers = new Headers({ Authorization: `Bearer ${capability}` });
        if (etag.current) headers.set("If-None-Match", etag.current);
        const response = await fetch(PROJECTION_ROUTE, {
          cache: "no-store",
          credentials: "omit",
          headers,
          method: "GET",
          referrerPolicy: "no-referrer",
        });

        if (response.status !== 304) {
          if (!response.ok) throw new Error(`Progress request failed (${response.status})`);
          const next: unknown = await response.json();
          if (!isProgressProjection(next)) throw new Error("Unsupported progress projection");
          etag.current = response.headers.get("etag");
          if (!stopped) {
            confirmed.current = true;
            setProjection(next);
          }
        }
        if (!stopped) setTransport("connected");
      } catch {
        // Keep the last valid projection. Dashboard transport never changes run state.
        if (!stopped) setTransport(confirmed.current ? "reconnecting" : "unavailable");
      } finally {
        if (!stopped) timer = window.setTimeout(poll, POLL_INTERVAL_MS);
      }
    };

    void poll();
    return () => {
      stopped = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [capability]);

  if (!projection) {
    return (
      <main className="transportShell" aria-busy={transport === "loading"} aria-label="Epic progress">
        <TransportNotice status={transport === "connected" ? "loading" : transport} />
      </main>
    );
  }

  return (
    <>
      {transport === "reconnecting" && <TransportNotice status="reconnecting" />}
      <App projection={projection} />
    </>
  );
}

const root = document.getElementById("root");
const capability = takeCapability();

if (root) {
  createRoot(root).render(
    <StrictMode>
      <MotionConfig reducedMotion="user">
        <ProgressRoot capability={capability} />
      </MotionConfig>
    </StrictMode>,
  );
}
