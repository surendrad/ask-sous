import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { RestaurantSwitcher } from "@/components/RestaurantSwitcher";
import {
  RestaurantProvider,
  useRestaurantContext,
} from "@/lib/restaurant-context";

const RESTAURANTS = [
  { id: "a", name: "Golden Skillet" },
  { id: "b", name: "Blue Lotus" },
];

function Selected() {
  const { selectedRestaurant } = useRestaurantContext();
  return <span data-testid="selected">{selectedRestaurant?.name}</span>;
}

function renderSwitcher() {
  return render(
    <RestaurantProvider restaurants={RESTAURANTS}>
      <RestaurantSwitcher />
      <Selected />
    </RestaurantProvider>,
  );
}

describe("RestaurantSwitcher", () => {
  it("lists every restaurant as an option", () => {
    renderSwitcher();

    expect(
      screen.getByRole("option", { name: "Golden Skillet" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: "Blue Lotus" }),
    ).toBeInTheDocument();
  });

  it("shows the currently selected restaurant", () => {
    renderSwitcher();

    expect(screen.getByRole("combobox")).toHaveValue("a");
  });

  it("switching updates the shared restaurant context", async () => {
    const user = userEvent.setup();
    renderSwitcher();

    await user.selectOptions(screen.getByRole("combobox"), "Blue Lotus");

    expect(screen.getByTestId("selected")).toHaveTextContent("Blue Lotus");
  });
});
