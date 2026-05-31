import React, { useState } from "react";

const sections = [
  { id: "journals", label: "Journals" },
  { id: "conferences", label: "Conferences" },
  { id: "predatory", label: "Predatory Venues" },
  { id: "prestige", label: "Prestige & Rankings" },
  { id: "quartiles", label: "Quartiles (Q1–Q4)" },
  { id: "core", label: "CORE Rankings" },
  { id: "open-access", label: "Open Access" },
  { id: "how-it-works", label: "How This Tool Works" },
];

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="mb-10 scroll-mt-6">
      <h2 className="text-xl font-bold text-gray-900 mb-4 pb-2 border-b border-gray-200">{title}</h2>
      <div className="space-y-3 text-gray-700 text-sm leading-relaxed">{children}</div>
    </section>
  );
}

function InfoBox({ color, title, children }: { color: string; title: string; children: React.ReactNode }) {
  const colors: Record<string, string> = {
    blue: "bg-blue-50 border-blue-200 text-blue-900",
    amber: "bg-amber-50 border-amber-200 text-amber-900",
    red: "bg-red-50 border-red-200 text-red-900",
    green: "bg-green-50 border-green-200 text-green-900",
    purple: "bg-purple-50 border-purple-200 text-purple-900",
  };
  return (
    <div className={`border rounded-lg p-4 ${colors[color] || colors.blue}`}>
      <p className="font-semibold mb-1">{title}</p>
      <p className="text-sm leading-relaxed">{children}</p>
    </div>
  );
}

export function AboutPage() {
  const [activeSection, setActiveSection] = useState("journals");

  const scrollTo = (id: string) => {
    setActiveSection(id);
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <div className="app-main">
      <div className="max-w-6xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">About Academic Publishing</h1>
          <p className="text-gray-500 text-sm mt-1">
            A quick guide to journals, conferences, rankings, and how to spot quality venues.
          </p>
        </div>

        <div className="flex gap-6">
          {/* Sticky side nav */}
          <aside className="hidden lg:block w-52 shrink-0">
            <div className="card p-4 sticky top-6">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Contents</p>
              <nav className="space-y-1">
                {sections.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => scrollTo(s.id)}
                    className={`w-full text-left text-sm px-3 py-2 rounded-lg transition ${
                      activeSection === s.id
                        ? "bg-blue-50 text-blue-700 font-medium"
                        : "text-gray-600 hover:bg-gray-50"
                    }`}
                  >
                    {s.label}
                  </button>
                ))}
              </nav>
            </div>
          </aside>

          {/* Main content */}
          <div className="flex-1 card p-8">
            <Section id="journals" title="📄 What is an Academic Journal?">
              <p>
                An <strong>academic journal</strong> is a periodical publication where researchers submit
                original research articles. Journals are subject-specific (e.g., <em>Nature</em> for science,
                <em> IEEE Transactions on Information Security</em> for cybersecurity) and publish on a
                rolling or scheduled basis throughout the year.
              </p>
              <p>
                Before publication, every article goes through <strong>peer review</strong> — experts in the
                field read, critique, and either accept, request revisions, or reject the submission. This
                process ensures quality and credibility.
              </p>
              <div className="grid sm:grid-cols-2 gap-3 mt-2">
                <InfoBox color="green" title="✅ Rolling Submissions">
                  Most journals accept papers year-round. You can submit anytime, and the review process
                  typically takes weeks to months.
                </InfoBox>
                <InfoBox color="blue" title="📊 Measured By">
                  Impact Factor, h-index, SJR score, and Quartile (Q1–Q4). Higher = more prestigious.
                </InfoBox>
              </div>
            </Section>

            <Section id="conferences" title="🎤 What is an Academic Conference?">
              <p>
                An <strong>academic conference</strong> is a scheduled event (annual or biennial) where
                researchers present their work. Papers are submitted before a <strong>deadline</strong>,
                reviewed, and if accepted, presented at the conference and published in <em>proceedings</em>.
              </p>
              <p>
                Conferences are especially important in <strong>computer science</strong>, where top venues
                like CVPR, NeurIPS, and ICSE are considered more prestigious than many journals. A CFP
                (Call for Papers) announces the conference topics, deadlines, and submission details.
              </p>
              <div className="grid sm:grid-cols-2 gap-3 mt-2">
                <InfoBox color="blue" title="📅 Fixed Deadlines">
                  Conferences have hard submission deadlines — typically once or twice a year. Missing the
                  deadline means waiting for the next cycle.
                </InfoBox>
                <InfoBox color="purple" title="🏆 Measured By">
                  CORE rank (A*, A, B, C), h5-index, and acceptance rate. Top conferences (A*) have
                  acceptance rates as low as 15–25%.
                </InfoBox>
              </div>
            </Section>

            <Section id="predatory" title="⚠️ What are Predatory Journals & Conferences?">
              <p>
                <strong>Predatory publishers</strong> exploit the academic publish-or-perish culture. They
                charge authors fees (Article Processing Charges) to publish but perform little or no real
                peer review. Their goal is profit, not scholarly quality.
              </p>
              <InfoBox color="red" title="🚩 Warning Signs of a Predatory Journal">
                Very fast acceptance (days), emails promising guaranteed publication, vague scope claiming
                to cover "all fields of science", missing or fake editorial board, website with many typos,
                not indexed in major databases (Scopus, Web of Science), and aggressive spam emails.
              </InfoBox>
              <p className="mt-2">
                Similarly, <strong>predatory conferences</strong> accept all papers regardless of quality,
                charge high registration fees, and often change venues or cancel at the last minute.
              </p>
              <InfoBox color="amber" title="💡 How to Stay Safe">
                Check if the journal is indexed in <strong>Scopus</strong> or <strong>Web of Science</strong>.
                Verify the publisher on <strong>Beall's List</strong>. Use only Q1/Q2 journals or CORE A*/A
                conferences for important research. Check the journal's ISSN on the ISSN portal.
              </InfoBox>
            </Section>

            <Section id="prestige" title="🌟 What is Venue Prestige?">
              <p>
                <strong>Prestige</strong> refers to how reputable and impactful a venue is in the academic
                community. A more prestigious venue means your paper reaches more readers, gets more
                citations, and carries more weight for your career.
              </p>
              <div className="grid sm:grid-cols-3 gap-3 mt-2">
                <InfoBox color="blue" title="h-index">
                  Measures a venue's citation impact. An h-index of 50 means at least 50 papers published
                  there have each been cited at least 50 times.
                </InfoBox>
                <InfoBox color="green" title="Impact Factor (IF)">
                  Average citations per article in the past 2 years. Nature has an IF of ~60; a solid
                  specialist journal might have IF 3–8.
                </InfoBox>
                <InfoBox color="purple" title="SJR Score">
                  SCImago Journal Rank — similar to IF but weights citations by the prestige of the citing
                  journal. Used by Scopus.
                </InfoBox>
              </div>
              <p className="mt-2">
                This tool computes a <strong>Prestige Score (0–100)</strong> combining h-index, SJR,
                impact factor, quartile, and CORE rank into a single number so you can compare venues at a
                glance.
              </p>
            </Section>

            <Section id="quartiles" title="📊 Journal Quartiles (Q1, Q2, Q3, Q4)">
              <p>
                Journals are ranked within their subject area and divided into four equal groups (quartiles)
                based on their SJR score. This ranking is updated annually by <strong>Scimago</strong>.
              </p>
              <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 mt-2">
                <div className="rounded-lg border-2 border-blue-400 p-3 text-center">
                  <p className="text-lg font-bold text-blue-700">Q1</p>
                  <p className="text-xs text-gray-600 mt-1">Top 25% in field. Highest impact. Most selective. Aim for these for your best work.</p>
                </div>
                <div className="rounded-lg border-2 border-green-400 p-3 text-center">
                  <p className="text-lg font-bold text-green-700">Q2</p>
                  <p className="text-xs text-gray-600 mt-1">26–50%. Very good journals. Strong peer review. Widely respected in the community.</p>
                </div>
                <div className="rounded-lg border-2 border-amber-400 p-3 text-center">
                  <p className="text-lg font-bold text-amber-700">Q3</p>
                  <p className="text-xs text-gray-600 mt-1">51–75%. Decent venues. Acceptable for early-career researchers or niche topics.</p>
                </div>
                <div className="rounded-lg border-2 border-red-300 p-3 text-center">
                  <p className="text-lg font-bold text-red-600">Q4</p>
                  <p className="text-xs text-gray-600 mt-1">Bottom 25%. Lower impact. Scrutinize carefully — some Q4 journals can be predatory.</p>
                </div>
              </div>
              <p className="mt-3">
                <strong>Tip:</strong> Always check both the quartile AND the subject area. A journal can be
                Q1 in a small niche but Q3 overall. Context matters.
              </p>
            </Section>

            <Section id="core" title="🏅 CORE Conference Rankings (A*, A, B, C)">
              <p>
                The <strong>CORE (Computing Research and Education)</strong> ranking system rates computer
                science and IT conferences. It's the gold standard for CS researchers.
              </p>
              <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 mt-2">
                <div className="rounded-lg border-2 border-purple-500 p-3 text-center">
                  <p className="text-lg font-bold text-purple-700">A*</p>
                  <p className="text-xs text-gray-600 mt-1">Flagship venues. Top ~5% of CS conferences. NeurIPS, CVPR, ICSE, SOSP. Extremely competitive.</p>
                </div>
                <div className="rounded-lg border-2 border-blue-500 p-3 text-center">
                  <p className="text-lg font-bold text-blue-700">A</p>
                  <p className="text-xs text-gray-600 mt-1">Excellent conferences. Highly selective. Strong community recognition. Great target for PhD work.</p>
                </div>
                <div className="rounded-lg border-2 border-green-500 p-3 text-center">
                  <p className="text-lg font-bold text-green-700">B</p>
                  <p className="text-xs text-gray-600 mt-1">Good quality conferences. Solid peer review. Good for early-career or specialised work.</p>
                </div>
                <div className="rounded-lg border-2 border-gray-400 p-3 text-center">
                  <p className="text-lg font-bold text-gray-600">C</p>
                  <p className="text-xs text-gray-600 mt-1">National or lower-tier international. Useful for local dissemination or practice submissions.</p>
                </div>
              </div>
              <p className="mt-3">
                Conferences <strong>not listed</strong> in CORE are "Unranked" — they may be legitimate but
                haven't been evaluated. Always verify independently before submitting.
              </p>
            </Section>

            <Section id="open-access" title="🔓 Open Access vs. Paid (Subscription)">
              <p>
                <strong>Open Access (OA)</strong> means anyone can read your paper for free online — no
                paywall. <strong>Subscription journals</strong> require institutional access or payment to
                read articles.
              </p>
              <div className="grid sm:grid-cols-3 gap-3 mt-2">
                <InfoBox color="green" title="🟢 Gold OA">
                  Paper is freely available immediately on the journal's website. Usually requires an Article
                  Processing Charge (APC) from the author — can range from $500 to $5,000+.
                </InfoBox>
                <InfoBox color="blue" title="🔵 Green OA">
                  Author deposits a preprint (e.g., on arXiv) for free access, while the final version is
                  behind a paywall. Free for authors.
                </InfoBox>
                <InfoBox color="amber" title="🟡 Pay after Acceptance">
                  Most conferences — you pay a registration fee after your paper is accepted to attend and
                  present. The fee is typically $300–$800 and is not a publication fee.
                </InfoBox>
              </div>
            </Section>

            <Section id="how-it-works" title="🤖 How This Recommendation Tool Works">
              <p>
                Enter your paper title and (optionally) abstract. The tool:
              </p>
              <ol className="list-decimal list-inside space-y-2 pl-2">
                <li><strong>Detects your research domain</strong> using keyword matching and zero-shot classification (e.g., "Machine Learning", "Cybersecurity", "NLP").</li>
                <li><strong>Scores every venue</strong> in our database using keyword overlap, domain relevance, semantic similarity (sentence embeddings), prestige, and deadline urgency.</li>
                <li><strong>Returns the top matches</strong> ranked by a weighted score combining all signals.</li>
                <li><strong>Filters</strong> let you narrow by venue type, quartile, CORE rank, open/closed status, and paid/free access model.</li>
              </ol>
              <InfoBox color="blue" title="📡 Data Sources">
                Live conference CFPs are scraped from HuggingFace AI Deadlines, PapersWithCode, WikiCFP,
                and Resurchify. Journals are sourced from OpenAlex, Scimago SJR, and rolling journal
                databases — updated periodically.
              </InfoBox>
            </Section>
          </div>
        </div>
      </div>
    </div>
  );
}
