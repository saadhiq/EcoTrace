"use client";

import QRCode from "qrcode";
import { useEffect, useState } from "react";

import styles from "./ui.module.css";

/** QR code rendered client-side as inline SVG. Encodes only `value`. */
export default function QrCode({ value, size = 128 }: { value: string; size?: number }) {
  const [svg, setSvg] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    QRCode.toString(value, { type: "svg", margin: 1, errorCorrectionLevel: "M" })
      .then((markup) => active && setSvg(markup))
      .catch(() => active && setSvg(null));
    return () => {
      active = false;
    };
  }, [value]);

  return (
    <span
      className={styles.qr}
      style={{ width: size, height: size }}
      role="img"
      aria-label={`QR code for ${value}`}
      // Markup is generated locally by the qrcode library from our own bag code.
      dangerouslySetInnerHTML={svg ? { __html: svg } : undefined}
    />
  );
}
