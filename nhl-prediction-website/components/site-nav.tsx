"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Menu, X, Snowflake } from "lucide-react"
import { Button } from "@/components/ui/button"

const links = [
  { label: "Games", href: "/#games" },
  { label: "Live", href: "/#live" },
  { label: "Matchups", href: "/#matchups" },
  { label: "Models", href: "/#leaderboard" },
  { label: "Season review", href: "/season" },
]

export function SiteNav() {
  const [open, setOpen] = useState(false)

  return (
    <header className="fixed inset-x-0 top-0 z-50 px-3 pt-3 sm:px-6">
      <nav className="glass mx-auto flex max-w-6xl items-center justify-between rounded-2xl border border-border px-4 py-3 shadow-xl">
        <a href="#top" className="flex items-center gap-2">
          <span className="flex size-9 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-[0_0_20px_color-mix(in_srgb,var(--primary)_60%,transparent)]">
            <Snowflake className="size-5" />
          </span>
          <span className="text-lg font-bold tracking-tight">
            Ice<span className="text-primary">Edge</span>
          </span>
        </a>

        <div className="hidden items-center gap-1 md:flex">
          {links.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className="rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
            >
              {l.label}
            </a>
          ))}
        </div>

        <div className="hidden md:block">
          <Button
            size="sm"
            className="rounded-lg font-semibold"
            render={<a href="/season" />}
          >
            Season review
          </Button>
        </div>

        <button
          className="rounded-lg p-2 text-foreground md:hidden"
          onClick={() => setOpen((v) => !v)}
          aria-label="Toggle menu"
          aria-expanded={open}
        >
          {open ? <X className="size-5" /> : <Menu className="size-5" />}
        </button>
      </nav>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="glass mx-auto mt-2 max-w-6xl rounded-2xl border border-border p-2 shadow-xl md:hidden"
          >
            {links.map((l) => (
              <a
                key={l.href}
                href={l.href}
                onClick={() => setOpen(false)}
                className="block rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
              >
                {l.label}
              </a>
            ))}
            <Button
              className="mt-1 w-full rounded-lg font-semibold"
              render={<a href="/season" />}
            >
              Season review
            </Button>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  )
}
