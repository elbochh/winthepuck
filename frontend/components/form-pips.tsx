import { cn } from "@/lib/utils"

export function FormPips({ form }: { form: ("W" | "L" | "O")[] }) {
  return (
    <div className="flex items-center gap-1">
      {form.map((r, i) => (
        <span
          key={i}
          className={cn(
            "flex size-4.5 items-center justify-center rounded text-[10px] font-bold",
            r === "W" && "bg-chart-3/20 text-chart-3",
            r === "L" && "bg-live/20 text-live",
            r === "O" && "bg-chart-4/20 text-chart-4",
          )}
          title={r === "W" ? "Win" : r === "L" ? "Loss" : "OT/SO loss"}
        >
          {r}
        </span>
      ))}
    </div>
  )
}
