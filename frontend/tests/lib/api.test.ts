import { beforeEach, describe, expect, it, vi } from "vitest";

import { generateCampaign, getRestaurants, streamChat } from "@/lib/api";

function sseStreamResponse(frames: string[], init?: { status?: number }) {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const frame of frames) {
        controller.enqueue(encoder.encode(frame));
      }
      controller.close();
    },
  });
  return new Response(body, {
    status: init?.status ?? 200,
    headers: { "content-type": "text/event-stream" },
  });
}

describe("streamChat", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("calls onChunk for each text_chunk event and onDone for the terminal event", async () => {
    const frames = [
      `data: ${JSON.stringify({ type: "text_chunk", text: "Hello " })}\n\n`,
      `data: ${JSON.stringify({ type: "text_chunk", text: "there." })}\n\n`,
      `data: ${JSON.stringify({ type: "done", answer: "Hello there.", tool_calls: [], model: "gemini-2.5-flash" })}\n\n`,
    ];
    vi.mocked(fetch).mockResolvedValue(sseStreamResponse(frames));

    const onChunk = vi.fn();
    const onDone = vi.fn();
    const onError = vi.fn();

    await streamChat("rid-1", "hi", { onChunk, onDone, onError });

    expect(onChunk.mock.calls).toEqual([["Hello "], ["there."]]);
    expect(onDone).toHaveBeenCalledWith({
      answer: "Hello there.",
      tool_calls: [],
      model: "gemini-2.5-flash",
    });
    expect(onError).not.toHaveBeenCalled();
  });

  it("calls onError for an error-type SSE event and stops", async () => {
    const frames = [
      `data: ${JSON.stringify({ type: "text_chunk", text: "Partial" })}\n\n`,
      `data: ${JSON.stringify({ type: "error", message: "unavailable", code: "agent_unavailable" })}\n\n`,
    ];
    vi.mocked(fetch).mockResolvedValue(sseStreamResponse(frames));

    const onChunk = vi.fn();
    const onDone = vi.fn();
    const onError = vi.fn();

    await streamChat("rid-1", "hi", { onChunk, onDone, onError });

    expect(onChunk).toHaveBeenCalledWith("Partial");
    expect(onError).toHaveBeenCalledWith({
      message: "unavailable",
      code: "agent_unavailable",
    });
    expect(onDone).not.toHaveBeenCalled();
  });

  it("calls onError when the request itself fails before any stream starts", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          data: null,
          error: { message: "down", code: "agent_unavailable" },
        }),
        {
          status: 503,
          headers: { "content-type": "application/json" },
        },
      ),
    );

    const onChunk = vi.fn();
    const onDone = vi.fn();
    const onError = vi.fn();

    await streamChat("rid-1", "hi", { onChunk, onDone, onError });

    expect(onError).toHaveBeenCalledWith({
      message: "down",
      code: "agent_unavailable",
    });
    expect(onChunk).not.toHaveBeenCalled();
  });

  it("splits SSE frames that arrive across multiple stream chunks", async () => {
    const fullFrame = `data: ${JSON.stringify({ type: "text_chunk", text: "split" })}\n\n`;
    const encoder = new TextEncoder();
    const halfway = Math.floor(fullFrame.length / 2);
    const part1 = fullFrame.slice(0, halfway);
    const part2 = fullFrame.slice(halfway);
    const donePart = `data: ${JSON.stringify({ type: "done", answer: "split", tool_calls: [], model: "gemini-2.5-flash" })}\n\n`;

    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode(part1));
        controller.enqueue(encoder.encode(part2));
        controller.enqueue(encoder.encode(donePart));
        controller.close();
      },
    });
    vi.mocked(fetch).mockResolvedValue(
      new Response(body, {
        status: 200,
        headers: { "content-type": "text/event-stream" },
      }),
    );

    const onChunk = vi.fn();
    await streamChat("rid-1", "hi", {
      onChunk,
      onDone: vi.fn(),
      onError: vi.fn(),
    });

    expect(onChunk).toHaveBeenCalledWith("split");
  });

  it("calls onError if the stream closes without a done or error event", async () => {
    const frames = [
      `data: ${JSON.stringify({ type: "text_chunk", text: "Partial" })}\n\n`,
    ];
    vi.mocked(fetch).mockResolvedValue(sseStreamResponse(frames));

    const onDone = vi.fn();
    const onError = vi.fn();

    await streamChat("rid-1", "hi", { onChunk: vi.fn(), onDone, onError });

    expect(onError).toHaveBeenCalledWith({
      message: "Failed to reach the backend.",
      code: "unknown_error",
    });
    expect(onDone).not.toHaveBeenCalled();
  });
});

describe("getRestaurants", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("returns the restaurant list from the envelope", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          data: { restaurants: [{ id: "a", name: "Golden Skillet" }] },
          error: null,
        }),
        { status: 200 },
      ),
    );

    const restaurants = await getRestaurants();

    expect(restaurants).toEqual([{ id: "a", name: "Golden Skillet" }]);
  });
});

describe("generateCampaign", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("returns the campaign data from the envelope", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          data: {
            copy_text: "Taco Tuesday!",
            examples_used: [],
            model: "gemini-2.5-pro",
          },
          error: null,
        }),
        { status: 200 },
      ),
    );

    const result = await generateCampaign("rid-1", "Announce taco special");

    expect(result.copy_text).toBe("Taco Tuesday!");
    expect(result.model).toBe("gemini-2.5-pro");
  });

  it("throws when the envelope carries an error", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          data: null,
          error: { message: "not found", code: "restaurant_not_found" },
        }),
        { status: 404 },
      ),
    );

    await expect(generateCampaign("rid-1", "brief")).rejects.toThrow(
      "not found",
    );
  });
});
