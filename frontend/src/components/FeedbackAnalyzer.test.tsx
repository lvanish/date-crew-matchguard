import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "../App";
import * as api from "../services/api";
import type { FeedbackAnalysis, Profile } from "../types/api";

vi.mock("../services/api");

const client = { id: "client-1", name: "Rahul" };

const profile: Profile = {
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

const FEEDBACK = "Great profile, but I don't want someone who smokes and I can't move to Bangalore.";

const twoReasons: FeedbackAnalysis = {
  id: "feedback-1",
  client_id: client.id,
  profile_id: profile.id,
  raw_feedback: FEEDBACK,
  structured_feedback: {
    reasons: [
      {
        attribute: "smoking",
        value: true,
        preference_type: "DEAL_BREAKER",
        kind: "VIOLATION",
        explanation: "Client explicitly says smoking is not acceptable.",
      },
      {
        attribute: "location",
        value: "Bangalore",
        preference_type: "SOFT",
        kind: "PREFERENCE",
        explanation: "Client indicates they may not be willing to relocate to Bangalore.",
      },
    ],
    needs_review: false,
  },
};

const ambiguous: FeedbackAnalysis = {
  ...twoReasons,
  raw_feedback: "Maybe smoking could be an issue.",
  structured_feedback: {
    reasons: [
      {
        attribute: "smoking",
        value: true,
        preference_type: "UNCLEAR",
        kind: "UNCLEAR",
        explanation: "Feedback is tentative about smoking; confirm with the client.",
      },
    ],
    needs_review: true,
  },
};

function analyzeButton(): HTMLButtonElement {
  return screen.getByRole("button", { name: /analyze feedback/i });
}

async function openFeedbackTab() {
  render(<App />);
  await screen.findByRole("option", { name: "Rahul" });
  fireEvent.click(screen.getByRole("tab", { name: "Analyze Rejection" }));
}

function selectBoth() {
  fireEvent.change(screen.getByRole("combobox", { name: "Client" }), { target: { value: client.id } });
  fireEvent.change(screen.getByRole("combobox", { name: "Candidate" }), {
    target: { value: profile.id },
  });
}

function typeFeedback(text: string) {
  fireEvent.change(screen.getByLabelText("Rejection feedback"), { target: { value: text } });
}

describe("Analyze Rejection mode", () => {
  beforeEach(() => {
    vi.mocked(api.getClients).mockResolvedValue([client]);
    vi.mocked(api.getProfiles).mockResolvedValue([profile]);
    vi.mocked(api.getClient).mockResolvedValue({ ...client, preferences: [] });
    vi.mocked(api.analyzeFeedback).mockResolvedValue(twoReasons);
  });

  it("renders both tabs and switches to the feedback screen", async () => {
    await openFeedbackTab();

    expect(screen.getByRole("tab", { name: "Check Match" }).getAttribute("aria-selected")).toBe("false");
    expect(screen.getByRole("tab", { name: "Analyze Rejection" }).getAttribute("aria-selected")).toBe("true");
    expect(screen.getByRole("heading", { name: "Analyze Rejection Feedback" })).toBeTruthy();
    expect(screen.getByLabelText("Rejection feedback")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /check match/i })).toBeNull();
  });

  it("keeps the analyze button disabled until client, candidate and feedback are set", async () => {
    await openFeedbackTab();

    expect(analyzeButton().disabled).toBe(true);
    fireEvent.change(screen.getByRole("combobox", { name: "Client" }), { target: { value: client.id } });
    expect(analyzeButton().disabled).toBe(true);
    fireEvent.change(screen.getByRole("combobox", { name: "Candidate" }), {
      target: { value: profile.id },
    });
    expect(analyzeButton().disabled).toBe(true);
    expect(screen.getByText("Enter the client's feedback to analyze the feedback.")).toBeTruthy();

    typeFeedback("   ");
    expect(analyzeButton().disabled).toBe(true);
    typeFeedback(FEEDBACK);
    expect(analyzeButton().disabled).toBe(false);
  });

  it("sends the feedback to the backend and shows the saved analysis", async () => {
    await openFeedbackTab();
    selectBoth();
    typeFeedback(`  ${FEEDBACK}  `);

    fireEvent.click(analyzeButton());

    expect(await screen.findByRole("heading", { name: "Structured reasons" })).toBeTruthy();
    expect(api.analyzeFeedback).toHaveBeenCalledWith(client.id, profile.id, FEEDBACK);
    expect(screen.getByText("Raw feedback")).toBeTruthy();
    expect(screen.getAllByText(FEEDBACK).some((el) => el.tagName === "BLOCKQUOTE")).toBe(true);
    expect(screen.queryByText("Needs review")).toBeNull();
  });

  it("renders every structured reason", async () => {
    await openFeedbackTab();
    selectBoth();
    typeFeedback(FEEDBACK);
    fireEvent.click(analyzeButton());

    await screen.findByRole("heading", { name: "Structured reasons" });
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(within(items[0]).getByText("Smoking")).toBeTruthy();
    expect(within(items[0]).getByText("Deal-breaker · Violation")).toBeTruthy();
    expect(within(items[0]).getByText("“Client explicitly says smoking is not acceptable.”")).toBeTruthy();
    expect(within(items[1]).getByText("Location")).toBeTruthy();
    expect(within(items[1]).getByText("Soft preference · Preference")).toBeTruthy();
    expect(within(items[1]).getByText("Mentioned: Bangalore")).toBeTruthy();
  });

  it("shows the needs-review warning for ambiguous feedback", async () => {
    vi.mocked(api.analyzeFeedback).mockResolvedValue(ambiguous);
    await openFeedbackTab();
    selectBoth();
    typeFeedback("Maybe smoking could be an issue.");
    fireEvent.click(analyzeButton());

    const banner = await screen.findByRole("status");
    expect(within(banner).getByText("Needs review")).toBeTruthy();
    expect(
      within(banner).getByText("Some feedback was ambiguous and should be confirmed by the matchmaker."),
    ).toBeTruthy();
    expect(screen.getByText("Unclear · Unclear")).toBeTruthy();
  });

  it("shows an error when the API call fails", async () => {
    vi.mocked(api.analyzeFeedback).mockRejectedValue(
      new Error("AI feedback analysis is not configured: OPENAI_API_KEY is not set."),
    );
    await openFeedbackTab();
    selectBoth();
    typeFeedback(FEEDBACK);
    fireEvent.click(analyzeButton());

    expect(
      await screen.findByText(
        "Feedback analysis failed: AI feedback analysis is not configured: OPENAI_API_KEY is not set.",
      ),
    ).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Structured reasons" })).toBeNull();
    expect(analyzeButton().disabled).toBe(false);
  });

  it("keeps typed feedback when switching tabs", async () => {
    await openFeedbackTab();
    typeFeedback(FEEDBACK);

    fireEvent.click(screen.getByRole("tab", { name: "Check Match" }));
    fireEvent.click(screen.getByRole("tab", { name: "Analyze Rejection" }));

    expect((screen.getByLabelText("Rejection feedback") as HTMLTextAreaElement).value).toBe(FEEDBACK);
  });
});
