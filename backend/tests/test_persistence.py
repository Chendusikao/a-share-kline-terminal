from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import inspect


def test_catalog_replacement_removes_stale_rows_and_searches_code_or_name() -> None:
    try:
        from app.persistence import Database, StockRecord, StockRepository
    except ModuleNotFoundError:
        pytest.fail("stock persistence has not been implemented")

    database = Database("sqlite+pysqlite:///:memory:")
    database.create_schema()
    updated_at = datetime(2026, 7, 29, 9, 30, tzinfo=UTC)

    with database.session() as session:
        repository = StockRepository(session)
        repository.replace_catalog(
            [
                StockRecord("000001", "平安银行", "SZ", updated_at),
                StockRecord("600000", "浦发银行", "SH", updated_at),
            ]
        )
        session.commit()

    with database.session() as session:
        repository = StockRepository(session)
        assert [stock.symbol for stock in repository.search("0000", limit=20)] == [
            "000001",
            "600000",
        ]
        assert [stock.symbol for stock in repository.search("平安", limit=20)] == [
            "000001"
        ]

        repository.replace_catalog(
            [StockRecord("000001", "平安银行", "SZ", updated_at)]
        )
        session.commit()

    with database.session() as session:
        repository = StockRepository(session)
        assert [stock.symbol for stock in repository.search("银行", limit=20)] == [
            "000001"
        ]


def test_replacing_forward_adjusted_candles_removes_obsolete_history() -> None:
    try:
        from app.persistence import CandleRecord, CandleRepository, Database
    except ModuleNotFoundError:
        pytest.fail("candle persistence has not been implemented")

    database = Database("sqlite+pysqlite:///:memory:")
    database.create_schema()
    first_fetch = datetime(2026, 7, 28, 16, tzinfo=UTC)
    second_fetch = datetime(2026, 7, 29, 16, tzinfo=UTC)

    with database.session() as session:
        repository = CandleRepository(session)
        repository.replace_symbol(
            "000001",
            [
                CandleRecord(
                    "000001",
                    date(2026, 7, 27),
                    10,
                    11,
                    9,
                    10.5,
                    1000,
                    10500,
                    "qfq",
                    first_fetch,
                ),
                CandleRecord(
                    "000001",
                    date(2026, 7, 28),
                    10.5,
                    12,
                    10,
                    11.5,
                    1200,
                    13800,
                    "qfq",
                    first_fetch,
                ),
            ],
        )
        session.commit()

        repository.replace_symbol(
            "000001",
            [
                CandleRecord(
                    "000001",
                    date(2026, 7, 28),
                    5.25,
                    6,
                    5,
                    5.75,
                    1200,
                    6900,
                    "qfq",
                    second_fetch,
                )
            ],
        )
        session.commit()

    with database.session() as session:
        candles = CandleRepository(session).list_symbol("000001")

    assert [candle.trade_date for candle in candles] == [date(2026, 7, 28)]
    assert candles[0].close == 5.75
    assert candles[0].adjustment == "qfq"
    assert candles[0].fetched_at == second_fetch


def test_database_schema_includes_scan_batches_and_per_symbol_results() -> None:
    from app.persistence import Database

    database = Database("sqlite+pysqlite:///:memory:")
    database.create_schema()
    inspector = inspect(database.engine)

    assert {column["name"] for column in inspector.get_columns("scan_runs")} == {
        "id",
        "market_date",
        "config_hash",
        "status",
        "created_at",
        "completed_at",
    }
    assert {column["name"] for column in inspector.get_columns("scan_results")} == {
        "run_id",
        "symbol",
        "score",
        "grade",
        "breakdown_json",
        "insights_json",
        "data_status",
        "error_code",
    }
    assert inspector.get_pk_constraint("scan_runs")["constrained_columns"] == ["id"]
    assert set(inspector.get_pk_constraint("scan_results")["constrained_columns"]) == {
        "run_id",
        "symbol",
    }
