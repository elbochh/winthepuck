"use client"

import { motion } from "framer-motion"

export function RinkBackground() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      {/* base ice glow */}
      <div className="absolute inset-0 bg-[radial-gradient(60%_60%_at_50%_-10%,color-mix(in_srgb,var(--primary)_22%,transparent),transparent_70%)]" />
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-background/40 to-background" />

      {/* rink markings */}
      <svg
        className="absolute left-1/2 top-1/2 h-[140%] w-[140%] -translate-x-1/2 -translate-y-1/2 opacity-[0.18]"
        viewBox="0 0 1200 600"
        fill="none"
        preserveAspectRatio="xMidYMid slice"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id="line" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor="var(--primary)" />
            <stop offset="1" stopColor="var(--chart-2)" />
          </linearGradient>
        </defs>
        {/* center red line */}
        <line x1="600" y1="40" x2="600" y2="560" stroke="var(--live)" strokeWidth="4" />
        {/* blue lines */}
        <line x1="430" y1="40" x2="430" y2="560" stroke="var(--primary)" strokeWidth="6" />
        <line x1="770" y1="40" x2="770" y2="560" stroke="var(--primary)" strokeWidth="6" />
        {/* center circle */}
        <circle cx="600" cy="300" r="90" stroke="url(#line)" strokeWidth="3" />
        <circle cx="600" cy="300" r="6" fill="var(--live)" />
        {/* faceoff circles */}
        <circle cx="250" cy="170" r="55" stroke="var(--live)" strokeWidth="2.5" />
        <circle cx="250" cy="430" r="55" stroke="var(--live)" strokeWidth="2.5" />
        <circle cx="950" cy="170" r="55" stroke="var(--live)" strokeWidth="2.5" />
        <circle cx="950" cy="430" r="55" stroke="var(--live)" strokeWidth="2.5" />
        {/* rink outline */}
        <rect x="40" y="40" width="1120" height="520" rx="120" stroke="var(--primary)" strokeWidth="3" />
        {/* goal creases */}
        <path d="M90 260 a40 40 0 0 1 0 80" stroke="var(--live)" strokeWidth="2.5" />
        <path d="M1110 260 a40 40 0 0 0 0 80" stroke="var(--live)" strokeWidth="2.5" />
      </svg>

      {/* gliding pucks */}
      {[0, 1, 2].map((i) => (
        <motion.div
          key={i}
          className="absolute h-3 w-3 rounded-full bg-foreground/70 shadow-[0_0_18px_var(--primary)]"
          style={{ top: `${28 + i * 22}%` }}
          initial={{ left: "-5%" }}
          animate={{ left: "105%" }}
          transition={{
            duration: 7 + i * 2,
            repeat: Number.POSITIVE_INFINITY,
            ease: "easeInOut",
            delay: i * 1.6,
          }}
        />
      ))}

      {/* drifting light streaks */}
      <motion.div
        className="absolute -top-1/3 left-1/4 h-[120%] w-40 rotate-12 bg-gradient-to-b from-primary/20 to-transparent blur-2xl"
        animate={{ opacity: [0.2, 0.5, 0.2] }}
        transition={{ duration: 6, repeat: Number.POSITIVE_INFINITY, ease: "easeInOut" }}
      />
    </div>
  )
}
