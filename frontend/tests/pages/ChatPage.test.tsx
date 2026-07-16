import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { streamChat } from "@/lib/api";
import ChatPage from "@/pages/ChatPage";

vi.mock("@/lib/api", () => ({
  streamChat: vi.fn(),
}));

// Rendered in StrictMode (matching main.tsx's real root) throughout this
// file — React intentionally double-invokes state updater functions in
// StrictMode dev mode to catch impure reducers. A real bug was caught this
// way: handleSend()'s onChunk/onDone updaters read a mutable outer-scope
// `hasStartedStreaming` variable as a side effect, which diverged between
// the two StrictMode invocations and silently corrupted the user's own
// message (merging the agent's answer into it) — invisible without
// StrictMode-wrapped rendering, since a single non-StrictMode render never
// exercises the double-invocation path at all.
function renderStrict(ui: React.ReactElement) {
  return render(<StrictMode>{ui}</StrictMode>);
}

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
    renderStrict(<ChatPage restaurantIds={["rid-1"]} />);

    await user.type(screen.getByRole("textbox"), "how much did I make?");
    await user.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => {
      expect(screen.getByText("Revenue was $500.")).toBeInTheDocument();
    });
    expect(screen.getByText("get_revenue_summary")).toBeInTheDocument();
    // The user's own question must remain visible alongside the answer —
    // a real bug (see renderStrict's comment above) silently erased it.
    expect(screen.getByText("how much did I make?")).toBeInTheDocument();
  });

  it("keeps every question and answer visible across multiple turns, even when a single chunk carries the whole answer", async () => {
    // The corrupting bug only manifested when a turn's answer arrived as
    // exactly one onChunk call (not zero, not several) — this reproduces
    // that exact shape for two consecutive turns.
    vi.mocked(streamChat).mockImplementation(
      async (_rid, question, handlers) => {
        handlers.onChunk(`Answer to: ${question}`);
        handlers.onDone({
          answer: `Answer to: ${question}`,
          tool_calls: [],
          model: "gemini-2.5-flash",
        });
      },
    );

    const user = userEvent.setup();
    renderStrict(<ChatPage restaurantIds={["rid-1"]} />);

    await user.type(screen.getByRole("textbox"), "first question");
    await user.click(screen.getByRole("button", { name: /send/i }));
    await waitFor(() => {
      expect(screen.getByText("Answer to: first question")).toBeInTheDocument();
    });

    await user.type(screen.getByRole("textbox"), "second question");
    await user.click(screen.getByRole("button", { name: /send/i }));
    await waitFor(() => {
      expect(
        screen.getByText("Answer to: second question"),
      ).toBeInTheDocument();
    });

    expect(screen.getByText("first question")).toBeInTheDocument();
    expect(screen.getByText("second question")).toBeInTheDocument();
    expect(screen.getByText("Answer to: first question")).toBeInTheDocument();
    expect(screen.getByText("Answer to: second question")).toBeInTheDocument();
  });

  it("shows an error banner when the stream reports an error", async () => {
    vi.mocked(streamChat).mockImplementation(async (_rid, _q, handlers) => {
      handlers.onError({
        message: "The agent is unavailable.",
        code: "agent_unavailable",
      });
    });

    const user = userEvent.setup();
    renderStrict(<ChatPage restaurantIds={["rid-1"]} />);

    await user.type(screen.getByRole("textbox"), "hi");
    await user.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => {
      expect(screen.getByText("The agent is unavailable.")).toBeInTheDocument();
    });
  });

  it("does not submit an empty question", async () => {
    const user = userEvent.setup();
    renderStrict(<ChatPage restaurantIds={["rid-1"]} />);

    await user.click(screen.getByRole("button", { name: /send/i }));

    expect(streamChat).not.toHaveBeenCalled();
  });
});
