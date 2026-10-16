"use client";

import {
  Scanner,
  setZXingModuleOverrides,
  type IDetectedBarcode,
  type IScannerError,
} from "@yudiel/react-qr-scanner";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

import Button from "@/components/ui/Button";

import styles from "./collector.module.css";

// Serve the QR decoder's wasm from our own domain (see scripts/copy-zxing-wasm.mjs).
setZXingModuleOverrides({
  locateFile: (path: string, prefix: string) =>
    path.endsWith(".wasm") ? "/vendor/zxing_reader.wasm" : prefix + path,
});

export type ScanOutcome = { ok: boolean; message: string };

type Props = {
  /** Handle a scanned or typed code; resolve with what to flash. */
  onCode: (code: string) => Promise<ScanOutcome>;
  disabled?: boolean;
  /** Start with the camera on (e.g. after the user has already allowed it). */
  autoStart?: boolean;
};

const SAME_CODE_COOLDOWN_MS = 3000;

// Soft preferences only. The library's defaults require height >= 640px,
// which rejects 480p webcams and some phone cameras ("overconstrained").
const CAMERA_CONSTRAINTS: MediaTrackConstraints = {
  facingMode: "environment",
  width: { ideal: 1280 },
  height: { ideal: 720 },
};

const CAMERA_ERRORS: Partial<Record<IScannerError["kind"], string>> = {
  "permission-denied": "Camera access was blocked. Allow it in your browser settings, or type the code below.",
  "no-camera": "No camera found on this device. Type the code below instead.",
  "in-use": "The camera is being used by another app. Close it and try again.",
  "insecure-context": "The camera needs a secure (https) connection.",
  unsupported: "This browser can't use the camera. Type the code below instead.",
};

function cameraErrorMessage(error: IScannerError): string {
  return CAMERA_ERRORS[error.kind] ?? "Camera unavailable. Try again, or type the code below.";
}

/** Camera QR scanner + manual entry, with a success/error flash. */
export default function ScanPanel({ onCode, disabled = false, autoStart = false }: Props) {
  const [cameraOn, setCameraOn] = useState(autoStart);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [manual, setManual] = useState("");
  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState<ScanOutcome | null>(null);
  const last = useRef<{ code: string; at: number } | null>(null);
  const flashTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (flashTimer.current) clearTimeout(flashTimer.current);
  }, []);

  const submit = useCallback(
    async (raw: string) => {
      const code = raw.trim().toUpperCase();
      if (!code || busy || disabled) return;
      const now = Date.now();
      // The camera reports the same QR many times per second: ignore repeats.
      if (last.current && last.current.code === code && now - last.current.at < SAME_CODE_COOLDOWN_MS) return;
      last.current = { code, at: now };
      setBusy(true);
      try {
        const outcome = await onCode(code);
        setFlash(outcome);
        if (outcome.ok) {
          setManual("");
          navigator.vibrate?.(60);
        } else {
          navigator.vibrate?.([40, 60, 40]);
        }
        if (flashTimer.current) clearTimeout(flashTimer.current);
        flashTimer.current = setTimeout(() => setFlash(null), 2200);
      } finally {
        setBusy(false);
      }
    },
    [busy, disabled, onCode],
  );

  function onScan(codes: IDetectedBarcode[]) {
    const value = codes[0]?.rawValue;
    if (value) void submit(value);
  }

  function onManual(event: FormEvent) {
    event.preventDefault();
    last.current = null; // typed codes are always submitted
    void submit(manual);
  }

  return (
    <div className={styles.scanPanel} data-testid="scan-panel">
      {flash && (
        <div
          role={flash.ok ? "status" : "alert"}
          className={`${styles.flash} ${flash.ok ? styles.flashOk : styles.flashError}`}
          data-testid="scan-flash"
          data-ok={flash.ok}
        >
          {flash.message}
        </div>
      )}

      {cameraOn ? (
        <div className={styles.camera} data-testid="camera">
          <Scanner
            onScan={onScan}
            onError={(error) => {
              console.warn("QR scanner error", error.kind, error.message);
              setCameraError(cameraErrorMessage(error));
            }}
            formats={["qr_code"]}
            constraints={CAMERA_CONSTRAINTS}
            paused={disabled}
            sound={false}
            components={{ finder: true, torch: true }}
            styles={{ container: { width: "100%", height: "100%" } }}
            startTimeoutMs={10_000}
          />
        </div>
      ) : null}
      {cameraError && <p className={styles.note}>{cameraError}</p>}
      <Button
        variant={cameraOn ? "secondary" : "primary"}
        block
        disabled={disabled}
        onClick={() => {
          setCameraError(null);
          setCameraOn((on) => !on);
        }}
        data-testid="camera-toggle"
      >
        {cameraOn ? "Stop camera" : "Scan with camera"}
      </Button>

      <form className={styles.manual} onSubmit={onManual}>
        <input
          aria-label="Bag code"
          placeholder="ECO-XXXX-XX"
          autoCapitalize="characters"
          autoComplete="off"
          spellCheck={false}
          value={manual}
          onChange={(e) => setManual(e.target.value)}
          disabled={disabled}
          data-testid="manual-code"
        />
        <Button type="submit" variant="secondary" loading={busy} disabled={disabled || !manual.trim()}>
          Enter
        </Button>
      </form>
    </div>
  );
}
