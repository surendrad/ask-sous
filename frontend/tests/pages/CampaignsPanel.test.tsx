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
      })
      .mockResolvedValueOnce({
        copy_text: "Second draft.",
        examples_used: [],
        model: "gemini-2.5-pro",
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
});
