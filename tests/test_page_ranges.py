import pytest

from pdf_extract.page_ranges import parse_page_spec


def test_parse_none_selects_all_pages():
    assert parse_page_spec(None, total_pages=3) == [1, 2, 3]


def test_parse_single_ranges_and_commas():
    assert parse_page_spec("1,3,5-7", total_pages=8) == [1, 3, 5, 6, 7]


def test_parse_deduplicates_and_sorts():
    assert parse_page_spec("3,1-2,2", total_pages=5) == [1, 2, 3]


@pytest.mark.parametrize("spec", ["0", "4", "3-2", "abc"])
def test_parse_rejects_invalid_specs(spec):
    with pytest.raises(ValueError):
        parse_page_spec(spec, total_pages=3)
