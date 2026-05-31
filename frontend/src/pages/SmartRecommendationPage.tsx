import React, { useMemo, useState } from "react";
import { apiUrl } from "../config";

type VenueType = "all" | "journal" | "conference";

type Venue = {
  id: string;
  title: string;
  type: "journal" | "conference";
  publisher?: string;
  source?: string;
  topics?: string;
  url?: string;
  page_url?: string;
  official_url?: string;
  submission_url?: string;
  deadline?: string;
  open_until?: string;

  h_index?: number | null;
  h5_index?: number | null;
  sjr?: number | null;
  impact_factor?: number | null;
  q_rank?: string;
  core_rank?: string;
  paid_or_free?: string;
  open_status?: string;

  recommendation_score?: number;
  keyword_score?: number;
  domain_score?: number;
  quality_score?: number;

  deadline_urgency?: number;
  scoring_breakdown?: {
    keyword_match?: number;
    domain_bonus?: number;
    prestige_score?: number;
    deadline_urgency?: number;
  };

  match_reason?: string;
};

function num(value: any): number | null {
  if (value === undefined || value === null || value === "") return null;
  const cleaned = String(value).replace("%", "").replace(",", "").trim();
  const n = Number(cleaned);
  return Number.isFinite(n) ? n : null;
}

function val(value: any) {
  if (value === undefined || value === null || value === "" || value === "nan")
    return "N/A";
  return value;
}

function formatPaidOrFree(raw: any): string {
  const v = String(raw || "").toLowerCase().trim();
  if (!v || v === "nan" || v === "n/a" || v === "none" || v === "not_specified" || v === "unknown")
    return "Pay after acceptance";
  if (v.includes("free") || v === "no_fee" || v === "open_access")
    return "Free";
  if (v.includes("paid_registration_likely") || v === "open_cfp_paid_registration_likely")
    return "Paid (registration likely)";
  if (v.includes("paid") || v.includes("fee") || v.includes("subscription"))
    return "Paid";
  return raw;
}

export default function SmartRecommendationPage() {
  const [title, setTitle] = useState("");
  const [abstractText, setAbstractText] = useState("");
  const [venueType, setVenueType] = useState<VenueType>("all");
  const [quartile, setQuartile] = useState("all");
  const [coreRank, setCoreRank] = useState("all");
  const [paidOrFree, setPaidOrFree] = useState("all");
  const [openStatus, setOpenStatus] = useState("all");
  const [location, setLocation] = useState("all");

  const [loadingRecommend, setLoadingRecommend] = useState(false);
  const [recommendations, setRecommendations] = useState<Venue[]>([]);
  const [detectedDomain, setDetectedDomain] = useState("");
  const [sources, setSources] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [hasSearched, setHasSearched] = useState(false);

  const filteredRecommendations = useMemo(() => {
    return recommendations.filter((v) => {
      if (venueType !== "all" && v.type !== venueType) return false;

      // Quartile filter (for journals)
      if (v.type === "journal" || venueType === "all") {
        const q = val(v.q_rank).toUpperCase();
        const qFilter = quartile.toUpperCase();
        if (quartile !== "all" && qFilter !== "ALL" && !q.includes(qFilter)) return false;
      }

      // CORE rank filter (for conferences)
      if (v.type === "conference" || venueType === "all") {
        const cr = val(v.core_rank).toUpperCase();
        const crFilter = coreRank.toUpperCase();
        if (coreRank !== "all" && crFilter !== "ALL") {
          if (crFilter === "UNRANKED") {
            if (cr && !["NOT AVAILABLE", "N/A", "NA", "UNRANKED", ""].includes(cr)) return false;
          } else if (!cr.includes(crFilter)) {
            return false;
          }
        }
      }

      // Paid / Free filter
      if (paidOrFree !== "all") {
        const pof = val(v.paid_or_free).toLowerCase();
        if (paidOrFree === "free" && !pof.includes("free") && !pof.includes("no")) return false;
        if (paidOrFree === "paid" && !pof.includes("paid") && !pof.includes("subscription") && !pof.includes("fee")) return false;
      }

      // Open / Closed filter
      if (openStatus !== "all") {
        const os = val(v.open_status).toLowerCase();
        const isEffectivelyOpen = ["open", "upcoming", "yes", "true", "rolling_journal", "deadline_open", "open_deadline_unknown"].includes(os);
        if (openStatus === "open" && !isEffectivelyOpen) return false;
        if (openStatus === "closed" && isEffectivelyOpen) return false;
      }

      if (location !== "all" && location !== "All Locations") {
        const locText = `${val((v as any).location)} ${val(v.title)}`.toLowerCase();
        if (!locText.includes(location.toLowerCase())) return false;
      }

      return true;
    });
  }, [recommendations, venueType, quartile, coreRank, paidOrFree, openStatus, location]);

  async function recommend() {
    if (!title.trim()) return;

    setLoadingRecommend(true);
    setError("");
    setRecommendations([]);
    setDetectedDomain("");
    setSources([]);
    setHasSearched(false);

    try {
      const response = await fetch(apiUrl("/api/smart-recommendations"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: title.trim(),
          abstract: abstractText.trim(),
          venue_type: venueType,
          top_k: 50,
          quartile: quartile,
          core_rank: coreRank,
          paid_or_free: paidOrFree,
          open_status: openStatus,
          location: location,
        }),
      });

      const data = await response.json();

      if (!response.ok || data.status === "error") {
        throw new Error(data.message || "Failed to get recommendations");
      }

      setRecommendations(data.recommendations || []);
      setDetectedDomain(data.detected_domain || data.domain || "");
      setSources(data.sources || []);
      setHasSearched(true);
    } catch (e: any) {
      const msg = e?.message || "Something went wrong";
      setError(
        msg.includes("fetch") || msg.includes("Failed to fetch")
          ? "Cannot reach the backend. Start it with: python backend/server.py"
          : msg
      );
    } finally {
      setLoadingRecommend(false);
    }
  }

  return (
    <div className="app-main">
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="space-y-2">
          <h1 className="text-2xl font-bold text-gray-900">Smart recommendations</h1>
          <p className="text-gray-600 text-sm">
            Enter your paper title and abstract. We match against conferences and journals
            using domain detection and venue scoring.
          </p>
        </div>

        <div className="grid lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1">
            <div className="card p-6 space-y-4">
              <h2 className="text-base font-medium text-gray-900">Paper Details</h2>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Paper Title <span className="text-red-500">*</span>
                </label>
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g., Graph Neural Network Based GST Fraud Detection"
                  className="input"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Abstract <span className="text-gray-400 text-xs">(Optional)</span>
                </label>
                <textarea
                  value={abstractText}
                  onChange={(e) => setAbstractText(e.target.value)}
                  placeholder="Paste abstract for better recommendations..."
                  rows={6}
                  className="input resize-none"
                />
              </div>

              <button
                onClick={recommend}
                disabled={loadingRecommend || !title.trim()}
                className="btn-primary w-full"
              >
                {loadingRecommend ? "Finding venues..." : "Get Recommendations"}
              </button>

              {error && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                  <p className="text-red-700 text-sm">{error}</p>
                </div>
              )}

              {(detectedDomain || sources.length > 0) && (
                <div className="bg-gray-50 rounded-lg p-4">
                  <h3 className="text-sm font-medium text-gray-700 mb-2">
                    Analysis Results
                  </h3>

                  {detectedDomain && (
                    <div className="mb-3">
                      <p className="text-xs text-gray-500 mb-1">Detected Domain</p>
                      <p className="text-sm font-medium text-gray-900">{detectedDomain}</p>
                    </div>
                  )}

                  {sources.length > 0 && (
                    <div>
                      <p className="text-xs text-gray-500 mb-2">Data Sources</p>
                      <div className="flex flex-wrap gap-1">
                        {sources.map((s) => (
                          <span
                            key={s}
                            className="inline-block px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded-md"
                          >
                            {s}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="lg:col-span-2 space-y-4">
            <div className="card p-6">
              <h2 className="text-base font-medium text-gray-900 mb-4">Filters</h2>

              <div className="grid md:grid-cols-3 gap-4 text-sm">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">
                    Venue Type
                  </label>
                  <select
                    value={venueType}
                    onChange={(e) => setVenueType(e.target.value as VenueType)}
                    className="input"
                  >
                    <option value="all">All Types</option>
                    <option value="conference">Conferences Only</option>
                    <option value="journal">Journals Only</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">
                    Quartile (Journals)
                  </label>
                  <select
                    value={quartile}
                    onChange={(e) => setQuartile(e.target.value)}
                    className="input"
                  >
                    <option value="all">All Quartiles</option>
                    <option value="Q1">Q1</option>
                    <option value="Q2">Q2</option>
                    <option value="Q3">Q3</option>
                    <option value="Q4">Q4</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">
                    CORE Rank (Conferences)
                  </label>
                  <select
                    value={coreRank}
                    onChange={(e) => setCoreRank(e.target.value)}
                    className="input"
                  >
                    <option value="all">All Ranks</option>
                    <option value="A*">A*</option>
                    <option value="A">A</option>
                    <option value="B">B</option>
                    <option value="C">C</option>
                    <option value="Unranked">Unranked</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">
                    Paid / Free
                  </label>
                  <select
                    value={paidOrFree}
                    onChange={(e) => setPaidOrFree(e.target.value)}
                    className="input"
                  >
                    <option value="all">All</option>
                    <option value="free">Free</option>
                    <option value="paid">Paid</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">
                    Open / Closed
                  </label>
                  <select
                    value={openStatus}
                    onChange={(e) => setOpenStatus(e.target.value)}
                    className="input"
                  >
                    <option value="all">All</option>
                    <option value="open">Open</option>
                    <option value="closed">Closed</option>
                  </select>
                </div>

                <div className="md:col-span-3">
                  <label className="block text-xs font-medium text-gray-600 mb-1">
                    Location
                  </label>
                  <select
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    className="input"
                  >
                    <option value="all">All Locations</option>
                    <option value="Austin">Austin</option>
                    <option value="Budapest">Budapest</option>
                    <option value="Mexico City">Mexico City</option>
                    <option value="Phoenix">Phoenix</option>
                    <option value="Dubai">Dubai</option>
                    <option value="Vilnius">Vilnius</option>
                  </select>
                </div>
              </div>
            </div>

            {loadingRecommend ? (
              <div className="card p-12 text-center text-sm text-gray-600">
                Analyzing your paper...
              </div>
            ) : filteredRecommendations.length === 0 ? (
              <div className="card p-12 text-center text-sm text-gray-600">
                {hasSearched
                  ? "No venues matched the current search and filters. Try relaxing filters (All Types, All Quartiles, All Ranks, All Locations) or lowering the minimum h-index."
                  : "No recommendations yet. Enter a title and click \"Get Recommendations\"."}
              </div>
            ) : (
              <div className="space-y-4">
                {filteredRecommendations.map((v, index) => (
                  <div key={v.id || index} className="card p-6 card-hover">
                    <div className="flex justify-between gap-4 mb-3">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2 flex-wrap">
                          <span className="inline-flex items-center justify-center w-6 h-6 bg-blue-600 text-white text-xs font-medium rounded-full">
                            {index + 1}
                          </span>
                          <span className="inline-block px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded-md capitalize">
                            {v.type}
                          </span>
                          {v.core_rank && v.core_rank !== "Not available" && (
                            <span className="inline-block px-2 py-1 bg-purple-100 text-purple-700 text-xs rounded-md font-medium">
                              CORE {v.core_rank}
                            </span>
                          )}
                          {v.q_rank && v.q_rank !== "N/A" && (
                            <span className="inline-block px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded-md">
                              {v.q_rank}
                            </span>
                          )}
                          {v.open_status && v.open_status !== "N/A" && (() => {
                            const os = String(v.open_status).toLowerCase();
                            const isOpen = os === "open" || os === "rolling_journal" || os === "deadline_open" || os === "open_deadline_unknown";
                            const isUpcoming = os === "upcoming";
                            const isClosed = os === "closed" || os === "deadline_passed";
                            const label = os === "rolling_journal" ? "Rolling"
                              : os === "open" || os === "deadline_open" ? "Open"
                              : os === "open_deadline_unknown" ? "Open (TBD)"
                              : os === "upcoming" ? "Upcoming"
                              : isClosed ? "Closed"
                              : v.open_status;
                            const cls = isOpen ? "bg-green-100 text-green-700"
                              : isUpcoming ? "bg-sky-100 text-sky-700"
                              : "bg-red-100 text-red-700";
                            return (
                              <span className={`inline-block px-2 py-1 text-xs rounded-md ${cls}`}>
                                {label}
                              </span>
                            );
                          })()}
                          {(() => {
                            const label = formatPaidOrFree(v.paid_or_free);
                            const isFree = label === "Free";
                            const isAfterAcceptance = label === "Pay after acceptance";
                            return (
                              <span className={`inline-block px-2 py-1 text-xs rounded-md ${isFree ? "bg-emerald-100 text-emerald-700" : isAfterAcceptance ? "bg-sky-100 text-sky-700" : "bg-amber-100 text-amber-700"}`}>
                                {label}
                              </span>
                            );
                          })()}
                          {v.deadline_urgency != null && (
                            <span className="inline-block px-2 py-1 bg-orange-100 text-orange-700 text-xs rounded-md">
                              Urgency: {Math.round(v.deadline_urgency)}%
                            </span>
                          )}
                        </div>

                        <h3 className="text-lg font-medium text-gray-900 mb-2 leading-tight">
                          {v.title}
                        </h3>
                        <p className="text-gray-600 text-sm">
                          {v.publisher || v.source || "Publisher not available"}
                        </p>
                      </div>

                      <div className="text-right">
                        <div className="bg-green-100 text-green-800 px-3 py-2 rounded-lg">
                          <p className="text-lg font-bold">
                            {Math.round(v.recommendation_score || 0)}
                          </p>
                          <p className="text-xs">Match Score</p>
                        </div>
                      </div>
                    </div>

                    {v.match_reason && (
                      <div className="bg-gray-50 rounded-lg p-3 mb-4">
                        <p className="text-gray-700 text-sm">{v.match_reason}</p>
                      </div>
                    )}

                    {v.scoring_breakdown && (
                      <div className="bg-gray-50 rounded-lg p-3 mb-4 text-xs text-gray-700">
                        <p className="font-medium mb-1">Scoring breakdown</p>
                        <p>
                          Keyword: {v.scoring_breakdown.keyword_match ?? "N/A"} · Domain:{" "}
                          {v.scoring_breakdown.domain_bonus ?? "N/A"} · Prestige:{" "}
                          {v.scoring_breakdown.prestige_score ?? "N/A"} · Deadline:{" "}
                          {v.scoring_breakdown.deadline_urgency ?? "N/A"}
                        </p>
                      </div>
                    )}

                    <div className="flex flex-wrap gap-2 text-xs">
                      {(v.official_url || v.url) && (
                        <a
                          href={v.official_url || v.url}
                          target="_blank"
                          rel="noreferrer"
                          className="px-3 py-1 rounded border border-gray-300 hover:bg-gray-50"
                        >
                          Official Page
                        </a>
                      )}
                      {v.page_url && (
                        <a
                          href={v.page_url}
                          target="_blank"
                          rel="noreferrer"
                          className="px-3 py-1 rounded border border-gray-300 hover:bg-gray-50"
                        >
                          CFP Page
                        </a>
                      )}
                      {v.submission_url && (
                        <a
                          href={v.submission_url}
                          target="_blank"
                          rel="noreferrer"
                          className="px-3 py-1 rounded bg-blue-600 text-white hover:bg-blue-700"
                        >
                          Submit Paper
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

