/**
 * telemetry.ts — Agentic Framework 2.1-OC  (v4)
 *
 * Records failed tool calls to .opencode/state/tool-errors.jsonl and a
 * per-session summary to .opencode/state/sessions.jsonl.
 *
 * Why this exists: published tool-calling benchmarks are measured on someone
 * else's workload with someone else's tool schemas. After a week of real use
 * this file tells you *your* measured tool-call failure rate per model on
 * *your* tasks, which is the only number that should actually drive tier
 * assignment in docs/MODEL_PROFILES.md.
 *
 * ---------------------------------------------------------------------------
 * v4 — why this was rewritten
 *
 * v3 hooked only `tool.execute.after`. That hook fires for tools that actually
 * EXECUTED, which excludes precisely the two failure classes worth measuring:
 *
 *   1. Permission denials — rejected before execution, so the hook never runs.
 *   2. Malformed `unknown` / `invalid` calls — no such tool exists to execute.
 *
 * Across three real phases those were ~100% of observed failures (14 denials,
 * 80 malformed calls), and `tool-errors.jsonl` was never created at all, because
 * appendFile only makes the file on first write. The calibration file that
 * MODEL_PROFILES.md tells you to trust over published benchmarks read "no
 * failures ever" by construction.
 *
 * v4 therefore counts from the EVENT STREAM as well as the execute hooks. Tool
 * parts carry a terminal `state.status` of "error" for both classes — that is
 * how they appear in `opencode export` output — so watching message/part events
 * catches what the execute hooks structurally cannot.
 *
 * It also writes a `plugin_loaded` line to sessions.jsonl at startup, so
 * "are my plugins even running?" is answerable with `ls` instead of hunting for
 * a console that the GUI does not surface.
 *
 * Event names differ across OpenCode builds, so the event handler is written
 * defensively: it walks whatever payload it gets looking for tool-shaped
 * objects rather than assuming a schema, and records each distinct event type
 * once to `events-seen.jsonl` so the real schema is discoverable from one run.
 * ---------------------------------------------------------------------------
 *
 * It deliberately does NOT write to progress.md. That file is the orchestrator's
 * hand-maintained phase state and — since the scoped-edit permission landed —
 * the one file the orchestrator rewrites wholesale. A plugin appending to it
 * means two writers race over one document: observed in a real run, where the
 * telemetry stamp was the only surviving line at the start of the next phase and
 * the orchestrator's next write erased it. State is curated; telemetry is
 * machine noise. They do not share a file.
 *
 * .gitignore: ignore .opencode/state/tool-errors.jsonl,
 * .opencode/state/sessions.jsonl and .opencode/state/events-seen.jsonl —
 * NOT the state/ directory, which holds progress.md.
 */

import type { Plugin } from "@opencode-ai/plugin"
import { appendFile, mkdir } from "node:fs/promises"
import { dirname } from "node:path"

const LOG = ".opencode/state/tool-errors.jsonl"
const SESSIONS = ".opencode/state/sessions.jsonl"
const EVENTS_SEEN = ".opencode/state/events-seen.jsonl"

async function append(file: string, line: string) {
  try {
    await mkdir(dirname(file), { recursive: true })
    await appendFile(file, line)
  } catch {
    /* telemetry is best-effort and must never break a session */
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

function trunc(v: unknown, n = 400): string | null {
  if (v === undefined || v === null) return null
  const s = typeof v === "string" ? v : String(v)
  return s.length > n ? `${s.slice(0, n)}…` : s
}

/**
 * Walk an arbitrary event payload for tool-shaped objects in a terminal state.
 * Shape assumed, defensively: { type?: "tool", tool?: string, state?: { status, input, output, error } }
 * Depth-limited so a deep payload cannot stall the handler.
 */
function findToolParts(node: any, depth = 0, out: any[] = []): any[] {
  if (!node || typeof node !== "object" || depth > 6) return out
  if (Array.isArray(node)) {
    for (const v of node) findToolParts(v, depth + 1, out)
    return out
  }
  const st = (node as any).state
  const looksLikeTool =
    st && typeof st === "object" && typeof st.status === "string" && ("tool" in node || node.type === "tool")
  if (looksLikeTool) out.push(node)
  for (const v of Object.values(node)) findToolParts(v, depth + 1, out)
  return out
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

  // Terminal tool states already logged, so the same part arriving on repeated
  // events is counted once. Keyed by callID (or a synthesised fallback).
  const seenTerminal = new Set<string>()
  const seenEventTypes = new Set<string>()

  // Proof-of-life. If this line is absent from sessions.jsonl, the plugin did
  // not load and NOTHING else in this file ran — including guard.ts's sibling
  // protections, which load by the same mechanism.
  await append(
    `${directory}/${SESSIONS}`,
    JSON.stringify({ ts: started, event: "plugin_loaded", plugin: "telemetry", directory }) + "\n",
  )

  async function record(kind: string, tool: string | null, err: unknown, args: unknown, callID: string | null) {
    toolErrors++
    await append(
      `${directory}/${LOG}`,
      JSON.stringify({
        ts: new Date().toISOString(),
        kind, // "denied" | "exec_error" | "malformed" | "error"
        tool,
        agent,
        model,
        callID,
        error: trunc(err),
        args: safeArgs(args),
      }) + "\n",
    )
  }

  return {
    // Fires for every dispatch that reaches execution. Counts volume; the
    // denial path never gets here, which is the whole reason for the event
    // handler below.
    "tool.execute.before": async (input: any, _output: any) => {
      toolCalls++
      void input
    },

    "tool.execute.after": async (input: any, output: any) => {
      // Heuristic: OpenCode surfaces failures either as a thrown error captured
      // on the output, or as an output whose text carries an error marker.
      const err =
        (output as any)?.error ??
        (output as any)?.isError ??
        (typeof (output as any)?.output === "string" && /^(error|Error:)/.test((output as any).output)
          ? (output as any).output
          : undefined)

      if (!err) return
      const callID = (input as any)?.callID ?? null
      if (callID && seenTerminal.has(callID)) return
      if (callID) seenTerminal.add(callID)
      await record("exec_error", (input as any)?.tool ?? null, err, (output as any)?.args, callID)
    },

    event: async ({ event }: { event: any }) => {
      const type = event?.type ?? "<untyped>"

      // Record each distinct event type once. One phase run then tells us the
      // real event schema for this OpenCode build, which is otherwise guesswork.
      if (!seenEventTypes.has(type)) {
        seenEventTypes.add(type)
        await append(
          `${directory}/${EVENTS_SEEN}`,
          JSON.stringify({ ts: new Date().toISOString(), type, keys: Object.keys(event?.properties ?? {}) }) + "\n",
        )
      }

      // Capture the active agent/model whenever a message updates.
      if (type === "message.updated") {
        const info = event?.properties?.info ?? {}
        if (info.agent) agent = String(info.agent)
        if (info.modelID) {
          model = info.providerID ? `${info.providerID}/${info.modelID}` : String(info.modelID)
        }
      }

      // THE v3 GAP. Permission denials and malformed `unknown`/`invalid` calls
      // never reach tool.execute.*, but they do surface as tool parts whose
      // state.status is "error". Catch them here.
      for (const part of findToolParts(event?.properties)) {
        const st = part.state ?? {}
        // `unknown` errors, but `invalid` reports status "completed" while
        // carrying the error string — measured 26 vs 9 in one real phase. Match
        // on the tool name too, or a quarter of the malformed calls go unlogged.
        const malformedName = part.tool === "unknown" || part.tool === "invalid"
        if (st.status !== "error" && !malformedName) continue
        if (st.status !== "error" && st.status !== "completed") continue

        const callID = part.callID ?? st.callID ?? part.id ?? null
        const key = callID ?? `${part.tool}:${trunc(st.error, 80)}`
        if (seenTerminal.has(key)) continue
        seenTerminal.add(key)

        const toolName = part.tool ?? null
        const errText = String(st.error ?? st.output ?? "")
        const kind = malformedName
          ? "malformed"
          : /rule which prevents you|permission|not permitted/i.test(errText)
            ? "denied"
            : "error"

        await record(kind, toolName, st.error ?? st.output, st.input, callID)
      }

      if (type !== "session.idle" || stamped) return
      stamped = true
      const rate = toolCalls ? ((toolErrors / toolCalls) * 100).toFixed(1) : "0.0"
      await append(
        `${directory}/${SESSIONS}`,
        JSON.stringify({
          ts: new Date().toISOString(),
          event: "session_idle",
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
