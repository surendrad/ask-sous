type ApiEnvelope<T> = {
  data: T | null;
  error: { message: string; code: string } | null;
};

type HealthStatus = {
  status: string;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export async function getHealth(): Promise<HealthStatus> {
  const response = await fetch(`${API_BASE_URL}/health`);
  const envelope: ApiEnvelope<HealthStatus> = await response.json();

  if (envelope.error) {
    throw new Error(envelope.error.message);
  }

  if (!response.ok || !envelope.data) {
    throw new Error("Failed to reach the backend.");
  }

  return envelope.data;
}
