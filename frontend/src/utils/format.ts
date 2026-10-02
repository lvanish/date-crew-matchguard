import type { JsonValue, PreferenceType, Profile } from "../types/api";

const ATTRIBUTE_LABELS: Record<string, string> = {
  age: "Age",
  location: "Location",
  smoking: "Smoking",
  drinking: "Drinking",
  wants_children: "Children",
  religion: "Religion",
  education: "Education",
  occupation: "Occupation",
};

const BOOLEAN_LABELS: Record<string, { yes: string; no: string }> = {
  smoking: { yes: "Smoker", no: "Non-smoker" },
  drinking: { yes: "Drinks", no: "Non-drinker" },
  wants_children: { yes: "Wants children", no: "Doesn't want children" },
};

const PREFERENCE_TYPE_LABELS: Record<PreferenceType, string> = {
  DEAL_BREAKER: "Deal-breaker",
  HARD: "Hard",
  SOFT: "Soft",
};

export function attributeLabel(attribute: string): string {
  if (attribute in ATTRIBUTE_LABELS) return ATTRIBUTE_LABELS[attribute];
  const words = attribute.replace(/_/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function preferenceTypeLabel(type: PreferenceType): string {
  return PREFERENCE_TYPE_LABELS[type];
}

/** Human-readable form of a preference value or a candidate value for an attribute. */
export function formatValue(attribute: string, value: JsonValue): string {
  if (value === null) return "Not provided";

  if (typeof value === "boolean" && attribute in BOOLEAN_LABELS) {
    return value ? BOOLEAN_LABELS[attribute].yes : BOOLEAN_LABELS[attribute].no;
  }

  if (Array.isArray(value)) {
    return value.map((item) => formatValue(attribute, item)).join(", ");
  }

  if (typeof value === "object") {
    const { min, max } = value;
    const hasMin = typeof min === "number";
    const hasMax = typeof max === "number";
    if (hasMin && hasMax) return `${min}–${max}`;
    if (hasMin) return `${min}+`;
    if (hasMax) return `Up to ${max}`;
    return JSON.stringify(value);
  }

  return String(value);
}

export function formatCount(value: number): string {
  return value.toLocaleString("en-US");
}

/** 0.35 → "35%", 0.2632 → "26.3%". */
export function formatPercent(rate: number): string {
  return rate.toLocaleString("en-US", { style: "percent", maximumFractionDigits: 1 });
}

/** Short one-line summary for a candidate dropdown option. */
export function profileOptionLabel(profile: Profile): string {
  const details = [profile.age, profile.location].filter((part) => part !== null);
  return details.length ? `${profile.name} — ${details.join(" · ")}` : profile.name;
}

/** Lifestyle facts for a candidate, skipping anything the candidate did not provide. */
export function profileLifestyle(profile: Profile): string[] {
  return (["smoking", "drinking", "wants_children"] as const)
    .filter((field) => profile[field] !== null)
    .map((field) => formatValue(field, profile[field]));
}
