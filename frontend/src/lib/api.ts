type ApiEnvelope<T> = {
  data: T | null;
  error: ApiError | null;
};

export type ApiError = {
  message: string;
  code: string;
};

type HealthStatus = {
  status: string;
};

export type Restaurant = {
  id: string;
  name: string;
};

export type ChatToolCall = {
  tool_name: string;
  arguments: Record<string, unknown>;
  // Most tools return a single object, but multi-restaurant tools like
  // compare_locations()/get_upsell_metrics() return an array (one entry
  // per restaurant).
  result: Record<string, unknown> | unknown[] | null;
  error: string | null;
};

export type ChatDoneEvent = {
  answer: string;
  tool_calls: ChatToolCall[];
  model: string;
};

export type CampaignExample = {
  campaign_id: string;
  copy_text: string;
};

export type CampaignResult = {
  copy_text: string;
  examples_used: CampaignExample[];
  model: string;
  // Campaign generation is agentic (Phase 8+) — the model may call the same
  // tools chat does (e.g. get_weekday_performance) before writing copy that
  // references real performance data. Reuses ChatToolCall's shape since
  // it's the identical envelope shape.
  tool_calls: ChatToolCall[];
};

export type DashboardKpis = {
  total_revenue: string;
  transaction_count: number;
  average_ticket: string;
};

export type RevenueTrendDay = {
  day: string;
  revenue: string;
};

export type TopItem = {
  menu_item_name: string;
  total_quantity: number;
};

export type LocationDashboard = {
  restaurant_id: string;
  restaurant_name: string;
  kpis: DashboardKpis;
  revenue_trend: RevenueTrendDay[];
  upsell_attach_rate: string;
};

export type DashboardData = {
  locations: LocationDashboard[];
  totals: DashboardKpis;
  top_items: TopItem[] | null;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
const UNKNOWN_ERROR: ApiError = {
  message: "Failed to reach the backend.",
  code: "unknown_error",
};

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  const envelope: ApiEnvelope<T> = await response.json();

  if (envelope.error) {
    throw new Error(envelope.error.message);
  }
  if (!response.ok || !envelope.data) {
    throw new Error(UNKNOWN_ERROR.message);
  }
  return envelope.data;
}

export async function getHealth(): Promise<HealthStatus> {
  return requestJson<HealthStatus>("/health");
}

export async function getRestaurants(): Promise<Restaurant[]> {
  const data = await requestJson<{ restaurants: Restaurant[] }>("/restaurants");
  return data.restaurants;
}

export async function getDashboard(
  restaurantIds: string[],
): Promise<DashboardData> {
  const params = restaurantIds
    .map((id) => `restaurant_ids=${encodeURIComponent(id)}`)
    .join("&");
  return requestJson<DashboardData>(`/dashboard?${params}`);
}

export async function generateCampaign(
  restaurantId: string,
  brief: string,
): Promise<CampaignResult> {
  return requestJson<CampaignResult>("/campaigns", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ restaurant_id: restaurantId, brief }),
  });
}

type StreamChatHandlers = {
  onChunk: (text: string) => void;
  onDone: (event: ChatDoneEvent) => void;
  onError: (error: ApiError) => void;
};

/**
 * POST /chat is a Server-Sent-Events stream, not a single JSON response
 * (see docs/decisions/011-sse-streaming-and-mid-stream-errors.md) — the
 * browser's EventSource API can't send a POST body, so this parses
 * `data: {...}\n\n` frames off a manual fetch()+ReadableStream reader
 * instead. A pre-stream failure (restaurant not found, agent unavailable
 * before anything was sent) arrives as a plain JSON envelope; everything
 * else arrives as SSE frames, including a mid-stream failure's final
 * `error` event.
 */
export async function streamChat(
  restaurantIds: string[],
  question: string,
  handlers: StreamChatHandlers,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ restaurant_ids: restaurantIds, question }),
  });

  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.startsWith("application/json")) {
    const envelope: ApiEnvelope<unknown> = await response.json();
    handlers.onError(envelope.error ?? UNKNOWN_ERROR);
    return;
  }

  if (!response.body) {
    handlers.onError(UNKNOWN_ERROR);
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let reachedTerminalEvent = false;

  const handleFrame = (frame: string) => {
    const trimmed = frame.trim();
    if (!trimmed.startsWith("data: ")) return;
    const payload = JSON.parse(trimmed.slice("data: ".length));

    if (payload.type === "text_chunk") {
      handlers.onChunk(payload.text);
    } else if (payload.type === "done") {
      reachedTerminalEvent = true;
      handlers.onDone({
        answer: payload.answer,
        tool_calls: payload.tool_calls,
        model: payload.model,
      });
    } else if (payload.type === "error") {
      reachedTerminalEvent = true;
      handlers.onError({ message: payload.message, code: payload.code });
    }
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    let frameEnd = buffer.indexOf("\n\n");
    while (frameEnd !== -1) {
      handleFrame(buffer.slice(0, frameEnd));
      buffer = buffer.slice(frameEnd + 2);
      frameEnd = buffer.indexOf("\n\n");
    }
  }

  if (!reachedTerminalEvent) {
    // The connection closed without a `done` or `error` frame — a backend
    // bug outside the two documented failure modes (see
    // docs/decisions/011), or the connection simply dropped. Either way
    // the caller must not be left waiting forever.
    handlers.onError(UNKNOWN_ERROR);
  }
}
