import io
from decimal import Decimal
from pathlib import Path

import pytest

from scripts.registry_import.parser import (
    TABLET_UNITS,
    _clean,
    _is_tablet_based,
    _parse_capacity,
    parse_registry,
)

FIXTURE = Path(__file__).parent / "fixtures" / "registry_sample.xml"


@pytest.fixture
def rows() -> list[dict]:
    return list(parse_registry(FIXTURE))


def by_name(rows: list[dict], name: str) -> list[dict]:
    return [r for r in rows if r["name"] == name]


class TestParseRegistry:
    def test_apap_tablet_packages(self, rows):
        apap = by_name(rows, "Apap")
        # 13 packages: the withdrawn (skasowane="TAK") 500-tabl. pack is excluded and
        # the duplicate 2-tabl. pack (same capacity, different GTIN) is collapsed → 11.
        assert len(apap) == 11
        assert all(r["is_tablet_based"] for r in apap)
        assert all(r["capacity_unit"] == "tabl." for r in apap)
        caps = sorted(r["capacity"] for r in apap)
        assert caps == [Decimal(n) for n in (2, 4, 6, 8, 10, 12, 24, 50, 60, 100, 200)]
        assert Decimal(500) not in caps
        # the sachet + blister 2-tabl. packages dedupe to a single row
        assert sum(r["capacity"] == Decimal(2) for r in apap) == 1

    def test_apap_field_mapping(self, rows):
        r = by_name(rows, "Apap")[0]
        assert r["source_product_id"] == "100006494"
        assert r["active_ingredient"] == "Paracetamolum"
        assert r["strength"] == "500 mg"
        assert r["pharmaceutical_form"] == "Tabletki powlekane"
        assert r["marketing_authorization_holder"] == "US Pharmacia Sp. z o.o."
        assert r["manufacturer"] == "US Pharmacia Sp. z o.o."
        assert r["route_of_administration"] == "doustna"
        assert r["atc_code"] == "N02BE01"
        assert r["availability_category"] == "OTC"
        assert r["leaflet_url"].endswith("/leaflet")
        assert r["specification_url"].endswith("/characteristic")

    def test_acodin_duo_syrup(self, rows):
        acodin = by_name(rows, "Acodin Duo")
        # the withdrawn 100 ml package is excluded, leaving two non-tablet rows
        assert len(acodin) == 2
        assert all(not r["is_tablet_based"] for r in acodin)
        assert all(r["capacity_unit"] == "ml" for r in acodin)
        expected = "Dexpanthenolum + Dextromethorphani hydrobromidum"
        assert all(r["active_ingredient"] == expected for r in acodin)
        assert sorted(r["capacity"] for r in acodin) == [Decimal(60), Decimal(100)]

    def test_gensulin_multiple_routes(self, rows):
        gensulin = by_name(rows, "Gensulin R")
        assert len(gensulin) == 1
        assert (
            gensulin[0]["route_of_administration"] == "domięśniowa, dożylna, podskórna"
        )

    def test_fanhdi_composite_pack(self, rows):
        fanhdi = by_name(rows, "FANHDI")
        # one <opakowanie> with two <jednostkaOpakowania> → two rows
        assert len(fanhdi) == 2
        powder = next(r for r in fanhdi if r["capacity"] is None)
        assert powder["capacity_unit"] is None  # empty pojemnosc → no crash, NULLs
        assert powder["is_tablet_based"] is False
        solvent = next(r for r in fanhdi if r["capacity"] is not None)
        assert solvent["capacity"] == Decimal(10)
        assert solvent["capacity_unit"] == "ml"
        # composite pack: both units carry the same (non-unique) GTIN
        assert fanhdi[0]["gtin"] == fanhdi[1]["gtin"] == "05909990783618"
        joined = "Ludzki VIII czynnik krzepnięcia krwi + Ludzki czynnik von Willebranda"
        assert powder["active_ingredient"] == joined

    def test_nar_wins_over_ir_regardless_of_document_order(self, rows):
        # APAP (Delfarma, IR) appears BEFORE Apap (US Pharmacia, NAR) in the
        # fixture — the two-pass dedup must still suppress the IR entry and keep
        # the NAR row as the canonical source for the 6/12/24 tabl. packs.
        assert by_name(rows, "APAP") == []
        apap = by_name(rows, "Apap")
        assert any(
            r["marketing_authorization_holder"] == "US Pharmacia Sp. z o.o."
            for r in apap
        )

    def test_veterinary_product_excluded(self, rows):
        assert by_name(rows, "Vetmedin") == []
        # APAP parallel import is fully deduped; only the five canonical products yield rows
        assert {r["name"] for r in rows} == {
            "Apap",
            "Acodin Duo",
            "Gensulin R",
            "Edelan",
            "FANHDI",
        }


class TestParseRegistrySource:
    def test_seekable_file_object_yields_rows(self):
        # A seekable file object is rewound between the two passes.
        with FIXTURE.open("rb") as fh:
            rows = list(parse_registry(fh))
        assert by_name(rows, "Apap")

    def test_non_seekable_stream_raises_value_error(self):
        # A non-seekable stream cannot be rewound for pass 2; it must fail loudly
        # rather than silently import zero rows.
        class _NonSeekable:
            def __init__(self, data: bytes):
                self._buf = io.BytesIO(data)

            def read(self, *args):
                return self._buf.read(*args)

            def seekable(self) -> bool:
                return False

        stream = _NonSeekable(FIXTURE.read_bytes())
        with pytest.raises(ValueError, match="seekable"):
            list(parse_registry(stream))


class TestClean:
    def test_none_returns_none(self):
        assert _clean(None) is None

    def test_empty_string_returns_none(self):
        assert _clean("") is None

    def test_whitespace_only_returns_none(self):
        assert _clean("   ") is None

    def test_strips_whitespace(self):
        assert _clean("  apap  ") == "apap"

    def test_dash_sentinel_returns_none(self):
        assert _clean("-") is None

    def test_dash_with_whitespace_returns_none(self):
        assert _clean("  -  ") is None

    def test_non_sentinel_value_returned(self):
        assert _clean("500 mg") == "500 mg"


class TestParseCapacity:
    def test_integer_string(self):
        assert _parse_capacity("6") == Decimal(6)

    def test_strips_whitespace(self):
        assert _parse_capacity(" 12 ") == Decimal(12)

    def test_comma_decimal_separator(self):
        assert _parse_capacity("0,5") == Decimal("0.5")

    def test_dot_decimal_separator(self):
        assert _parse_capacity("1.5") == Decimal("1.5")

    def test_empty_string_returns_none(self):
        assert _parse_capacity("") is None

    def test_none_returns_none(self):
        assert _parse_capacity(None) is None

    def test_non_numeric_returns_none(self):
        assert _parse_capacity("abc") is None


class TestIsTabletBased:
    def test_tablet_unit_returns_true(self):
        assert _is_tablet_based("tabl.") is True

    def test_capsule_unit_returns_true(self):
        assert _is_tablet_based("kaps.") is True

    def test_ml_returns_false(self):
        assert _is_tablet_based("ml") is False

    def test_gram_returns_false(self):
        assert _is_tablet_based("g") is False

    def test_none_returns_false(self):
        assert _is_tablet_based(None) is False

    def test_tablet_unit_in_constant(self):
        assert "tabl." in TABLET_UNITS
