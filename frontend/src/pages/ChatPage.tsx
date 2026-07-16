import { Send } from "lucide-react";
import { useState } from "react";

import { ChatMessage } from "@/components/ChatMessage";
import { StatusTag } from "@/components/StatusTag";
import { ThinkingIndicator } from "@/components/ThinkingIndicator";
import { Button } from "@/components/ui/button";
import type { ChatToolCall } from "@/lib/api";
import { streamChat } from "@/lib/api";

type Message = {
  id: string;
  sender: "user" | "agent";
  text: string;
  toolCalls?: ChatToolCall[];
  isStreaming?: boolean;
};

type ChatPageProps = {
  restaurantIds: string[];
};

export default function ChatPage({ restaurantIds }: ChatPageProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [isWaiting, setIsWaiting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSend() {
    const trimmed = question.trim();
    if (!trimmed) return;

    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), sender: "user", text: trimmed },
    ]);
    setQuestion("");
    setError(null);
    setIsWaiting(true);

    // agentMessageId is a stable id (never mutated), not a "has streaming
    // started" flag — "has the placeholder already been added" is derived
    // from `prev` itself on every call, so these updaters stay pure
    // (same input always produces the same output). This matters because
    // React StrictMode double-invokes state updaters in development to
    // catch impure ones: an earlier version tracked "started streaming" via
    // a mutable outer-scope boolean, which diverged between the two
    // StrictMode invocations and silently corrupted the user's own message
    // by merging the agent's answer into it.
    const agentMessageId = crypto.randomUUID();

    await streamChat(restaurantIds, trimmed, {
      onChunk: (text) => {
        setIsWaiting(false);
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.id === agentMessageId) {
            const next = [...prev];
            next[next.length - 1] = { ...last, text: last.text + text };
            return next;
          }
          return [
            ...prev,
            { id: agentMessageId, sender: "agent", text, isStreaming: true },
          ];
        });
      },
      onDone: (result) => {
        setIsWaiting(false);
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          const agentMessage = {
            id: agentMessageId,
            sender: "agent" as const,
            text: result.answer,
            toolCalls: result.tool_calls,
          };
          if (last?.id === agentMessageId) {
            const next = [...prev];
            next[next.length - 1] = agentMessage;
            return next;
          }
          return [...prev, agentMessage];
        });
      },
      onError: (apiError) => {
        setIsWaiting(false);
        setError(apiError.message);
      },
    });
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {messages.map((message) => (
          <ChatMessage
            key={message.id}
            sender={message.sender}
            text={message.text}
            toolCalls={message.toolCalls}
            isStreaming={message.isStreaming}
          />
        ))}
        {isWaiting && <ThinkingIndicator />}
        {error && <StatusTag variant="error">{error}</StatusTag>}
      </div>
      <form
        className="flex items-center gap-2 border-t border-border p-3"
        onSubmit={(e) => {
          e.preventDefault();
          void handleSend();
        }}
      >
        <input
          className="flex-1 rounded-md border border-border-strong bg-elevated px-3 py-2 text-sm text-text outline-none focus:border-brand"
          placeholder="Ask a question about your restaurant…"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <Button type="submit" aria-label="Send">
          <Send size={16} />
        </Button>
      </form>
    </div>
  );
}
