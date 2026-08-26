import { Snowflake } from "lucide-react"

export function SiteFooter() {
  return (
    <footer className="border-t border-border">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 py-10 sm:flex-row">
        <div className="flex items-center gap-2">
          <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Snowflake className="size-4" />
          </span>
          <span className="font-bold">
            Win<span className="text-primary">ThePuck</span>
          </span>
        </div>
        <p className="text-center text-xs text-muted-foreground">
          Predictions are model-generated for entertainment. Data is simulated and
          ready to wire to a live prediction API.
        </p>
        <p className="text-xs text-muted-foreground">
          &copy; {new Date().getFullYear()} WinThePuck
        </p>
      </div>
    </footer>
  )
}
