import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import * as api from "./services/api";
import type { ClientDetail, MatchResult, Profile } from "./types/api";

vi.mock("./services/api");

const rahul: ClientDetail = {
  id: "client-1",
  name: "Rahul",
  preferences: [
    { attribute: "age", value: { min: 26, max: 32 }, preference_type: "HARD" },
    { attribute: "smoking", value: false, preference_type: "DEAL_BREAKER" },
  ],
};

const ishita: Profile = {
  id: "profile-1",
  name: "Ishita",
  age: 29,
  location: "Delhi NCR",
  smoking: true,
  drinking: false,
  wants_children: true,
  religion: "Hindu",
  education: "B.Com",
  occupation: "Chartered Accountant",
};

const blockResult: MatchResult = {
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

function checkButton(): HTMLButtonElement {
  return screen.getByRole("button", { name: /check match/i });
}

function clientSelect(): HTMLSelectElement {
  return screen.getByRole("combobox", { name: "Client" });
}

function candidateSelect(): HTMLSelectElement {
  return screen.getByRole("combobox", { name: "Candidate" });
}

describe("App", () => {
  beforeEach(() => {
    vi.mocked(api.getClients).mockResolvedValue([{ id: rahul.id, name: rahul.name }]);
    vi.mocked(api.getProfiles).mockResolvedValue([ishita]);
    vi.mocked(api.getClient).mockResolvedValue(rahul);
    vi.mocked(api.checkMatch).mockResolvedValue(blockResult);
  });

  it("renders the title and subtitle", async () => {
    render(<App />);

    expect(screen.getByRole("heading", { level: 1, name: "MatchGuard" })).toBeTruthy();
    expect(screen.getByText("Pre-send preference check for matchmakers")).toBeTruthy();
    await screen.findByRole("option", { name: "Rahul" });
  });

  it("keeps the check button disabled until both selections are made", async () => {
    render(<App />);
    await screen.findByRole("option", { name: "Rahul" });

    expect(checkButton().disabled).toBe(true);
    expect(screen.getByText("Select a client to run the check.")).toBeTruthy();

    fireEvent.change(clientSelect(), { target: { value: rahul.id } });
    expect(checkButton().disabled).toBe(true);
    expect(screen.getByText("Select a candidate to run the check.")).toBeTruthy();

    fireEvent.change(candidateSelect(), { target: { value: ishita.id } });
    expect(checkButton().disabled).toBe(false);
  });

  it("shows client preferences and candidate details from the API", async () => {
    render(<App />);
    await screen.findByRole("option", { name: "Rahul" });

    fireEvent.change(clientSelect(), { target: { value: rahul.id } });
    fireEvent.change(candidateSelect(), { target: { value: ishita.id } });

    expect(await screen.findByText("Rahul's preferences")).toBeTruthy();
    expect(screen.getByText("26–32")).toBeTruthy();
    expect(screen.getByText("Smoker · Non-drinker · Wants children")).toBeTruthy();
    expect(api.getClient).toHaveBeenCalledWith(rahul.id);
  });

  it("runs a check and shows the result", async () => {
    render(<App />);
    await screen.findByRole("option", { name: "Rahul" });
    fireEvent.change(clientSelect(), { target: { value: rahul.id } });
    fireEvent.change(candidateSelect(), { target: { value: ishita.id } });
    await screen.findByText("Rahul's preferences");

    fireEvent.click(checkButton());

    expect(await screen.findByRole("heading", { name: "BLOCK" })).toBeTruthy();
    expect(screen.getByText("Candidate conflicts with 1 deal-breaker.")).toBeTruthy();
    expect(api.checkMatch).toHaveBeenCalledWith(rahul.id, ishita.id);
  });

  it("shows an error when the API cannot be reached", async () => {
    vi.mocked(api.getClients).mockRejectedValue(new Error("Backend is down"));

    render(<App />);

    expect(await screen.findByText("Could not load clients: Backend is down")).toBeTruthy();
  });
});
