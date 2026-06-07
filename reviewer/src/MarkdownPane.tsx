import { useId, useMemo, useState } from 'react';
import Markdown, { defaultUrlTransform } from 'react-markdown';
import rehypeMathjax from 'rehype-mathjax';
import rehypeRaw from 'rehype-raw';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import { buildAssetMap, resolveAssetUrl } from './assetResolver';
import { ErrorBoundary } from './ErrorBoundary';
import type { ViewerPage } from './manifest';

type Props = {
  page: ViewerPage;
};

function transformUrl(url: string): string {
  return url.startsWith('asset://') ? url : defaultUrlTransform(url);
}

export function markdownPaneResetKey(page: ViewerPage): string {
  return `${page.page}:${page.markdown_sha256 ?? page.markdown_text.length}`;
}

export function MarkdownPane({ page }: Props) {
  const [mode, setMode] = useState<'rendered' | 'raw'>('rendered');
  const paneId = useId();
  const assetMap = useMemo(() => buildAssetMap(page), [page]);
  const resetKey = markdownPaneResetKey(page);
  const renderedTabId = `${paneId}-rendered-tab`;
  const renderedPanelId = `${paneId}-rendered-panel`;
  const rawTabId = `${paneId}-raw-tab`;
  const rawPanelId = `${paneId}-raw-panel`;

  return (
    <section className="markdown-pane" aria-label="Markdown output">
      <div className="pane-toolbar" role="tablist" aria-label="Markdown view mode">
        <button
          id={renderedTabId}
          className={mode === 'rendered' ? 'active' : ''}
          type="button"
          role="tab"
          aria-selected={mode === 'rendered'}
          aria-controls={renderedPanelId}
          onClick={() => setMode('rendered')}
        >
          Rendered
        </button>
        <button
          id={rawTabId}
          className={mode === 'raw' ? 'active' : ''}
          type="button"
          role="tab"
          aria-selected={mode === 'raw'}
          aria-controls={rawPanelId}
          onClick={() => setMode('raw')}
        >
          Raw Markdown
        </button>
      </div>
      {mode === 'raw' ? (
        <pre id={rawPanelId} className="raw-markdown" role="tabpanel" aria-labelledby={rawTabId}>
          {page.markdown_text}
        </pre>
      ) : (
        <ErrorBoundary
          resetKey={resetKey}
          fallback={(error) => (
            <div id={renderedPanelId} className="render-error" role="tabpanel" aria-labelledby={renderedTabId}>
              <strong>Render error</strong>
              <p>{error.message}</p>
              <pre className="raw-markdown">{page.markdown_text}</pre>
            </div>
          )}
        >
          <div id={renderedPanelId} className="rendered-markdown" role="tabpanel" aria-labelledby={renderedTabId}>
            <Markdown
              remarkPlugins={[remarkGfm, remarkMath]}
              // Raw HTML is intentional for local, trusted PaddleOCR pipeline output; revisit before hosted or public use.
              rehypePlugins={[rehypeRaw, rehypeMathjax]}
              urlTransform={transformUrl}
              components={{
                img({ node: _node, ...props }) {
                  const resolved = resolveAssetUrl(props.src, assetMap);
                  if (!resolved) {
                    return (
                      <span className="image-fallback">
                        Unresolved image <code>{props.src}</code>
                      </span>
                    );
                  }
                  return <img {...props} src={resolved} alt={props.alt ?? ''} />;
                },
                table({ node: _node, ...props }) {
                  return (
                    <div className="table-scroll">
                      <table {...props} />
                    </div>
                  );
                },
                a({ node: _node, ...props }) {
                  return <a {...props} target="_blank" rel="noreferrer" />;
                },
              }}
            >
              {page.markdown_text}
            </Markdown>
          </div>
        </ErrorBoundary>
      )}
    </section>
  );
}
