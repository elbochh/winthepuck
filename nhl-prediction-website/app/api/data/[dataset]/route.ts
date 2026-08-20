// Read-only API over the model's exported datasets.
//
// CLOUD NOTE (Azure phase): this is the HTTP surface that moves to the cloud.
// Today it serves the JSON files exported by ../nhl_model/export_site_data.py
// from local disk; on Azure the same routes would read from Blob Storage /
// Azure SQL behind Azure Functions or App Service, with identical response
// shapes so the frontend does not change.

import { promises as fs } from "fs"
import path from "path"

const DATASETS: Record<string, string> = {
  teams: "teams.json",
  season: "season.json",
  "model-leaderboard": "model_leaderboard.json",
  upcoming: "upcoming.json",
  hero: "hero.json",
  "live-demo": "live_demo.json",
}

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ dataset: string }> },
) {
  const { dataset } = await params
  const file = DATASETS[dataset]
  if (!file) {
    return Response.json(
      { error: `Unknown dataset '${dataset}'`, available: Object.keys(DATASETS) },
      { status: 404 },
    )
  }
  try {
    const raw = await fs.readFile(path.join(process.cwd(), "data", file), "utf8")
    return new Response(raw, {
      headers: { "content-type": "application/json" },
    })
  } catch {
    return Response.json(
      { error: `Dataset '${dataset}' not exported yet. Run export_site_data.py.` },
      { status: 503 },
    )
  }
}
