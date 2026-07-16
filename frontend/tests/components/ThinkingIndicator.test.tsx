import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ThinkingIndicator } from "@/components/ThinkingIndicator";

describe("ThinkingIndicator", () => {
  it("renders with an accessible label", () => {
    render(<ThinkingIndicator />);

    expect(screen.getByRole("status")).toHaveAccessibleName(/thinking/i);
  });
});
