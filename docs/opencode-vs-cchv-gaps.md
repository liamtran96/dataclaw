# OpenCode Gaps vs CCHV

## Scope

This note compares OpenCode handling in:

- DataClaw: `~/dataclaw`
- Claude Code History Viewer (CCHV): `~/claude-code-history-viewer`

The goal is to identify OpenCode data that CCHV captures more faithfully than DataClaw today, with references to both codebases and to the real OpenCode data stored on this machine.

## Summary

CCHV preserves substantially more OpenCode part-level structure than DataClaw.

The biggest current DataClaw gaps are:

1. It drops OpenCode `file` parts, including real image `data:` URIs stored in the database.
2. It drops `patch`, `step-start`, `step-finish`, and `compaction` parts.
3. It loses per-message usage and cost derived from `step-finish` parts.
4. It loses message threading via `parentID`.
5. It flattens OpenCode content into a smaller normalized schema and drops part-level structure that CCHV keeps.

## Detailed Findings

### 1. CCHV keeps OpenCode `file` parts; DataClaw drops them

CCHV processes OpenCode `part.type == "file"` and preserves:

- image `data:` URIs as image blocks
- image URLs as image blocks
- non-image file references as file text blocks

References:

- CCHV OpenCode part processing: `~/claude-code-history-viewer/src-tauri/src/providers/opencode.rs:1204-1240`

DataClaw's OpenCode parser ignores `file` parts entirely.

References:

- DataClaw user extraction only keeps `text` parts: `~/dataclaw/dataclaw/parsers/opencode.py:210-223`
- DataClaw assistant extraction only handles `text`, `reasoning`, and `tool`: `~/dataclaw/dataclaw/parsers/opencode.py:226-277`

Practical consequence:

- DataClaw drops OpenCode file references and image payloads that CCHV keeps.

Observed in real OpenCode data on this machine:

- querying `~/.local/share/opencode/opencode.db` showed `99` `file` parts
- `7` of those were image parts with `mime: image/png`
- those image parts used `data:image/png;base64,...` URLs

Example real image part from the database:

- DB file: `~/.local/share/opencode/opencode.db`
- session: `ses_3321dc5e9ffeljot1d6UlwCGOB`
- message: `msg_ccde78ea3001CsoqVaRwira24N`
- part payload contains:
  - `type: "file"`
  - `mime: "image/png"`
  - `url: "data:image/png;base64,..."`

### 2. CCHV keeps `patch`, `step-start`, `step-finish`, and `compaction` parts; DataClaw drops them

CCHV explicitly handles these OpenCode part types:

- `patch`
- `step-start`
- `step-finish`
- `compaction`

References:

- `step-finish` and `compaction`: `~/claude-code-history-viewer/src-tauri/src/providers/opencode.rs:1130-1181`
- `patch`: `~/claude-code-history-viewer/src-tauri/src/providers/opencode.rs:1182-1202`
- `step-start`: `~/claude-code-history-viewer/src-tauri/src/providers/opencode.rs:1242-1249`

DataClaw's OpenCode parser does not handle any of these part types.

References:

- DataClaw assistant extraction only branches on `text`, `reasoning`, and `tool`: `~/dataclaw/dataclaw/parsers/opencode.py:235-265`

Practical consequence:

- DataClaw drops patch summaries, step boundaries, and compaction markers that CCHV shows.

Observed in real OpenCode data on this machine:

- `patch`: `2349` parts
- `step-start`: `9572` parts
- `step-finish`: `9451` parts
- `compaction`: `32` parts

Example real parts from the database:

- Patch part:
  - DB file: `~/.local/share/opencode/opencode.db`
  - session: `ses_3abf6a2e7ffeRw4KIgQY5d0prz`
  - message: `msg_c540a13e8001dgyT9upME85T5v`
  - part payload: `{"type":"patch","files":["~/ComfyUI/comfy/ldm/wan/model.py"],...}`

- Compaction part:
  - DB file: `~/.local/share/opencode/opencode.db`
  - session: `ses_3afeba227ffeLYbMdEzqlMWeKD`
  - message: `msg_c51049d72001i65GspUCMGRSZB`
  - part payload: `{"type":"compaction","auto":true}`

### 3. CCHV keeps per-message token usage and cost; DataClaw only keeps session totals

CCHV derives OpenCode per-message usage and cost from both:

- message-level fields
- `step-finish` parts

References:

- message-level usage/cost extraction: `~/claude-code-history-viewer/src-tauri/src/providers/opencode.rs:822-883`
- `step-finish` token/cost accumulation: `~/claude-code-history-viewer/src-tauri/src/providers/opencode.rs:1130-1171`

DataClaw only accumulates OpenCode token counts into session-level `stats`, and does not keep per-message usage or cost.

References:

- DataClaw token accumulation: `~/dataclaw/dataclaw/parsers/opencode.py:180-186`
- DataClaw normalized session schema: `~/dataclaw/dataclaw/parsers/common.py:56-71`

Practical consequence:

- DataClaw loses per-message usage/cost fidelity that CCHV preserves.

Observed in real OpenCode data on this machine:

- many messages have no `tokens` in `message.data`, but real `step-finish` parts do have:
  - `tokens.input`
  - `tokens.output`
  - `tokens.cache.read`
  - `tokens.cache.write`
  - `cost`

Example `step-finish` payload from the database:

- DB file: `~/.local/share/opencode/opencode.db`
- contains values like:
  - `{"type":"step-finish","reason":"tool-calls","cost":0,"tokens":{"input":11294,"output":83,"cache":{"read":0,"write":0}}}`

### 4. CCHV keeps message threading via `parentID`; DataClaw drops it

CCHV maps OpenCode `parentID` to `parent_uuid` in the loaded message model.

References:

- OpenCode DB path message metadata extraction: `~/claude-code-history-viewer/src-tauri/src/providers/opencode.rs:827-830`
- JSON fallback path does the same: `~/claude-code-history-viewer/src-tauri/src/providers/opencode.rs:416-420`

DataClaw's normalized export schema does not preserve message parent links.

References:

- DataClaw session schema: `~/dataclaw/dataclaw/parsers/common.py:56-71`

Practical consequence:

- DataClaw loses OpenCode message threading / parent-child structure that CCHV keeps.

Observed in real OpenCode data on this machine:

- querying `~/.local/share/opencode/opencode.db` showed that many OpenCode messages include `parentID`
- at inspection time, `9697` messages had a non-empty `parentID`

### 5. CCHV keeps a richer OpenCode content array; DataClaw flattens it

CCHV turns OpenCode parts into a structured content array with items like:

- `text`
- `thinking`
- `tool_use`
- `tool_result`
- `image`
- patch summaries
- step summaries

References:

- CCHV `process_parts(...)`: `~/claude-code-history-viewer/src-tauri/src/providers/opencode.rs:1049-1260`

DataClaw flattens OpenCode into a smaller schema:

- user `content`
- assistant `content`
- assistant `thinking`
- assistant `tool_uses`

References:

- DataClaw user content extraction: `~/dataclaw/dataclaw/parsers/opencode.py:210-223`
- DataClaw assistant content extraction: `~/dataclaw/dataclaw/parsers/opencode.py:226-277`

Practical consequence:

- DataClaw loses OpenCode part-level fidelity beyond the normalized text/thinking/tool schema.

### 6. Potential additional gap: CCHV has a JSON-storage fallback path; DataClaw only reads SQLite

CCHV loads OpenCode messages from SQLite first, then falls back to JSON storage files under `storage/` when needed.

References:

- CCHV SQLite-first, JSON-fallback loading: `~/claude-code-history-viewer/src-tauri/src/providers/opencode.rs:333-497`

DataClaw only reads the SQLite database at:

- `~/.local/share/opencode/opencode.db`

References:

- DataClaw OpenCode DB-only parser: `~/dataclaw/dataclaw/parsers/opencode.py:103-194`

Practical consequence:

- If some OpenCode data exists only in JSON storage and not in SQLite, CCHV can see it but DataClaw cannot.

This note does not claim that such DB-missing session content was observed on this machine; it is an implementation difference worth noting.

## Observed In Real OpenCode Data On This Machine

At inspection time, querying `~/.local/share/opencode/opencode.db` showed these real OpenCode part types:

- `tool`: `12112`
- `step-start`: `9572`
- `step-finish`: `9451`
- `reasoning`: `8641`
- `text`: `3886`
- `patch`: `2349`
- `file`: `99`
- `compaction`: `32`

The most important real payload classes for the comparison were:

- image file parts with base64 `data:` URIs
- patch parts with modified file lists
- step-finish parts with tokens/cost
- compaction markers
- pervasive `parentID` message links

## Bottom Line

Compared with CCHV, DataClaw currently loses substantial OpenCode fidelity around:

- image/file parts
- patch / step / compaction parts
- per-message usage and cost
- parent-child message threading
- part-level content structure generally

The largest practical gap on this machine is that OpenCode stores real base64 image payloads in the database, CCHV preserves them, and DataClaw currently drops them.
