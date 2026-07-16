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
  selectedRestaurant: Restaurant | null;
  selectRestaurant: (id: string) => void;
};

const RestaurantContext = createContext<RestaurantContextValue | null>(null);

type RestaurantProviderProps = {
  restaurants: Restaurant[];
  children: ReactNode;
};

/** Holds the currently-selected restaurant — the single source of truth
 * both the chat page and campaigns panel read to scope their requests, per
 * design-guidelines.md's "purely a data-context switch" framing. Defaults
 * to the first restaurant once the list loads. */
export function RestaurantProvider({
  restaurants,
  children,
}: RestaurantProviderProps) {
  const [selectedId, setSelectedId] = useState<string | null>(
    restaurants[0]?.id ?? null,
  );

  const value = useMemo<RestaurantContextValue>(
    () => ({
      restaurants,
      selectedRestaurant: restaurants.find((r) => r.id === selectedId) ?? null,
      selectRestaurant: setSelectedId,
    }),
    [restaurants, selectedId],
  );

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
