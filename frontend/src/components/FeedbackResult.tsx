import type { FeedbackAnalysis, FeedbackKind, FeedbackPreferenceType } from "../types/api";
import { attributeLabel, formatValue } from "../utils/format";

const STRENGTH_LABELS: Record<FeedbackPreferenceType, string> = {
  DEAL_BREAKER: "Deal-breaker",
  HARD: "Hard preference",
  SOFT: "Soft preference",
  UNCLEAR: "Unclear",
};

const KIND_LABELS: Record<FeedbackKind, string> = {
  VIOLATION: "Violation",
  PREFERENCE: "Preference",
  UNCLEAR: "Unclear",
};

export default function FeedbackResult({ analysis }: { analysis: FeedbackAnalysis }) {
  const { reasons, needs_review: needsReview } = analysis.structured_feedback;

  return (
    <section className="card" aria-labelledby="feedback-result-heading" aria-live="polite">
      <h2 id="feedback-result-heading" className="section-title">
        Structured reasons
      </h2>

      {needsReview && (
        <div className="review-banner" role="status">
          <p className="review-banner__title">
            <span aria-hidden="true">⚠</span> Needs review
          </p>
          <p>Some feedback was ambiguous and should be confirmed by the matchmaker.</p>
        </div>
      )}

      <ul className="reason-list">
        {reasons.map((reason, index) => (
          <li key={`${reason.attribute}-${index}`} className={`reason reason--${reason.kind.toLowerCase()}`}>
            <p className="reason__title">{attributeLabel(reason.attribute)}</p>
            <p className="reason__meta">
              {STRENGTH_LABELS[reason.preference_type]} · {KIND_LABELS[reason.kind]}
            </p>
            {reason.value !== null && (
              <p className="muted">Mentioned: {formatValue(reason.attribute, reason.value)}</p>
            )}
            <p className="reason__explanation">“{reason.explanation}”</p>
          </li>
        ))}
      </ul>

      <div className="conflict-group">
        <h3>Raw feedback</h3>
        <blockquote className="raw-feedback">{analysis.raw_feedback}</blockquote>
      </div>

      <p className="muted">
        Saved to the client's rejection history. These reasons describe what the client said;
        they do not change match decisions.
      </p>
    </section>
  );
}
