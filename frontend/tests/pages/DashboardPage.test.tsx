import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getDashboard } from "@/lib/api";
import DashboardPage from "@/pages/DashboardPage";

vi.mock("@/lib/api", () => ({
  getDashboard: vi.fn(),
}));

function renderDashboard(restaurantId: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <DashboardPage restaurantId={restaurantId} />
    </QueryClientProvider>,
  );
}

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.mocked(getDashboard).mockReset();
  });

  it("renders KPIs, revenue trend bars, and top items once loaded", async () => {
    vi.mocked(getDashboard).mockResolvedValue({
      kpis: {
        total_revenue: "1500.00",
        transaction_count: 33,
        average_ticket: "50.00",
      },
      revenue_trend: [
        { day: "2026-07-10", revenue: "100.00" },
        { day: "2026-07-11", revenue: "200.00" },
      ],
      top_items: [
        { menu_item_name: "Truffle Fries", total_quantity: 42 },
        { menu_item_name: "Margherita", total_quantity: 30 },
      ],
    });

    renderDashboard("rid-1");

    await waitFor(() => {
      expect(screen.getByText("$1500.00")).toBeInTheDocument();
    });
    expect(screen.getByText("33")).toBeInTheDocument();
    expect(screen.getByText("Truffle Fries")).toBeInTheDocument();
    expect(screen.getByText("Margherita")).toBeInTheDocument();
  });

  it("does not crash when revenue trend and top items are empty", async () => {
    vi.mocked(getDashboard).mockResolvedValue({
      kpis: { total_revenue: "0", transaction_count: 0, average_ticket: "0" },
      revenue_trend: [],
      top_items: [],
    });

    renderDashboard("rid-1");

    await waitFor(() => {
      expect(screen.getAllByText("$0.00").length).toBeGreaterThan(0);
    });
  });

  it("formats a long-precision Decimal average ticket to 2 decimal places", async () => {
    vi.mocked(getDashboard).mockResolvedValue({
      kpis: {
        total_revenue: "14692.43",
        transaction_count: 384,
        average_ticket: "38.26153645833333333333333333",
      },
      revenue_trend: [],
      top_items: [],
    });

    renderDashboard("rid-1");

    await waitFor(() => {
      expect(screen.getByText("$38.26")).toBeInTheDocument();
    });
    expect(screen.queryByText(/38\.26153/)).not.toBeInTheDocument();
  });

  it("gives each revenue-trend bar column an explicit height so its bar's percentage height resolves", async () => {
    // jsdom doesn't perform real CSS layout, so this can't assert a
    // rendered pixel height directly — it instead locks in the structural
    // fix for a real bug found via manual browser verification: a
    // percentage `height` style only resolves against an ancestor with an
    // explicitly set height. Without `h-full` on this column, every bar
    // silently rendered at zero height (invisible), even though the
    // computed percentage itself was always correct.
    vi.mocked(getDashboard).mockResolvedValue({
      kpis: {
        total_revenue: "100.00",
        transaction_count: 1,
        average_ticket: "100.00",
      },
      revenue_trend: [{ day: "2026-07-10", revenue: "100.00" }],
      top_items: [],
    });

    renderDashboard("rid-1");

    await waitFor(() => {
      expect(screen.getByText("07-10")).toBeInTheDocument();
    });
    const column = screen.getByText("07-10").parentElement;
    expect(column?.className).toContain("h-full");
  });

  it("shows an error state if the request fails", async () => {
    vi.mocked(getDashboard).mockRejectedValue(new Error("backend down"));

    renderDashboard("rid-1");

    await waitFor(() => {
      expect(screen.getByText("backend down")).toBeInTheDocument();
    });
  });
});
