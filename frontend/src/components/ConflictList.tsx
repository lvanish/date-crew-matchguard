import type { Conflict, ConflictKind, PreferenceType } from "../types/api";
import { attributeLabel, formatValue, preferenceTypeLabel } from "../utils/format";

const GROUPS: { title: string; kinds: ConflictKind[]; icon: string; tone: string }[] = [
  { title: "Preference conflicts", kinds: ["VIOLATION"], icon: "✗", tone: "violation" },
  { title: "Missing candidate information", kinds: ["MISSING_DATA"], icon: "?", tone: "missing" },
  {
    title: "Preferences that could not be checked",
    kinds: ["INVALID_PREFERENCE", "UNSUPPORTED_ATTRIBUTE"],
    icon: "!",
    tone: "invalid",
  },
];

const TYPE_ORDER: Record<PreferenceType, number> = { DEAL_BREAKER: 0, HARD: 1, SOFT: 2 };

export default function ConflictList({ conflicts }: { conflicts: Conflict[] }) {
  return (
    <>
      {GROUPS.map((group) => {
        const items = conflicts
          .filter((conflict) => group.kinds.includes(conflict.kind))
          .sort((a, b) => TYPE_ORDER[a.preference_type] - TYPE_ORDER[b.preference_type]);
        if (items.length === 0) return null;

        return (
          <div key={group.tone} className="conflict-group">
            <h3>{group.title}</h3>
            <ul className="conflict-list">
              {items.map((conflict, index) => (
                <ConflictItem
                  key={`${conflict.attribute}-${index}`}
                  conflict={conflict}
                  icon={group.icon}
                  tone={group.tone}
                />
              ))}
            </ul>
          </div>
        );
      })}
    </>
  );
}

function ConflictItem({ conflict, icon, tone }: { conflict: Conflict; icon: string; tone: string }) {
  const comparable = conflict.kind === "VIOLATION" || conflict.kind === "MISSING_DATA";

  return (
    <li className={`conflict conflict--${tone}`}>
      <p className="conflict__title">
        <span className="conflict__icon" aria-hidden="true">
          {icon}
        </span>
        {attributeLabel(conflict.attribute)}
        <code className="conflict__kind">{conflict.kind}</code>
      </p>
      <dl className="conflict__details">
        <div>
          <dt>Client preference:</dt>
          <dd>
            {comparable
              ? formatValue(conflict.attribute, conflict.expected_value)
              : JSON.stringify(conflict.expected_value)}
          </dd>
        </div>
        {comparable && (
          <div>
            <dt>Candidate:</dt>
            <dd>{formatValue(conflict.attribute, conflict.candidate_value)}</dd>
          </div>
        )}
        <div>
          <dt>Type:</dt>
          <dd>{preferenceTypeLabel(conflict.preference_type)}</dd>
        </div>
      </dl>
      <p className="conflict__reason">{conflict.reason}</p>
    </li>
  );
}
