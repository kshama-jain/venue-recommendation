import React, { useMemo, useState } from "react";
import { useVenues, type Venue } from "./VenuesContext";

type FilterType = "all" | "journal" | "conference";

type VenuesPageProps = {
  kind?: FilterType;
  title?: string;
};

function getMeta(kind: FilterType) {
  if (kind === "conference") {
    return { title: "Conferences", emptyHint: "No conferences match your filters.", defaultFilter: "conference" as FilterType };
  }
  if (kind === "journal") {
    return { title: "Journals", emptyHint: "No journals match your filters.", defaultFilter: "journal" as FilterType };
  }
  return { title: "Venues", emptyHint: "No venues match your filters.", defaultFilter: "all" as FilterType };
}

function VenueRow({ venue }: { venue: Venue }) {
  return (
    <div className="p-5 flex items-start justify-between gap-4">
      <div className="min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <h3 className="font-medium text-gray-900 truncate">{venue.title || "Untitled venue"}</h3>
          {venue.type && (
            <span className="inline-block px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded-md">
              {venue.type}
            </span>
          )}
          {venue.is_predatory && (
            <span className="inline-block px-2 py-1 bg-red-100 text-red-700 text-xs rounded-md">
              Predatory
            </span>
          )}
        </div>
        <p className="text-sm text-gray-600 mt-1">
          {venue.publisher || venue.source || "Publisher not available"}
        </p>
        {(venue.deadline || venue.open_until) && (
          <p className="text-xs text-gray-500 mt-2">
            {venue.deadline ? `Deadline: ${venue.deadline}` : `Open until: ${venue.open_until}`}
          </p>
        )}
      </div>

      {(venue.official_url || venue.page_url) && (
        <a
          href={(venue.official_url as string) || (venue.page_url as string)}
          target="_blank"
          rel="noreferrer"
          className="shrink-0 px-3 py-2 rounded border border-gray-300 text-sm hover:bg-gray-50"
        >
          View
        </a>
      )}
    </div>
  );
}

function VenuesPageInner({ kind = "all", title }: VenuesPageProps) {
  const meta = getMeta(kind);
  const { venues, loading, error } = useVenues();

  const [searchTerm, setSearchTerm] = useState("");
  const [filterType, setFilterType] = useState<FilterType>(meta.defaultFilter);
  const [showPredatoryOnly, setShowPredatoryOnly] = useState(false);

  const filtered = useMemo(() => {
    const s = searchTerm.trim().toLowerCase();
    return venues.filter((venue) => {
      if (filterType !== "all" && (venue.type || "").toLowerCase() !== filterType) return false;
      if (showPredatoryOnly && !venue.is_predatory) return false;
      if (!s) return true;

      const hay = `${venue.title ?? ""} ${venue.publisher ?? ""} ${venue.source ?? ""} ${venue.topics ?? ""}`.toLowerCase();
      return hay.includes(s);
    });
  }, [venues, searchTerm, filterType, showPredatoryOnly]);

  return (
    <div className="app-main">
      <div className="max-w-5xl mx-auto space-y-6">
        <div className="space-y-2">
          <h1 className="text-2xl font-bold text-gray-900">{title || meta.title}</h1>
          <p className="text-sm text-gray-600">Browse venues and filter by type/predatory flag.</p>
        </div>

        <div className="card p-6">
          <div className="grid md:grid-cols-3 gap-4 items-end">
            <div className="md:col-span-1">
              <label className="block text-xs font-medium text-gray-600 mb-1">Search</label>
              <input
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder={`Search ${meta.title.toLowerCase()}…`}
                className="input"
              />
            </div>

            <div className="md:col-span-1">
              <label className="block text-xs font-medium text-gray-600 mb-1">Venue type</label>
              <select value={filterType} onChange={(e) => setFilterType(e.target.value as FilterType)} className="input">
                <option value="all">All Types</option>
                <option value="conference">Conferences</option>
                <option value="journal">Journals</option>
              </select>
            </div>

            <div className="md:col-span-1">
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input type="checkbox" checked={showPredatoryOnly} onChange={(e) => setShowPredatoryOnly(e.target.checked)} />
                Predatory only
              </label>
            </div>
          </div>

          {error && <div className="mt-4 bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">{error}</div>}
        </div>

        <div className="card overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
            <h2 className="font-semibold text-gray-900">
              {loading ? "Loading…" : `${filtered.length} ${meta.title.toLowerCase()} found`}
            </h2>
          </div>

          {loading ? (
            <p className="p-8 text-center text-gray-500">Fetching venues…</p>
          ) : filtered.length === 0 ? (
            <p className="p-8 text-center text-gray-500">{meta.emptyHint}</p>
          ) : (
            <div className="divide-y divide-gray-200">
              {filtered.map((venue, i) => (
                <VenueRow key={venue.id || `${venue.title}-${i}`} venue={venue} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function VenuesPage(props: VenuesPageProps = {}) {
  return <VenuesPageInner {...props} />;
}

export default VenuesPage;
