import type {
  AnalyticsSummary,
  ClientDetail,
  ClientSummary,
  FeedbackAnalysis,
  MatchResult,
  Profile,
} from "../types/api";

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"
).replace(/\/+$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch {
    throw new ApiError(
      `Could not reach the MatchGuard API at ${API_BASE_URL}. Is the backend running?`,
      0,
    );
  }

  if (!response.ok) {
    let message = `Request failed with status ${response.status}.`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") message = body.detail;
    } catch {
      // Non-JSON error body; keep the generic message.
    }
    throw new ApiError(message, response.status);
  }

  return (await response.json()) as T;
}

export function getClients(): Promise<ClientSummary[]> {
  return request("/api/clients");
}

export function getClient(id: string): Promise<ClientDetail> {
  return request(`/api/clients/${encodeURIComponent(id)}`);
}

export function getProfiles(): Promise<Profile[]> {
  return request("/api/profiles");
}

export function checkMatch(clientId: string, profileId: string): Promise<MatchResult> {
  return request("/api/matches/check", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ client_id: clientId, profile_id: profileId }),
  });
}

/** Feedback is analysed by the backend; the browser never talks to an AI provider. */
export function analyzeFeedback(
  clientId: string,
  profileId: string,
  rawFeedback: string,
): Promise<FeedbackAnalysis> {
  return request("/api/feedback/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ client_id: clientId, profile_id: profileId, raw_feedback: rawFeedback }),
  });
}

export function getAnalyticsSummary(): Promise<AnalyticsSummary> {
  return request("/api/analytics/summary");
}
