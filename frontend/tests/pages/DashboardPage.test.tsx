import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getDashboard } from "@/lib/api";
import DashboardPage from "@/pages/DashboardPage";

vi.mock("@/lib/api", () => ({
  getDashboard: vi.fn(),
}));

function renderDashboard(restaurantIds: string[]) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <DashboardPage restaurantIds={restaurantIds} />
    </QueryClientProvider>,
  );
}

describe("DashboardPage — single location", () => {
  beforeEach(() => {
    vi.mocked(getDashboard).mockReset();
  });

  it("renders KPIs, revenue trend bars, top items, and upsell attach rate once loaded", async () => {
    vi.mocked(getDashboard).mockResolvedValue({
      locations: [
        {
          restaurant_id: "rid-1",
          restaurant_name: "Golden Skillet",
          kpis: {
            total_revenue: "1500.00",
            transaction_count: 33,
            average_ticket: "50.00",
          },
          revenue_trend: [
            { day: "2026-07-10", revenue: "100.00" },
            { day: "2026-07-11", revenue: "200.00" },
          ],
          upsell_attach_rate: "0.25",
        },
      ],
      totals: {
        total_revenue: "1500.00",
        transaction_count: 33,
        average_ticket: "50.00",
      },
      top_items: [
        { menu_item_name: "Truffle Fries", total_quantity: 42 },
        { menu_item_name: "Margherita", total_quantity: 30 },
      ],
    });

    renderDashboard(["rid-1"]);

    await waitFor(() => {
      expect(screen.getByText("$1500.00")).toBeInTheDocument();
    });
    expect(screen.getByText("33")).toBeInTheDocument();
    expect(screen.getByText("Truffle Fries")).toBeInTheDocument();
    expect(screen.getByText("Margherita")).toBeInTheDocument();
    expect(screen.getByText("25.0%")).toBeInTheDocument();
  });

  it("does not crash when revenue trend and top items are empty", async () => {
    vi.mocked(getDashboard).mockResolvedValue({
      locations: [
        {
          restaurant_id: "rid-1",
          restaurant_name: "Golden Skillet",
          kpis: {
            total_revenue: "0",
            transaction_count: 0,
            average_ticket: "0",
          },
          revenue_trend: [],
          upsell_attach_rate: "0",
        },
      ],
      totals: { total_revenue: "0", transaction_count: 0, average_ticket: "0" },
      top_items: [],
    });

    renderDashboard(["rid-1"]);

    await waitFor(() => {
      expect(screen.getAllByText("$0.00").length).toBeGreaterThan(0);
    });
    expect(screen.getByText("0.0%")).toBeInTheDocument();
  });

  it("formats a long-precision Decimal average ticket to 2 decimal places", async () => {
    vi.mocked(getDashboard).mockResolvedValue({
      locations: [
        {
          restaurant_id: "rid-1",
          restaurant_name: "Golden Skillet",
          kpis: {
            total_revenue: "14692.43",
            transaction_count: 384,
            average_ticket: "38.26153645833333333333333333",
          },
          revenue_trend: [],
          upsell_attach_rate: "0.19",
        },
      ],
      totals: {
        total_revenue: "14692.43",
        transaction_count: 384,
        average_ticket: "38.26153645833333333333333333",
      },
      top_items: [],
    });

    renderDashboard(["rid-1"]);

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
      locations: [
        {
          restaurant_id: "rid-1",
          restaurant_name: "Golden Skillet",
          kpis: {
            total_revenue: "100.00",
            transaction_count: 1,
            average_ticket: "100.00",
          },
          revenue_trend: [{ day: "2026-07-10", revenue: "100.00" }],
          upsell_attach_rate: "0",
        },
      ],
      totals: {
        total_revenue: "100.00",
        transaction_count: 1,
        average_ticket: "100.00",
      },
      top_items: [],
    });

    renderDashboard(["rid-1"]);

    await waitFor(() => {
      expect(screen.getByText("07-10")).toBeInTheDocument();
    });
    const column = screen.getByText("07-10").parentElement;
    expect(column?.className).toContain("h-full");
  });

  it("shows an error state if the request fails", async () => {
    vi.mocked(getDashboard).mockRejectedValue(new Error("backend down"));

    renderDashboard(["rid-1"]);

    await waitFor(() => {
      expect(screen.getByText("backend down")).toBeInTheDocument();
    });
  });
});

describe("DashboardPage — multiple locations", () => {
  beforeEach(() => {
    vi.mocked(getDashboard).mockReset();
  });

  it("renders a combined comparison table with a row per location, upsell rates, and a totals row", async () => {
    vi.mocked(getDashboard).mockResolvedValue({
      locations: [
        {
          restaurant_id: "rid-1",
          restaurant_name: "Golden Skillet",
          kpis: {
            total_revenue: "1500.00",
            transaction_count: 33,
            average_ticket: "45.45",
          },
          revenue_trend: [
            { day: "2026-07-10", revenue: "700.00" },
            { day: "2026-07-11", revenue: "800.00" },
          ],
          upsell_attach_rate: "0.3",
        },
        {
          restaurant_id: "rid-2",
          restaurant_name: "Bella Notte",
          kpis: {
            total_revenue: "900.00",
            transaction_count: 20,
            average_ticket: "45.00",
          },
          revenue_trend: [
            { day: "2026-07-10", revenue: "400.00" },
            { day: "2026-07-11", revenue: "500.00" },
          ],
          upsell_attach_rate: "0.1",
        },
      ],
      totals: {
        total_revenue: "2400.00",
        transaction_count: 53,
        average_ticket: "45.28",
      },
      top_items: null,
    });

    renderDashboard(["rid-1", "rid-2"]);

    await waitFor(() => {
      expect(screen.getByText("Golden Skillet")).toBeInTheDocument();
    });
    expect(screen.getByText("Bella Notte")).toBeInTheDocument();
    expect(screen.getByText("$1500.00")).toBeInTheDocument();
    expect(screen.getByText("$900.00")).toBeInTheDocument();
    // Totals row.
    expect(screen.getByText("$2400.00")).toBeInTheDocument();
    expect(screen.getByText("53")).toBeInTheDocument();
    // Per-location upsell attach rate column.
    expect(screen.getByText("30.0%")).toBeInTheDocument();
    expect(screen.getByText("10.0%")).toBeInTheDocument();

    // Top items panel is a single-location-only feature.
    expect(screen.queryByText("Top Items")).not.toBeInTheDocument();
  });
});
