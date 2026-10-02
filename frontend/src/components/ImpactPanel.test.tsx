import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "../App";
import * as api from "../services/api";
import type { AnalyticsSummary } from "../types/api";

vi.mock("../services/api");

const summary: AnalyticsSummary = {
  total_checks: 19,
  decisions: { pass: 5, review: 6, block: 8 },
  decision_rates: { pass: 0.2632, review: 0.3158, block: 0.4211 },
  conflicts: {
    violations: 18,
    deal_breaker_violations: 8,
    missing_data: 3,
    unsupported_attributes: 0,
    invalid_preferences: 0,
  },
  assessment_baseline: {
    profiles_shared: 1000,
    profiles_accepted: 310,
    contact_details_shared: 210,
    conversations_started: 150,
    meetings_fixed: 75,
    meetings_completed: 42,
    rejected_profiles: 690,
    preference_violation_rejection_rate: 0.35,
    matchmaker_a_acceptance_rate: 0.44,
    matchmaker_b_acceptance_rate: 0.21,
    search_hours_per_client_per_week: 2,
    estimated_preference_violation_rejections: 241.5,
  },
};

/** The stat card whose label is `label`. */
function stat(label: string): HTMLElement {
  return screen.getByText(label, { selector: ".stat dt" }).closest(".stat") as HTMLElement;
}

function decisionRow(label: string): HTMLElement {
  return screen.getByText(label, { selector: ".bar__name" }).closest("li") as HTMLElement;
}

async function openImpactTab() {
  render(<App />);
  await screen.findByRole("option", { name: "Rahul" });
  fireEvent.click(screen.getByRole("tab", { name: "Impact" }));
}

describe("Impact mode", () => {
  beforeEach(() => {
    vi.mocked(api.getClients).mockResolvedValue([{ id: "client-1", name: "Rahul" }]);
    vi.mocked(api.getProfiles).mockResolvedValue([]);
    vi.mocked(api.getClient).mockResolvedValue({ id: "client-1", name: "Rahul", preferences: [] });
    vi.mocked(api.getAnalyticsSummary).mockResolvedValue(summary);
  });

  it("shows all three tabs and renders the Impact screen", async () => {
    await openImpactTab();

    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual([
      "Check Match",
      "Analyze Rejection",
      "Impact",
    ]);
    expect(screen.getByRole("heading", { name: "MatchGuard Impact" })).toBeTruthy();
    expect(screen.getByText("Leading indicators from pre-send checks")).toBeTruthy();
    expect(screen.queryByRole("combobox", { name: "Client" })).toBeNull();
    expect(await screen.findByText("Assessment-provided baseline")).toBeTruthy();
    expect(api.getAnalyticsSummary).toHaveBeenCalledTimes(1);
  });

  it("shows the assessment baseline numbers", async () => {
    await openImpactTab();
    await screen.findByText("Assessment-provided baseline");

    expect(within(stat("Profiles shared")).getByText("1,000")).toBeTruthy();
    expect(within(stat("Profiles rejected")).getByText("690")).toBeTruthy();
    expect(within(stat("Preference-violation rejection rate")).getByText("35%")).toBeTruthy();
  });

  it("labels ~242 as an estimated, derived figure", async () => {
    await openImpactTab();
    await screen.findByText("Assessment-provided baseline");

    expect(within(stat("Estimated avoidable rejections")).getByText("~242")).toBeTruthy();
    expect(screen.getByText("~242 is a derived estimate, not an observed result.")).toBeTruthy();
  });

  it("renders MatchGuard activity from the API", async () => {
    await openImpactTab();
    await screen.findByText("MatchGuard activity");

    expect(screen.getByText("Demo activity — generated from 19 deterministic scenarios")).toBeTruthy();
    expect(within(stat("Checks performed")).getByText("19")).toBeTruthy();
    expect(within(decisionRow("PASS")).getByText("5 (26.3%)")).toBeTruthy();
    expect(within(decisionRow("REVIEW")).getByText("6 (31.6%)")).toBeTruthy();
    expect(within(decisionRow("BLOCK")).getByText("8 (42.1%)")).toBeTruthy();
    expect(within(stat("Preference violations")).getByText("18")).toBeTruthy();
    expect(within(stat("Deal-breaker violations")).getByText("8")).toBeTruthy();
    expect(within(stat("Missing candidate data")).getByText("3")).toBeTruthy();
  });

  it("shows the success metric without inventing a post-launch value", async () => {
    await openImpactTab();
    const section = (await screen.findByText("How we would measure success")).closest("section")!;

    expect(within(section).getByText("Baseline: 35%")).toBeTruthy();
    expect(within(section).getByText("After launch: Not measured yet")).toBeTruthy();
    expect(within(section).getByText("Preference-violation rejection rate")).toBeTruthy();
  });

  it("shows an error when analytics cannot be loaded", async () => {
    vi.mocked(api.getAnalyticsSummary).mockRejectedValue(new Error("Backend is down"));
    await openImpactTab();

    expect(await screen.findByText("Could not load analytics: Backend is down")).toBeTruthy();
    expect(screen.queryByText("Baseline: 35%")).toBeNull();
  });

  it("keeps the client selection when returning to Check Match", async () => {
    render(<App />);
    await screen.findByRole("option", { name: "Rahul" });
    fireEvent.change(screen.getByRole("combobox", { name: "Client" }), { target: { value: "client-1" } });

    fireEvent.click(screen.getByRole("tab", { name: "Impact" }));
    await screen.findByText("Assessment-provided baseline");
    fireEvent.click(screen.getByRole("tab", { name: "Check Match" }));

    expect((screen.getByRole("combobox", { name: "Client" }) as HTMLSelectElement).value).toBe("client-1");
  });
});
