import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CitationChip } from "@/components/CitationChip";

describe("CitationChip", () => {
  it("renders the tool name", () => {
    render(<CitationChip toolName="get_revenue_summary" />);

    expect(screen.getByText("get_revenue_summary")).toBeInTheDocument();
  });

  it("renders an error indicator when the tool call failed", () => {
    render(<CitationChip toolName="get_revenue_summary" hasError />);

    expect(screen.getByText(/error/i)).toBeInTheDocument();
  });
});
