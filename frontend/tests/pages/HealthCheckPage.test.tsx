import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getHealth } from "@/lib/api";
import HealthCheckPage from "@/pages/HealthCheckPage";

vi.mock("@/lib/api", () => ({
  getHealth: vi.fn(),
}));

function renderWithQueryClient() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <HealthCheckPage />
    </QueryClientProvider>,
  );
}

describe("HealthCheckPage", () => {
  beforeEach(() => {
    vi.mocked(getHealth).mockReset();
  });

  it("shows a loading state, then the success pill once the backend responds", async () => {
    vi.mocked(getHealth).mockResolvedValue({ status: "ok" });

    renderWithQueryClient();

    expect(screen.getByText(/checking backend/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("ok")).toBeInTheDocument();
    });
  });

  it("shows the error pill when the backend call fails", async () => {
    vi.mocked(getHealth).mockRejectedValue(new Error("connection refused"));

    renderWithQueryClient();

    await waitFor(() => {
      expect(screen.getByText("connection refused")).toBeInTheDocument();
    });
  });
});
