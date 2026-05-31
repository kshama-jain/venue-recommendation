import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { apiUrl } from "../config";

export type Venue = {
  id?: string;
  title?: string;
  type?: string;
  publisher?: string;
  source?: string;
  topics?: string;
  url?: string;
  page_url?: string;
  official_url?: string;
  submission_url?: string;
  deadline?: string;
  open_until?: string;
  location?: string;
  is_predatory: boolean;
  // Allow extra backend fields without breaking strict TS.
  [key: string]: unknown;
};

type VenuesContextValue = {
  venues: Venue[];
  loading: boolean;
  error: string;
  refresh: () => Promise<void>;
};

const VenuesContext = createContext<VenuesContextValue | undefined>(undefined);

function detectPredatory(raw: Record<string, unknown>): boolean {
  const existing = raw.is_predatory;
  if (typeof existing === "boolean") return existing;

  const title = typeof raw.title === "string" ? raw.title : "";
  const publisher = typeof raw.publisher === "string" ? raw.publisher : "";
  const source = typeof raw.source === "string" ? raw.source : "";
  const hay = `${title} ${publisher} ${source}`.toLowerCase();

  // Very lightweight heuristic; replace/extend with backend-provided flags later.
  return /(predatory|questionable|scam|spam)/i.test(hay);
}

export function VenuesProvider({ children }: { children: React.ReactNode }) {
  const [venues, setVenues] = useState<Venue[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>("");

  const fetchVenues = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const res = await fetch(apiUrl("/api/venues"));
      if (!res.ok) throw new Error(`Server error (${res.status})`);

      const ct = res.headers.get("content-type") || "";
      if (!ct.includes("application/json")) {
        throw new Error("Backend not reachable. Run: python backend/server.py");
      }

      const data: unknown = await res.json();
      const arr = (data as any)?.data ?? (data as any)?.venues ?? [];
      const list = (Array.isArray(arr) ? arr : []).map((v: Record<string, unknown>) => ({
        ...v,
        is_predatory: detectPredatory(v),
      })) as Venue[];

      setVenues(list);
    } catch (e: unknown) {
      setVenues([]);
      const msg = e instanceof Error ? e.message : "Failed to load venues";
      setError(
        msg.includes("fetch") || msg.includes("Failed to fetch")
          ? "Cannot reach backend at http://127.0.0.1:5000 — run: python backend/server.py"
          : msg
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchVenues();
  }, [fetchVenues]);

  const value = useMemo(
    () => ({
      venues,
      loading,
      error,
      refresh: fetchVenues,
    }),
    [venues, loading, error, fetchVenues]
  );

  return <VenuesContext.Provider value={value}>{children}</VenuesContext.Provider>;
}

export function useVenues() {
  const ctx = useContext(VenuesContext);
  if (!ctx) throw new Error("useVenues must be used within VenuesProvider");
  return ctx;
}