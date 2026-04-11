import { useState, useRef, useEffect, useMemo } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import remarkMath from "remark-math"
import rehypeKatex from "rehype-katex"
import "katex/dist/katex.min.css"
import {
  Search, Loader2, CheckCircle2, AlertCircle, ChevronRight, ChevronDown, X,
  FileText, Send,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { useResearchStore, type ResearchTask } from "@/stores/research-store"
import { useWikiStore } from "@/stores/wiki-store"
import { research } from "@/api/research"

export function ResearchPanel() {
  const tasks = useResearchStore((s) => s.tasks)
  const removeTask = useResearchStore((s) => s.removeTask)
  const setPanelOpen = useResearchStore((s) => s.setPanelOpen)
  const project = useWikiStore((s) => s.project)
  const [inputValue, setInputValue] = useState("")

  const running = tasks.filter((t) => ["searching", "synthesizing", "saving"].includes(t.status))
  const queued = tasks.filter((t) => t.status === "queued")
  const done = tasks.filter((t) => t.status === "done" || t.status === "error")

  function handleStartResearch() {
    const topic = inputValue.trim()
    if (!topic || !project?.id) return
    // Start research via API
    research.start(project.id, topic).catch((err) => {
      console.error("Failed to start research:", err)
    })
    setInputValue("")
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex shrink-0 items-center justify-between border-b px-3 py-2">
        <div className="flex items-center gap-2">
          <Search className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-semibold">Deep Research</span>
          {(running.length > 0 || queued.length > 0) && (
            <span className="rounded-full bg-primary/20 px-1.5 py-0.5 text-[10px] font-medium text-primary">
              {running.length} active{queued.length > 0 ? `, ${queued.length} queued` : ""}
            </span>
          )}
        </div>
        <button
          onClick={() => setPanelOpen(false)}
          className="rounded p-1 text-muted-foreground hover:bg-accent"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Research input */}
      <div className="flex shrink-0 items-center gap-1.5 border-b px-3 py-2">
        <input
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") handleStartResearch() }}
          placeholder="Enter a research topic..."
          className="flex-1 rounded border bg-background px-2 py-1 text-xs outline-none placeholder:text-muted-foreground focus:ring-1 focus:ring-ring"
        />
        <Button size="icon" variant="ghost" className="h-7 w-7" onClick={handleStartResearch} disabled={!inputValue.trim()}>
          <Send className="h-3.5 w-3.5" />
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {tasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 p-8 text-center text-xs text-muted-foreground">
            <Search className="h-8 w-8 opacity-20" />
            <p>No research tasks yet</p>
            <p>Enter a topic above or click "Deep Research" in Review</p>
          </div>
        ) : (
          <div className="flex flex-col gap-1 p-2">
            {running.map((task) => (
              <ResearchTaskCard key={task.id} task={task} onRemove={removeTask} />
            ))}
            {queued.map((task) => (
              <ResearchTaskCard key={task.id} task={task} onRemove={removeTask} />
            ))}
            {done.map((task) => (
              <ResearchTaskCard key={task.id} task={task} onRemove={removeTask} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

/** Separate <think>/<thinking> blocks from main content */
function separateThinking(text: string): { thinking: string; answer: string } {
  const thinkRegex = /^<think(?:ing)?>([\s\S]*?)(?:<\/think(?:ing)?>|$)/i
  const match = text.match(thinkRegex)
  if (match) {
    const thinking = match[1].trim()
    const rest = text.slice(match[0].length).trim()
    return { thinking, answer: rest }
  }
  return { thinking: "", answer: text }
}

function SynthesisBlock({ synthesis, isStreaming }: { synthesis: string; isStreaming: boolean }) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const { thinking, answer } = useMemo(() => separateThinking(synthesis), [synthesis])
  const [thinkingCollapsed, setThinkingCollapsed] = useState(false)

  useEffect(() => {
    if (answer.length > 0 && thinking.length > 0 && !thinkingCollapsed) {
      setThinkingCollapsed(true)
    }
  }, [answer, thinking, thinkingCollapsed])

  useEffect(() => {
    if (isStreaming && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [synthesis, isStreaming])

  return (
    <div className="mb-2 flex flex-col min-h-0">
      <div className="mb-1 font-medium text-muted-foreground">Synthesis</div>
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto rounded bg-muted/30 p-2 prose prose-xs prose-invert max-w-none"
        style={{ maxHeight: "calc(100vh - 400px)", minHeight: "120px" }}
      >
        {thinking && (
          <div className="mb-2">
            <button
              onClick={() => setThinkingCollapsed((v) => !v)}
              className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground"
            >
              {thinkingCollapsed ? (
                <ChevronRight className="h-3 w-3" />
              ) : (
                <ChevronDown className="h-3 w-3" />
              )}
              Thinking{isStreaming && !answer ? "..." : ""}
            </button>
            {!thinkingCollapsed && (
              <div className="mt-1 rounded border border-muted px-2 py-1 text-[10px] text-muted-foreground opacity-70 leading-relaxed whitespace-pre-wrap">
                {isStreaming && !answer
                  ? thinking.split("\n").slice(-5).join("\n")
                  : thinking}
              </div>
            )}
          </div>
        )}
        {answer && (
          <ReactMarkdown
            remarkPlugins={[remarkGfm, remarkMath]}
            rehypePlugins={[rehypeKatex]}
            components={{
              table: ({ children, ...props }) => (
                <div className="my-2 overflow-x-auto rounded border border-border">
                  <table className="w-full border-collapse text-xs" {...props}>{children}</table>
                </div>
              ),
              thead: ({ children, ...props }) => (
                <thead className="bg-muted" {...props}>{children}</thead>
              ),
              th: ({ children, ...props }) => (
                <th className="border border-border/80 px-3 py-1.5 text-left font-semibold bg-muted" {...props}>{children}</th>
              ),
              td: ({ children, ...props }) => (
                <td className="border border-border/60 px-3 py-1.5" {...props}>{children}</td>
              ),
            }}
          >
            {answer}
          </ReactMarkdown>
        )}
        {isStreaming && <span className="animate-pulse">&#9610;</span>}
      </div>
    </div>
  )
}

function ResearchTaskCard({ task, onRemove }: { task: ResearchTask; onRemove: (id: string) => void }) {
  const [expanded, setExpanded] = useState(
    task.status === "synthesizing" || task.status === "searching"
  )

  const statusIcon = {
    queued: <div className="h-3 w-3 rounded-full border-2 border-muted-foreground" />,
    searching: <Loader2 className="h-3 w-3 animate-spin text-primary" />,
    synthesizing: <Loader2 className="h-3 w-3 animate-spin text-primary" />,
    saving: <Loader2 className="h-3 w-3 animate-spin text-primary" />,
    done: <CheckCircle2 className="h-3 w-3 text-primary" />,
    error: <AlertCircle className="h-3 w-3 text-destructive" />,
  }[task.status]

  const statusText = {
    queued: "Queued",
    searching: "Searching web...",
    synthesizing: "Synthesizing...",
    saving: "Saving to wiki...",
    done: task.savedPath ? "Saved" : "Done",
    error: "Failed",
  }[task.status]

  // TODO: handleOpenSaved needs to be reworked to find pages by path via API
  async function handleOpenSaved() {
    // Simplified: just log for now. In a full implementation, we'd find the page ID from the saved path.
    console.log("Open saved research:", task.savedPath)
  }

  return (
    <div className="rounded-lg border text-xs">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-accent/50"
      >
        {expanded ? (
          <ChevronDown className="h-3 w-3 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-3 w-3 shrink-0 text-muted-foreground" />
        )}
        {statusIcon}
        <span className="flex-1 truncate font-medium">{task.topic}</span>
        <span className="shrink-0 text-muted-foreground">{statusText}</span>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="border-t px-3 py-2">
          {task.error && (
            <p className="mb-2 text-destructive">{task.error}</p>
          )}

          {task.webResults.length > 0 && (
            <div className="mb-2">
              <div className="mb-1 font-medium text-muted-foreground">
                Sources ({task.webResults.length})
              </div>
              <div className="flex flex-col gap-1">
                {task.webResults.map((r, i) => (
                  <div key={i} className="flex items-start gap-1.5 rounded bg-muted/50 px-2 py-1">
                    <span className="shrink-0 font-mono text-muted-foreground">[{i + 1}]</span>
                    <div className="min-w-0 flex-1">
                      <div className="truncate font-medium">{r.title}</div>
                      <div className="truncate text-muted-foreground">{r.source}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {task.synthesis && (
            <SynthesisBlock synthesis={task.synthesis} isStreaming={task.status === "synthesizing"} />
          )}

          <div className="flex items-center gap-1.5 mt-2">
            {task.savedPath && (
              <Button variant="outline" size="sm" className="h-6 text-[11px] gap-1" onClick={handleOpenSaved}>
                <FileText className="h-3 w-3" />
                Open
              </Button>
            )}
            {(task.status === "done" || task.status === "error") && (
              <Button
                variant="ghost"
                size="sm"
                className="h-6 text-[11px] gap-1 text-muted-foreground"
                onClick={() => onRemove(task.id)}
              >
                <X className="h-3 w-3" />
                Remove
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
