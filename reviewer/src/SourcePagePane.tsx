import type { ViewerPage } from './manifest';

export function SourcePagePane({ page }: { page: ViewerPage }) {
  return (
    <section className="pane source-pane" aria-label="Source PDF page">
      <div className="pane-title">Source PDF Page Image</div>
      {page.source_page_image_url ? (
        <img src={page.source_page_image_url} alt={`Source PDF page ${page.page}`} />
      ) : (
        <div className="image-fallback">No source page image</div>
      )}
      <div className="path-text">{page.source_page_image_path}</div>
    </section>
  );
}
