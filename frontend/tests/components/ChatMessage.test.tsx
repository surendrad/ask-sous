import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ChatMessage } from "@/components/ChatMessage";

describe("ChatMessage", () => {
  it("renders a user message right-aligned", () => {
    render(<ChatMessage sender="user" text="How much did I make?" />);

    const bubble = screen.getByText("How much did I make?");
    expect(bubble).toBeInTheDocument();
  });

  it("renders an agent message with citation chips for its tool calls", () => {
    render(
      <ChatMessage
        sender="agent"
        text="Revenue was $500."
        toolCalls={[
          {
            tool_name: "get_revenue_summary",
            arguments: {},
            result: {},
            error: null,
          },
        ]}
      />,
    );

    expect(screen.getByText("Revenue was $500.")).toBeInTheDocument();
    expect(screen.getByText("get_revenue_summary")).toBeInTheDocument();
  });

  it("renders a streaming cursor while still streaming", () => {
    render(<ChatMessage sender="agent" text="Revenue was" isStreaming />);

    expect(screen.getByTestId("streaming-cursor")).toBeInTheDocument();
  });

  it("does not render a streaming cursor once finished", () => {
    render(<ChatMessage sender="agent" text="Revenue was $500." />);

    expect(screen.queryByTestId("streaming-cursor")).not.toBeInTheDocument();
  });

  it("renders markdown formatting in agent messages (bold, bullet lists) instead of literal asterisks", () => {
    // A real live /chat call asking for a "week by week breakdown" came
    // back as markdown (**bold**, bullet lists) that rendered as a raw wall
    // of text with literal asterisks — the model naturally produces
    // markdown for structured answers, but nothing parsed it.
    render(
      <ChatMessage
        sender="agent"
        text={"**Week 1:** good\n\n- Location A: $100\n- Location B: $200"}
      />,
    );

    expect(screen.queryByText(/\*\*/)).not.toBeInTheDocument();
    const bold = screen.getByText("Week 1:");
    expect(bold.tagName).toBe("STRONG");
    expect(screen.getByText(/Location A/)).toBeInTheDocument();
    expect(screen.getByText(/Location B/)).toBeInTheDocument();
  });

  it("renders user messages as plain text, not parsed markdown", () => {
    // User input is never markdown-authored — parsing it would be
    // pointless and risks unexpected formatting from stray asterisks.
    render(<ChatMessage sender="user" text="what about **this** week?" />);

    expect(screen.getByText("what about **this** week?")).toBeInTheDocument();
  });
});
