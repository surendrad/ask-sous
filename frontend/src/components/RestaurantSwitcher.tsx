import { ChevronDown, Store } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useRestaurantContext } from "@/lib/restaurant-context";

/** Restaurant switcher — lives at the top of the sidebar per
 * design-guidelines.md §11. A checkbox-based multi-select dropdown built
 * from plain elements rather than a headless dropdown-menu primitive: a
 * trigger button showing the single selected name (or "N locations
 * selected") that opens a checkbox-per-restaurant panel plus a "Select
 * all" toggle — a deliberate simplification given this is purely a
 * data-context switch (design-guidelines.md §5), not a case where a richer
 * dropdown-menu visual treatment carries real product value. */
export function RestaurantSwitcher() {
  const {
    restaurants,
    selectedRestaurantIds,
    toggleRestaurant,
    selectAllRestaurants,
  } = useRestaurantContext();
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    function handleClickOutside(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen]);

  const selectedRestaurants = restaurants.filter((r) =>
    selectedRestaurantIds.includes(r.id),
  );
  const label =
    selectedRestaurants.length === 1
      ? selectedRestaurants[0].name
      : `${selectedRestaurants.length} locations selected`;
  const allSelected =
    restaurants.length > 0 &&
    selectedRestaurantIds.length === restaurants.length;

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        aria-haspopup="true"
        aria-expanded={isOpen}
        onClick={() => setIsOpen((v) => !v)}
        className="flex w-full items-center gap-2 rounded-md border border-border-strong bg-elevated px-3 py-2 text-left"
      >
        <Store size={16} className="shrink-0 text-brand" />
        <span className="flex-1 truncate text-sm font-medium text-text">
          {label}
        </span>
        <ChevronDown size={16} className="shrink-0 text-text-muted" />
      </button>

      {isOpen && (
        <div className="absolute z-10 mt-1 w-full rounded-md border border-border bg-elevated p-1 shadow-e2">
          <label className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-overlay">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={selectAllRestaurants}
              className="h-[18px] w-[18px] shrink-0 rounded-sm accent-brand"
            />
            Select all
          </label>
          <div className="my-1 border-t border-border" />
          {restaurants.map((restaurant) => (
            <label
              key={restaurant.id}
              className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-overlay"
            >
              <input
                type="checkbox"
                checked={selectedRestaurantIds.includes(restaurant.id)}
                onChange={() => toggleRestaurant(restaurant.id)}
                className="h-[18px] w-[18px] shrink-0 rounded-sm accent-brand"
              />
              {restaurant.name}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
