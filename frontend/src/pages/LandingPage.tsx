import React from "react";
import { Link } from "react-router-dom";

export function LandingPage() {
  return (
    <div className="app-main">
      <div className="max-w-4xl">
        <h1 className="text-3xl font-semibold text-gray-900">
          Find strong academic venues for your research
        </h1>
        <p className="mt-3 text-gray-600 text-sm leading-relaxed">
          Enter your paper title and optional abstract. We detect the research
          domain and rank relevant conferences/journals using multi-signal
          heuristics (keywords, prestige quartiles, and deadline urgency).
        </p>

        <div className="mt-6 flex gap-3 flex-wrap">
          <Link to="/dashboard" className="btn-primary inline-flex items-center">
            Open dashboard
          </Link>
          <Link
            to="/recommendations"
            className="px-4 py-2 rounded-lg border border-gray-300 text-sm hover:bg-gray-50 inline-flex items-center"
          >
            Get recommendations
          </Link>
          <Link
            to="/venues"
            className="px-4 py-2 rounded-lg border border-gray-300 text-sm hover:bg-gray-50 inline-flex items-center"
          >
            Browse venues
          </Link>
          <a
            href="http://127.0.0.1:5000/api/health"
            target="_blank"
            rel="noreferrer"
            className="px-4 py-2 rounded-lg border border-gray-300 text-sm hover:bg-gray-50 inline-flex items-center"
          >
            Check backend health
          </a>
        </div>

        <div className="mt-8 card p-6">
          <h2 className="font-medium text-gray-900">What you’ll get</h2>
          <p className="mt-2 text-sm text-gray-600">
            Ranked venue list + a per-venue explanation (match reason) including
            domain detection and scoring breakdown when available.
          </p>
        </div>
      </div>
    </div>
  );
}

