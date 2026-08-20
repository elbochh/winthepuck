"use client"

import { motion } from "framer-motion"

export function ConfidenceRing({
  value,
  size = 56,
  stroke = 6,
  label = true,
}: {
  value: number
  size?: number
  stroke?: number
  label?: boolean
}) {
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const offset = c - (value / 100) * c

  const color =
    value >= 75
      ? "var(--chart-3)"
      : value >= 60
        ? "var(--primary)"
        : "var(--chart-4)"

  return (
    <div
      className="relative shrink-0"
      style={{ width: size, height: size }}
      role="img"
      aria-label={`Prediction confidence ${value}%`}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--secondary)"
          strokeWidth={stroke}
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          whileInView={{ strokeDashoffset: offset }}
          viewport={{ once: true }}
          transition={{ duration: 1, ease: "easeOut" }}
        />
      </svg>
      {label && (
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span
            className="font-mono text-sm font-bold leading-none tabular-nums"
            style={{ color }}
          >
            {value}
          </span>
          <span className="text-[8px] uppercase tracking-wide text-muted-foreground">
            conf
          </span>
        </div>
      )}
    </div>
  )
}
