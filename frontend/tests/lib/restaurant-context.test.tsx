import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import {
  RestaurantProvider,
  useRestaurantContext,
} from "@/lib/restaurant-context";

const RESTAURANTS = [
  { id: "a", name: "Golden Skillet" },
  { id: "b", name: "Blue Lotus" },
  { id: "c", name: "Casa Verde" },
];

function Consumer() {
  const {
    selectedRestaurantIds,
    restaurants,
    toggleRestaurant,
    selectAllRestaurants,
  } = useRestaurantContext();
  return (
    <div>
      <span data-testid="selected">{selectedRestaurantIds.join(",")}</span>
      {restaurants.map((r) => (
        <button key={r.id} type="button" onClick={() => toggleRestaurant(r.id)}>
          {r.name}
        </button>
      ))}
      <button type="button" onClick={selectAllRestaurants}>
        Select all
      </button>
    </div>
  );
}

describe("RestaurantProvider", () => {
  it("defaults the selection to just the first restaurant", () => {
    render(
      <RestaurantProvider restaurants={RESTAURANTS}>
        <Consumer />
      </RestaurantProvider>,
    );

    expect(screen.getByTestId("selected")).toHaveTextContent("a");
  });

  it("has no selection when the restaurant list is empty", () => {
    render(
      <RestaurantProvider restaurants={[]}>
        <Consumer />
      </RestaurantProvider>,
    );

    expect(screen.getByTestId("selected")).toHaveTextContent("");
  });

  it("toggleRestaurant adds a restaurant to the selection", async () => {
    const user = userEvent.setup();
    render(
      <RestaurantProvider restaurants={RESTAURANTS}>
        <Consumer />
      </RestaurantProvider>,
    );

    await user.click(screen.getByRole("button", { name: "Blue Lotus" }));

    expect(screen.getByTestId("selected")).toHaveTextContent("a,b");
  });

  it("toggleRestaurant removes a restaurant already in the selection", async () => {
    const user = userEvent.setup();
    render(
      <RestaurantProvider restaurants={RESTAURANTS}>
        <Consumer />
      </RestaurantProvider>,
    );

    await user.click(screen.getByRole("button", { name: "Blue Lotus" }));
    await user.click(screen.getByRole("button", { name: "Golden Skillet" }));

    expect(screen.getByTestId("selected")).toHaveTextContent("b");
  });

  it("toggleRestaurant refuses to remove the last remaining selected restaurant", async () => {
    const user = userEvent.setup();
    render(
      <RestaurantProvider restaurants={RESTAURANTS}>
        <Consumer />
      </RestaurantProvider>,
    );

    await user.click(screen.getByRole("button", { name: "Golden Skillet" }));

    expect(screen.getByTestId("selected")).toHaveTextContent("a");
  });

  it("selectAllRestaurants selects every restaurant, in list order", async () => {
    const user = userEvent.setup();
    render(
      <RestaurantProvider restaurants={RESTAURANTS}>
        <Consumer />
      </RestaurantProvider>,
    );

    await user.click(screen.getByRole("button", { name: "Select all" }));

    expect(screen.getByTestId("selected")).toHaveTextContent("a,b,c");
  });
});
