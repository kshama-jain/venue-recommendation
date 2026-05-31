import React, { useMemo } from "react";
import { Link } from "react-router-dom";
import { useVenues } from "./VenuesContext";

export function DashboardPage() {
  const { venues, loading, error } = useVenues();

  const stats = useMemo(() => {
    const conferences = venues.filter((v) => (v.type || "").toLowerCase() === "conference").length;
    const journals = venues.filter((v) => (v.type || "").toLowerCase() === "journal").length;
    const predatory = venues.filter((v) => v.is_predatory).length;
    return { conferences, journals, predatory };
  }, [venues]);

  return (
    <div className="app-main">
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="space-y-1">
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-sm text-gray-600">
            {loading ? "Loading venue stats…" : "Overview of venues and predatory flags."}
          </p>
          {error && (
            <div className="mt-2 bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
              {error}
            </div>
          )}
        </div>

        <div className="grid md:grid-cols-3 gap-4">
          <div className="card p-5">
            <p className="text-sm text-gray-500">Conferences</p>
            <p className="text-3xl font-bold text-green-600">{stats.conferences}</p>
          </div>
          <div className="card p-5">
            <p className="text-sm text-gray-500">Journals</p>
            <p className="text-3xl font-bold text-purple-600">{stats.journals}</p>
          </div>
          <div className="card p-5">
            <p className="text-sm text-gray-500">Flagged predatory</p>
            <p className="text-3xl font-bold text-red-600">{stats.predatory}</p>
          </div>
        </div>

        <div className="grid md:grid-cols-3 gap-4">
          <Link
            to="/conferences"
            className="card p-6 card-hover border-l-4 border-l-green-500 block"
          >
            <h2 className="font-semibold text-gray-900 mb-1">Conferences</h2>
            <p className="text-sm text-gray-600">Open CFPs, deadlines, locations</p>
          </Link>
          <Link
            to="/journals"
            className="card p-6 card-hover border-l-4 border-l-purple-500 block"
          >
            <h2 className="font-semibold text-gray-900 mb-1">Journals</h2>
            <p className="text-sm text-gray-600">Rolling submissions & metrics</p>
          </Link>
          <Link
            to="/recommendations"
            className="card p-6 card-hover border-l-4 border-l-blue-500 block"
          >
            <h2 className="font-semibold text-gray-900 mb-1">Smart recommendations</h2>
            <p className="text-sm text-gray-600">Match venues to your title & abstract</p>
          </Link>
        </div>
      </div>
    </div>
  );
}

export default DashboardPage;