import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "@/App";
import { getRestaurants, streamChat } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, getRestaurants: vi.fn(), streamChat: vi.fn() };
});

function renderApp() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  );
}

describe("App", () => {
  beforeEach(() => {
    vi.mocked(getRestaurants).mockReset();
  });

  it("shows a loading state, then the app shell once restaurants load", async () => {
    vi.mocked(getRestaurants).mockResolvedValue([
      { id: "a", name: "Golden Skillet" },
      { id: "b", name: "Blue Lotus" },
    ]);

    renderApp();

    expect(screen.getByText(/loading/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Ask Sous")).toBeInTheDocument();
    });
    expect(screen.getByRole("combobox")).toHaveValue("a");
  });

  it("shows an error state when restaurants fail to load", async () => {
    vi.mocked(getRestaurants).mockRejectedValue(new Error("backend down"));

    renderApp();

    await waitFor(() => {
      expect(screen.getByText("backend down")).toBeInTheDocument();
    });
  });

  it("clears chat history when switching restaurants", async () => {
    vi.mocked(getRestaurants).mockResolvedValue([
      { id: "a", name: "Golden Skillet" },
      { id: "b", name: "Blue Lotus" },
    ]);
    vi.mocked(streamChat).mockImplementation(async (_rid, _q, handlers) => {
      handlers.onDone({
        answer: "Revenue was $500.",
        tool_calls: [],
        model: "gemini-2.5-flash",
      });
    });

    const user = userEvent.setup();
    renderApp();
    await waitFor(() =>
      expect(screen.getByText("Ask Sous")).toBeInTheDocument(),
    );

    await user.type(
      screen.getByPlaceholderText(/ask a question/i),
      "how much did I make?",
    );
    await user.click(screen.getByRole("button", { name: /send/i }));
    await waitFor(() =>
      expect(screen.getByText("Revenue was $500.")).toBeInTheDocument(),
    );

    await user.selectOptions(screen.getByRole("combobox"), "Blue Lotus");

    expect(screen.queryByText("Revenue was $500.")).not.toBeInTheDocument();
  });
});
