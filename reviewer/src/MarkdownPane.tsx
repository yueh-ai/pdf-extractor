import { useMemo, useState } from 'react';
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

export function MarkdownPane({ page }: Props) {
  const [mode, setMode] = useState<'rendered' | 'raw'>('rendered');
  const assetMap = useMemo(() => buildAssetMap(page), [page]);

  return (
    <section className="markdown-pane" aria-label="Markdown output">
      <div className="pane-toolbar" role="tablist" aria-label="Markdown view mode">
        <button className={mode === 'rendered' ? 'active' : ''} role="tab" aria-selected={mode === 'rendered'} onClick={() => setMode('rendered')}>
          Rendered
        </button>
        <button className={mode === 'raw' ? 'active' : ''} role="tab" aria-selected={mode === 'raw'} onClick={() => setMode('raw')}>
          Raw Markdown
        </button>
      </div>
      {mode === 'raw' ? (
        <pre className="raw-markdown">{page.markdown_text}</pre>
      ) : (
        <ErrorBoundary
          fallback={(error) => (
            <div className="render-error">
              <strong>Render error</strong>
              <p>{error.message}</p>
              <pre className="raw-markdown">{page.markdown_text}</pre>
            </div>
          )}
        >
          <div className="rendered-markdown">
            <Markdown
              remarkPlugins={[remarkGfm, remarkMath]}
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
