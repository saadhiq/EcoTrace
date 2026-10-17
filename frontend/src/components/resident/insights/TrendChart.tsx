"use client";

import { useEffect, useRef, useState } from "react";

import { formatDay } from "@/lib/dates";
import type { PickupPoint } from "@/lib/insights";

import styles from "./insights.module.css";

const HEIGHT = 180;
const PAD = { top: 18, right: 34, bottom: 26, left: 30 };

/** Eco score per processed pickup: one series, one 0-100 axis, crosshair tooltip. */
export default function TrendChart({ points }: { points: PickupPoint[] }) {
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const [active, setActive] = useState<number | null>(null);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.floor(entry.contentRect.width)));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const data = points.filter((p) => p.ecoScore !== null);
  const innerW = Math.max(0, width - PAD.left - PAD.right);
  const innerH = HEIGHT - PAD.top - PAD.bottom;
  const x = (i: number) => PAD.left + (data.length <= 1 ? innerW / 2 : (i / (data.length - 1)) * innerW);
  const y = (v: number) => PAD.top + innerH - (v / 100) * innerH;
  const path = data.map((p, i) => `${i ? "L" : "M"}${x(i)},${y(p.ecoScore!)}`).join(" ");
  const last = data.length - 1;
  const shown = active ?? null;

  function onMove(e: React.PointerEvent<SVGRectElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - rect.left + PAD.left;
    let best = 0;
    data.forEach((_, i) => {
      if (Math.abs(x(i) - px) < Math.abs(x(best) - px)) best = i;
    });
    setActive(best);
  }

  return (
    <div>
      <div ref={box} className={styles.chartBox} data-testid="trend">
        {width > 0 && data.length > 0 && (
          <svg width={width} height={HEIGHT} role="img" aria-label="Eco score per pickup">
            {[0, 50, 100].map((v) => (
              <g key={v}>
                <line className={styles.grid} x1={PAD.left} x2={width - PAD.right} y1={y(v)} y2={y(v)} />
                <text className={styles.axisText} x={PAD.left - 6} y={y(v) + 4} textAnchor="end">
                  {v}
                </text>
              </g>
            ))}
            {[0, last].filter((i, k, a) => a.indexOf(i) === k).map((i) => (
              <text key={i} className={styles.axisText} x={x(i)} y={HEIGHT - 6} textAnchor={i === 0 && last ? "start" : "end"}>
                {data[i].date ? formatDay(data[i].date!) : ""}
              </text>
            ))}
            {shown !== null && <line className={styles.crosshair} x1={x(shown)} x2={x(shown)} y1={PAD.top} y2={PAD.top + innerH} />}
            <path className={styles.line} d={path} />
            {data.map((p, i) => (
              <circle key={p.pickupId} className={styles.dot} cx={x(i)} cy={y(p.ecoScore!)} r={shown === i ? 6 : 4} />
            ))}
            {/* Selective direct label: latest value only. */}
            <text className={styles.valueLabel} x={x(last) + 8} y={y(data[last].ecoScore!) + 4}>
              {data[last].ecoScore}
            </text>
            <rect
              x={PAD.left - 10}
              y={0}
              width={innerW + 20}
              height={HEIGHT}
              fill="transparent"
              onPointerMove={onMove}
              onPointerLeave={() => setActive(null)}
            />
          </svg>
        )}
        {shown !== null && data[shown] && (
          <div className={styles.tooltip} style={{ left: x(shown), top: y(data[shown].ecoScore!) }} role="tooltip">
            <strong>{data[shown].date ? formatDay(data[shown].date!) : "Pickup"}</strong> · score {data[shown].ecoScore}
            {data[shown].recyclableShare !== null && <> · {Math.round(data[shown].recyclableShare! * 100)}% recyclable</>}
            {" · "}
            {data[shown].bags} bag{data[shown].bags === 1 ? "" : "s"}
          </div>
        )}
      </div>
      <details className={styles.details}>
        <summary>Show as table</summary>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Pickup</th>
              <th>Score</th>
              <th>Recyclable</th>
              <th>Bags</th>
            </tr>
          </thead>
          <tbody>
            {data.map((p) => (
              <tr key={p.pickupId}>
                <td>{p.date ? formatDay(p.date) : p.pickupId}</td>
                <td>{p.ecoScore}</td>
                <td>{p.recyclableShare === null ? "–" : `${Math.round(p.recyclableShare * 100)}%`}</td>
                <td>{p.bags}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}
