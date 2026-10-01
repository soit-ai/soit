"""The observe dashboard never adds amounts in different currencies."""

from decimal import Decimal
from types import SimpleNamespace

from app.modules.observe.application.dashboard_service import ObserveDashboardService


def _cost(run_id: str, amount: str | None, currency: str | None) -> SimpleNamespace:
    return SimpleNamespace(
        run_id=run_id,
        amount=Decimal(amount) if amount is not None else None,
        currency=currency,
    )


def test_cost_by_currency_skips_unpriced_entries() -> None:
    costs = [_cost("r1", "1.5", "USD"), _cost("r1", None, None), _cost("r2", "2", "CNY"), _cost("r3", "0.5", "USD")]

    assert ObserveDashboardService._cost_by_currency(costs) == {
        "USD": Decimal("2.0"),
        "CNY": Decimal("2"),
    }


def test_cost_by_run_leaves_out_runs_priced_in_two_currencies() -> None:
    costs = [
        _cost("single", "0.25", "USD"),
        _cost("single", "0.5", "USD"),
        _cost("mixed", "1", "USD"),
        _cost("mixed", "7", "CNY"),
        _cost("unpriced", None, None),
    ]

    assert ObserveDashboardService._cost_by_run(costs) == {"single": 0.75}


def test_cost_card_names_its_single_currency_and_gives_a_delta() -> None:
    label, value, delta = ObserveDashboardService._cost_card_text(
        {"USD": Decimal("12.5")},
        {"USD": Decimal("10")},
    )

    assert (label, value, delta) == ("Cost (USD)", "12.50 USD", "2.50")


def test_cost_card_lists_each_currency_and_gives_no_delta() -> None:
    label, value, delta = ObserveDashboardService._cost_card_text(
        {"USD": Decimal("3"), "CNY": Decimal("20")},
        {"USD": Decimal("1")},
    )

    assert (label, value, delta) == ("Cost", "20.00 CNY · 3.00 USD", None)


def test_cost_card_gives_no_delta_when_the_currency_changed_between_windows() -> None:
    _, _, delta = ObserveDashboardService._cost_card_text({"EUR": Decimal("1")}, {"USD": Decimal("1")})

    assert delta is None


def test_cost_card_with_nothing_priced() -> None:
    assert ObserveDashboardService._cost_card_text({}, {}) == ("Cost", "0.00", "0.00")
    assert ObserveDashboardService._cost_card_text({}, {"USD": Decimal("4")}) == ("Cost", "0.00", "-4.00")
