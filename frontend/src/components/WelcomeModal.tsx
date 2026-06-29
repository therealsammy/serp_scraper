"use client";

import { useEffect, useState } from "react";
import { Button, Card } from "./ui";

const SEEN_KEY = "serp_welcome_seen";
export const GITHUB_URL = "https://github.com/therealsammy/serp_scraper";

// Minimal line-style icons (no emojis).
function Icon({ path }: { path: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-4 w-4 shrink-0 text-accent"
      aria-hidden
    >
      <path d={path} />
    </svg>
  );
}

const NOTES = [
  {
    // clock
    path: "M12 7v5l3 2M12 21a9 9 0 100-18 9 9 0 000 18z",
    text: "The backend runs on a free tier and may take 30–60s to wake up on the first request. Please be patient.",
  },
  {
    // gauge / fair use
    path: "M12 14l4-4M3 12a9 9 0 1118 0M7.5 16.5a6 6 0 019 0",
    text: "This is a free project — please keep to about 3 searches per day so others can use it too.",
  },
  {
    // info
    path: "M12 16v-4M12 8h.01M12 21a9 9 0 100-18 9 9 0 000 18z",
    text: "DuckDuckGo is best for local/dev testing and may not work here due to anti-bot proxy issues — use Google.",
  },
  {
    // shield
    path: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3z",
    text: "This is a demo — please don't enter sensitive or private queries.",
  },
];

export function WelcomeModal() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem(SEEN_KEY)) setOpen(true);
  }, []);

  function dismiss() {
    localStorage.setItem(SEEN_KEY, "1");
    setOpen(false);
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <Card className="w-full max-w-md p-6">
        <h2 className="text-lg font-semibold">Welcome to the SERP Research Tool</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          A quick heads-up before you start.
        </p>

        <ul className="mt-4 space-y-3">
          {NOTES.map((n, i) => (
            <li key={i} className="flex items-start gap-2.5 text-sm">
              <span className="mt-0.5">
                <Icon path={n.path} />
              </span>
              <span>{n.text}</span>
            </li>
          ))}
        </ul>

        <p className="mt-4 text-sm">
          Found a bug or have feedback? Open an issue on{" "}
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noreferrer"
            className="font-medium text-accent hover:underline"
          >
            GitHub
          </a>
          .
        </p>

        <Button className="mt-5 w-full" onClick={dismiss}>
          Got it
        </Button>
      </Card>
    </div>
  );
}
