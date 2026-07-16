import {
  createContext,
  type ReactNode,
  useContext,
  useMemo,
  useState,
} from "react";

import type { Restaurant } from "@/lib/api";

type RestaurantContextValue = {
  restaurants: Restaurant[];
  selectedRestaurantIds: string[];
  toggleRestaurant: (id: string) => void;
  selectAllRestaurants: () => void;
};

const RestaurantContext = createContext<RestaurantContextValue | null>(null);

type RestaurantProviderProps = {
  restaurants: Restaurant[];
  children: ReactNode;
};

/** Holds the currently-selected restaurants — the single source of truth
 * the chat page, campaigns panel, and dashboard read to scope their
 * requests. Multi-select (Phase 8): defaults to just the first restaurant
 * (matching the original single-selection behavior), and always keeps at
 * least one restaurant selected — toggling the last remaining selection off
 * is a no-op rather than leaving nothing selected. */
export function RestaurantProvider({
  restaurants,
  children,
}: RestaurantProviderProps) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(
    () => new Set(restaurants[0] ? [restaurants[0].id] : []),
  );

  const value = useMemo<RestaurantContextValue>(() => {
    const selectedRestaurantIds = restaurants
      .filter((r) => selectedIds.has(r.id))
      .map((r) => r.id);

    return {
      restaurants,
      selectedRestaurantIds,
      toggleRestaurant: (id: string) => {
        setSelectedIds((prev) => {
          if (prev.has(id)) {
            if (prev.size === 1) return prev;
            const next = new Set(prev);
            next.delete(id);
            return next;
          }
          return new Set(prev).add(id);
        });
      },
      selectAllRestaurants: () => {
        setSelectedIds(new Set(restaurants.map((r) => r.id)));
      },
    };
  }, [restaurants, selectedIds]);

  return (
    <RestaurantContext.Provider value={value}>
      {children}
    </RestaurantContext.Provider>
  );
}

export function useRestaurantContext(): RestaurantContextValue {
  const context = useContext(RestaurantContext);
  if (!context) {
    throw new Error(
      "useRestaurantContext must be used within a RestaurantProvider",
    );
  }
  return context;
}
