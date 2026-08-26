"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Heart, Send, MessageSquare } from "lucide-react"
import { SectionHeading } from "@/components/section-heading"
import { Button } from "@/components/ui/button"
import { TeamLogo } from "@/components/team-logo"
import { comments as seed, type Comment, type Game } from "@/lib/data"

function Avatar({ seed }: { seed: string }) {
  const hue = (seed.split("").reduce((a, c) => a + c.charCodeAt(0), 0) * 7) % 360
  return (
    <span
      className="flex size-9 shrink-0 items-center justify-center rounded-full text-xs font-bold uppercase text-white ring-1 ring-white/15"
      style={{
        background: `radial-gradient(120% 120% at 30% 20%, hsl(${hue} 70% 55%), hsl(${(hue + 40) % 360} 65% 35%))`,
      }}
      aria-hidden="true"
    >
      {seed.slice(0, 2)}
    </span>
  )
}

export function Discussion({ game }: { game: Game }) {
  const [list, setList] = useState<Comment[]>(seed)
  const [text, setText] = useState("")
  const [pick, setPick] = useState<"home" | "away">("away")
  const [liked, setLiked] = useState<Record<string, boolean>>({})

  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!text.trim()) return
    const c: Comment = {
      id: `c${Date.now()}`,
      user: "You",
      avatarSeed: "yo",
      time: "now",
      text: text.trim(),
      likes: 0,
      pick,
    }
    setList((l) => [c, ...l])
    setText("")
  }

  function toggleLike(id: string) {
    setLiked((m) => ({ ...m, [id]: !m[id] }))
    setList((l) =>
      l.map((c) =>
        c.id === id ? { ...c, likes: c.likes + (liked[id] ? -1 : 1) } : c,
      ),
    )
  }

  return (
    <section id="discussion" className="mx-auto w-full max-w-3xl px-4 py-16 sm:py-20">
      <SectionHeading
        eyebrow="Talk hockey"
        title="Game discussion"
        description="Share your read on the matchup, defend your pick, and see where the community lands."
      />

      {/* game context bar */}
      <div className="glass mb-5 flex items-center justify-between rounded-2xl border border-border p-4">
        <div className="flex items-center gap-3">
          <TeamLogo team={game.home} size={36} />
          <span className="font-bold">{game.home.abbr}</span>
          <span className="text-xs text-muted-foreground">vs</span>
          <span className="font-bold">{game.away.abbr}</span>
          <TeamLogo team={game.away} size={36} />
        </div>
        <span className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
          <MessageSquare className="size-4" />
          {list.length}
        </span>
      </div>

      {/* composer */}
      <form
        onSubmit={submit}
        className="glass mb-6 rounded-2xl border border-border p-4"
      >
        <div className="flex gap-3">
          <Avatar seed="yo" />
          <div className="flex-1">
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="What's your prediction for this game?"
              rows={2}
              className="w-full resize-none rounded-xl border border-input bg-background/40 px-3 py-2 text-sm outline-none transition-colors placeholder:text-muted-foreground focus:border-primary focus:ring-1 focus:ring-primary"
            />
            <div className="mt-2 flex items-center justify-between">
              <div className="flex items-center gap-1 rounded-lg bg-secondary p-1 text-xs">
                {(["home", "away"] as const).map((side) => {
                  const team = side === "home" ? game.home : game.away
                  return (
                    <button
                      key={side}
                      type="button"
                      onClick={() => setPick(side)}
                      className={`rounded-md px-2.5 py-1 font-semibold transition-colors ${
                        pick === side
                          ? "bg-primary text-primary-foreground"
                          : "text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      {team.abbr}
                    </button>
                  )
                })}
              </div>
              <Button
                type="submit"
                size="sm"
                disabled={!text.trim()}
                className="rounded-lg font-semibold"
              >
                <Send className="size-3.5" />
                Post
              </Button>
            </div>
          </div>
        </div>
      </form>

      {/* comments */}
      <div className="space-y-3">
        <AnimatePresence initial={false}>
          {list.map((c) => {
            const team = c.pick === "home" ? game.home : game.away
            return (
              <motion.div
                key={c.id}
                layout
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="glass flex gap-3 rounded-2xl border border-border p-4"
              >
                <Avatar seed={c.avatarSeed} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold">{c.user}</span>
                    <span
                      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase"
                      style={{
                        color: team.color,
                        background: `color-mix(in srgb, ${team.color} 18%, transparent)`,
                      }}
                    >
                      picks {team.abbr}
                    </span>
                    <span className="text-xs text-muted-foreground">{c.time}</span>
                  </div>
                  <p className="mt-1 text-sm leading-relaxed text-foreground/90">
                    {c.text}
                  </p>
                  <button
                    onClick={() => toggleLike(c.id)}
                    className="mt-2 inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground transition-colors hover:text-live"
                  >
                    <Heart
                      className={`size-3.5 transition-all ${liked[c.id] ? "fill-live text-live" : ""}`}
                    />
                    {c.likes}
                  </button>
                </div>
              </motion.div>
            )
          })}
        </AnimatePresence>
      </div>
    </section>
  )
}
