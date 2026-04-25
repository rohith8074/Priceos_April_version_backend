# Live Execution Graph Implementation Guide

This document explains how the "Live Execution" graph is implemented in the `dev2` codebase, across both frontend and backend, and how to reproduce the same pattern in another project.

Codebase analyzed:

- `supply_chain_agentic_os_ui`
- `supply_chain_agentic_os_backend`

Important conclusion up front:

- The graph is not streamed from this FastAPI backend.
- The realtime execution events come from Lyzr's websocket metrics stream, keyed by `session_id`.
- The backend's role is to create a job, preserve the `session_id`, forward the prompt to Lyzr, expose polling endpoints, and persist chat/proposal history.
- The frontend then merges:
  - realtime websocket events from Lyzr
  - synthetic local events emitted by the UI itself
  - backend polling state
  - final structured response payloads

That combination is what makes the graph feel "live" even when some upstream events are missing.

## 1. Main files involved

### Frontend

- `supply_chain_agentic_os_ui/src/components/ui/agent-page.tsx`
  - Shared chat shell used by multiple agent pages.
  - Owns the chat request lifecycle, live flow state, local synthetic graph events, and the compact/expanded graph UI.
- `supply_chain_agentic_os_ui/src/components/ui/live-inference-flow-graph.tsx`
  - Converts stage state and event history into React Flow nodes and edges.
- `supply_chain_agentic_os_ui/src/hooks/use-lyzr-agent-events.ts`
  - Connects to the Lyzr websocket using `session_id`, normalizes incoming events, deduplicates them, and exposes them to the UI.
- `supply_chain_agentic_os_ui/src/lib/chat/inference-events.ts`
  - Small browser event bus used for synthetic local events.
- `supply_chain_agentic_os_ui/src/app/api/chat/route.ts`
  - Next.js BFF route for creating chat jobs.
- `supply_chain_agentic_os_ui/src/app/api/chat/status/route.ts`
  - Next.js BFF route for polling job status and also returning websocket key/config when no `jobId` is supplied.
- `supply_chain_agentic_os_ui/src/app/api/sessions/route.ts`
- `supply_chain_agentic_os_ui/src/app/api/sessions/[id]/route.ts`
- `supply_chain_agentic_os_ui/src/app/api/proposals/route.ts`
  - Session and proposal persistence proxies.

### Backend

- `supply_chain_agentic_os_backend/main.py`
  - Creates/polls chat jobs, calls Lyzr inference, stores job state, stores session history, stores proposal decisions.
- `supply_chain_agentic_os_backend/routes/agent_query.py`
  - Returns structured tool response metadata such as `collection`, `total_matched`, and `returned`, which the graph can surface as row statistics.

### Example page using the shared implementation

- `supply_chain_agentic_os_ui/src/app/spend-intelligence/spend-intelligence-client.tsx:281-310`
  - Shows how a domain page simply renders `AgentPage` and inherits the Live Execution experience automatically.

## 2. High-level architecture

```text
User types prompt
  -> AgentPage.sendMessage()
  -> Next.js /api/chat
  -> FastAPI /chat/jobs
  -> background task _process_job()
  -> FastAPI _agent_chat()
  -> Lyzr inference API
  -> Lyzr processes the request under a session_id
  -> Lyzr websocket emits execution events for that same session_id
  -> Frontend hook subscribes to wss://metrics.studio.lyzr.ai/ws/{session_id}
  -> AgentPage combines:
       - websocket events
       - local synthetic events
       - polling status
       - final structured response
  -> LiveInferenceFlowGraph builds nodes/edges and renders with React Flow
```

There are really two channels in parallel:

1. The response channel
   - HTTP request/response plus job polling.
   - Used to get the final answer safely and reliably.

2. The observability channel
   - Lyzr websocket events plus local synthetic UI events.
   - Used to visualize execution before the final answer lands.

This split is the core pattern to copy.

## 3. Frontend implementation

## 3.1 Shared host component: `AgentPage`

The Live Execution graph is not page-specific. It is implemented once inside `AgentPage`, then reused by multiple domain pages.

Relevant references:

- `agent-page.tsx:1377+` exports `AgentPage`
- `spend-intelligence-client.tsx:281-310` shows a page composing `AgentPage`

This is a good design choice for replication because:

- the graph logic stays in one place
- all agent pages get the same execution UX
- only the domain content changes per page

## 3.2 Local state model

`AgentPage` defines a small lifecycle state machine:

- `LiveInferenceStatus = "idle" | "submitting" | "queued" | "processing" | "completed" | "failed"`
- `LiveInferenceFlow` stores:
  - `status`
  - `jobId`
  - `backendStatus`
  - `error`
  - `startedAt`
  - `isPolling`

Reference:

- `agent-page.tsx:210-231`

This state exists independently of websocket events, which is important because it gives you a fallback graph even when no realtime events arrive.

## 3.3 Request lifecycle in `sendMessage()`

The full client-side flow lives in `agent-page.tsx:1790-2068`.

### Step A: optimistic chat + initial flow state

When the user submits:

- the user message is appended to chat immediately
- `loading` becomes `true`
- `liveInferenceFlow` moves to `submitting`

Reference:

- `agent-page.tsx:1804-1813`

It also tries to emit a synthetic local event:

- `event_type: "agent_process_start"`
- `status: "submitting"`
- `message: "Submitting query to agent"`

Reference:

- `agent-page.tsx:1814-1819`

Nuance:

- `emitLocalGraphEvent()` requires a non-empty `sessionId` (`agent-page.tsx:1433-1440`).
- On a brand-new chat there is no session yet, so this first synthetic event does not fire.
- The graph still shows progress because `liveInferenceFlow` itself changed to `submitting`.

### Step B: call the Next.js BFF

The UI posts to:

- `POST /api/chat`

Reference:

- `agent-page.tsx:1821-1826`

### Step C: normalize session and job identity

After the BFF responds, the client extracts:

- `session_id`
- `job_id`
- initial backend `status`
- any immediate `response`

Reference:

- `agent-page.tsx:1848-1856`

This is where the graph gets its correlation key: `session_id`.

### Step D: emit a second synthetic start event

Once a real `session_id` exists, the client emits another synthetic start event:

- `event_type: "agent_process_start"`
- `status: queued/processing`
- `message: "Inference job accepted"` or `"Inference started"`

Reference:

- `agent-page.tsx:1857-1862`

This is more important than the first synthetic event because now it is session-scoped and can be ingested by the event hook.

### Step E: start polling if the backend returned a job

If there is no immediate final response, the client polls:

- `GET /api/chat/status?jobId=...`

Reference:

- `agent-page.tsx:1875-2003`

While polling:

- changes in polled status emit `agent_process_update`
- success emits `process_complete`
- failures emit `process_error`
- `liveInferenceFlow` is continuously updated

References:

- status update event: `agent-page.tsx:1906-1915`
- status-to-flow update: `agent-page.tsx:1916-1923`
- completion path: `agent-page.tsx:1925-1947`
- failure path: `agent-page.tsx:1950-1980`

### Step F: parse the final structured payload

Once a final `agentText` arrives, `parseAgentReply()` attempts to split:

- structured JSON payload
- human-readable plain text

References:

- parser helpers: `agent-page.tsx:247-325`
- final parse usage: `agent-page.tsx:2046-2068`

This matters because the graph later uses structured payload fields to create "artifact" nodes such as:

- summary
- recommendation
- proposal candidate
- data sources
- chart/table counts

### Step G: emit synthetic tool events from final payload

If the final structured payload contains `data_used`, the client emits synthetic `tool_response` events for each tool name.

Reference:

- `agent-page.tsx:2047-2060`

Why this exists:

- websocket streams are not always guaranteed to include every tool event in the exact shape the graph wants
- the final payload already knows which tools contributed
- synthesizing `tool_response` events ensures the graph can still display tool nodes

This is a very practical replication pattern.

### Step H: save chat and proposal state

After a successful response:

- the conversation is saved to `/api/sessions`
- proposals are saved to `/api/proposals`

References:

- session save helper: `agent-page.tsx:1740-1762`
- proposal persistence helper: `agent-page.tsx:1764-1788`
- save after completion: `agent-page.tsx:2068+`

The graph itself is for live execution, but these persistence hooks make the surrounding UX complete.

## 3.4 Event ingestion hook: `useLyzrAgentEvents`

This hook is the realtime backbone.

References:

- event shape: `use-lyzr-agent-events.ts:9-33`
- websocket config: `use-lyzr-agent-events.ts:41-44`
- normalize/dedupe: `use-lyzr-agent-events.ts:75-145`, `200-212`
- websocket lifecycle: `use-lyzr-agent-events.ts:226-271`
- local event bus listener: `use-lyzr-agent-events.ts:273-290`

### What it does

1. Fetches websocket API key/config from `/api/chat/status` when called without `jobId`
   - `use-lyzr-agent-events.ts:161-176`
   - `chat/status/route.ts:43-54`
2. Resets event memory when `sessionId` changes
   - `use-lyzr-agent-events.ts:178-182`
3. Opens:

```text
wss://metrics.studio.lyzr.ai/ws/{sessionId}?x-api-key={key}
```

Reference:

- `use-lyzr-agent-events.ts:234-242`

4. Reconnects automatically on close/error
   - `use-lyzr-agent-events.ts:253-261`
5. Deduplicates events by a fingerprint composed of timestamp, type, iteration, status, message, thinking, and tool/function name
   - `use-lyzr-agent-events.ts:75-86`
   - `use-lyzr-agent-events.ts:204-206`
6. Stores only the latest 180 events
   - `use-lyzr-agent-events.ts:44`
   - `use-lyzr-agent-events.ts:208`

### Important implementation detail

Events are stored newest-first:

- `setEvents((prev) => [normalized, ...prev].slice(0, MAX_SESSION_EVENTS))`

Reference:

- `use-lyzr-agent-events.ts:208`

Then the graph builder reverses them back to chronological order:

- `const orderedEvents = [...streamEvents].reverse()`

Reference:

- `live-inference-flow-graph.tsx:479-487`

That is a clean pattern:

- prepend for cheap updates in React state
- reverse once during graph build

## 3.5 Local synthetic event bus

`src/lib/chat/inference-events.ts` defines a browser-only event bus:

- event name: `support-agent-stream-event`
- payload: `{ sessionId, event }`

Reference:

- `inference-events.ts:1-41`

`AgentPage` uses it through `emitLocalGraphEvent()`:

- `agent-page.tsx:1433-1440`

The websocket hook listens to the same browser event and ingests it exactly like a real upstream event:

- `use-lyzr-agent-events.ts:273-290`

This is an elegant design because:

- the graph has a single consumer path
- synthetic and real events share one event model
- the UI can patch observability gaps without special-case rendering logic

## 3.6 Stage derivation before/without graph events

Before building the actual graph nodes, the UI derives high-level stages.

References:

- websocket-aware stages: `agent-page.tsx:546-635`
- polling fallback stages: `agent-page.tsx:637-683`

There are two strategies:

### Websocket-aware stages

If stream events exist, the UI detects whether execution has:

- started
- completed
- hit knowledge retrieval
- hit memory recall
- prepared/executed tools
- produced output

This drives stages like:

- Query
- Orchestrator
- Knowledge
- Memory
- Tool Calls
- Response

### Polling fallback stages

If stream events do not exist, it uses a simpler flow:

- Query
- Dispatch
- Inference
- Response

This fallback is why the Live Execution card still works when websocket data is sparse or absent.

## 3.7 Compact card and expanded modal

The graph appears in two places:

1. Compact card inside the chat sidebar
2. Expanded dialog with the full graph

References:

- compact card rendering: `agent-page.tsx:2697-2705`
- expanded dialog: `agent-page.tsx:2943-2957`
- card component behavior: `agent-page.tsx:685-803`

That split is worth copying:

- the compact view acts as a live status chip
- the expanded view gives deep inspection without cluttering the chat area

## 4. Graph builder internals: `live-inference-flow-graph.tsx`

This file contains the actual graph intelligence.

## 4.1 Rendering stack

The graph uses:

- `@xyflow/react` for node/edge layout and interaction
- `@tabler/icons-react` for node iconography

References:

- imports: `live-inference-flow-graph.tsx:3-26`
- package dependency: `supply_chain_agentic_os_ui/package.json`

## 4.2 Event-to-graph conversion

The main work happens in:

- `buildEventGraph()` at `live-inference-flow-graph.tsx:479-924`

### Event bucketing by iteration

The graph groups events into `IterationBucket`s:

- each bucket tracks:
  - `iteration`
  - `thoughts`
  - `tools`

References:

- bucket types: `live-inference-flow-graph.tsx:173-203`
- bucket creation: `live-inference-flow-graph.tsx:487-500`

The graph uses `tool_calling_iteration` to switch active iteration:

- `live-inference-flow-graph.tsx:513-517`

That is how it lays out "Iteration 1", "Iteration 2", etc.

### Thought capture

If an event is a `thinking_log` or contains `thinking`, it becomes a reasoning node candidate.

Reference:

- `live-inference-flow-graph.tsx:523-527`

### Tool accumulation

For each tool name/function name, the graph collects:

- call count
- response count
- output count
- matched row count
- returned row count
- execution time
- parallel execution flag
- collection name
- status

References:

- tool aggregation block: `live-inference-flow-graph.tsx:529-579`

### Structured output artifacts

When the graph sees `process_complete`, it attempts to parse the final response into artifacts:

- summary
- recommendation
- proposal
- data source list
- chart/table counts

References:

- `parseCompletionArtifact()`: `live-inference-flow-graph.tsx:287-325`
- completion trigger: `live-inference-flow-graph.tsx:582-584`

## 4.3 Tool statistics extraction

One of the smartest parts of this implementation is `extractToolStats()`.

Reference:

- `live-inference-flow-graph.tsx:221-285`

It can read row/count metadata from either:

- structured objects
- loosely formatted JSON-like strings

It looks for fields like:

- `collection`
- `total_matched`
- `totalMatched`
- `total_count`
- `returned`
- `rows_returned`
- `data.length`

This makes the graph resilient to inconsistent tool payload formatting.

## 4.4 Graph layout strategy

The node layout is fixed-position, not auto-laid-out.

References:

- layout constants: `live-inference-flow-graph.tsx:595-602`

Pattern:

- start node on the left
- one main iteration node per column
- thinking node above the iteration
- tool nodes below the iteration
- final node after the last iteration
- artifact nodes to the far right

References:

- start node: `live-inference-flow-graph.tsx:604-617`
- iteration nodes: `live-inference-flow-graph.tsx:622-668`
- thinking nodes: `live-inference-flow-graph.tsx:670-690`
- tool nodes: `live-inference-flow-graph.tsx:697-731`
- final node: `live-inference-flow-graph.tsx:756-783`
- artifact nodes: `live-inference-flow-graph.tsx:785-900`

This is a strong choice for a reproducible "execution storyboard" because the graph is deterministic and readable.

## 4.5 Truncation and readability choices

The graph deliberately limits visual complexity:

- only 4 tool nodes are shown per iteration
- extra tools collapse into a `+N more tool calls` node

Reference:

- `live-inference-flow-graph.tsx:602`
- `live-inference-flow-graph.tsx:693-753`

This is important to replicate. Without truncation, dense agent runs quickly become unreadable.

## 4.6 Summary header metrics

Above the graph, the component shows:

- iterations
- tools
- outputs
- thinking logs
- rows matched
- last event

Reference:

- `live-inference-flow-graph.tsx:948-979`

These are computed from the aggregated graph metadata:

- `live-inference-flow-graph.tsx:912-923`

This summary adds value even if the user never zooms into the graph.

## 4.7 React Flow rendering

The final render uses:

- `fitView`
- non-draggable nodes
- non-connectable nodes
- `MiniMap`
- `Controls`
- background grid

Reference:

- `live-inference-flow-graph.tsx:981-1016`

That means the graph is intended as a viewer, not an editor.

## 5. Backend implementation

Again, the key point:

- the backend does not broadcast Live Execution graph events itself
- it provides identity, job control, persistence, and final responses

## 5.1 Backend API key routing

The backend chooses Lyzr keys based on agent identity:

- spend/logistics agents use `LYZR_API_KEY`
- other agents use `LYZR_API_KEY2`

Reference:

- `main.py:89-98`

Replication note:

- `.env.example` currently documents `LYZR_API_KEY`, but the code also expects `LYZR_API_KEY2`.
- When copying this pattern, explicitly define both.

## 5.2 Job creation and async processing

FastAPI creates a background job at:

- `POST /chat/jobs`

Reference:

- `main.py:805-836`

What it does:

1. Validates `message` and `agentId`
2. Creates a `job_id`
3. Creates or reuses a `session_id`
4. Stores the job in memory and, if configured, in DocumentDB/Mongo or Supabase
5. Starts `_process_job(job_id)` as a background task

This is the backend foundation that the UI polls.

## 5.3 Calling Lyzr inference

The actual upstream call happens in `_agent_chat()`:

- `main.py:637-704`

Payload sent upstream:

```json
{
  "user_id": "...",
  "agent_id": "...",
  "session_id": "...",
  "message": "..."
}
```

That `session_id` is the most important field for Live Execution because:

- the final response uses it
- the websocket stream is keyed by it
- session persistence also uses it

If you replicate this feature with another provider, you need an equivalent correlation key.

## 5.4 Background job worker

`_process_job()` is the async worker:

- `main.py:707-761`

It:

1. marks the job `processing`
2. calls `_agent_chat()`
3. extracts the reply text
4. stores raw results
5. marks job `completed` or `failed`

Notice what it does not do:

- it does not stream partial events to the frontend
- it does not expose server-sent events
- it does not maintain a websocket for execution tracing

That is why the frontend must subscribe directly to the Lyzr metrics websocket.

## 5.5 Polling status endpoint

The polling endpoint is:

- `GET /chat/jobs/{job_id}`

Reference:

- `main.py:839-844`

The response is normalized by `_chat_job_status_payload()`:

- `main.py:782-802`

Possible payloads are roughly:

```json
{ "status": "queued" }
```

```json
{ "status": "processing" }
```

```json
{
  "status": "completed",
  "response": "...",
  "session_id": "..."
}
```

```json
{
  "status": "failed",
  "error": "...",
  "errorCode": 500
}
```

That is enough for the UI to drive fallback stages even if no stream events are available.

## 5.6 Job persistence

Job state is stored in several places:

- in-memory `_jobs`
- DocumentDB/Mongo (best effort)
- Supabase (best effort)

References:

- startup wiring: `main.py:369-469`
- DocumentDB insert/update/get: `main.py:481-540`
- Supabase insert/update/get: `main.py:543-619`
- `_get_job_by_id()`: `main.py:771-779`

This gives the polling flow some resilience across process boundaries, assuming persistence is configured.

## 5.7 Session history persistence

The graph is live-only, but chat history persistence makes the overall feature usable.

Backend routes:

- save message pair: `main.py:1235-1264`
- list sessions: `main.py:1267-1282`
- get one session: `main.py:1285-1292`
- delete session: `main.py:1295-1302`

The frontend proxies these through:

- `api/sessions/route.ts`
- `api/sessions/[id]/route.ts`

References:

- frontend proxy list/save: `api/sessions/route.ts:1-41`
- frontend proxy get/delete: `api/sessions/[id]/route.ts:1-43`

Important nuance:

- restoring a previous chat restores messages and proposal state
- it does not restore prior realtime event history
- `loadSession()` explicitly resets `liveInferenceFlow` to idle

Reference:

- `agent-page.tsx:1592-1619`

So the graph is "current run live state", not a historical trace viewer.

## 5.8 Proposal persistence and graph-adjacent artifacts

Proposal decisions are stored in backend collections:

- save decision: `main.py:1305-1347`
- list decisions: `main.py:1350-1368`

The Next.js BFF proxies these via:

- `api/proposals/route.ts:1-57`

This matters for the graph because the final artifact/proposal nodes are derived from the same structured response shape that proposal persistence uses.

## 5.9 Tool route metadata that powers graph statistics

The graph can show counts like "rows matched" because tool route responses include fields such as:

- `collection`
- `total_matched`
- `returned`

Reference:

- `routes/agent_query.py:23-84`

Example return shape:

```json
{
  "collection": "fact_inventory_on_hand",
  "total_matched": 1240,
  "returned": 100,
  "skip": 0,
  "limit": 100,
  "data": [ ... ]
}
```

Then `extractToolStats()` in the frontend reads that and displays it in tool chips and graph summary.

This is an important replication detail: if your tool APIs do not return lightweight stats, your graph will look much less informative.

## 6. Next.js BFF layer

The Next.js routes are doing more than proxying.

## 6.1 `POST /api/chat`

Reference:

- `api/chat/route.ts:232-331`

Responsibilities:

- forwards to FastAPI `/chat/jobs`
- normalizes `job_id`, `session_id`, and `status`
- accepts either immediate responses or queued jobs
- parses structured responses when immediate
- optionally enriches spend responses with fallback proposal data
- persists pending proposals

This BFF layer keeps frontend code cleaner and centralizes backend quirks.

## 6.2 `GET /api/chat/status`

Reference:

- `api/chat/status/route.ts:39-120`

It has two modes:

1. No `jobId`
   - returns websocket config:
   - `wsApiKey`
   - `inferenceConfigured`

2. With `jobId`
   - polls FastAPI `/chat/jobs/{jobId}`
   - normalizes `status`, `response`, `session_id`, `results`, `error`

This dual-purpose route is clever, but a little non-obvious. If you replicate it, document it clearly.

## 6.3 Backend URL and API key centralization

Reference:

- `backend-config.ts:1-34`

This file centralizes:

- `BACKEND_URL`
- `NEXT_PUBLIC_BACKEND_URL`
- `BACKEND_API_KEY`

That is the right pattern to copy so graph, chat, sessions, and proposals all talk to the same backend consistently.

## 7. Exact data contracts that matter

## 7.1 Chat job creation response

Expected by the frontend:

```json
{
  "status": "queued",
  "job_id": "job_123",
  "session_id": "agent-abc123"
}
```

Why it matters:

- `job_id` drives polling
- `session_id` drives the websocket subscription

## 7.2 Job status response

Expected by the frontend:

```json
{
  "status": "processing"
}
```

or

```json
{
  "status": "completed",
  "response": "{ ... possibly structured JSON ... }",
  "session_id": "agent-abc123"
}
```

or

```json
{
  "status": "failed",
  "error": "Upstream Lyzr API error",
  "errorCode": 502
}
```

## 7.3 Websocket event shape

After normalization, the frontend cares most about:

- `event_type`
- `status`
- `message`
- `thinking`
- `iteration`
- `max_iterations`
- `execution_time`
- `parallel_execution`
- `response`
- `tool_output`
- `function_name`
- `tool_name`
- `session_id`

Reference:

- `use-lyzr-agent-events.ts:94-130`

## 7.4 Structured final response shape

The graph and UI both understand a final structured response with fields such as:

- `summary`
- `analysis`
- `data_used`
- `table_data`
- `chart_data`
- `recommendation`
- `proposal`

References:

- frontend type: `agent-page.tsx:156-202`
- BFF type: `api/chat/route.ts:4-46`

This is what feeds:

- rendered charts/tables
- proposal cards
- graph artifact nodes

## 8. How the graph remains useful even when realtime data is incomplete

This codebase is intentionally layered so the graph does not depend on a perfect stream.

It has four fallback levels:

1. `liveInferenceFlow` state machine
   - always available once the user sends a prompt
2. polling status changes
   - emits local `agent_process_update` / `process_complete` / `process_error`
3. synthetic tool events from `data_used`
   - creates tool nodes even if live tool events are missing
4. fallback stage graph
   - renders a simple Query -> Dispatch -> Inference -> Response pipeline if there are zero stream events

References:

- local flow stages: `agent-page.tsx:637-683`
- local synthetic events: `agent-page.tsx:1814-1819`, `1857-1862`, `1909-1914`, `1933-1938`, `1966-1970`, `2053-2059`, `2062-2067`
- fallback graph: `live-inference-flow-graph.tsx:431-477`

This resilience is one of the best parts of the implementation and absolutely should be preserved in any copy.

## 9. Replication recipe for another project

If you want the same feature elsewhere, copy the pattern below, not just the UI widget.

## 9.1 Backend requirements

You need:

1. A stable `session_id` created before or at job submission time
2. A `job_id` for polling
3. A job creation endpoint
4. A job status endpoint
5. A way to call your agent/provider using that same `session_id`
6. Optional persistence for:
   - job records
   - chat sessions
   - proposals/actions

Minimal backend API shape:

```text
POST /chat/jobs
GET  /chat/jobs/{job_id}
POST /chat/sessions/message
GET  /chat/sessions?agent_id=...
GET  /chat/sessions/{session_id}
DELETE /chat/sessions/{session_id}
POST /chat/proposals/decision
GET  /chat/proposals
```

## 9.2 Realtime event requirements

You need one of these:

- provider websocket event stream keyed by session
- your own websocket/SSE event stream keyed by session
- or both

The most important requirement is correlation, not transport.

Every live event must be attributable to the same `session_id` used by the chat request.

## 9.3 Frontend requirements

Build these pieces:

1. A shared `AgentPage`-like shell
2. A `LiveInferenceFlow` state machine
3. A `useAgentEvents(sessionId, isProcessing)` hook
4. A local synthetic event bus
5. A graph renderer that can work with:
   - full event streams
   - partial event streams
   - zero event streams
6. A final response parser that can split structured JSON from plain text

## 9.4 Event normalization layer

Do not let your graph component consume raw provider events directly.

Instead:

- define one normalized event interface
- map all provider payloads into that interface
- also emit synthetic UI events in the same interface

That is exactly what this code does with:

- `LyzrAgentEvent`
- `SupportAgentActivityEvent`

## 9.5 Instrument your tool responses

If you want useful graph chips and summary metrics, return tool metadata such as:

- tool name
- collection/dataset name
- returned row count
- total matched row count
- execution time
- parallel execution flag

Without that, your graph can still exist, but it will feel shallow.

## 9.6 Keep the graph generic

Do not hardcode it into one page.

Instead:

- create one shared host component
- pass in `agentId`, title, prompts, and domain visuals
- let every agent page inherit the graph

That is the difference between a one-off demo and a reusable platform feature.

## 9.7 Keep a fallback path

Your UI should still show execution progress if:

- websocket auth fails
- provider events are delayed
- some tool events are missing
- the backend only gives queued/processing/completed statuses

This project handles that correctly with:

- fallback stage derivation
- local synthetic events
- polling-driven flow updates

## 10. Recommended implementation order if recreating this

Build it in this order:

1. Implement job creation and polling with `job_id` and `session_id`
2. Make your agent call preserve `session_id`
3. Add frontend polling UI with a simple 4-stage fallback graph
4. Add a websocket event hook keyed by `session_id`
5. Normalize provider event payloads
6. Add a synthetic local event bus
7. Add tool-stat extraction and iteration grouping
8. Add final artifact nodes from structured responses
9. Add session persistence
10. Add proposal/action persistence if your product uses that pattern

That order gets you a working graph early and makes it more detailed over time.

## 11. Dependencies and configuration to carry over

### Frontend packages used here

- `@xyflow/react`
- `@tabler/icons-react`
- `react-markdown`
- `remark-gfm`
- `recharts`

Reference:

- `supply_chain_agentic_os_ui/package.json`

### Backend packages used here

- FastAPI
- httpx
- motor / MongoDB
- supabase
- anyio

### Environment variables to think about

Frontend:

- `BACKEND_URL`
- `NEXT_PUBLIC_BACKEND_URL`
- `BACKEND_API_KEY`
- `NEXT_PUBLIC_LYZR_WS_BASE_URL`
- `NEXT_PUBLIC_LYZR_API_KEY`
- `NEXT_PUBLIC_LYZR_API_KEY2`

Backend:

- `SECRET_KEY`
- `LYZR_API_KEY`
- `LYZR_API_KEY2`
- agent ID env vars
- `MONGODB_URI` or `DOCDB_URI`
- optional Supabase keys

References:

- backend URL config: `backend-config.ts:11-34`
- websocket config: `use-lyzr-agent-events.ts:41-44`
- backend env example: `supply_chain_agentic_os_backend/.env.example`

## 12. Pitfalls and nuances in the current implementation

These are worth knowing if you are copying this exactly.

1. The first synthetic start event is skipped for brand-new sessions.
   - Reason: there is no `sessionId` yet.
   - The flow still looks correct because local stage state updates immediately.

2. Historical chats do not restore historical event traces.
   - They restore message history only.
   - The graph is for the current live run.

3. The websocket key is exposed through `/api/chat/status` without a `jobId`.
   - This works, but it is easy to miss when reading the code.

4. The graph truncates tool nodes to 4 per iteration.
   - This is intentional for readability.

5. The backend itself is not a streaming server.
   - If you replace Lyzr with a provider that has no execution event stream, you will need to build one or accept a reduced graph.

6. The `.env.example` does not fully reflect current key usage.
   - Backend code expects both `LYZR_API_KEY` and `LYZR_API_KEY2`.

## 13. If I were replicating this in a new project

I would copy the architecture, not just the component:

- keep `session_id` as the universal correlation key
- separate final response delivery from observability streaming
- normalize event payloads before rendering
- emit synthetic local events to cover gaps
- make the graph degrade gracefully to polling-only mode
- keep the graph in one reusable host component
- instrument tool APIs with lightweight statistics

That is the real reason this implementation works well.

