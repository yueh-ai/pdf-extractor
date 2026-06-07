import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from './App';
import type { ViewerManifest } from './manifest';

const manifest: ViewerManifest = {
  document_id: 'Full_30015375000000',
  generated_at: '2026-06-07T00:00:00Z',
  pages: [
    {
      page: 40,
      status: 'published',
      needs_human_review: false,
      warning_count: 0,
      asset_count: 0,
      markdown_key: 'md',
      decision_key: 'decision',
      assets_key: 'assets',
      markdown_path: 'object_store/output.md',
      markdown_url: '/object_store/output.md',
      source_page_image_path: 'runs/doc/page.png',
      source_page_image_url: '/runs/doc/page.png',
      markdown_sha256: 'hash',
      markdown_text: 'Rendered body for page 40',
      error_message: null,
      decision: { winner: 'union' },
      assets: [],
    },
    {
      page: 41,
      status: 'published',
      needs_human_review: false,
      warning_count: 1,
      asset_count: 2,
      markdown_key: 'md-41',
      decision_key: 'decision-41',
      assets_key: 'assets-41',
      markdown_path: 'object_store/output-41.md',
      markdown_url: '/object_store/output-41.md',
      source_page_image_path: 'runs/doc/page-41.png',
      source_page_image_url: '/runs/doc/page-41.png',
      markdown_sha256: 'hash-41',
      markdown_text: 'Rendered body for page 41',
      error_message: null,
      decision: { winner: 'vision' },
      assets: [],
    },
  ],
};

describe('App', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        json: async () => manifest,
      })),
    );
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('loads the manifest and shows the split reviewer', async () => {
    render(<App />);

    await waitFor(() => expect(screen.getByText('Full_30015375000000')).toBeInTheDocument());
    expect(screen.getByRole('button', { name: /Page 40/ })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Source PDF page 40' })).toHaveAttribute('src', '/runs/doc/page.png');
    expect(screen.getByText('decision')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Page 40' })).toBeInTheDocument();
  });

  it('marks the active page and switches page content when selected', async () => {
    render(<App />);

    const page40Button = await screen.findByRole('button', { name: /Page 40/ });
    const page41Button = screen.getByRole('button', { name: /Page 41/ });

    expect(page40Button).toHaveAttribute('aria-current', 'page');
    expect(page41Button).not.toHaveAttribute('aria-current');

    fireEvent.click(page41Button);

    expect(page40Button).not.toHaveAttribute('aria-current');
    expect(page41Button).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('heading', { name: 'Page 41' })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Source PDF page 41' })).toHaveAttribute('src', '/runs/doc/page-41.png');
    expect(screen.getByText('decision-41')).toBeInTheDocument();
  });
});
