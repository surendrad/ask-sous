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
  restaurantId: string;
};

export default function ChatPage({ restaurantId }: ChatPageProps) {
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

    let hasStartedStreaming = false;
    const agentMessageId = crypto.randomUUID();

    await streamChat(restaurantId, trimmed, {
      onChunk: (text) => {
        setIsWaiting(false);
        setMessages((prev) => {
          if (!hasStartedStreaming) {
            hasStartedStreaming = true;
            return [
              ...prev,
              { id: agentMessageId, sender: "agent", text, isStreaming: true },
            ];
          }
          const next = [...prev];
          const last = next[next.length - 1];
          next[next.length - 1] = { ...last, text: last.text + text };
          return next;
        });
      },
      onDone: (result) => {
        setIsWaiting(false);
        setMessages((prev) => {
          const next = [...prev];
          if (hasStartedStreaming) {
            next[next.length - 1] = {
              id: agentMessageId,
              sender: "agent",
              text: result.answer,
              toolCalls: result.tool_calls,
              isStreaming: false,
            };
          } else {
            next.push({
              id: agentMessageId,
              sender: "agent",
              text: result.answer,
              toolCalls: result.tool_calls,
            });
          }
          return next;
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
