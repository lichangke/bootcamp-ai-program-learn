import path from "path"
import { appendFile, mkdir } from "fs/promises"

type TurnDraft = {
  id: string
  index: number
  sessionID: string
  userMessageID: string
  assistantMessageID?: string
  startedAt: number
  completedAt?: number
  input: {
    model: Record<string, any>
    provider: Record<string, any>
    agent: unknown
    userMessage: unknown
    messages: unknown
    system: unknown
    params: unknown
    headers?: unknown
    meta: {
      messagesSnapshotAt?: number
      systemSnapshotAt?: number
    }
  }
  partsByID: Map<string, Record<string, any>>
}

type SessionState = {
  seq: number
  drafts: Map<string, TurnDraft>
  draftIDsByUser: Map<string, string[]>
  waitingDraftByUser: Map<string, string[]>
  pendingAssistantByUser: Map<string, string[]>
  activeDraftByAssistant: Map<string, string>
  orphanPartsByAssistant: Map<string, Map<string, Record<string, any>>>
  queuedAssistantIDs: Set<string>
  completedAssistantInfo: Map<string, Record<string, any>>
  latestMessages?: unknown
  latestMessagesAt?: number
  latestSystem?: unknown
  latestSystemAt?: number
}

function clone<T>(input: T): T {
  if (input === undefined || input === null) return input
  try {
    return structuredClone(input)
  } catch {
    try {
      return JSON.parse(JSON.stringify(input)) as T
    } catch {
      return input
    }
  }
}

function sessionState(state: Map<string, SessionState>, sessionID: string): SessionState {
  const existing = state.get(sessionID)
  if (existing) return existing
  const created: SessionState = {
    seq: 0,
    drafts: new Map(),
    draftIDsByUser: new Map(),
    waitingDraftByUser: new Map(),
    pendingAssistantByUser: new Map(),
    activeDraftByAssistant: new Map(),
    orphanPartsByAssistant: new Map(),
    queuedAssistantIDs: new Set(),
    completedAssistantInfo: new Map(),
  }
  state.set(sessionID, created)
  return created
}

function removeFromArrayMap(map: Map<string, string[]>, key: string, value: string) {
  const list = map.get(key)
  if (!list) return
  const filtered = list.filter((x) => x !== value)
  if (filtered.length === 0) {
    map.delete(key)
    return
  }
  map.set(key, filtered)
}

function extractModel(model: any): Record<string, any> {
  return {
    providerID: model?.providerID ?? model?.providerId ?? model?.provider_id,
    modelID: model?.id ?? model?.modelID ?? model?.modelId ?? model?.model_id,
    raw: clone(model),
  }
}

function findLatestOpenDraftForUser(s: SessionState, userMessageID: string): TurnDraft | undefined {
  const ids = s.draftIDsByUser.get(userMessageID)
  if (!ids || ids.length === 0) return
  for (let i = ids.length - 1; i >= 0; i--) {
    const draft = s.drafts.get(ids[i])
    if (draft && !draft.completedAt) return draft
  }
}

function mergeOrphanPartsIntoDraft(s: SessionState, assistantMessageID: string, draft: TurnDraft) {
  const orphan = s.orphanPartsByAssistant.get(assistantMessageID)
  if (!orphan) return
  for (const [partID, part] of orphan.entries()) {
    draft.partsByID.set(partID, clone(part))
  }
  s.orphanPartsByAssistant.delete(assistantMessageID)
}

function bindAssistantToDraft(s: SessionState, userMessageID: string, assistantMessageID: string) {
  if (s.activeDraftByAssistant.has(assistantMessageID)) return
  if (s.queuedAssistantIDs.has(assistantMessageID)) return

  const waiting = s.waitingDraftByUser.get(userMessageID)
  if (waiting && waiting.length > 0) {
    const draftID = waiting.shift()!
    if (waiting.length === 0) s.waitingDraftByUser.delete(userMessageID)
    const draft = s.drafts.get(draftID)
    if (draft) {
      draft.assistantMessageID = assistantMessageID
      s.activeDraftByAssistant.set(assistantMessageID, draftID)
      mergeOrphanPartsIntoDraft(s, assistantMessageID, draft)
      return
    }
  }

  const pending = s.pendingAssistantByUser.get(userMessageID) ?? []
  pending.push(assistantMessageID)
  s.pendingAssistantByUser.set(userMessageID, pending)
  s.queuedAssistantIDs.add(assistantMessageID)
}

function bindDraftToAssistantIfAny(s: SessionState, draft: TurnDraft): string | undefined {
  const pending = s.pendingAssistantByUser.get(draft.userMessageID)
  if (!pending || pending.length === 0) {
    const waiting = s.waitingDraftByUser.get(draft.userMessageID) ?? []
    waiting.push(draft.id)
    s.waitingDraftByUser.set(draft.userMessageID, waiting)
    return
  }

  const assistantMessageID = pending.shift()!
  if (pending.length === 0) s.pendingAssistantByUser.delete(draft.userMessageID)
  s.queuedAssistantIDs.delete(assistantMessageID)
  draft.assistantMessageID = assistantMessageID
  s.activeDraftByAssistant.set(assistantMessageID, draft.id)
  mergeOrphanPartsIntoDraft(s, assistantMessageID, draft)
  return assistantMessageID
}

function applyPartDelta(part: Record<string, any>, field: string, delta: string) {
  const current = part[field]
  if (typeof current === "string") {
    part[field] = current + delta
    return
  }
  if (current === undefined || current === null) {
    part[field] = delta
    return
  }
  part[field] = String(current) + delta
}

function finalizeFallbackOutput(draft: TurnDraft, assistantInfo: Record<string, any>) {
  const parts = Array.from(draft.partsByID.values()).sort((a, b) => String(a.id).localeCompare(String(b.id)))
  return {
    info: clone(assistantInfo),
    parts,
  }
}

function pruneStale(s: SessionState, now = Date.now()) {
  const maxAge = 24 * 60 * 60 * 1000
  for (const draft of s.drafts.values()) {
    if (draft.completedAt) continue
    if (draft.assistantMessageID) continue
    if (now - draft.startedAt <= maxAge) continue

    s.drafts.delete(draft.id)
    removeFromArrayMap(s.draftIDsByUser, draft.userMessageID, draft.id)
    removeFromArrayMap(s.waitingDraftByUser, draft.userMessageID, draft.id)
  }
}

export default async function LogConversationPlugin(input: any) {
  const states = new Map<string, SessionState>()
  const writeLocks = new Map<string, Promise<void>>()
  const logDir = path.resolve(input.directory, "logs")
  await mkdir(logDir, { recursive: true })

  async function appendJSONL(sessionID: string, payload: Record<string, any>) {
    const filepath = path.join(logDir, `${sessionID}.jsonl`)
    const line = JSON.stringify(payload) + "\n"
    const prev = writeLocks.get(filepath) ?? Promise.resolve()
    const next = prev.catch(() => undefined).then(() => appendFile(filepath, line, "utf8"))
    writeLocks.set(filepath, next)
    await next.catch((error) => {
      console.error("[log-conversation] failed to append JSONL", {
        filepath,
        error: error instanceof Error ? error.message : String(error),
      })
    })
  }

  async function getMessage(sessionID: string, messageID: string) {
    if (!messageID) return undefined
    const response = await input.client.session
      .message({
        path: {
          id: sessionID,
          messageID,
        },
        query: {
          directory: input.directory,
        },
        throwOnError: true,
      })
      .catch(() => undefined)
    return response?.data
  }

  async function finalizeAssistantTurn(sessionID: string, assistantInfo: Record<string, any>) {
    const s = sessionState(states, sessionID)
    const assistantMessageID = String(assistantInfo.id ?? "")
    if (!assistantMessageID) return

    const draftID = s.activeDraftByAssistant.get(assistantMessageID)
    if (!draftID) return
    const draft = s.drafts.get(draftID)
    if (!draft || draft.completedAt) return

    draft.completedAt = Number(assistantInfo.time?.completed ?? Date.now())
    s.activeDraftByAssistant.delete(assistantMessageID)

    const [assistantMessage, userMessage] = await Promise.all([
      getMessage(sessionID, assistantMessageID),
      getMessage(sessionID, draft.userMessageID),
    ])

    const record = {
      schema: "opencode.llm.turn.v1",
      session_id: sessionID,
      turn_id: draft.id,
      turn_index: draft.index,
      user_message_id: draft.userMessageID,
      assistant_message_id: assistantMessageID,
      started_at: new Date(draft.startedAt).toISOString(),
      completed_at: new Date(draft.completedAt).toISOString(),
      llm_input: {
        model: draft.input.model,
        provider: draft.input.provider,
        agent: draft.input.agent,
        user_message: userMessage ?? draft.input.userMessage,
        messages: draft.input.messages,
        system: draft.input.system,
        params: draft.input.params,
        headers: draft.input.headers,
        capture_meta: {
          stage: "pre_provider_transform",
          messages_snapshot_at: draft.input.meta.messagesSnapshotAt,
          system_snapshot_at: draft.input.meta.systemSnapshotAt,
        },
      },
      llm_output: {
        assistant_message: assistantMessage ?? finalizeFallbackOutput(draft, assistantInfo),
      },
    }

    await appendJSONL(sessionID, record)

    s.drafts.delete(draft.id)
    s.completedAssistantInfo.delete(assistantMessageID)
    s.orphanPartsByAssistant.delete(assistantMessageID)
    removeFromArrayMap(s.draftIDsByUser, draft.userMessageID, draft.id)
    removeFromArrayMap(s.waitingDraftByUser, draft.userMessageID, draft.id)
  }

  return {
    "experimental.chat.messages.transform": async (_incoming: any, outgoing: any) => {
      const messages = outgoing?.messages
      if (!Array.isArray(messages) || messages.length === 0) return
      const last = messages[messages.length - 1]
      const sessionID = last?.info?.sessionID
      if (!sessionID) return
      const s = sessionState(states, String(sessionID))
      s.latestMessages = clone(messages)
      s.latestMessagesAt = Date.now()
    },

    "experimental.chat.system.transform": async (incoming: any, outgoing: any) => {
      const sessionID = incoming?.sessionID
      if (!sessionID) return
      const s = sessionState(states, String(sessionID))
      s.latestSystem = clone(outgoing?.system)
      s.latestSystemAt = Date.now()
    },

    "chat.params": async (incoming: any, outgoing: any) => {
      const sessionID = String(incoming?.sessionID ?? "")
      const userMessageID = String(incoming?.message?.id ?? "")
      if (!sessionID || !userMessageID) return

      const s = sessionState(states, sessionID)
      pruneStale(s)

      const index = ++s.seq
      const draft: TurnDraft = {
        id: `${sessionID}:${index}`,
        index,
        sessionID,
        userMessageID,
        startedAt: Date.now(),
        input: {
          model: extractModel(incoming?.model),
          provider: clone(incoming?.provider ?? {}),
          agent: clone(incoming?.agent),
          userMessage: clone(incoming?.message),
          messages: clone(s.latestMessages),
          system: clone(s.latestSystem),
          params: clone(outgoing),
          meta: {
            messagesSnapshotAt: s.latestMessagesAt,
            systemSnapshotAt: s.latestSystemAt,
          },
        },
        partsByID: new Map(),
      }

      s.drafts.set(draft.id, draft)
      const userDrafts = s.draftIDsByUser.get(userMessageID) ?? []
      userDrafts.push(draft.id)
      s.draftIDsByUser.set(userMessageID, userDrafts)
      const assistantMessageID = bindDraftToAssistantIfAny(s, draft)
      if (assistantMessageID) {
        const completedInfo = s.completedAssistantInfo.get(assistantMessageID)
        if (completedInfo) {
          await finalizeAssistantTurn(sessionID, completedInfo)
        }
      }
    },

    "chat.headers": async (incoming: any, outgoing: any) => {
      const sessionID = String(incoming?.sessionID ?? "")
      const userMessageID = String(incoming?.message?.id ?? "")
      if (!sessionID || !userMessageID) return

      const s = sessionState(states, sessionID)
      const draft = findLatestOpenDraftForUser(s, userMessageID)
      if (!draft) return
      draft.input.headers = clone(outgoing?.headers ?? {})
    },

    event: async ({ event }: any) => {
      const type = event?.type
      if (!type) return

      if (type === "message.updated") {
        const info = event?.properties?.info
        if (!info || info.role !== "assistant") return
        const sessionID = String(info.sessionID ?? "")
        if (!sessionID) return

        const s = sessionState(states, sessionID)
        pruneStale(s)

        const assistantMessageID = String(info.id ?? "")
        if (!assistantMessageID) return

        if (info.time?.completed) {
          s.completedAssistantInfo.set(assistantMessageID, clone(info))
          const parentID = String(info.parentID ?? "")
          if (parentID) {
            bindAssistantToDraft(s, parentID, assistantMessageID)
          }
          await finalizeAssistantTurn(sessionID, info)
          return
        }

        const parentID = String(info.parentID ?? "")
        if (!parentID) return
        bindAssistantToDraft(s, parentID, assistantMessageID)
        return
      }

      if (type === "message.part.updated") {
        const part = event?.properties?.part
        if (!part) return
        const sessionID = String(part.sessionID ?? "")
        const assistantMessageID = String(part.messageID ?? "")
        if (!sessionID || !assistantMessageID) return

        const s = sessionState(states, sessionID)
        const draftID = s.activeDraftByAssistant.get(assistantMessageID)
        if (!draftID) {
          const orphan = s.orphanPartsByAssistant.get(assistantMessageID) ?? new Map<string, Record<string, any>>()
          orphan.set(String(part.id), clone(part))
          s.orphanPartsByAssistant.set(assistantMessageID, orphan)
          return
        }
        const draft = s.drafts.get(draftID)
        if (!draft) return

        draft.partsByID.set(String(part.id), clone(part))
        return
      }

      if (type === "message.part.delta") {
        const props = event?.properties ?? {}
        const sessionID = String(props.sessionID ?? "")
        const assistantMessageID = String(props.messageID ?? "")
        const partID = String(props.partID ?? "")
        const field = String(props.field ?? "")
        const delta = String(props.delta ?? "")
        if (!sessionID || !assistantMessageID || !partID || !field) return

        const s = sessionState(states, sessionID)
        const draftID = s.activeDraftByAssistant.get(assistantMessageID)
        if (!draftID) {
          const orphan = s.orphanPartsByAssistant.get(assistantMessageID) ?? new Map<string, Record<string, any>>()
          const part = orphan.get(partID) ?? { id: partID, messageID: assistantMessageID, sessionID }
          applyPartDelta(part, field, delta)
          orphan.set(partID, part)
          s.orphanPartsByAssistant.set(assistantMessageID, orphan)
          return
        }
        const draft = s.drafts.get(draftID)
        if (!draft) return

        const part = draft.partsByID.get(partID) ?? { id: partID, messageID: assistantMessageID, sessionID }
        applyPartDelta(part, field, delta)
        draft.partsByID.set(partID, part)
      }
    },
  }
}
