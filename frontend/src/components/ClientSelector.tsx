import type { ClientSummary } from "../types/api";

interface Props {
  clients: ClientSummary[];
  loading: boolean;
  error: string | null;
  selectedId: string;
  disabled?: boolean;
  onChange: (clientId: string) => void;
}

export default function ClientSelector({
  clients,
  loading,
  error,
  selectedId,
  disabled = false,
  onChange,
}: Props) {
  return (
    <section className="card" aria-labelledby="client-heading">
      <h2 id="client-heading" className="section-title">
        <label htmlFor="client-select">Client</label>
      </h2>

      {error ? (
        <p className="message message--error" role="alert">
          Could not load clients: {error}
        </p>
      ) : (
        <select
          id="client-select"
          value={selectedId}
          disabled={loading || disabled || clients.length === 0}
          onChange={(event) => onChange(event.target.value)}
        >
          <option value="">{loading ? "Loading clients…" : "Select client"}</option>
          {clients.map((client) => (
            <option key={client.id} value={client.id}>
              {client.name}
            </option>
          ))}
        </select>
      )}

      {!loading && !error && clients.length === 0 && (
        <p className="message">
          No clients found. Load the demo data with <code>python seed.py</code>.
        </p>
      )}
    </section>
  );
}
