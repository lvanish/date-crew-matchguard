import { useEffect, useState } from "react";

import ClientSelector from "./components/ClientSelector";
import FeedbackAnalyzer from "./components/FeedbackAnalyzer";
import ImpactPanel from "./components/ImpactPanel";
import MatchResult from "./components/MatchResult";
import PreferencePanel from "./components/PreferencePanel";
import ProfileSelector from "./components/ProfileSelector";
import { checkMatch, getClient, getClients, getProfiles } from "./services/api";
import type {
  ClientDetail,
  ClientSummary,
  MatchResult as MatchResultData,
  Profile,
} from "./types/api";

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unexpected error.";
}

type Mode = "match" | "feedback" | "impact";

const MODES: { id: Mode; label: string; heading: string }[] = [
  { id: "match", label: "Check Match", heading: "Check Match" },
  { id: "feedback", label: "Analyze Rejection", heading: "Analyze Rejection Feedback" },
  { id: "impact", label: "Impact", heading: "MatchGuard Impact" },
];

export default function App() {
  const [mode, setMode] = useState<Mode>("match");
  const [analyzing, setAnalyzing] = useState(false);

  const [clients, setClients] = useState<ClientSummary[]>([]);
  const [clientsLoading, setClientsLoading] = useState(true);
  const [clientsError, setClientsError] = useState<string | null>(null);

  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [profilesLoading, setProfilesLoading] = useState(true);
  const [profilesError, setProfilesError] = useState<string | null>(null);

  const [clientId, setClientId] = useState("");
  const [profileId, setProfileId] = useState("");

  const [clientDetail, setClientDetail] = useState<ClientDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const [checking, setChecking] = useState(false);
  const [checkError, setCheckError] = useState<string | null>(null);
  const [result, setResult] = useState<MatchResultData | null>(null);

  useEffect(() => {
    getClients()
      .then(setClients)
      .catch((error) => setClientsError(errorMessage(error)))
      .finally(() => setClientsLoading(false));
    getProfiles()
      .then(setProfiles)
      .catch((error) => setProfilesError(errorMessage(error)))
      .finally(() => setProfilesLoading(false));
  }, []);

  useEffect(() => {
    setClientDetail(null);
    setDetailError(null);
    setDetailLoading(false);
    if (!clientId) return;

    // Ignore a response that arrives after the user has picked another client.
    let current = true;
    setDetailLoading(true);
    getClient(clientId)
      .then((detail) => current && setClientDetail(detail))
      .catch((error) => current && setDetailError(errorMessage(error)))
      .finally(() => current && setDetailLoading(false));
    return () => {
      current = false;
    };
  }, [clientId]);

  function selectClient(id: string) {
    setClientId(id);
    setResult(null);
    setCheckError(null);
  }

  function selectProfile(id: string) {
    setProfileId(id);
    setResult(null);
    setCheckError(null);
  }

  async function runCheck() {
    setChecking(true);
    setCheckError(null);
    setResult(null);
    try {
      setResult(await checkMatch(clientId, profileId));
    } catch (error) {
      setCheckError(errorMessage(error));
    } finally {
      setChecking(false);
    }
  }

  const missingSelection = !clientId ? "client" : !profileId ? "candidate" : null;
  const busy = checking || analyzing;
  const activeMode = MODES.find((m) => m.id === mode)!;

  return (
    <main className="page">
      <header className="page-header">
        <h1>MatchGuard</h1>
        <p className="page-header__subtitle">Pre-send preference check for matchmakers</p>
        <p className="muted">Check a candidate before sharing their profile.</p>
      </header>

      <div className="tabs" role="tablist" aria-label="Mode">
        {MODES.map((m) => (
          <button
            key={m.id}
            type="button"
            role="tab"
            id={`tab-${m.id}`}
            aria-selected={mode === m.id}
            aria-controls="mode-panel"
            className="tab"
            disabled={busy}
            onClick={() => setMode(m.id)}
          >
            {m.label}
          </button>
        ))}
      </div>

      <div id="mode-panel" role="tabpanel" aria-labelledby={`tab-${mode}`} className="mode-panel">
        <h2 className="mode-heading">{activeMode.heading}</h2>

        {mode !== "impact" && (
          <ClientSelector
            clients={clients}
            loading={clientsLoading}
            error={clientsError}
            selectedId={clientId}
            disabled={busy}
            onChange={selectClient}
          />
        )}

        {mode === "match" && (
          <PreferencePanel
            client={clientDetail}
            loading={detailLoading}
            error={detailError}
            hasSelection={Boolean(clientId)}
          />
        )}

        {mode !== "impact" && (
          <ProfileSelector
            profiles={profiles}
            loading={profilesLoading}
            error={profilesError}
            selectedId={profileId}
            disabled={busy}
            onChange={selectProfile}
          />
        )}

        <div hidden={mode !== "feedback"} className="mode-panel">
          <FeedbackAnalyzer clientId={clientId} profileId={profileId} onBusyChange={setAnalyzing} />
        </div>

        {mode === "match" && (
          <MatchCheckActions
            missingSelection={missingSelection}
            checking={checking}
            checkError={checkError}
            onCheck={runCheck}
          />
        )}

        {mode === "match" && result && (
          <MatchResult result={result} preferences={clientDetail?.preferences ?? []} />
        )}

        {mode === "impact" && <ImpactPanel />}
      </div>
    </main>
  );
}

function MatchCheckActions({
  missingSelection,
  checking,
  checkError,
  onCheck,
}: {
  missingSelection: string | null;
  checking: boolean;
  checkError: string | null;
  onCheck: () => void;
}) {
  return (
    <>
      <div className="actions">
        <button
          type="button"
          className="check-button"
          disabled={missingSelection !== null || checking}
          onClick={onCheck}
        >
          {checking ? "Checking…" : "Check match"}
        </button>
        {missingSelection && !checking && (
          <p className="muted">Select a {missingSelection} to run the check.</p>
        )}
      </div>

      {checkError && (
        <p className="message message--error" role="alert">
          Match check failed: {checkError}
        </p>
      )}
    </>
  );
}
