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
  const { selectedRestaurantIds } = useRestaurantContext();
  return <span data-testid="selected">{selectedRestaurantIds.join(",")}</span>;
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
  it("shows the single restaurant's name as the trigger label by default", () => {
    renderSwitcher();

    expect(
      screen.getByRole("button", { name: /Golden Skillet/ }),
    ).toBeInTheDocument();
  });

  it("opens a checkbox list of every restaurant when clicked", async () => {
    const user = userEvent.setup();
    renderSwitcher();

    await user.click(screen.getByRole("button", { name: /Golden Skillet/ }));

    expect(
      screen.getByRole("checkbox", { name: "Golden Skillet" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("checkbox", { name: "Blue Lotus" }),
    ).toBeInTheDocument();
  });

  it("checking an additional restaurant updates the selection and the trigger label", async () => {
    const user = userEvent.setup();
    renderSwitcher();

    await user.click(screen.getByRole("button", { name: /Golden Skillet/ }));
    await user.click(screen.getByRole("checkbox", { name: "Blue Lotus" }));

    expect(screen.getByTestId("selected")).toHaveTextContent("a,b");
    expect(
      screen.getByRole("button", { name: /2 locations selected/ }),
    ).toBeInTheDocument();
  });

  it("the select-all checkbox selects every restaurant", async () => {
    const user = userEvent.setup();
    renderSwitcher();

    await user.click(screen.getByRole("button", { name: /Golden Skillet/ }));
    await user.click(screen.getByRole("checkbox", { name: /select all/i }));

    expect(screen.getByTestId("selected")).toHaveTextContent("a,b");
  });

  it("unchecking a restaurant removes it from the selection", async () => {
    const user = userEvent.setup();
    renderSwitcher();

    await user.click(screen.getByRole("button", { name: /Golden Skillet/ }));
    await user.click(screen.getByRole("checkbox", { name: "Blue Lotus" }));
    await user.click(screen.getByRole("checkbox", { name: "Golden Skillet" }));

    expect(screen.getByTestId("selected")).toHaveTextContent("b");
  });
});
