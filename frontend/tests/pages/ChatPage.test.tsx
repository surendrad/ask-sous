import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { streamChat } from "@/lib/api";
import ChatPage from "@/pages/ChatPage";

vi.mock("@/lib/api", () => ({
  streamChat: vi.fn(),
}));

describe("ChatPage", () => {
  beforeEach(() => {
    vi.mocked(streamChat).mockReset();
  });

  it("shows the thinking indicator, then streams chunks, then citation chips", async () => {
    vi.mocked(streamChat).mockImplementation(async (_rid, _q, handlers) => {
      handlers.onChunk("Revenue ");
      handlers.onChunk("was $500.");
      handlers.onDone({
        answer: "Revenue was $500.",
        tool_calls: [
          {
            tool_name: "get_revenue_summary",
            arguments: {},
            result: {},
            error: null,
          },
        ],
        model: "gemini-2.5-flash",
      });
    });

    const user = userEvent.setup();
    render(<ChatPage restaurantIds={["rid-1"]} />);

    await user.type(screen.getByRole("textbox"), "how much did I make?");
    await user.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => {
      expect(screen.getByText("Revenue was $500.")).toBeInTheDocument();
    });
    expect(screen.getByText("get_revenue_summary")).toBeInTheDocument();
  });

  it("shows an error banner when the stream reports an error", async () => {
    vi.mocked(streamChat).mockImplementation(async (_rid, _q, handlers) => {
      handlers.onError({
        message: "The agent is unavailable.",
        code: "agent_unavailable",
      });
    });

    const user = userEvent.setup();
    render(<ChatPage restaurantIds={["rid-1"]} />);

    await user.type(screen.getByRole("textbox"), "hi");
    await user.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => {
      expect(screen.getByText("The agent is unavailable.")).toBeInTheDocument();
    });
  });

  it("does not submit an empty question", async () => {
    const user = userEvent.setup();
    render(<ChatPage restaurantIds={["rid-1"]} />);

    await user.click(screen.getByRole("button", { name: /send/i }));

    expect(streamChat).not.toHaveBeenCalled();
  });
});
