from __future__ import annotations


def parse_page_spec(spec: str | None, *, total_pages: int) -> list[int]:
    if total_pages < 1:
        return []
    if spec is None or spec.strip() == "":
        return list(range(1, total_pages + 1))

    pages: set[int] = set()
    for raw_part in spec.split(","):
        part = raw_part.strip()
        if not part:
            raise ValueError(f"Invalid empty page range in {spec!r}")
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            if not start_text.isdigit() or not end_text.isdigit():
                raise ValueError(f"Invalid page range {part!r}")
            start = int(start_text)
            end = int(end_text)
            if start < 1 or end < start or end > total_pages:
                raise ValueError(f"Page range {part!r} is outside 1-{total_pages}")
            pages.update(range(start, end + 1))
        else:
            if not part.isdigit():
                raise ValueError(f"Invalid page number {part!r}")
            page = int(part)
            if page < 1 or page > total_pages:
                raise ValueError(f"Page {page} is outside 1-{total_pages}")
            pages.add(page)
    return sorted(pages)
