import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { AppShell } from "@/components/AppShell";
import { RestaurantProvider } from "@/lib/restaurant-context";

const RESTAURANTS = [{ id: "a", name: "Golden Skillet" }];

function renderShell() {
  return render(
    <RestaurantProvider restaurants={RESTAURANTS}>
      <AppShell
        chatPanel={<div>chat content</div>}
        campaignsPanel={<div>campaigns content</div>}
      />
    </RestaurantProvider>,
  );
}

describe("AppShell", () => {
  it("renders the brand mark and nav items", () => {
    renderShell();

    expect(screen.getByText("Ask Sous")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^chat$/i })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /^campaigns$/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /dashboard/i })).toBeDisabled();
  });

  it("renders the restaurant switcher", () => {
    renderShell();

    expect(screen.getByRole("combobox")).toBeInTheDocument();
  });

  it("renders both panels", () => {
    renderShell();

    expect(screen.getByText("chat content")).toBeInTheDocument();
    expect(screen.getByText("campaigns content")).toBeInTheDocument();
  });

  it("marks the Chat nav item active by default, and switching updates it", async () => {
    const user = userEvent.setup();
    renderShell();

    expect(screen.getByRole("button", { name: /^chat$/i })).toHaveAttribute(
      "aria-current",
      "page",
    );

    await user.click(screen.getByRole("button", { name: /^campaigns$/i }));

    expect(
      screen.getByRole("button", { name: /^campaigns$/i }),
    ).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("button", { name: /^chat$/i })).not.toHaveAttribute(
      "aria-current",
    );
  });
});
