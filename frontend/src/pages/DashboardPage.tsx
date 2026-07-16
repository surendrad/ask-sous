import { useQuery } from "@tanstack/react-query";
import { BarChart3 } from "lucide-react";

import { StatusTag } from "@/components/StatusTag";
import { getDashboard, type LocationDashboard } from "@/lib/api";

type DashboardPageProps = {
  restaurantIds: string[];
};

// The backend returns exact Decimal string values (e.g. an average ticket
// can carry 20+ digits after the point from unrounded division) — fine for
// an API contract that shouldn't silently lose precision, but not fit for
// display. Formatted to 2 decimal places here, at the UI boundary, rather
// than rounding the underlying value server-side.
function formatCurrency(value: string): string {
  return `$${Number(value).toFixed(2)}`;
}

function formatPercent(value: string): string {
  return `${(Number(value) * 100).toFixed(1)}%`;
}

function maxRevenueOf(revenueTrend: { revenue: string }[]): number {
  return Math.max(1, ...revenueTrend.map((d) => Number(d.revenue)));
}

/** Dashboard view — KPI stat-card row + two CSS-drawn chart cards
 * (design-guidelines.md §11: "CSS-drawn bars, no charting library needed
 * for the demo's visual weight" — a deliberate divergence from
 * implementation-plan.md 7.2's literal "using Recharts" wording, reconciled
 * in docs/decisions/012-live-trickle-generator.md in favor of the more
 * specific, later /designer decision). Full-width, not part of the
 * chat/campaigns split view, per design-guidelines.md §5.
 *
 * A single selected location renders the original single-location layout
 * unchanged; 2+ selected locations render a combined comparison table with
 * per-location revenue sparklines instead (Phase 8, docs/decisions —
 * multi-location dashboard comparison). */
export default function DashboardPage({ restaurantIds }: DashboardPageProps) {
  const { data, error, isPending } = useQuery({
    queryKey: ["dashboard", restaurantIds],
    queryFn: () => getDashboard(restaurantIds),
  });

  if (isPending) {
    return <p className="p-4 text-sm text-text-muted">Loading…</p>;
  }

  if (error) {
    return (
      <div className="p-4">
        <StatusTag variant="error">{error.message}</StatusTag>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center gap-2">
        <BarChart3 size={18} className="text-brand" />
        <h2 className="font-display text-[23px] font-semibold leading-[30px]">
          Dashboard
        </h2>
      </div>

      {data.locations.length === 1 ? (
        <SingleLocationDashboard
          location={data.locations[0]}
          topItems={data.top_items ?? []}
        />
      ) : (
        <MultiLocationDashboard
          locations={data.locations}
          totals={data.totals}
        />
      )}
    </div>
  );
}

function SingleLocationDashboard({
  location,
  topItems,
}: {
  location: LocationDashboard;
  topItems: { menu_item_name: string; total_quantity: number }[];
}) {
  const maxRevenue = maxRevenueOf(location.revenue_trend);
  const maxQuantity = Math.max(1, ...topItems.map((i) => i.total_quantity));

  return (
    <>
      <div className="grid grid-cols-4 gap-4">
        <StatCard
          label="Revenue (7 days)"
          value={formatCurrency(location.kpis.total_revenue)}
        />
        <StatCard
          label="Transactions"
          value={String(location.kpis.transaction_count)}
        />
        <StatCard
          label="Average Ticket"
          value={formatCurrency(location.kpis.average_ticket)}
        />
        <StatCard
          label="Upsell Attach Rate"
          value={formatPercent(location.upsell_attach_rate)}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-lg border border-border bg-elevated p-4 shadow-e1">
          <h3 className="mb-3 text-[17px] font-semibold">Revenue Trend</h3>
          <div className="flex h-32 gap-2">
            {location.revenue_trend.map((day) => (
              <div
                key={day.day}
                // justify-end (not the parent's items-end) pushes the bar
                // to the bottom of a column that fills the h-32 parent's
                // height — the bar's percentage `height` below only
                // resolves against an explicitly-sized ancestor, so this
                // column must actually stretch to h-32, not just size to
                // its own content.
                className="flex h-full flex-1 flex-col items-center justify-end gap-1"
              >
                <div
                  className="w-full rounded-t bg-brand"
                  style={{
                    height: `${(Number(day.revenue) / maxRevenue) * 100}%`,
                  }}
                />
                <span className="font-mono text-[11px] text-text-muted">
                  {day.day.slice(5)}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-border bg-elevated p-4 shadow-e1">
          <h3 className="mb-3 text-[17px] font-semibold">Top Items</h3>
          <div className="flex flex-col gap-2">
            {topItems.map((item) => (
              <div key={item.menu_item_name} className="flex flex-col gap-1">
                <div className="flex justify-between text-sm">
                  <span>{item.menu_item_name}</span>
                  <span className="font-mono text-text-muted">
                    {item.total_quantity}
                  </span>
                </div>
                <div className="h-1.5 rounded-full bg-overlay">
                  <div
                    className="h-full rounded-full bg-brand"
                    style={{
                      width: `${(item.total_quantity / maxQuantity) * 100}%`,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

function MultiLocationDashboard({
  locations,
  totals,
}: {
  locations: LocationDashboard[];
  totals: {
    total_revenue: string;
    transaction_count: number;
    average_ticket: string;
  };
}) {
  return (
    <div className="rounded-lg border border-border bg-elevated p-4 shadow-e1">
      <h3 className="mb-3 text-[17px] font-semibold">Locations Compared</h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border-strong text-left">
            <th className="pb-2 text-xs font-semibold tracking-[0.04em] text-text-muted uppercase">
              Location
            </th>
            <th className="pb-2 text-right text-xs font-semibold tracking-[0.04em] text-text-muted uppercase">
              Revenue
            </th>
            <th className="pb-2 text-right text-xs font-semibold tracking-[0.04em] text-text-muted uppercase">
              Transactions
            </th>
            <th className="pb-2 text-right text-xs font-semibold tracking-[0.04em] text-text-muted uppercase">
              Avg Ticket
            </th>
            <th className="pb-2 text-right text-xs font-semibold tracking-[0.04em] text-text-muted uppercase">
              Upsell Rate
            </th>
            <th className="pb-2 text-right text-xs font-semibold tracking-[0.04em] text-text-muted uppercase">
              Trend
            </th>
          </tr>
        </thead>
        <tbody>
          {locations.map((location) => (
            <tr key={location.restaurant_id} className="border-b border-border">
              <td className="py-2.5 font-medium">{location.restaurant_name}</td>
              <td className="py-2.5 text-right font-mono">
                {formatCurrency(location.kpis.total_revenue)}
              </td>
              <td className="py-2.5 text-right font-mono">
                {location.kpis.transaction_count}
              </td>
              <td className="py-2.5 text-right font-mono">
                {formatCurrency(location.kpis.average_ticket)}
              </td>
              <td className="py-2.5 text-right font-mono">
                {formatPercent(location.upsell_attach_rate)}
              </td>
              <td className="py-2.5">
                <Sparkline revenueTrend={location.revenue_trend} />
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t border-border-strong font-semibold text-text-secondary">
            <td className="pt-3">Total</td>
            <td className="pt-3 text-right font-mono">
              {formatCurrency(totals.total_revenue)}
            </td>
            <td className="pt-3 text-right font-mono">
              {totals.transaction_count}
            </td>
            <td className="pt-3 text-right font-mono">
              {formatCurrency(totals.average_ticket)}
            </td>
            <td className="pt-3" />
            <td className="pt-3" />
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

function Sparkline({
  revenueTrend,
}: {
  revenueTrend: { day: string; revenue: string }[];
}) {
  const maxRevenue = maxRevenueOf(revenueTrend);

  return (
    <div className="flex h-[18px] items-end justify-end gap-[2px]">
      {revenueTrend.map((day) => (
        <div
          key={day.day}
          className="w-[3px] rounded-sm bg-brand opacity-70"
          style={{ height: `${(Number(day.revenue) / maxRevenue) * 100}%` }}
        />
      ))}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-elevated p-4 shadow-e1">
      <p className="text-xs font-semibold tracking-[0.04em] text-text-muted uppercase">
        {label}
      </p>
      <p className="mt-1 font-mono text-xl font-semibold">{value}</p>
    </div>
  );
}
