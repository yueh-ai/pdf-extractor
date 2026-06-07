import { useEffect, useId, useMemo, useRef, useState } from 'react';
import Markdown, { defaultUrlTransform } from 'react-markdown';
import rehypeMathjax from 'rehype-mathjax/browser';
import rehypeRaw from 'rehype-raw';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import { buildAssetMap, resolveAssetUrl } from './assetResolver';
import { ErrorBoundary } from './ErrorBoundary';
import type { ViewerPage } from './manifest';

type Props = {
  page: ViewerPage;
};

type MathJaxApi = {
  tex?: {
    inlineMath?: string[][];
    displayMath?: string[][];
  };
  startup?: {
    promise?: Promise<void>;
    typeset?: boolean;
  };
  typesetClear?: (elements?: HTMLElement[]) => void;
  typesetPromise?: (elements?: HTMLElement[]) => Promise<void>;
};

declare global {
  interface Window {
    MathJax?: MathJaxApi;
    __pdfExtractMathJaxPromise?: Promise<void>;
  }
}

const MATHJAX_SCRIPT_ID = 'pdf-extract-mathjax';
const MATHJAX_SCRIPT_URL = 'https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js';

function transformUrl(url: string): string {
  return url.startsWith('asset://') ? url : defaultUrlTransform(url);
}

export function markdownPaneResetKey(page: ViewerPage): string {
  return `${page.page}:${page.markdown_sha256 ?? page.markdown_text.length}`;
}

function containsMath(markdown: string): boolean {
  return markdown.includes('$') || markdown.includes('\\(') || markdown.includes('\\[');
}

function ensureMathJaxLoaded(): Promise<void> {
  if (import.meta.env.MODE === 'test') {
    return Promise.resolve();
  }
  if (window.MathJax?.typesetPromise) {
    return window.MathJax.startup?.promise ?? Promise.resolve();
  }
  if (window.__pdfExtractMathJaxPromise) {
    return window.__pdfExtractMathJaxPromise;
  }

  window.MathJax = {
    ...window.MathJax,
    tex: {
      inlineMath: [['\\(', '\\)']],
      displayMath: [['\\[', '\\]']],
      ...window.MathJax?.tex,
    },
    startup: {
      ...window.MathJax?.startup,
      typeset: false,
    },
  };

  window.__pdfExtractMathJaxPromise = new Promise((resolve, reject) => {
    const existingScript = document.getElementById(MATHJAX_SCRIPT_ID);
    if (existingScript) {
      existingScript.addEventListener('load', () => resolve(), { once: true });
      existingScript.addEventListener('error', () => reject(new Error('Failed to load MathJax')), {
        once: true,
      });
      return;
    }

    const script = document.createElement('script');
    script.id = MATHJAX_SCRIPT_ID;
    script.async = true;
    script.src = MATHJAX_SCRIPT_URL;
    script.addEventListener('load', () => resolve(), { once: true });
    script.addEventListener('error', () => reject(new Error('Failed to load MathJax')), { once: true });
    document.head.append(script);
  });

  return window.__pdfExtractMathJaxPromise;
}

export function MarkdownPane({ page }: Props) {
  const [mode, setMode] = useState<'rendered' | 'raw'>('rendered');
  const renderedPanelRef = useRef<HTMLDivElement>(null);
  const paneId = useId();
  const assetMap = useMemo(() => buildAssetMap(page), [page]);
  const resetKey = markdownPaneResetKey(page);
  const renderedTabId = `${paneId}-rendered-tab`;
  const renderedPanelId = `${paneId}-rendered-panel`;
  const rawTabId = `${paneId}-raw-tab`;
  const rawPanelId = `${paneId}-raw-panel`;

  useEffect(() => {
    if (mode !== 'rendered' || !containsMath(page.markdown_text)) {
      return;
    }

    let isCancelled = false;
    void ensureMathJaxLoaded()
      .then(() => {
        if (isCancelled || !renderedPanelRef.current || !window.MathJax?.typesetPromise) {
          return;
        }
        window.MathJax.typesetClear?.([renderedPanelRef.current]);
        return window.MathJax.typesetPromise([renderedPanelRef.current]);
      })
      .catch(() => {
        // Keep TeX visible if MathJax is offline or blocked; raw Markdown remains available.
      });

    return () => {
      isCancelled = true;
    };
  }, [mode, page.markdown_text, resetKey]);

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
          <div
            ref={renderedPanelRef}
            id={renderedPanelId}
            className="rendered-markdown"
            role="tabpanel"
            aria-labelledby={renderedTabId}
          >
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
