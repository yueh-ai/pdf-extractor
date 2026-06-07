import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { MarkdownPane } from './MarkdownPane';
import type { ViewerPage } from './manifest';

afterEach(() => {
  cleanup();
});

function makePage(markdown: string): ViewerPage {
  return {
    page: 40,
    status: 'published',
    needs_human_review: false,
    warning_count: 0,
    asset_count: 1,
    markdown_key: 'md',
    decision_key: 'decision',
    assets_key: 'assets',
    markdown_path: 'object_store/output.md',
    markdown_url: '/object_store/output.md',
    source_page_image_path: 'runs/page.png',
    source_page_image_url: '/runs/page.png',
    markdown_sha256: 'hash',
    markdown_text: markdown,
    error_message: null,
    decision: {},
    assets: [
      {
        asset_uri: 'asset://pdf-extract/reconciled/doc/pages/page_0040/assets/seal.jpg',
        object_key: 'pdf-extract/reconciled/doc/pages/page_0040/assets/seal.jpg',
        local_path: 'object_store/pdf-extract/reconciled/doc/pages/page_0040/assets/seal.jpg',
        local_url: '/object_store/pdf-extract/reconciled/doc/pages/page_0040/assets/seal.jpg',
        source_path: 'runs/doc/union/pages/page_0040/imgs/seal.jpg',
        description: 'seal',
        content_type: 'image/jpeg',
        sha256: 'hash',
        byte_size: 4,
      },
    ],
  };
}

describe('MarkdownPane', () => {
  it('renders raw HTML tables and resolves asset images', () => {
    render(
      <MarkdownPane
        page={makePage('<table><tr><td>Lease Line</td></tr></table><img src="asset://pdf-extract/reconciled/doc/pages/page_0040/assets/seal.jpg" alt="Seal" />')}
      />,
    );

    expect(screen.getByRole('cell', { name: 'Lease Line' })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Seal' })).toHaveAttribute(
      'src',
      '/object_store/pdf-extract/reconciled/doc/pages/page_0040/assets/seal.jpg',
    );
  });

  it('renders GFM pipe tables', () => {
    render(<MarkdownPane page={makePage('| MD | TVD |\n|---:|---:|\n| 5669 | 5667 |')} />);

    expect(screen.getByRole('columnheader', { name: 'MD' })).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: '5669' })).toBeInTheDocument();
  });

  it('keeps raw markdown available', () => {
    const markdown = 'Dip Angle: $60.02^{\\circ}$';
    render(<MarkdownPane page={makePage(markdown)} />);

    fireEvent.click(screen.getByRole('tab', { name: 'Raw Markdown' }));
    expect(screen.getByText(markdown)).toBeInTheDocument();
  });

  it('shows unresolved image fallback', () => {
    render(<MarkdownPane page={makePage('<img src="missing.jpg" alt="Missing seal" />')} />);

    const fallback = screen.getByText(/Unresolved image/);
    expect(within(fallback.closest('.image-fallback') as HTMLElement).getByText('missing.jpg')).toBeInTheDocument();
  });
});
