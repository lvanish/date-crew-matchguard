import type { Profile } from "../types/api";
import { profileLifestyle, profileOptionLabel } from "../utils/format";

interface Props {
  profiles: Profile[];
  loading: boolean;
  error: string | null;
  selectedId: string;
  disabled?: boolean;
  onChange: (profileId: string) => void;
}

export default function ProfileSelector({
  profiles,
  loading,
  error,
  selectedId,
  disabled = false,
  onChange,
}: Props) {
  const selected = profiles.find((profile) => profile.id === selectedId);

  return (
    <section className="card" aria-labelledby="candidate-heading">
      <h2 id="candidate-heading" className="section-title">
        <label htmlFor="candidate-select">Candidate</label>
      </h2>

      {error ? (
        <p className="message message--error" role="alert">
          Could not load candidates: {error}
        </p>
      ) : (
        <select
          id="candidate-select"
          value={selectedId}
          disabled={loading || disabled || profiles.length === 0}
          onChange={(event) => onChange(event.target.value)}
        >
          <option value="">{loading ? "Loading candidates…" : "Select candidate"}</option>
          {profiles.map((profile) => (
            <option key={profile.id} value={profile.id}>
              {profileOptionLabel(profile)}
            </option>
          ))}
        </select>
      )}

      {!loading && !error && profiles.length === 0 && (
        <p className="message">
          No candidate profiles found. Load the demo data with <code>python seed.py</code>.
        </p>
      )}

      {selected && <ProfileCard profile={selected} />}
    </section>
  );
}

function ProfileCard({ profile }: { profile: Profile }) {
  const basics = [profile.age, profile.location ?? "Location not provided"].filter(
    (part) => part !== null,
  );
  const lifestyle = profileLifestyle(profile);
  const background = [profile.religion, profile.education, profile.occupation].filter(Boolean);

  return (
    <div className="profile-card" data-testid="profile-card">
      <p className="profile-card__name">{profile.name}</p>
      <p>{basics.join(" · ")}</p>
      {lifestyle.length > 0 && <p>{lifestyle.join(" · ")}</p>}
      {background.length > 0 && <p className="muted">{background.join(" · ")}</p>}
    </div>
  );
}
