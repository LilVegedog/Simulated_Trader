interface SparklineProps {
  values: number[];
  width?: number;
  height?: number;
}

/** Mini price trace accumulated from the SSE stream since page load. */
export function Sparkline({ values, width = 76, height = 22 }: SparklineProps) {
  if (values.length < 2) {
    return (
      <svg width={width} height={height} aria-hidden>
        <line
          x1={0}
          y1={height / 2}
          x2={width}
          y2={height / 2}
          stroke="var(--color-line)"
          strokeWidth={1}
          strokeDasharray="2 3"
        />
      </svg>
    );
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const step = width / (values.length - 1);
  const points = values.map((v, i) => [i * step, height - 1 - ((v - min) / span) * (height - 2)]);
  const rising = values[values.length - 1] >= values[0];
  const stroke = rising ? "var(--color-up)" : "var(--color-down)";
  const line = points.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");

  return (
    <svg width={width} height={height} aria-hidden>
      <polygon points={`0,${height} ${line} ${width},${height}`} fill={stroke} opacity={0.12} />
      <polyline
        points={line}
        fill="none"
        stroke={stroke}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
