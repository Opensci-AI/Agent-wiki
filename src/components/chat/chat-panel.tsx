import { useRef, useEffect, useCallback, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { Plus, Trash2, MessageSquare } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ChatMessage, StreamingMessage } from "./chat-message"
import { ChatInput } from "./chat-input"
import { useChatStore } from "@/stores/chat-store"
import { useWikiStore } from "@/stores/wiki-store"
import { chat, streamChat } from "@/api/chat"

// Store the page mapping from the last query so CitedReferencesPanel can show which pages were cited
export let lastQueryPages: { title: string; path: string }[] = []

function formatDate(timestamp: number): string {
  const d = new Date(timestamp)
  const now = new Date()
  const isToday = d.toDateString() === now.toDateString()
  if (isToday) {
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
  }
  return d.toLocaleDateString([], { month: "short", day: "numeric" })
}

function ConversationSidebar() {
  const navigate = useNavigate()
  const { conversationId } = useParams<{ conversationId?: string }>()
  const conversations = useChatStore((s) => s.conversations)
  const messages = useChatStore((s) => s.messages)
  const deleteConversation = useChatStore((s) => s.deleteConversation)
  const project = useWikiStore((s) => s.project)

  const [hoveredId, setHoveredId] = useState<string | null>(null)

  const handleNewChat = async () => {
    if (!project?.id) return
    try {
      const newConv = await chat.createConversation(project.id, "New Conversation")
      useChatStore.setState((s) => ({
        conversations: [
          {
            id: newConv.id,
            title: newConv.title,
            createdAt: new Date(newConv.created_at).getTime(),
            updatedAt: new Date(newConv.updated_at).getTime(),
          },
          ...s.conversations,
        ],
      }))
      navigate(`/projects/${project.id}/chat/${newConv.id}`)
    } catch (err) {
      console.error("Failed to create conversation:", err)
    }
  }

  const handleSelectConversation = (convId: string) => {
    if (project) {
      navigate(`/projects/${project.id}/chat/${convId}`)
    }
  }

  const handleDeleteConversation = async (convId: string) => {
    deleteConversation(convId)
    chat.deleteConversation(convId).catch(() => {})
    // If deleted active conversation, go back to chat home
    if (convId === conversationId && project) {
      navigate(`/projects/${project.id}/chat`)
    }
  }

  const sorted = [...conversations].sort((a, b) => b.updatedAt - a.updatedAt)

  function getMessageCount(convId: string): number {
    return messages.filter((m) => m.conversationId === convId).length
  }

  return (
    <div className="flex h-full w-[200px] flex-shrink-0 flex-col border-r bg-muted/30">
      <div className="border-b p-2">
        <Button
          variant="outline"
          size="sm"
          className="w-full gap-2"
          onClick={handleNewChat}
        >
          <Plus className="h-3.5 w-3.5" />
          New Chat
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto py-1">
        {sorted.length === 0 ? (
          <p className="px-3 py-4 text-xs text-muted-foreground text-center">
            No conversations yet
          </p>
        ) : (
          sorted.map((conv) => {
            const isActive = conv.id === conversationId
            const msgCount = getMessageCount(conv.id)
            return (
              <div
                key={conv.id}
                className={`group relative mx-1 my-0.5 flex cursor-pointer flex-col rounded-md px-2 py-1.5 text-sm transition-colors ${
                  isActive
                    ? "bg-primary/10 text-primary"
                    : "hover:bg-accent text-foreground"
                }`}
                onClick={() => handleSelectConversation(conv.id)}
                onMouseEnter={() => setHoveredId(conv.id)}
                onMouseLeave={() => setHoveredId(null)}
              >
                <div className="flex items-start justify-between gap-1">
                  <span className="line-clamp-2 flex-1 text-xs font-medium leading-snug">
                    {conv.title}
                  </span>
                  {hoveredId === conv.id && (
                    <button
                      className="flex-shrink-0 rounded p-0.5 text-muted-foreground hover:text-destructive"
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDeleteConversation(conv.id)
                      }}
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  )}
                </div>
                <div className="mt-0.5 flex items-center gap-1.5 text-[10px] text-muted-foreground">
                  <span>{formatDate(conv.updatedAt)}</span>
                  {msgCount > 0 && (
                    <>
                      <span>&middot;</span>
                      <span>{msgCount} msgs</span>
                    </>
                  )}
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}

export function ChatPanel() {
  const navigate = useNavigate()
  const { conversationId } = useParams<{ conversationId?: string }>()
  const isStreaming = useChatStore((s) => s.isStreaming)
  const streamingContent = useChatStore((s) => s.streamingContent)
  const mode = useChatStore((s) => s.mode)
  const addMessage = useChatStore((s) => s.addMessage)
  const setStreaming = useChatStore((s) => s.setStreaming)
  const appendStreamToken = useChatStore((s) => s.appendStreamToken)
  const finalizeStream = useChatStore((s) => s.finalizeStream)
  const removeLastAssistantMessage = useChatStore((s) => s.removeLastAssistantMessage)
  const setActiveConversation = useChatStore((s) => s.setActiveConversation)

  const allMessages = useChatStore((s) => s.messages)
  const activeMessages = conversationId
    ? allMessages.filter((m) => m.conversationId === conversationId)
    : []

  const project = useWikiStore((s) => s.project)
  const closeRef = useRef<(() => void) | null>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Sync URL conversationId with store
  useEffect(() => {
    setActiveConversation(conversationId || null)
  }, [conversationId, setActiveConversation])

  // Load messages when conversation changes
  useEffect(() => {
    async function loadMessages() {
      if (!conversationId) return
      try {
        const msgs = await chat.getMessages(conversationId)
        // Add to store if not already there
        const existingIds = new Set(allMessages.map((m) => m.id))
        const newMsgs = msgs
          .filter((m) => !existingIds.has(m.id))
          .map((m) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            timestamp: new Date(m.created_at).getTime(),
            conversationId: m.conversation_id,
          }))
        if (newMsgs.length > 0) {
          useChatStore.setState((s) => ({
            messages: [...s.messages, ...newMsgs],
          }))
        }
      } catch {
        // ignore
      }
    }
    loadMessages()
  }, [conversationId])

  useEffect(() => {
    const container = scrollContainerRef.current
    if (container) {
      container.scrollTop = container.scrollHeight
    }
  }, [activeMessages, streamingContent])

  const handleSend = useCallback(
    async (text: string) => {
      if (!project?.id) {
        finalizeStream("No project selected.", undefined)
        return
      }

      let convId = conversationId

      // If no conversation, create one via backend API
      if (!convId) {
        try {
          const newConv = await chat.createConversation(project.id, text.slice(0, 50))
          convId = newConv.id
          // Add to local store
          useChatStore.setState((s) => ({
            conversations: [
              {
                id: newConv.id,
                title: newConv.title,
                createdAt: new Date(newConv.created_at).getTime(),
                updatedAt: new Date(newConv.updated_at).getTime(),
              },
              ...s.conversations,
            ],
          }))
          // Navigate to the new conversation
          navigate(`/projects/${project.id}/chat/${newConv.id}`, { replace: true })
        } catch (err) {
          console.error("Failed to create conversation:", err)
          finalizeStream("Failed to create conversation.", undefined)
          return
        }
      }

      addMessage("user", text)
      setStreaming(true)

      // Send user message to the backend conversation
      try {
        await chat.sendMessage(convId, text)
      } catch (err) {
        console.error("Failed to send message:", err)
      }

      let accumulated = ""

      // Stream the AI response via SSE
      const close = streamChat(
        project.id,
        convId,
        (token) => {
          accumulated += token
          appendStreamToken(token)
        },
        () => {
          finalizeStream(accumulated, undefined)
          closeRef.current = null
        },
        (err) => {
          finalizeStream(`Error: ${err}`, undefined)
          closeRef.current = null
        },
      )
      closeRef.current = close
    },
    [project, conversationId, navigate, addMessage, setStreaming, appendStreamToken, finalizeStream],
  )

  const handleStop = useCallback(() => {
    closeRef.current?.()
    closeRef.current = null
  }, [])

  const handleRegenerate = useCallback(async () => {
    if (isStreaming) return
    const active = activeMessages
    const lastUserMsg = [...active].reverse().find((m) => m.role === "user")
    if (!lastUserMsg) return
    removeLastAssistantMessage()
    await new Promise((r) => setTimeout(r, 50))
    const store = useChatStore.getState()
    const updatedActive = store.messages.filter((m) => m.conversationId === conversationId)
    const lastUser = [...updatedActive].reverse().find((m) => m.role === "user")
    if (lastUser) {
      useChatStore.setState((s) => ({
        messages: s.messages.filter((m) => m.id !== lastUser.id),
      }))
    }
    handleSend(lastUserMsg.content)
  }, [isStreaming, activeMessages, conversationId, removeLastAssistantMessage, handleSend])


  return (
    <div className="flex h-full flex-row overflow-hidden">
      <ConversationSidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        {!conversationId ? (
          <div className="flex flex-1 items-center justify-center text-muted-foreground">
            <div className="text-center">
              <MessageSquare className="mx-auto mb-3 h-8 w-8 opacity-30" />
              <p className="text-sm">Start a new conversation</p>
              <p className="mt-1 text-xs opacity-60">Click "New Chat" or type a message</p>
            </div>
          </div>
        ) : (
          <>
            <div
              ref={scrollContainerRef}
              className="flex-1 overflow-y-auto px-3 py-2"
            >
              <div className="flex flex-col gap-3">
                {activeMessages.map((msg, idx) => {
                  const isLastAssistant = msg.role === "assistant" &&
                    !activeMessages.slice(idx + 1).some((m) => m.role === "assistant")
                  return (
                    <ChatMessage
                      key={msg.id}
                      message={msg}
                      isLastAssistant={isLastAssistant && !isStreaming}
                      onRegenerate={isLastAssistant ? handleRegenerate : undefined}
                    />
                  )
                })}
                {isStreaming && <StreamingMessage content={streamingContent} />}
                <div ref={bottomRef} />
              </div>
            </div>
          </>
        )}

        <ChatInput
          onSend={handleSend}
          onStop={handleStop}
          isStreaming={isStreaming}
          placeholder={
            mode === "ingest"
              ? "Discuss the source or ask follow-up questions..."
              : "Type a message..."
          }
        />
      </div>
    </div>
  )
}
