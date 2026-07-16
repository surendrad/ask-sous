import { useQuery } from "@tanstack/react-query";

import { AppShell } from "@/components/AppShell";
import { StatusTag } from "@/components/StatusTag";
import { getRestaurants } from "@/lib/api";
import {
  RestaurantProvider,
  useRestaurantContext,
} from "@/lib/restaurant-context";
import CampaignsPanel from "@/pages/CampaignsPanel";
import ChatPage from "@/pages/ChatPage";
import DashboardPage from "@/pages/DashboardPage";

function AppShellWithData() {
  const { restaurants, selectedRestaurantIds } = useRestaurantContext();

  if (restaurants.length === 0) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-base">
        <StatusTag variant="warning">No restaurants found.</StatusTag>
      </div>
    );
  }

  // Campaign generation stays single-location (brand voice + copy are
  // generated per-restaurant) — it always scopes to the first selected
  // restaurant and disables itself when more than one is selected.
  const primaryRestaurantId = selectedRestaurantIds[0];
  const isMultipleSelected = selectedRestaurantIds.length > 1;
  // `key` forces a remount on selection change — otherwise each page's own
  // state (chat history, campaign draft) would persist across restaurants
  // instead of resetting, since only the restaurantIds prop would change
  // on an existing instance.
  const selectionKey = selectedRestaurantIds.join(",");

  return (
    <AppShell
      chatPanel={
        <ChatPage key={selectionKey} restaurantIds={selectedRestaurantIds} />
      }
      campaignsPanel={
        <CampaignsPanel
          key={primaryRestaurantId}
          restaurantId={primaryRestaurantId}
          isMultipleSelected={isMultipleSelected}
        />
      }
      dashboardPanel={
        <DashboardPage
          key={selectionKey}
          restaurantIds={selectedRestaurantIds}
        />
      }
    />
  );
}

function App() {
  const { data, error, isPending } = useQuery({
    queryKey: ["restaurants"],
    queryFn: getRestaurants,
  });

  if (isPending) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-base">
        <p className="text-sm text-text-muted">Loading…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-base">
        <StatusTag variant="error">{error.message}</StatusTag>
      </div>
    );
  }

  return (
    <RestaurantProvider restaurants={data}>
      <AppShellWithData />
    </RestaurantProvider>
  );
}

export default App;
