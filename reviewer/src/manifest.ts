export type ViewerAsset = {
  asset_uri: string;
  object_key: string;
  local_path: string;
  local_url: string;
  source_path: string;
  description: string;
  content_type: string;
  sha256: string;
  byte_size: number;
};

export type ViewerPage = {
  page: number;
  status: string;
  needs_human_review: boolean;
  warning_count: number;
  asset_count: number;
  markdown_key: string | null;
  decision_key: string | null;
  assets_key: string | null;
  markdown_path: string | null;
  markdown_url: string | null;
  source_page_image_path: string | null;
  source_page_image_url: string | null;
  markdown_sha256: string | null;
  markdown_text: string;
  error_message: string | null;
  decision: Record<string, unknown>;
  assets: ViewerAsset[];
};

export type ViewerManifest = {
  document_id: string;
  generated_at: string;
  pages: ViewerPage[];
};

export function manifestUrlFromLocation(locationSearch = window.location.search): string {
  const params = new URLSearchParams(locationSearch);
  return params.get('manifest') ?? '/runs/Full_30015375000000/reconciled_viewer/viewer-manifest.json';
}

export async function loadManifest(url = manifestUrlFromLocation()): Promise<ViewerManifest> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to load viewer manifest: ${response.status} ${response.statusText}`);
  }
  return (await response.json()) as ViewerManifest;
}
