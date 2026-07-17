import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  generateCampaign,
  getDashboard,
  getRestaurants,
  streamChat,
} from "@/lib/api";

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

    await streamChat(["rid-1"], "hi", { onChunk, onDone, onError });

    expect(onChunk.mock.calls).toEqual([["Hello "], ["there."]]);
    expect(onDone).toHaveBeenCalledWith({
      answer: "Hello there.",
      tool_calls: [],
      model: "gemini-2.5-flash",
    });
    expect(onError).not.toHaveBeenCalled();
  });

  it("sends restaurant_ids as a list in the request body", async () => {
    vi.mocked(fetch).mockResolvedValue(
      sseStreamResponse([
        `data: ${JSON.stringify({ type: "done", answer: "ok", tool_calls: [], model: "gemini-2.5-flash" })}\n\n`,
      ]),
    );

    await streamChat(["rid-1", "rid-2"], "hi", {
      onChunk: vi.fn(),
      onDone: vi.fn(),
      onError: vi.fn(),
    });

    const [, init] = vi.mocked(fetch).mock.calls[0];
    expect(JSON.parse(init?.body as string)).toEqual({
      restaurant_ids: ["rid-1", "rid-2"],
      question: "hi",
    });
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

    await streamChat(["rid-1"], "hi", { onChunk, onDone, onError });

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

    await streamChat(["rid-1"], "hi", { onChunk, onDone, onError });

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
    await streamChat(["rid-1"], "hi", {
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

    await streamChat(["rid-1"], "hi", { onChunk: vi.fn(), onDone, onError });

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
            tool_calls: [],
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

describe("getDashboard", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("returns the dashboard data from the envelope", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          data: {
            locations: [
              {
                restaurant_id: "rid-1",
                restaurant_name: "Golden Skillet",
                kpis: {
                  total_revenue: "500.00",
                  transaction_count: 10,
                  average_ticket: "50.00",
                },
                revenue_trend: [{ day: "2026-07-10", revenue: "100.00" }],
                upsell_attach_rate: "0.2",
              },
            ],
            totals: {
              total_revenue: "500.00",
              transaction_count: 10,
              average_ticket: "50.00",
            },
            top_items: [
              { menu_item_name: "Truffle Fries", total_quantity: 42 },
            ],
          },
          error: null,
        }),
        { status: 200 },
      ),
    );

    const result = await getDashboard(["rid-1"]);

    expect(result.locations[0].kpis.total_revenue).toBe("500.00");
    expect(result.locations[0].revenue_trend[0].day).toBe("2026-07-10");
    expect(result.top_items?.[0].menu_item_name).toBe("Truffle Fries");
    expect(vi.mocked(fetch).mock.calls[0][0]).toContain(
      "/dashboard?restaurant_ids=rid-1",
    );
  });

  it("encodes multiple restaurant_ids as repeated query params", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          data: {
            locations: [],
            totals: {
              total_revenue: "0",
              transaction_count: 0,
              average_ticket: "0",
            },
            top_items: null,
          },
          error: null,
        }),
        { status: 200 },
      ),
    );

    await getDashboard(["rid-1", "rid-2"]);

    expect(vi.mocked(fetch).mock.calls[0][0]).toContain(
      "/dashboard?restaurant_ids=rid-1&restaurant_ids=rid-2",
    );
  });
});
