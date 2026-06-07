import type { ViewerPage } from './manifest';

export function MetadataPanel({ page }: { page: ViewerPage }) {
  return (
    <section className="metadata-panel" aria-label="Page metadata">
      <div>
        <strong>Decision</strong>
        <code>{page.decision_key}</code>
      </div>
      <div>
        <strong>Markdown</strong>
        <code>{page.markdown_key}</code>
      </div>
      <div>
        <strong>Assets</strong>
        <code>{page.assets_key}</code>
      </div>
      <ul>
        {page.assets.map((asset) => (
          <li key={asset.asset_uri}>
            <code>{asset.asset_uri}</code> | {asset.content_type} | {asset.byte_size} bytes | {asset.sha256}
          </li>
        ))}
      </ul>
    </section>
  );
}
