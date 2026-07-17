import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { generateCampaign } from "@/lib/api";
import CampaignsPanel from "@/pages/CampaignsPanel";

vi.mock("@/lib/api", () => ({
  generateCampaign: vi.fn(),
}));

describe("CampaignsPanel", () => {
  beforeEach(() => {
    vi.mocked(generateCampaign).mockReset();
  });

  it("shows an empty state when there is no draft yet", () => {
    render(<CampaignsPanel restaurantId="rid-1" />);

    expect(screen.getByText(/no campaign draft yet/i)).toBeInTheDocument();
  });

  it("submitting a brief shows a loading state then a populated card", async () => {
    vi.mocked(generateCampaign).mockResolvedValue({
      copy_text: "Taco Tuesday is back!",
      examples_used: [],
      model: "gemini-2.5-pro",
      tool_calls: [],
    });

    const user = userEvent.setup();
    render(<CampaignsPanel restaurantId="rid-1" />);

    await user.type(screen.getByRole("textbox"), "Announce taco special");
    await user.click(screen.getByRole("button", { name: /generate/i }));

    await waitFor(() => {
      expect(screen.getByText("Taco Tuesday is back!")).toBeInTheDocument();
    });
    expect(generateCampaign).toHaveBeenCalledWith(
      "rid-1",
      "Announce taco special",
    );
  });

  it("regenerate re-calls the API with the same brief", async () => {
    vi.mocked(generateCampaign)
      .mockResolvedValueOnce({
        copy_text: "First draft.",
        examples_used: [],
        model: "gemini-2.5-pro",
        tool_calls: [],
      })
      .mockResolvedValueOnce({
        copy_text: "Second draft.",
        examples_used: [],
        model: "gemini-2.5-pro",
        tool_calls: [],
      });

    const user = userEvent.setup();
    render(<CampaignsPanel restaurantId="rid-1" />);

    await user.type(screen.getByRole("textbox"), "Announce taco special");
    await user.click(screen.getByRole("button", { name: /generate/i }));
    await waitFor(() =>
      expect(screen.getByText("First draft.")).toBeInTheDocument(),
    );

    await user.click(screen.getByRole("button", { name: /regenerate/i }));

    await waitFor(() =>
      expect(screen.getByText("Second draft.")).toBeInTheDocument(),
    );
    expect(generateCampaign).toHaveBeenCalledTimes(2);
  });

  it("copy writes the campaign copy to the clipboard", async () => {
    vi.mocked(generateCampaign).mockResolvedValue({
      copy_text: "Taco Tuesday is back!",
      examples_used: [],
      model: "gemini-2.5-pro",
      tool_calls: [],
    });

    const user = userEvent.setup();
    const writeText = vi
      .spyOn(navigator.clipboard, "writeText")
      .mockResolvedValue(undefined);
    render(<CampaignsPanel restaurantId="rid-1" />);

    await user.type(screen.getByRole("textbox"), "Announce taco special");
    await user.click(screen.getByRole("button", { name: /generate/i }));
    await waitFor(() =>
      expect(screen.getByText("Taco Tuesday is back!")).toBeInTheDocument(),
    );

    await user.click(screen.getByRole("button", { name: /copy/i }));

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith("Taco Tuesday is back!");
    });
  });

  it("shows a prompt and disables Generate when multiple locations are selected", () => {
    render(<CampaignsPanel restaurantId="rid-1" isMultipleSelected />);

    expect(
      screen.getByText(/select exactly one location/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /generate/i })).toBeDisabled();
  });

  it("does not call generateCampaign while multiple locations are selected", async () => {
    const user = userEvent.setup();
    render(<CampaignsPanel restaurantId="rid-1" isMultipleSelected />);

    await user.type(screen.getByRole("textbox"), "Announce taco special");
    await user.click(screen.getByRole("button", { name: /generate/i }));

    expect(generateCampaign).not.toHaveBeenCalled();
  });

  it("shows a citation chip when the model called a tool before writing copy", async () => {
    // Campaign generation is agentic (Phase 8+) — a brief referencing real
    // performance data ("our slowest weekday") should show which tool
    // grounded the claim, the same way chat's citation chips do.
    vi.mocked(generateCampaign).mockResolvedValue({
      copy_text: "Tuesdays are slow — 20% off dine-in orders over $20!",
      examples_used: [],
      model: "gemini-2.5-pro",
      tool_calls: [
        {
          tool_name: "get_weekday_performance",
          arguments: { restaurant_id: "rid-1" },
          result: [{ day_of_week: "Tuesday", total_revenue: "100.00" }],
          error: null,
        },
      ],
    });

    const user = userEvent.setup();
    render(<CampaignsPanel restaurantId="rid-1" />);

    await user.type(
      screen.getByRole("textbox"),
      "Create a campaign for our slowest weekday",
    );
    await user.click(screen.getByRole("button", { name: /generate/i }));

    await waitFor(() => {
      expect(screen.getByText("get_weekday_performance")).toBeInTheDocument();
    });
  });

  it("shows no citation chips when the brief needed no tool calls", async () => {
    vi.mocked(generateCampaign).mockResolvedValue({
      copy_text: "Come try our new patio seating!",
      examples_used: [],
      model: "gemini-2.5-pro",
      tool_calls: [],
    });

    const user = userEvent.setup();
    render(<CampaignsPanel restaurantId="rid-1" />);

    await user.type(screen.getByRole("textbox"), "Announce our new patio");
    await user.click(screen.getByRole("button", { name: /generate/i }));

    await waitFor(() => {
      expect(
        screen.getByText("Come try our new patio seating!"),
      ).toBeInTheDocument();
    });
    expect(screen.queryByText(/get_/)).not.toBeInTheDocument();
  });
});
