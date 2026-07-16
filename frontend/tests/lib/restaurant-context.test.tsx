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
];

function Consumer() {
  const { selectedRestaurant, restaurants, selectRestaurant } =
    useRestaurantContext();
  return (
    <div>
      <span data-testid="selected">{selectedRestaurant?.name ?? "none"}</span>
      {restaurants.map((r) => (
        <button key={r.id} type="button" onClick={() => selectRestaurant(r.id)}>
          {r.name}
        </button>
      ))}
    </div>
  );
}

describe("RestaurantProvider", () => {
  it("defaults the selection to the first restaurant", () => {
    render(
      <RestaurantProvider restaurants={RESTAURANTS}>
        <Consumer />
      </RestaurantProvider>,
    );

    expect(screen.getByTestId("selected")).toHaveTextContent("Golden Skillet");
  });

  it("updates the selection when selectRestaurant is called", async () => {
    const user = userEvent.setup();
    render(
      <RestaurantProvider restaurants={RESTAURANTS}>
        <Consumer />
      </RestaurantProvider>,
    );

    await user.click(screen.getByRole("button", { name: "Blue Lotus" }));

    expect(screen.getByTestId("selected")).toHaveTextContent("Blue Lotus");
  });

  it("has no selection when the restaurant list is empty", () => {
    render(
      <RestaurantProvider restaurants={[]}>
        <Consumer />
      </RestaurantProvider>,
    );

    expect(screen.getByTestId("selected")).toHaveTextContent("none");
  });
});
