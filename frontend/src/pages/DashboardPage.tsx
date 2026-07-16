import { useQuery } from "@tanstack/react-query";
import { BarChart3 } from "lucide-react";

import { StatusTag } from "@/components/StatusTag";
import { getDashboard } from "@/lib/api";

type DashboardPageProps = {
  restaurantId: string;
};

// The backend returns exact Decimal string values (e.g. an average ticket
// can carry 20+ digits after the point from unrounded division) — fine for
// an API contract that shouldn't silently lose precision, but not fit for
// display. Formatted to 2 decimal places here, at the UI boundary, rather
// than rounding the underlying value server-side.
function formatCurrency(value: string): string {
  return `$${Number(value).toFixed(2)}`;
}

/** Dashboard view — KPI stat-card row + two CSS-drawn chart cards
 * (design-guidelines.md §11: "CSS-drawn bars, no charting library needed
 * for the demo's visual weight" — a deliberate divergence from
 * implementation-plan.md 7.2's literal "using Recharts" wording, reconciled
 * in docs/decisions/012-live-trickle-generator.md in favor of the more
 * specific, later /designer decision). Full-width, not part of the
 * chat/campaigns split view, per design-guidelines.md §5. */
export default function DashboardPage({ restaurantId }: DashboardPageProps) {
  const { data, error, isPending } = useQuery({
    queryKey: ["dashboard", restaurantId],
    queryFn: () => getDashboard(restaurantId),
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

  const maxRevenue = Math.max(
    1,
    ...data.revenue_trend.map((d) => Number(d.revenue)),
  );
  const maxQuantity = Math.max(
    1,
    ...data.top_items.map((i) => i.total_quantity),
  );

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center gap-2">
        <BarChart3 size={18} className="text-brand" />
        <h2 className="font-display text-[23px] font-semibold leading-[30px]">
          Dashboard
        </h2>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <StatCard
          label="Revenue (7 days)"
          value={formatCurrency(data.kpis.total_revenue)}
        />
        <StatCard
          label="Transactions"
          value={String(data.kpis.transaction_count)}
        />
        <StatCard
          label="Average Ticket"
          value={formatCurrency(data.kpis.average_ticket)}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-lg border border-border bg-elevated p-4 shadow-e1">
          <h3 className="mb-3 text-[17px] font-semibold">Revenue Trend</h3>
          <div className="flex h-32 gap-2">
            {data.revenue_trend.map((day) => (
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
            {data.top_items.map((item) => (
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
