import { describe, expect, it } from "vitest";

import type { Profile } from "../types/api";
import {
  attributeLabel,
  formatCount,
  formatPercent,
  formatValue,
  profileLifestyle,
  profileOptionLabel,
} from "./format";

describe("number formatting", () => {
  it("formats counts and rates", () => {
    expect(formatCount(1000)).toBe("1,000");
    expect(formatPercent(0.35)).toBe("35%");
    expect(formatPercent(0.2632)).toBe("26.3%");
    expect(formatPercent(0)).toBe("0%");
  });
});

describe("formatValue", () => {
  it.each([
    ["age", { min: 28, max: 35 }, "28–35"],
    ["age", { min: 28 }, "28+"],
    ["age", { max: 35 }, "Up to 35"],
    ["age", 31, "31"],
    ["smoking", false, "Non-smoker"],
    ["smoking", true, "Smoker"],
    ["wants_children", true, "Wants children"],
    ["location", ["Delhi NCR", "Noida"], "Delhi NCR, Noida"],
    ["religion", "Hindu", "Hindu"],
    ["drinking", null, "Not provided"],
  ] as const)("formats %s %j as %s", (attribute, value, expected) => {
    expect(formatValue(attribute, value as never)).toBe(expected);
  });
});

describe("profile summaries", () => {
  const profile: Profile = {
    id: "p1",
    name: "Kavya",
    age: 27,
    location: "Delhi NCR",
    smoking: null,
    drinking: false,
    wants_children: true,
    religion: "Hindu",
    education: "MBBS",
    occupation: "Doctor",
  };

  it("builds a readable option label", () => {
    expect(profileOptionLabel(profile)).toBe("Kavya — 27 · Delhi NCR");
  });

  it("skips lifestyle facts the candidate did not provide", () => {
    expect(profileLifestyle(profile)).toEqual(["Non-drinker", "Wants children"]);
  });

  it("labels attributes, including unknown ones", () => {
    expect(attributeLabel("wants_children")).toBe("Children");
    expect(attributeLabel("star_sign")).toBe("Star sign");
  });
});
