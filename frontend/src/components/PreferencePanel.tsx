import type { ClientDetail } from "../types/api";
import { attributeLabel, formatValue, preferenceTypeLabel } from "../utils/format";

interface Props {
  client: ClientDetail | null;
  loading: boolean;
  error: string | null;
  hasSelection: boolean;
}

export default function PreferencePanel({ client, loading, error, hasSelection }: Props) {
  return (
    <section className="card" aria-labelledby="preferences-heading" aria-busy={loading}>
      <h2 id="preferences-heading" className="section-title">
        Client preferences
      </h2>
      <PanelBody client={client} loading={loading} error={error} hasSelection={hasSelection} />
    </section>
  );
}

function PanelBody({ client, loading, error, hasSelection }: Props) {
  if (!hasSelection) {
    return <p className="message">Select a client to see their preferences.</p>;
  }
  if (loading) {
    return <p className="message">Loading preferences…</p>;
  }
  if (error) {
    return (
      <p className="message message--error" role="alert">
        Could not load preferences: {error}
      </p>
    );
  }
  if (!client) return null;

  if (client.preferences.length === 0) {
    return (
      <p className="message">
        {client.name} has no recorded preferences, so every candidate will pass.
      </p>
    );
  }

  return (
    <>
      <p className="panel-subtitle">{client.name}'s preferences</p>
      <dl className="preference-list">
        {client.preferences.map((preference) => (
          <div key={preference.attribute} className="preference">
            <dt>{attributeLabel(preference.attribute)}</dt>
            <dd>
              {formatValue(preference.attribute, preference.value)}
              <span className={`badge badge--${preference.preference_type.toLowerCase()}`}>
                {preferenceTypeLabel(preference.preference_type)}
              </span>
            </dd>
          </div>
        ))}
      </dl>
    </>
  );
}
