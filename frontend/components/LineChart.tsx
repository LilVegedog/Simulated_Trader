"use client";

import { useState } from "react";
import { useSize } from "@/lib/useSize";

export interface ChartPoint {
  x: number;
  y: number;
}

interface LineChartProps {
  points: ChartPoint[];
  color: string;
  formatValue: (n: number) => string;
  emptyMessage: string;
  gradientId: string;
}

const PAD = { top: 12, right: 76, bottom: 20, left: 10 };
const TIME = new Intl.DateTimeFormat("en-US", { hour: "2-digit", minute: "2-digit" });

/** Time-series line with a value axis, recessive grid, and a crosshair tooltip. */
export function LineChart({
  points,
  color,
  formatValue,
  emptyMessage,
  gradientId,
}: LineChartProps) {
  const { ref, width, height } = useSize<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);

  const plotW = Math.max(width - PAD.left - PAD.right, 0);
  const plotH = Math.max(height - PAD.top - PAD.bottom, 0);
  const ready = points.length > 1 && plotW > 0 && plotH > 0;

  let min = 0;
  let max = 1;
  if (ready) {
    min = Math.min(...points.map((p) => p.y));
    max = Math.max(...points.map((p) => p.y));
    const pad = (max - min || Math.abs(max) * 0.01 || 1) * 0.12;
    min -= pad;
    max += pad;
  }
  const x0 = points[0]?.x ?? 0;
  const x1 = points[points.length - 1]?.x ?? 1;
  const sx = (x: number) => PAD.left + ((x - x0) / (x1 - x0 || 1)) * plotW;
  const sy = (y: number) => PAD.top + (1 - (y - min) / (max - min || 1)) * plotH;

  const path = ready
    ? points.map((p, i) => `${i === 0 ? "M" : "L"}${sx(p.x).toFixed(1)} ${sy(p.y).toFixed(1)}`).join(" ")
    : "";
  const ticks = ready ? [0, 0.25, 0.5, 0.75, 1].map((t) => min + (max - min) * t) : [];
  const active = hover === null ? null : points[hover];

  const onMove = (event: React.MouseEvent<SVGSVGElement>) => {
    if (!ready) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const ratio = (event.clientX - rect.left - PAD.left) / (plotW || 1);
    const index = Math.round(ratio * (points.length - 1));
    setHover(Math.min(Math.max(index, 0), points.length - 1));
  };

  return (
    <div ref={ref} className="relative h-full w-full overflow-hidden">
      {!ready && (
        <p className="eyebrow absolute inset-0 flex items-center justify-center">{emptyMessage}</p>
      )}
      {ready && (
        <svg
          width={width}
          height={height}
          onMouseMove={onMove}
          onMouseLeave={() => setHover(null)}
        >
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.28} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          {ticks.map((t) => (
            <g key={t}>
              <line
                x1={PAD.left}
                x2={PAD.left + plotW}
                y1={sy(t)}
                y2={sy(t)}
                stroke="var(--color-line-soft)"
                strokeWidth={1}
              />
              <text
                x={PAD.left + plotW + 8}
                y={sy(t) + 3}
                className="num"
                fontSize={10}
                fill="var(--color-ink-faint)"
              >
                {formatValue(t)}
              </text>
            </g>
          ))}
          <path d={`${path} L${sx(x1)} ${PAD.top + plotH} L${sx(x0)} ${PAD.top + plotH} Z`} fill={`url(#${gradientId})`} />
          <path d={path} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" />
          <text x={PAD.left} y={height - 6} className="num" fontSize={10} fill="var(--color-ink-faint)">
            {TIME.format(x0)}
          </text>
          {plotW > 180 && (
            <text
              x={PAD.left + plotW}
              y={height - 6}
              textAnchor="end"
              className="num"
              fontSize={10}
              fill="var(--color-ink-faint)"
            >
              {TIME.format(x1)}
            </text>
          )}
          {active && (
            <g>
              <line
                x1={sx(active.x)}
                x2={sx(active.x)}
                y1={PAD.top}
                y2={PAD.top + plotH}
                stroke="var(--color-ink-faint)"
                strokeDasharray="3 3"
              />
              <circle
                cx={sx(active.x)}
                cy={sy(active.y)}
                r={4}
                fill={color}
                stroke="var(--color-panel)"
                strokeWidth={2}
              />
            </g>
          )}
        </svg>
      )}
      {active && (
        <div
          className="pointer-events-none absolute top-2 rounded-sm border border-line bg-raised px-2 py-1 text-[11px]"
          style={{ left: Math.min(sx(active.x) + 8, Math.max(width - 120, 0)) }}
        >
          <span className="num text-ink">{formatValue(active.y)}</span>
          <span className="num ml-2 text-ink-faint">{TIME.format(active.x)}</span>
        </div>
      )}
    </div>
  );
}
