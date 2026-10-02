// Mirrors the FastAPI response schemas in backend/app/schemas/.

export type Decision = "PASS" | "REVIEW" | "BLOCK";

export type ConflictKind =
  | "VIOLATION"
  | "MISSING_DATA"
  | "INVALID_PREFERENCE"
  | "UNSUPPORTED_ATTRIBUTE";

export type PreferenceType = "DEAL_BREAKER" | "HARD" | "SOFT";

export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

export interface ClientSummary {
  id: string;
  name: string;
}

export interface Preference {
  attribute: string;
  value: JsonValue;
  preference_type: PreferenceType;
}

export interface ClientDetail extends ClientSummary {
  preferences: Preference[];
}

export interface Profile {
  id: string;
  name: string;
  age: number | null;
  location: string | null;
  smoking: boolean | null;
  drinking: boolean | null;
  wants_children: boolean | null;
  religion: string | null;
  education: string | null;
  occupation: string | null;
}

export interface Conflict {
  kind: ConflictKind;
  attribute: string;
  candidate_value: JsonValue;
  expected_value: JsonValue;
  preference_type: PreferenceType;
  reason: string;
}

export interface MatchResult {
  decision: Decision;
  conflicts: Conflict[];
}

// Rejection feedback analysis (backend/app/schemas/feedback.py). These describe what the
// client said; they are never match decisions.

export type FeedbackAttribute =
  | "age"
  | "location"
  | "smoking"
  | "drinking"
  | "wants_children"
  | "religion"
  | "education"
  | "occupation"
  | "other";

export type FeedbackPreferenceType = PreferenceType | "UNCLEAR";

export type FeedbackKind = "VIOLATION" | "PREFERENCE" | "UNCLEAR";

export interface FeedbackReason {
  attribute: FeedbackAttribute;
  value: JsonValue;
  preference_type: FeedbackPreferenceType;
  kind: FeedbackKind;
  explanation: string;
}

export interface StructuredFeedback {
  reasons: FeedbackReason[];
  needs_review: boolean;
}

export interface FeedbackAnalysis {
  id: string;
  client_id: string;
  profile_id: string;
  raw_feedback: string;
  structured_feedback: StructuredFeedback;
}

// Analytics (backend/app/schemas/analytics.py).

export interface DecisionCounts {
  pass: number;
  review: number;
  block: number;
}

/** Share of all checks per decision, from 0 to 1. */
export type DecisionRates = DecisionCounts;

export interface ConflictCounts {
  violations: number;
  deal_breaker_violations: number;
  missing_data: number;
  unsupported_attributes: number;
  invalid_preferences: number;
}

/** Monthly figures supplied by the assessment brief. Not measured by MatchGuard. */
export interface AssessmentBaseline {
  profiles_shared: number;
  profiles_accepted: number;
  contact_details_shared: number;
  conversations_started: number;
  meetings_fixed: number;
  meetings_completed: number;
  rejected_profiles: number;
  preference_violation_rejection_rate: number;
  matchmaker_a_acceptance_rate: number;
  matchmaker_b_acceptance_rate: number;
  search_hours_per_client_per_week: number;
  /** Derived estimate (rejected × rate), not an observed result. */
  estimated_preference_violation_rejections: number;
}

export interface AnalyticsSummary {
  total_checks: number;
  decisions: DecisionCounts;
  decision_rates: DecisionRates;
  conflicts: ConflictCounts;
  assessment_baseline: AssessmentBaseline;
}
