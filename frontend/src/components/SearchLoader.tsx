"use client";

import { useEffect, useState } from "react";
import { Card } from "./ui";

const STAGES = [
  "Browsing the web…",
  "Fetching results…",
  "Opening pages…",
  "Scraping content…",
  "Parsing articles…",
  "Stripping the boilerplate…",
  "Extracting the good stuff…",
  "Compiling results…",
  "Almost there…",
];

export function SearchLoader() {
  const [i, setI] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setI((n) => (n + 1) % STAGES.length), 1800);
    return () => clearInterval(id);
  }, []);

  return (
    <Card className="overflow-hidden p-5">
      <div className="flex items-center gap-3">
        {/* pulsing dots */}
        <div className="flex gap-1">
          {[0, 1, 2].map((d) => (
            <span
              key={d}
              className="h-2 w-2 animate-bounce rounded-full bg-accent"
              style={{ animationDelay: `${d * 0.15}s` }}
            />
          ))}
        </div>
        <span
          key={i}
          className="text-sm font-medium text-foreground"
          style={{ animation: "fadeIn 0.4s ease" }}
        >
          {STAGES[i]}
        </span>
      </div>

      {/* indeterminate sliding bar */}
      <div className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div className="h-full w-1/3 rounded-full bg-accent" style={{ animation: "slide 1.4s ease-in-out infinite" }} />
      </div>

      <style>{`
        @keyframes slide {
          0% { transform: translateX(-100%); }
          50% { transform: translateX(150%); }
          100% { transform: translateX(320%); }
        }
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(3px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </Card>
  );
}
