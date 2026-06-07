import type { ViewerPage } from './manifest';

type Props = {
  pages: ViewerPage[];
  selectedPage: number;
  onSelectPage: (page: number) => void;
};

export function PageSidebar({ pages, selectedPage, onSelectPage }: Props) {
  return (
    <aside className="page-sidebar" aria-label="Pages">
      <div className="section-label">Pages</div>
      {pages.map((page) => (
        <button
          key={page.page}
          className={page.page === selectedPage ? 'selected' : ''}
          aria-current={page.page === selectedPage ? 'page' : undefined}
          onClick={() => onSelectPage(page.page)}
        >
          Page {page.page} | {page.status} | assets {page.asset_count}
        </button>
      ))}
    </aside>
  );
}
