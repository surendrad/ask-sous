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
});
