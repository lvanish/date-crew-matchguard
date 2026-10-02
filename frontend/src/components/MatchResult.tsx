import type { Conflict, MatchResult as MatchResultData, Preference } from "../types/api";
import { attributeLabel } from "../utils/format";
import ConflictList from "./ConflictList";

interface Props {
  result: MatchResultData;
  /** The client's preferences, used to list the ones that were checked without conflict. */
  preferences: Preference[];
}

export default function MatchResult({ result, preferences }: Props) {
  const conflictAttributes = new Set(result.conflicts.map((conflict) => conflict.attribute));
  const satisfied = preferences.filter((p) => !conflictAttributes.has(p.attribute));

  return (
    <section
      className={`card result result--${result.decision.toLowerCase()}`}
      aria-labelledby="result-heading"
      aria-live="polite"
    >
      <h2 id="result-heading" className="result__decision">
        {result.decision}
      </h2>
      <p className="result__summary">{summarize(result.decision, result.conflicts)}</p>

      <ConflictList conflicts={result.conflicts} />

      {satisfied.length > 0 && (
        <div className="conflict-group">
          <h3>{result.conflicts.length > 0 ? "Other checked preferences" : "Checked preferences"}</h3>
          <ul className="satisfied-list">
            {satisfied.map((preference) => (
              <li key={preference.attribute}>
                <span className="satisfied-list__icon" aria-hidden="true">
                  ✓
                </span>
                {attributeLabel(preference.attribute)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function plural(count: number, singular: string, pluralForm = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : pluralForm}`;
}

export function summarize(decision: MatchResultData["decision"], conflicts: Conflict[]): string {
  if (decision === "PASS") return "No known preference conflicts were found.";

  if (decision === "BLOCK") {
    const dealBreakers = conflicts.filter(
      (c) => c.kind === "VIOLATION" && c.preference_type === "DEAL_BREAKER",
    ).length;
    return `Candidate conflicts with ${plural(dealBreakers, "deal-breaker")}.`;
  }

  const violations = conflicts.filter((c) => c.kind === "VIOLATION").length;
  const missing = conflicts.filter((c) => c.kind === "MISSING_DATA").length;
  const unchecked = conflicts.length - violations - missing;
  const parts = [
    violations && plural(violations, "preference conflict"),
    missing && `${plural(missing, "missing candidate detail")}`,
    unchecked && `${plural(unchecked, "preference")} that could not be checked`,
  ].filter(Boolean);
  return `Needs matchmaker review: ${parts.join(", ")}.`;
}
