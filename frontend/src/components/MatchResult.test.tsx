import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { MatchResult as MatchResultData, Preference } from "../types/api";
import MatchResult from "./MatchResult";

const preferences: Preference[] = [
  { attribute: "age", value: { min: 28, max: 35 }, preference_type: "HARD" },
  { attribute: "location", value: ["Delhi NCR", "Noida"], preference_type: "SOFT" },
  { attribute: "smoking", value: false, preference_type: "DEAL_BREAKER" },
  { attribute: "wants_children", value: true, preference_type: "HARD" },
];

describe("MatchResult", () => {
  it("renders PASS with every preference checked", () => {
    render(<MatchResult result={{ decision: "PASS", conflicts: [] }} preferences={preferences} />);

    expect(screen.getByRole("heading", { name: "PASS" })).toBeTruthy();
    expect(screen.getByText("No known preference conflicts were found.")).toBeTruthy();
    const checked = within(screen.getByRole("list"));
    expect(checked.getAllByRole("listitem").map((li) => li.textContent)).toEqual([
      "✓Age",
      "✓Location",
      "✓Smoking",
      "✓Children",
    ]);
  });

  it("renders BLOCK with the deal-breaker explained and the rest checked", () => {
    const result: MatchResultData = {
      decision: "BLOCK",
      conflicts: [
        {
          kind: "VIOLATION",
          attribute: "smoking",
          candidate_value: true,
          expected_value: false,
          preference_type: "DEAL_BREAKER",
          reason: "Candidate smokes, while smoking is marked as a client deal-breaker.",
        },
      ],
    };

    render(<MatchResult result={result} preferences={preferences} />);

    expect(screen.getByRole("heading", { name: "BLOCK" })).toBeTruthy();
    expect(screen.getByText("Candidate conflicts with 1 deal-breaker.")).toBeTruthy();
    expect(screen.getByText("Preference conflicts")).toBeTruthy();
    expect(screen.getByText("Non-smoker")).toBeTruthy();
    expect(screen.getByText("Smoker")).toBeTruthy();
    expect(screen.getByText("Deal-breaker")).toBeTruthy();
    expect(screen.getByText(result.conflicts[0].reason)).toBeTruthy();
    expect(screen.getByText("Other checked preferences")).toBeTruthy();
    expect(screen.queryByText("Missing candidate information")).toBeNull();
  });

  it("separates violations, missing data and unchecked preferences for REVIEW", () => {
    const result: MatchResultData = {
      decision: "REVIEW",
      conflicts: [
        {
          kind: "MISSING_DATA",
          attribute: "smoking",
          candidate_value: null,
          expected_value: false,
          preference_type: "DEAL_BREAKER",
          reason: "Candidate smoking information is missing, so the deal-breaker cannot be verified.",
        },
        {
          kind: "VIOLATION",
          attribute: "location",
          candidate_value: "Mumbai",
          expected_value: ["Delhi NCR", "Noida"],
          preference_type: "SOFT",
          reason: "Candidate location Mumbai is not one of the client's preferred locations: Delhi NCR, Noida.",
        },
        {
          kind: "UNSUPPORTED_ATTRIBUTE",
          attribute: "height",
          candidate_value: null,
          expected_value: { min: 170 },
          preference_type: "SOFT",
          reason: "Unsupported preference attribute: height",
        },
      ],
    };

    render(<MatchResult result={result} preferences={preferences} />);

    expect(screen.getByRole("heading", { name: "REVIEW" })).toBeTruthy();
    expect(
      screen.getByText(
        "Needs matchmaker review: 1 preference conflict, 1 missing candidate detail, 1 preference that could not be checked.",
      ),
    ).toBeTruthy();
    expect(screen.getByText("Preference conflicts")).toBeTruthy();
    expect(screen.getByText("Missing candidate information")).toBeTruthy();
    expect(screen.getByText("Preferences that could not be checked")).toBeTruthy();
    expect(screen.getByText("MISSING_DATA")).toBeTruthy();
    expect(screen.getByText("Not provided")).toBeTruthy();
    expect(screen.getByText(result.conflicts[0].reason)).toBeTruthy();
  });
});
