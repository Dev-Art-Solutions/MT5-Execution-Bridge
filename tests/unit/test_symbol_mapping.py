from app.services.symbol_mapper import SymbolMapper


def test_mapped_symbol_resolves():
    mapper = SymbolMapper({"EURUSD": "EURUSD.a"})
    assert mapper.resolve("EURUSD") == "EURUSD.a"


def test_unknown_symbol_returns_none():
    mapper = SymbolMapper({"EURUSD": "EURUSD"})
    assert mapper.resolve("US100") is None
