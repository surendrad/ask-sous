import { useQuery } from "@tanstack/react-query";
import { Store } from "lucide-react";

import { StatusTag } from "@/components/StatusTag";
import { getHealth } from "@/lib/api";

export default function HealthCheckPage() {
  const { data, error, isPending } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
  });

  return (
    <main className="flex min-h-screen items-center justify-center bg-base">
      <div className="rounded-lg border border-border bg-elevated p-6 shadow-e1">
        <div className="mb-4 flex items-center gap-2">
          <Store className="text-brand" size={24} />
          <h1 className="font-display text-[23px] font-semibold leading-[30px]">
            Ask Sous
          </h1>
        </div>

        {isPending && (
          <p className="text-sm text-text-muted">Checking backend…</p>
        )}
        {data && <StatusTag variant="success">{data.status}</StatusTag>}
        {error && <StatusTag variant="error">{error.message}</StatusTag>}
      </div>
    </main>
  );
}
