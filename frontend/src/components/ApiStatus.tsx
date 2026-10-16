"use client";

import { useEffect, useState } from "react";

type Status = "checking" | "connected" | "unreachable";

const LABELS: Record<Status, string> = {
  checking: "API: checking…",
  connected: "API: connected",
  unreachable: "API: unreachable",
};

const API_URL = process.env.NEXT_PUBLIC_API_URL;

export default function ApiStatus() {
  const [status, setStatus] = useState<Status>(
    API_URL ? "checking" : "unreachable",
  );

  useEffect(() => {
    const apiUrl = API_URL;
    if (!apiUrl) return;

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10_000);

    fetch(`${apiUrl.replace(/\/$/, "")}/health`, { signal: controller.signal })
      .then(async (res) => {
        const body: unknown = await res.json();
        const ok =
          res.ok &&
          typeof body === "object" &&
          body !== null &&
          (body as { status?: unknown }).status === "ok";
        setStatus(ok ? "connected" : "unreachable");
      })
      .catch(() => setStatus("unreachable"))
      .finally(() => clearTimeout(timeout));

    return () => {
      clearTimeout(timeout);
      controller.abort();
    };
  }, []);

  return (
    <p data-status={status} aria-live="polite">
      {LABELS[status]}
    </p>
  );
}
