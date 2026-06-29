"use client";

import { useEffect, useState } from "react";
import { Card } from "./ui";

// Main sequence runs once, then we settle into the reassurance tail and cycle
// only within it — so a long/slow request never visibly "restarts" from the top.
const STAGES = [
  "Browsing the web",
  "Fetching results",
  "Opening pages",
  "Scraping content",
  "Waking the server",
  "Parsing articles",
  "Stripping the boilerplate",
  "Extracting the good stuff",
  "Compiling results",
];
const TAIL = [
  "Still working",
  "Hang tight, almost there",
  "Wrangling a few slow pages",
  "Nearly done",
];

function GearIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-10 w-10 text-accent"
      style={{ animation: "spin 2.4s linear infinite" }}
      aria-hidden
    >
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}

export function SearchLoader() {
  const [step, setStep] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setStep((n) => n + 1), 2200);
    return () => clearInterval(id);
  }, []);

  const message =
    step < STAGES.length
      ? STAGES[step]
      : TAIL[(step - STAGES.length) % TAIL.length];

  return (
    <Card className="p-10">
      <div className="flex flex-col items-center justify-center gap-4 text-center">
        <GearIcon />
        <span
          key={step}
          className="text-sm font-medium text-foreground"
          style={{ animation: "fadeIn 0.4s ease" }}
        >
          {message}…
        </span>
      </div>
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(3px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </Card>
  );
}

/** Small inline spinner shown at the bottom while more results stream in. */
export function ResultsSpinner() {
  return (
    <div className="flex items-center justify-center gap-2 py-4 text-sm text-muted-foreground">
      <svg
        viewBox="0 0 24 24"
        fill="none"
        className="h-4 w-4"
        style={{ animation: "spin 0.8s linear infinite" }}
        aria-hidden
      >
        <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="3" opacity="0.2" />
        <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
      </svg>
      <span>Fetching more results…</span>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
