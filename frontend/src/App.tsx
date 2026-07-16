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

function AppShellWithData() {
  const { selectedRestaurant } = useRestaurantContext();

  if (!selectedRestaurant) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-base">
        <StatusTag variant="warning">No restaurants found.</StatusTag>
      </div>
    );
  }

  return (
    <AppShell
      // `key` forces a remount on restaurant switch — otherwise each
      // page's own state (chat history, campaign draft) would persist
      // across restaurants instead of resetting, since only the
      // restaurantId prop would change on an existing instance.
      chatPanel={
        <ChatPage
          key={selectedRestaurant.id}
          restaurantId={selectedRestaurant.id}
        />
      }
      campaignsPanel={
        <CampaignsPanel
          key={selectedRestaurant.id}
          restaurantId={selectedRestaurant.id}
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
