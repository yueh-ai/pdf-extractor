import { describe, expect, it } from 'vitest';
import { buildAssetMap, resolveAssetUrl } from './assetResolver';
import type { ViewerPage } from './manifest';

const page: ViewerPage = {
  page: 40,
  status: 'published',
  needs_human_review: false,
  warning_count: 0,
  asset_count: 1,
  markdown_key: 'pdf-extract/reconciled/doc/pages/page_0040/output.md',
  decision_key: 'pdf-extract/reconciled/doc/pages/page_0040/decision.json',
  assets_key: 'pdf-extract/reconciled/doc/pages/page_0040/assets.json',
  markdown_path: 'object_store/pdf-extract/reconciled/doc/pages/page_0040/output.md',
  markdown_url: '/object_store/pdf-extract/reconciled/doc/pages/page_0040/output.md',
  source_page_image_path: 'runs/doc/union/pages/page_0040/page.png',
  source_page_image_url: '/runs/doc/union/pages/page_0040/page.png',
  markdown_sha256: 'abc',
  markdown_text: '<img src="asset://pdf-extract/reconciled/doc/pages/page_0040/assets/seal.jpg" />',
  error_message: null,
  decision: { source_refs: {} },
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

describe('assetResolver', () => {
  it('resolves asset uri, object key, and source path through the page asset map', () => {
    const map = buildAssetMap(page);
    expect(resolveAssetUrl('asset://pdf-extract/reconciled/doc/pages/page_0040/assets/seal.jpg', map)).toBe(
      '/object_store/pdf-extract/reconciled/doc/pages/page_0040/assets/seal.jpg',
    );
    expect(resolveAssetUrl('pdf-extract/reconciled/doc/pages/page_0040/assets/seal.jpg', map)).toBe(
      '/object_store/pdf-extract/reconciled/doc/pages/page_0040/assets/seal.jpg',
    );
    expect(resolveAssetUrl('runs/doc/union/pages/page_0040/imgs/seal.jpg', map)).toBe(
      '/object_store/pdf-extract/reconciled/doc/pages/page_0040/assets/seal.jpg',
    );
  });

  it('passes through existing browser URLs and marks unresolved values', () => {
    const map = buildAssetMap(page);
    expect(resolveAssetUrl('/runs/doc/page.png', map)).toBe('/runs/doc/page.png');
    expect(resolveAssetUrl('https://example.test/image.jpg', map)).toBe('https://example.test/image.jpg');
    expect(resolveAssetUrl('missing.jpg', map)).toBeNull();
  });
});
