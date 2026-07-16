import { ChevronDown, Store } from "lucide-react";

import { useRestaurantContext } from "@/lib/restaurant-context";

/** Restaurant switcher — lives at the top of the sidebar per
 * design-guidelines.md §11. Implemented as a styled native <select> rather
 * than a headless dropdown-menu primitive: fully accessible and
 * keyboard-native out of the box, and far simpler to test reliably than a
 * portal-based popup — a deliberate simplification given this is purely a
 * data-context switch (design-guidelines.md §5), not a case where the
 * richer dropdown-menu visual treatment carries real product value. */
export function RestaurantSwitcher() {
  const { restaurants, selectedRestaurant, selectRestaurant } =
    useRestaurantContext();

  return (
    <div className="relative flex items-center gap-2 rounded-md border border-border-strong bg-elevated px-3 py-2">
      <Store size={16} className="shrink-0 text-brand" />
      <select
        aria-label="Restaurant"
        className="w-full appearance-none bg-transparent pr-5 text-sm font-medium text-text outline-none"
        value={selectedRestaurant?.id ?? ""}
        onChange={(e) => selectRestaurant(e.target.value)}
      >
        {restaurants.map((restaurant) => (
          <option key={restaurant.id} value={restaurant.id}>
            {restaurant.name}
          </option>
        ))}
      </select>
      <ChevronDown
        size={16}
        className="pointer-events-none absolute right-3 text-text-muted"
      />
    </div>
  );
}
