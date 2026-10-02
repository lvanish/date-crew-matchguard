import { useEffect, useState } from "react";

import { getAnalyticsSummary } from "../services/api";
import type { AnalyticsSummary, AssessmentBaseline, Decision } from "../types/api";
import { formatCount, formatPercent } from "../utils/format";

const DECISIONS: { key: keyof AnalyticsSummary["decisions"]; label: Decision }[] = [
  { key: "pass", label: "PASS" },
  { key: "review", label: "REVIEW" },
  { key: "block", label: "BLOCK" },
];

export default function ImpactPanel() {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let current = true;
    getAnalyticsSummary()
      .then((data) => current && setSummary(data))
      .catch((err) => current && setError(err instanceof Error ? err.message : "Unexpected error."))
      .finally(() => current && setLoading(false));
    return () => {
      current = false;
    };
  }, []);

  return (
    <>
      <p className="page-header__subtitle">Leading indicators from pre-send checks</p>

      {loading && <p className="message">Loading analytics…</p>}
      {error && (
        <p className="message message--error" role="alert">
          Could not load analytics: {error}
        </p>
      )}

      {summary && (
        <>
          <BaselineSection baseline={summary.assessment_baseline} />
          <ActivitySection summary={summary} />
          <MeasurementSection baselineRate={summary.assessment_baseline.preference_violation_rejection_rate} />
        </>
      )}
    </>
  );
}

function Stat({ value, label, highlight = false }: { value: string; label: string; highlight?: boolean }) {
  return (
    <div className={highlight ? "stat stat--highlight" : "stat"}>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function BaselineSection({ baseline }: { baseline: AssessmentBaseline }) {
  const rate = formatPercent(baseline.preference_violation_rejection_rate);
  const estimate = `~${Math.round(baseline.estimated_preference_violation_rejections)}`;

  return (
    <section className="card" aria-labelledby="baseline-title">
      <div className="impact-section-header">
        <h3 id="baseline-title" className="section-title">
          Assessment baseline
        </h3>
        <span className="source-tag">Assessment-provided baseline</span>
      </div>

      <dl className="stat-grid">
        <Stat value={formatCount(baseline.profiles_shared)} label="Profiles shared" />
        <Stat value={formatCount(baseline.rejected_profiles)} label="Profiles rejected" />
        <Stat value={rate} label="Preference-violation rejection rate" />
        <Stat value={estimate} label="Estimated avoidable rejections" highlight />
      </dl>

      <p className="impact-note">{estimate} is a derived estimate, not an observed result.</p>
      <p className="muted">
        Assessment baseline: {rate} of rejected profiles were reported as preference-related.
        Estimated avoidable rejection events: {estimate}/month ({formatCount(baseline.rejected_profiles)}{" "}
        rejected × {rate}). MatchGuard is designed to catch these conflicts before a profile is shared.
      </p>
    </section>
  );
}

function ActivitySection({ summary }: { summary: AnalyticsSummary }) {
  const { conflicts } = summary;
  const unchecked = conflicts.unsupported_attributes + conflicts.invalid_preferences;

  return (
    <section className="card" aria-labelledby="activity-title">
      <div className="impact-section-header">
        <h3 id="activity-title" className="section-title">
          MatchGuard activity
        </h3>
        <span className="source-tag source-tag--demo">
          Demo activity — generated from 19 deterministic scenarios
        </span>
      </div>

      <dl className="stat-grid">
        <Stat value={formatCount(summary.total_checks)} label="Checks performed" />
      </dl>
      {summary.total_checks === 0 && <p className="muted">No match checks have been run yet.</p>}

      <ul className="bar-list" aria-label="Decisions">
        {DECISIONS.map(({ key, label }) => {
          const share = formatPercent(summary.decision_rates[key]);
          return (
            <li key={key} className={`bar bar--${key}`}>
              <div className="bar__label">
                <span className="bar__name">{label}</span>
                <span>
                  {formatCount(summary.decisions[key])} ({share})
                </span>
              </div>
              <div className="bar__track" aria-hidden="true">
                <div className="bar__fill" style={{ width: `${summary.decision_rates[key] * 100}%` }} />
              </div>
            </li>
          );
        })}
      </ul>

      <h4 className="panel-subtitle">Conflict types</h4>
      <dl className="stat-grid">
        <Stat value={formatCount(conflicts.violations)} label="Preference violations" />
        <Stat value={formatCount(conflicts.deal_breaker_violations)} label="Deal-breaker violations" />
        <Stat value={formatCount(conflicts.missing_data)} label="Missing candidate data" />
      </dl>
      {unchecked > 0 && (
        <p className="muted">
          {formatCount(unchecked)} preference conflicts could not be checked (unsupported attribute or
          invalid format).
        </p>
      )}

      <p className="muted">
        These are real MatchEngine checks saved in the database, created from the demo scenarios plus
        any checks run by hand in this environment. They show how the tool behaves, not The Date
        Crew&apos;s business results. Post-launch impact is not yet measured.
      </p>
    </section>
  );
}

function MeasurementSection({ baselineRate }: { baselineRate: number }) {
  return (
    <section className="card" aria-labelledby="measure-title">
      <h3 id="measure-title" className="section-title">
        How we would measure success
      </h3>

      <dl className="measure-list">
        <div>
          <dt>Primary metric</dt>
          <dd>Preference-violation rejection rate</dd>
        </div>
        <div>
          <dt>Definition</dt>
          <dd>
            Rejected profiles where the client rejection reason was already represented in an explicit
            client preference/deal-breaker.
          </dd>
        </div>
        <div>
          <dt>Target</dt>
          <dd>Reduce this rate materially after MatchGuard is introduced.</dd>
        </div>
      </dl>

      <div className="metric-compare">
        <p className="metric-compare__item">Baseline: {formatPercent(baselineRate)}</p>
        <p className="metric-compare__item metric-compare__item--pending">After launch: Not measured yet</p>
      </div>

      <p className="muted">
        To measure the business outcome, profile-check events should be linked to the eventual profile
        outcome (accepted/rejected) and rejection reason.
      </p>
    </section>
  );
}
