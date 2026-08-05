/**
 * telemetry.ts — Agentic Framework 2.1-OC
 *
 * Records every failed tool call to .opencode/state/tool-errors.jsonl.
 *
 * Why this exists: published tool-calling benchmarks are measured on someone
 * else's workload with someone else's tool schemas. After a week of real use
 * this file tells you *your* measured tool-call failure rate per model on
 * *your* tasks, which is the only number that should actually drive tier
 * assignment in docs/MODEL_PROFILES.md.
 *
 * Also ports Framework 2.1's SessionEnd timestamp via `session.idle`, written
 * to .opencode/state/sessions.jsonl.
 *
 * It deliberately does NOT write to progress.md. That file is the orchestrator's
 * hand-maintained phase state and — since the scoped-edit permission landed —
 * the one file the orchestrator rewrites wholesale. A plugin appending to it
 * means two writers race over one document: observed in a real run, where the
 * telemetry stamp was the only surviving line at the start of the next phase and
 * the orchestrator's next write erased it. State is curated; telemetry is
 * machine noise. They do not share a file.
 *
 * .gitignore: ignore .opencode/state/tool-errors.jsonl and
 * .opencode/state/sessions.jsonl — NOT the state/ directory, which holds
 * progress.md.
 */

import type { Plugin } from "@opencode-ai/plugin"
import { appendFile, mkdir } from "node:fs/promises"
import { dirname } from "node:path"

const LOG = ".opencode/state/tool-errors.jsonl"
const SESSIONS = ".opencode/state/sessions.jsonl"

async function append(file: string, line: string) {
  try {
    await mkdir(dirname(file), { recursive: true })
    await appendFile(file, line)
  } catch {
    /* telemetry is best-effort and must never break a session */
  }
}

export const Telemetry: Plugin = async ({ directory }) => {
  const started = new Date().toISOString()
  let toolCalls = 0
  let toolErrors = 0
  let stamped = false

  // Tracks which agent/model is currently active, so failures can be attributed.
  // Without this the log tells you a tool failed but not who failed it, which
  // makes it useless for tier calibration.
  let agent: string | null = null
  let model: string | null = null

  return {
    "tool.execute.after": async (input: any, output: any) => {
      toolCalls++

      // Heuristic: OpenCode surfaces failures either as a thrown error captured
      // on the output, or as an output whose text carries an error marker.
      const err =
        (output as any)?.error ??
        (output as any)?.isError ??
        (typeof (output as any)?.output === "string" &&
        /^(error|Error:)/.test((output as any).output)
          ? (output as any).output.slice(0, 400)
          : undefined)

      if (!err) return
      toolErrors++

      await append(
        `${directory}/${LOG}`,
        JSON.stringify({
          ts: new Date().toISOString(),
          tool: input.tool,
          agent,
          model,
          sessionID: (input as any).sessionID ?? null,
          callID: (input as any).callID ?? null,
          error: typeof err === "string" ? err.slice(0, 400) : String(err).slice(0, 400),
          args: safeArgs((output as any)?.args),
        }) + "\n",
      )
    },

    event: async ({ event }: { event: any }) => {
      // Capture the active agent/model whenever a message updates.
      if (event.type === "message.updated") {
        const info = (event as any).properties?.info ?? {}
        if (info.agent) agent = String(info.agent)
        if (info.modelID) {
          model = info.providerID ? `${info.providerID}/${info.modelID}` : String(info.modelID)
        }
      }

      if (event.type !== "session.idle" || stamped) return
      stamped = true
      const rate = toolCalls ? ((toolErrors / toolCalls) * 100).toFixed(1) : "0.0"
      await append(
        `${directory}/${SESSIONS}`,
        JSON.stringify({
          ts: new Date().toISOString(),
          started,
          agent,
          model,
          toolCalls,
          toolErrors,
          errorRatePct: Number(rate),
        }) + "\n",
      )
    },
  }
}

/** Keep argument shape for diagnosis without logging file contents or secrets. */
function safeArgs(args: any) {
  if (!args || typeof args !== "object") return null
  const out: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(args)) {
    if (typeof v === "string") {
      out[k] = v.length > 120 ? `${v.slice(0, 120)}…(${v.length} chars)` : v
    } else if (typeof v === "object" && v !== null) {
      out[k] = `<${Array.isArray(v) ? "array" : "object"}>`
    } else {
      out[k] = v
    }
  }
  return out
}
