/**
 * guard.ts — Agentic Framework 2.1-OC
 *
 * Port of Framework 2.1's PreToolUse blocking hook (`exit 2`).
 * Throwing inside `tool.execute.before` rejects the tool call.
 *
 * This is deterministic enforcement: it does not depend on the model
 * reading, understanding, or obeying an instruction.
 */

import type { Plugin } from "@opencode-ai/plugin"

/**
 * Paths no agent may read or write, regardless of permissions.
 *
 * These are matched against a FILE PATH argument, so loose substring patterns
 * like /secret/ are fine here — `config/secrets.json` should match.
 */
const PROTECTED = [
  /(^|[\/\\])\.env($|\.)/i,
  /secret/i,
  /credential/i,
  /\.pem$/i,
  /\.p12$/i,
  /(^|[\/\\])id_rsa/i,
  /(^|[\/\\])id_ed25519/i,
  /\.key$/i,
  /(^|[\/\\])\.npmrc$/i,
  /(^|[\/\\])\.netrc$/i,
  /opencode\.local\.json$/i,
]

/**
 * A bash command is a sentence, not a path. Running PROTECTED against the raw
 * command string was a real bug: it blocked
 *
 *     gh label create "type:security" -d "Vulnerability, secret exposure, ..."
 *
 * because the word "secret" appeared in prose. Worse, the deny message claimed
 * a "protected path" was involved, which was false — so the agent correctly
 * inferred a false positive and spent several turns trying to smuggle the word
 * past the check. A guard that lies about why it fired teaches agents to evade
 * it.
 *
 * So for bash we only test tokens that actually look like filesystem paths:
 * something containing a slash, or a dotfile/extension-bearing basename.
 * `cat .env`, `cp ~/.aws/credentials .` and `rg -f secrets.json` still match;
 * the word "secret" inside a quoted sentence does not.
 */
function pathLikeTokens(cmd: string): string[] {
  // Strip quoted spans first — prose lives in quotes, paths usually do not.
  const unquoted = cmd.replace(/'[^']*'/g, " ").replace(/"[^"]*"/g, " ")
  return unquoted
    .split(/[\s;|&<>()]+/)
    .filter(Boolean)
    .filter((t) => /[\/\\]/.test(t) || /^\.?[\w.-]+\.[\w]+$/.test(t) || /^\.[\w-]+$/.test(t))
}

/** Paths that may be read but never written (lockfiles etc.). */
const WRITE_PROTECTED = [
  /\.lock$/i,
  /-lock\.(json|yaml|yml)$/i,
  /(^|[\/\\])Cargo\.lock$/i,
  /(^|[\/\\])poetry\.lock$/i,
  /(^|[\/\\])bun\.lock(b)?$/i,
]

/** Bash patterns that are never acceptable, even if a permission rule allows them. */
const BANNED_COMMANDS = [
  /\brm\s+-rf\s+\/(?!\w)/,
  /\bchmod\s+777\b/,
  /\bcurl\b[^|]*\|\s*(ba)?sh\b/,
  /\bwget\b[^|]*\|\s*(ba)?sh\b/,
  /\bgit\s+push\s+.*--force(?!-with-lease)/,
  /:\s*>\s*\//,
  /\bmkfs\b/,
  /\bdd\s+.*of=\/dev\//,
]

const READ_TOOLS = new Set(["read", "grep"])

// NOTE: the patch tool's registry ID is `apply_patch`, not `patch`.
// It is handled separately below because its arguments are shaped differently.
const WRITE_TOOLS = new Set(["write", "edit"])

function pathOf(args: any): string | undefined {
  return args?.filePath ?? args?.file_path ?? args?.path
}

/**
 * apply_patch carries `patchText`, NOT `filePath`. Target paths live in
 * marker lines inside the patch body, relative to the project root:
 *   *** Add File: src/new.ts
 *   *** Update File: src/old.ts
 *   *** Delete File: src/gone.ts
 *   *** Move to: src/moved.ts
 *
 * Note also that for GPT-class models OpenCode exposes apply_patch and
 * REMOVES edit and write entirely — so on those models this is the ONLY
 * write path, and missing it would leave the guard with nothing to check.
 */
function patchTargets(args: any): string[] {
  const text = String(args?.patchText ?? "")
  const out: string[] = []
  const rx = /^\*\*\*\s+(?:Add File|Update File|Delete File|Move to):\s*(.+?)\s*$/gm
  let m: RegExpExecArray | null
  while ((m = rx.exec(text))) out.push(m[1])
  return out
}

export const Guard: Plugin = async ({ client }) => {
  const deny = async (reason: string) => {
    await client.app
      .log({ body: { service: "af-guard", level: "warn", message: reason } })
      .catch(() => {})
    throw new Error(`[af-guard] ${reason}`)
  }

  return {
    "tool.execute.before": async (input: any, output: any) => {
      const tool = input.tool
      const args = output.args ?? {}

      // Collect every path this call would touch, and whether it is a write.
      let paths: string[] = []
      let isWrite = false

      if (tool === "apply_patch") {
        paths = patchTargets(args)
        isWrite = true
      } else if (WRITE_TOOLS.has(tool)) {
        const p = pathOf(args)
        if (typeof p === "string") paths = [p]
        isWrite = true
      } else if (READ_TOOLS.has(tool)) {
        const p = pathOf(args)
        if (typeof p === "string") paths = [p]
      }

      for (const p of paths) {
        for (const rx of PROTECTED) {
          if (rx.test(p)) {
            await deny(`Protected path, access denied: ${p}`)
          }
        }
        if (isWrite) {
          for (const rx of WRITE_PROTECTED) {
            if (rx.test(p)) {
              await deny(
                `Lockfile is write-protected: ${p}. ` +
                  `Change the manifest and re-run the package manager instead.`,
              )
            }
          }
        }
      }

      if (tool === "bash") {
        const cmd = String(args.command ?? "")

        for (const rx of BANNED_COMMANDS) {
          if (rx.test(cmd)) {
            await deny(`Command matches a hard-denied pattern: ${cmd}`)
          }
        }

        // Bash is the hole in file-tool guarding: `cat .env` never touches the
        // read tool, so the checks above would miss it entirely. It also cannot
        // be closed with OpenCode's bash permission patterns, which match
        // PARSED COMMANDS — a pattern containing a pipe or redirect never
        // matches. So we scan path-like TOKENS, not the whole command string.
        for (const token of pathLikeTokens(cmd)) {
          for (const rx of PROTECTED) {
            if (rx.test(token)) {
              await deny(
                `Shell command touches a protected path: "${token}". ` +
                  `If this is a false positive, fix the rule in ` +
                  `.opencode/plugins/guard.ts — do not reword the command to ` +
                  `slip past it.`,
              )
            }
          }
        }

        // Redirect-based writes to lockfiles (`> bun.lock`, `>> Cargo.lock`).
        if (/[>]{1,2}\s*\S*(\.lock|-lock\.(json|ya?ml))\b/i.test(cmd)) {
          await deny(`Shell redirect would overwrite a lockfile: ${cmd}`)
        }
      }
    },
  }
}
