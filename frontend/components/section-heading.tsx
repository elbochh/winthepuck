"use client"

import { motion } from "framer-motion"
import type { ReactNode } from "react"

export function SectionHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.5 }}
        className="max-w-2xl"
      >
        <div className="mb-2 inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-primary">
          <span className="h-px w-6 bg-primary" />
          {eyebrow}
        </div>
        <h2 className="text-balance text-2xl font-bold tracking-tight sm:text-3xl md:text-4xl">
          {title}
        </h2>
        {description && (
          <p className="mt-3 text-pretty leading-relaxed text-muted-foreground">
            {description}
          </p>
        )}
      </motion.div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}
