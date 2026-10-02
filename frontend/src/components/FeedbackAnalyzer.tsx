import { useEffect, useState } from "react";

import { analyzeFeedback } from "../services/api";
import type { FeedbackAnalysis } from "../types/api";
import FeedbackResult from "./FeedbackResult";

const MAX_FEEDBACK_LENGTH = 5000;

interface Props {
  clientId: string;
  profileId: string;
  onBusyChange: (busy: boolean) => void;
}

export default function FeedbackAnalyzer({ clientId, profileId, onBusyChange }: Props) {
  const [feedback, setFeedback] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<FeedbackAnalysis | null>(null);

  useEffect(() => {
    setAnalysis(null);
    setError(null);
  }, [clientId, profileId]);

  const missing = !clientId
    ? "Select a client"
    : !profileId
      ? "Select a candidate"
      : !feedback.trim()
        ? "Enter the client's feedback"
        : null;

  async function analyze() {
    setAnalyzing(true);
    onBusyChange(true);
    setError(null);
    setAnalysis(null);
    try {
      setAnalysis(await analyzeFeedback(clientId, profileId, feedback.trim()));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unexpected error.");
    } finally {
      setAnalyzing(false);
      onBusyChange(false);
    }
  }

  return (
    <>
      <section className="card">
        <label htmlFor="feedback-input" className="section-title">
          Rejection feedback
        </label>
        <textarea
          id="feedback-input"
          rows={4}
          maxLength={MAX_FEEDBACK_LENGTH}
          value={feedback}
          disabled={analyzing}
          placeholder="Paste what the client said about this candidate."
          onChange={(event) => {
            setFeedback(event.target.value);
            setAnalysis(null);
          }}
        />
      </section>

      <div className="actions">
        <button
          type="button"
          className="check-button"
          disabled={missing !== null || analyzing}
          onClick={analyze}
        >
          {analyzing ? "Analyzing…" : "Analyze feedback"}
        </button>
        {missing && !analyzing && <p className="muted">{missing} to analyze the feedback.</p>}
      </div>

      {error && (
        <p className="message message--error" role="alert">
          Feedback analysis failed: {error}
        </p>
      )}

      {analysis && <FeedbackResult analysis={analysis} />}
    </>
  );
}
