import { useEffect, useMemo, useState } from 'react';
import { MarkdownPane } from './MarkdownPane';
import { MetadataPanel } from './MetadataPanel';
import { PageSidebar } from './PageSidebar';
import { SourcePagePane } from './SourcePagePane';
import { loadManifest, type ViewerManifest } from './manifest';

export function App() {
  const [manifest, setManifest] = useState<ViewerManifest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedPage, setSelectedPage] = useState<number | null>(null);

  useEffect(() => {
    loadManifest()
      .then((loaded) => {
        setManifest(loaded);
        setSelectedPage(loaded.pages[0]?.page ?? null);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  const page = useMemo(
    () => manifest?.pages.find((candidate) => candidate.page === selectedPage) ?? null,
    [manifest, selectedPage],
  );

  if (error) {
    return (
      <main className="app-shell">
        <div className="render-error">{error}</div>
      </main>
    );
  }
  if (!manifest || !page) {
    return <main className="app-shell">Loading reviewer...</main>;
  }

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <div className="section-label">Document</div>
          <h1>{manifest.document_id}</h1>
        </div>
        <div className="header-meta">Generated {manifest.generated_at}</div>
      </header>
      <div className="reviewer-grid">
        <PageSidebar pages={manifest.pages} selectedPage={page.page} onSelectPage={setSelectedPage} />
        <section className="page-review">
          <div className="page-heading">
            <div>
              <div className="section-label">Page {page.page}</div>
              <h2>Page {page.page}</h2>
            </div>
            <div className="status-line">
              {page.status} | warnings {page.warning_count} | assets {page.asset_count}
            </div>
          </div>
          <div className="split-view">
            <SourcePagePane page={page} />
            <section className="pane markdown-shell" aria-label="Rendered Markdown">
              <MarkdownPane page={page} />
            </section>
          </div>
          <MetadataPanel page={page} />
        </section>
      </div>
    </main>
  );
}
