"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Radio, ArrowUpRight, ArrowDownRight, History } from "lucide-react"
import { SectionHeading } from "@/components/section-heading"
import { TeamLogo } from "@/components/team-logo"
import { WinProbBar } from "@/components/win-prob-bar"
import type { LiveDemo, Team } from "@/lib/data"

const W = 640
const H = 180
const PAD = 8

const WS_URL = process.env.NEXT_PUBLIC_LIVE_WS ?? "ws://localhost:8765"

type Snapshot = {
  minute: number
  label: string
  team: "home" | "away" | "neutral"
  homeProb: number
  period: number
  clock: string
  homeScore: number
  awayScore: number
}

type Feed = {
  mode: "live" | "replay" | "demo"
  events: Snapshot[]
}

/**
 * Live section. Connects to the Python live server (ws://localhost:8765),
 * which streams the in-game model's win probability: real NHL games when
 * the league is playing, otherwise a replay of a real playoff game. If the
 * server isn't running, falls back to a pre-computed replay of the same
 * model (data/live_demo.json) so the section always shows real model output.
 */
export function LiveGameSection({
  demo,
  home,
  away,
}: {
  demo: LiveDemo
  home: Team
  away: Team
}) {
  const [feed, setFeed] = useState<Feed>({ mode: "demo", events: [] })
  const wsConnected = useRef(false)
  const demoTimer = useRef<ReturnType<typeof setInterval> | null>(null)

  // 1) try the websocket
  useEffect(() => {
    let ws: WebSocket | null = null
    try {
      ws = new WebSocket(WS_URL)
    } catch {
      return
    }
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        if (msg.type !== "snapshot") return
        wsConnected.current = true
        if (demoTimer.current) {
          clearInterval(demoTimer.current)
          demoTimer.current = null
        }
        setFeed((f) => {
          const fresh =
            f.mode === "demo" || (f.events.length && msg.minute < f.events[f.events.length - 1].minute)
          const events = fresh ? [] : f.events.slice(-400)
          return {
            mode: msg.mode === "live" ? "live" : "replay",
            events: [
              ...events,
              {
                minute: msg.minute,
                label: msg.label,
                team: msg.team ?? "neutral",
                homeProb: msg.homeProb,
                period: msg.period,
                clock: msg.clock,
                homeScore: msg.homeScore,
                awayScore: msg.awayScore,
              },
            ],
          }
        })
      } catch {
        /* ignore malformed frames */
      }
    }
    return () => ws?.close()
  }, [])

  // 2) fallback: auto-advance the pre-computed demo timeline
  useEffect(() => {
    const t = setTimeout(() => {
      if (wsConnected.current) return
      let i = 0
      setFeed({ mode: "demo", events: demo.timeline.slice(0, 1) as Snapshot[] })
      demoTimer.current = setInterval(() => {
        i += 1
        if (i >= demo.timeline.length) {
          i = 0
          setFeed({ mode: "demo", events: demo.timeline.slice(0, 1) as Snapshot[] })
          return
        }
        setFeed((f) => ({
          mode: "demo",
          events: [...f.events, demo.timeline[i] as Snapshot],
        }))
      }, 1400)
    }, 2000)
    return () => {
      clearTimeout(t)
      if (demoTimer.current) clearInterval(demoTimer.current)
    }
  }, [demo])

  const events = feed.events
  const current = events[events.length - 1]
  const prev = events[events.length - 2] ?? current
  const delta = current ? current.homeProb - prev.homeProb : 0

  const maxMinute = Math.max(60, current?.minute ?? 60)

  const points = useMemo(
    () =>
      events.map((e) => {
        const x = PAD + (e.minute / maxMinute) * (W - PAD * 2)
        const y = PAD + (1 - e.homeProb / 100) * (H - PAD * 2)
        return { x, y, e }
      }),
    [events, maxMinute],
  )

  const linePath = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`)
    .join(" ")
  const areaPath =
    points.length > 1
      ? `${linePath} L${points[points.length - 1].x.toFixed(1)},${H - PAD} L${points[0].x.toFixed(1)},${H - PAD} Z`
      : ""
  const last = points[points.length - 1]

  const isTrulyLive = feed.mode === "live"
  const periodLabel = current
    ? current.period <= 3
      ? `Period ${current.period}`
      : "Overtime"
    : "n/a"

  return (
    <section id="live" className="mx-auto w-full max-w-6xl px-4 py-16 sm:py-20">
      <SectionHeading
        eyebrow={isTrulyLive ? "Live now" : "Game replay"}
        title="Win probability, updating in real time"
        description={
          isTrulyLive
            ? "The bar and chart react to every goal, penalty, and momentum swing as the game unfolds."
            : `No NHL games are live right now, so you're watching the in-game model replay a real playoff game: ${demo.away} @ ${demo.home} (${demo.date}). Every probability is the model's actual output for that moment.`
        }
      />

      <motion.div
        initial={{ opacity: 0, y: 24 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.5 }}
        className="glass overflow-hidden rounded-3xl border border-border shadow-2xl"
      >
        <div className="grid gap-0 lg:grid-cols-[1.1fr_1fr]">
          {/* left: scoreboard + bar */}
          <div className="border-b border-border p-5 sm:p-7 lg:border-b-0 lg:border-r">
            <div className="mb-5 flex items-center justify-between">
              {isTrulyLive ? (
                <span className="inline-flex items-center gap-2 rounded-full bg-live/15 px-3 py-1 text-xs font-bold uppercase tracking-wide text-live">
                  <span className="relative flex size-2">
                    <span className="absolute inline-flex size-full animate-ping rounded-full bg-live opacity-75" />
                    <span className="relative inline-flex size-2 rounded-full bg-live" />
                  </span>
                  <Radio className="size-3.5" /> Live
                </span>
              ) : (
                <span className="inline-flex items-center gap-2 rounded-full bg-primary/15 px-3 py-1 text-xs font-bold uppercase tracking-wide text-primary">
                  <History className="size-3.5" /> Replay ·{" "}
                  {feed.mode === "demo" ? "in-browser" : "live model"}
                </span>
              )}
              <span className="font-mono text-sm text-muted-foreground">
                {periodLabel} · {current?.clock ?? "--:--"}
              </span>
            </div>

            <div className="flex items-center justify-between gap-3">
              <TeamRow team={home} score={current?.homeScore ?? 0} />
              <span className="px-2 font-mono text-xs text-muted-foreground">
                VS
              </span>
              <TeamRow team={away} score={current?.awayScore ?? 0} reverse />
            </div>

            <div className="mt-7">
              <WinProbBar
                home={home}
                away={away}
                homeProb={Math.round(current?.homeProb ?? demo.pregameHomeProb)}
              />
            </div>

            <div className="mt-5 flex items-center gap-3 rounded-2xl bg-secondary/60 p-3">
              <span
                className={`flex size-8 items-center justify-center rounded-lg ${
                  delta >= 0
                    ? "bg-chart-3/15 text-chart-3"
                    : "bg-live/15 text-live"
                }`}
              >
                {delta >= 0 ? (
                  <ArrowUpRight className="size-4" />
                ) : (
                  <ArrowDownRight className="size-4" />
                )}
              </span>
              <AnimatePresence mode="wait">
                <motion.div
                  key={`${current?.minute}-${current?.label}`}
                  initial={{ opacity: 0, x: 8 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -8 }}
                  transition={{ duration: 0.25 }}
                  className="min-w-0"
                >
                  <p className="truncate text-sm font-semibold">
                    {current?.label ?? "Waiting for events…"}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {home.abbr} win prob {delta >= 0 ? "+" : ""}
                    {delta.toFixed(1)}% on this play
                  </p>
                </motion.div>
              </AnimatePresence>
            </div>
          </div>

          {/* right: animated chart */}
          <div className="p-5 sm:p-7">
            <div className="mb-3 flex items-center justify-between">
              <p className="text-sm font-semibold text-muted-foreground">
                {home.abbr} win probability
              </p>
              <span className="font-mono text-2xl font-bold tabular-nums text-primary">
                {(current?.homeProb ?? demo.pregameHomeProb).toFixed(0)}%
              </span>
            </div>

            <div className="relative w-full">
              <svg
                viewBox={`0 0 ${W} ${H}`}
                className="h-44 w-full"
                preserveAspectRatio="none"
                aria-hidden="true"
              >
                <defs>
                  <linearGradient id="liveArea" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0" stopColor="var(--primary)" stopOpacity="0.35" />
                    <stop offset="1" stopColor="var(--primary)" stopOpacity="0" />
                  </linearGradient>
                </defs>
                {[0, 0.25, 0.5, 0.75, 1].map((g) => (
                  <line
                    key={g}
                    x1={PAD}
                    x2={W - PAD}
                    y1={PAD + g * (H - PAD * 2)}
                    y2={PAD + g * (H - PAD * 2)}
                    stroke="var(--border)"
                    strokeWidth="1"
                  />
                ))}
                <line
                  x1={PAD}
                  x2={W - PAD}
                  y1={H / 2}
                  y2={H / 2}
                  stroke="var(--live)"
                  strokeOpacity="0.4"
                  strokeDasharray="4 4"
                />
                {areaPath && <path d={areaPath} fill="url(#liveArea)" />}
                {points.length > 1 && (
                  <motion.path
                    d={linePath}
                    fill="none"
                    stroke="var(--primary)"
                    strokeWidth="3"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    initial={false}
                    animate={{ d: linePath }}
                    transition={{ duration: 0.5 }}
                  />
                )}
                {last && (
                  <>
                    <circle cx={last.x} cy={last.y} r="9" fill="var(--primary)" opacity="0.2">
                      <animate
                        attributeName="r"
                        values="6;12;6"
                        dur="1.6s"
                        repeatCount="indefinite"
                      />
                    </circle>
                    <circle cx={last.x} cy={last.y} r="4.5" fill="var(--primary)" />
                  </>
                )}
              </svg>
            </div>

            <div className="mt-4 max-h-28 space-y-1.5 overflow-hidden">
              {events
                .slice(-3)
                .reverse()
                .map((e, i) => (
                  <motion.div
                    key={`${e.minute}-${e.label}-${i}`}
                    initial={{ opacity: 0, y: -6 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex items-center justify-between rounded-lg bg-secondary/40 px-3 py-2 text-xs"
                  >
                    <span className="flex items-center gap-2">
                      <span className="font-mono text-muted-foreground">
                        {String(Math.floor(e.minute)).padStart(2, "0")}'
                      </span>
                      <span className="font-medium">{e.label}</span>
                    </span>
                    <span className="font-mono font-semibold text-primary">
                      {e.homeProb.toFixed(0)}%
                    </span>
                  </motion.div>
                ))}
            </div>
          </div>
        </div>
      </motion.div>
    </section>
  )
}

function TeamRow({
  team,
  score,
  reverse,
}: {
  team: Team
  score: number
  reverse?: boolean
}) {
  return (
    <div
      className={`flex flex-1 items-center gap-3 ${reverse ? "flex-row-reverse text-right" : ""}`}
    >
      <TeamLogo team={team} size={48} />
      <div className={reverse ? "items-end" : ""}>
        <div className="text-xs text-muted-foreground">{team.city}</div>
        <div className="font-bold leading-tight">{team.name}</div>
      </div>
      <motion.div
        key={score}
        initial={{ scale: 1.3 }}
        animate={{ scale: 1 }}
        className={`font-mono text-4xl font-bold tabular-nums ${reverse ? "mr-auto" : "ml-auto"}`}
      >
        {score}
      </motion.div>
    </div>
  )
}
