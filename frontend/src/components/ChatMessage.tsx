import { CitationChip } from "@/components/CitationChip";
import type { ChatToolCall } from "@/lib/api";
import { cn } from "@/lib/utils";

type ChatMessageProps = {
  sender: "user" | "agent";
  text: string;
  toolCalls?: ChatToolCall[];
  isStreaming?: boolean;
};

/** Message bubble per design-guidelines.md §11: user messages right-aligned
 * brand-filled, agent messages left-aligned `elevated` with a border.
 * Citation chips render under an agent message backed by tool calls — the
 * UI's own expression of the "no naked numbers" grounding rule.
 *
 * Prop is named `sender`, not `role`, to avoid colliding with the ARIA
 * `role` attribute — Biome's a11y linter otherwise treats this component's
 * own prop as an (invalid) ARIA role on the JSX element. */
export function ChatMessage({
  sender,
  text,
  toolCalls = [],
  isStreaming = false,
}: ChatMessageProps) {
  const isUser = sender === "user";

  return (
    <div
      className={cn(
        "flex flex-col gap-1.5",
        isUser ? "items-end" : "items-start",
      )}
    >
      <div
        className={cn(
          "max-w-[80%] rounded-lg px-3 py-2 text-sm leading-[22px]",
          isUser
            ? "bg-brand text-on-brand"
            : "border border-border bg-elevated text-text",
        )}
      >
        {text}
        {isStreaming && (
          <span
            data-testid="streaming-cursor"
            className="ml-0.5 inline-block h-3.5 w-0.5 animate-pulse bg-brand align-middle motion-reduce:animate-none"
          />
        )}
      </div>
      {toolCalls.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {toolCalls.map((tc, i) => (
            <CitationChip
              // biome-ignore lint/suspicious/noArrayIndexKey: tool calls carry no id from the API and this list is fixed once a message finishes streaming, never reordered
              key={`${tc.tool_name}-${i}`}
              toolName={tc.tool_name}
              hasError={!!tc.error}
            />
          ))}
        </div>
      )}
    </div>
  );
}
