# Copyright (c) 2026, Deepak Patel and Contributors
# See license.txt

import frappe
from frappe.exceptions import ValidationError
from frappe.tests import IntegrationTestCase
from frappe.utils import getdate

from bond_management.bond_management.doctype.bond_transaction.bond_transaction import (
    get_calculated_amounts,
)
from bond_management.bond_management.tests.factories import (
    make_bond,
    make_portfolio,
    make_transaction,
    unique_name,
)
from bond_management.bond_management.utils.portfolio import (
    get_position,
    get_position_for_payment,
)


class TestBondTransaction(IntegrationTestCase):
    def test_calculates_transaction_amounts(self):
        transaction = make_transaction(make_bond(), make_portfolio())

        self.assertEqual(transaction.principal, 1000)
        self.assertEqual(transaction.commission_amount, 20)
        self.assertEqual(transaction.settlement_amount, 1051)
        self.assertNotEqual(
            transaction.settlement_amount,
            transaction.principal * transaction.price / 100
            + transaction.accrued_interest_paid
            + transaction.commission_amount,
        )

    def test_value_endpoint_clears_amounts_without_an_isin(self):
        self.assertEqual(
            get_calculated_amounts(
                isin=None,
                settlement_date="2025-12-31",
                quantity_face_value=10,
                price=105,
                accrued_interest_paid=12,
                commission=2,
            ),
            {
                "principal": 0.0,
                "commission_amount": 0.0,
                "settlement_amount": 0.0,
                "accrued_interest_calculated": 0.0,
            },
        )

    def test_uses_authoritative_bond_snapshot(self):
        bond = make_bond()
        transaction = make_transaction(
            bond,
            make_portfolio(),
            face_value_per_unit=999,
            currency="KES",
            coupon_rate=99,
            issue_date="2000-01-01",
            maturity_date="2099-01-01",
        )

        self.assertEqual(transaction.face_value_per_unit, bond.face_value_per_unit)
        self.assertEqual(transaction.currency, bond.currency)
        self.assertEqual(transaction.coupon_rate, bond.coupon_rate)
        self.assertEqual(getdate(transaction.issue_date), getdate(bond.issue_date))
        self.assertEqual(getdate(transaction.maturity_date), getdate(bond.maturity_date))

    def test_financial_value_boundaries(self):
        transaction = make_transaction(make_bond(), make_portfolio())

        for quantity in (0, -1):
            with self.subTest(quantity=quantity):
                transaction.quantity_face_value = quantity
                with self.assertRaisesRegex(ValidationError, "Quantity.*greater than zero"):
                    transaction.save()
                transaction.reload()
        transaction.quantity_face_value = 1
        transaction.save()

        for price in (0, -0.01):
            with self.subTest(price=price):
                transaction.price = price
                with self.assertRaisesRegex(ValidationError, "Price must be greater than zero"):
                    transaction.save()
                transaction.reload()
        transaction.price = 0.01
        transaction.save()

        transaction.commission = 0
        transaction.save()
        transaction.commission = -0.01
        with self.assertRaisesRegex(ValidationError, "Commission must be zero"):
            transaction.save()

    def test_rejects_invalid_transaction_type_and_missing_inputs(self):
        bond = make_bond()
        portfolio = make_portfolio()

        invalid_type = make_transaction(bond, portfolio, insert=False, transaction_type="Transfer")
        with self.assertRaisesRegex(ValidationError, "must be Purchase or Sale"):
            invalid_type.insert()

        missing_trade_date = make_transaction(bond, portfolio, insert=False, trade_date=None)
        with self.assertRaisesRegex(ValidationError, "Trade Date is required"):
            missing_trade_date.insert()

    def test_rejects_sale_larger_than_position(self):
        bond = make_bond()
        portfolio = make_portfolio()
        make_transaction(bond, portfolio)

        sale = frappe.get_doc(
            {
                "doctype": "Bond Transaction",
                "transaction_reference": unique_name("TEST-SALE"),
                "trade_date": "2025-12-30",
                "settlement_date": "2025-12-31",
                "isin": bond.name,
                "portfolio_name": portfolio.name,
                "transaction_type": "Sale",
                "quantity_face_value": 11,
                "price": 105,
                "accrued_interest_paid": 0,
                "commission": 0,
                "face_value_per_unit": bond.face_value_per_unit,
                "currency": bond.currency,
                "issue_date": bond.issue_date,
                "maturity_date": bond.maturity_date,
            }
        )

        self.assertRaises(ValidationError, sale.insert)

    def test_allows_settlement_on_issue_and_maturity_dates(self):
        bond = make_bond()

        issue_date_transaction = make_transaction(
            bond,
            make_portfolio(),
            trade_date=bond.issue_date,
            settlement_date=bond.issue_date,
        )
        maturity_date_transaction = make_transaction(
            bond, make_portfolio(), settlement_date=bond.maturity_date
        )

        self.assertEqual(issue_date_transaction.settlement_date, bond.issue_date)
        self.assertEqual(maturity_date_transaction.settlement_date, bond.maturity_date)

    def test_rejects_dates_outside_bond_and_trade_after_settlement(self):
        bond = make_bond()
        portfolio = make_portfolio()

        for trade_date, settlement_date, message in (
            ("2024-12-31", "2025-01-01", "Trade Date must be on or after"),
            ("2025-01-01", "2024-12-31", "Settlement Date must be on or after"),
            ("2027-01-02", "2027-01-02", "Trade Date must be on or before"),
            ("2027-01-01", "2027-01-02", "Settlement Date must be on or before"),
            ("2026-01-02", "2026-01-01", "Trade Date must be on or before Settlement"),
        ):
            with self.subTest(trade_date=trade_date, settlement_date=settlement_date):
                transaction = make_transaction(
                    bond,
                    portfolio,
                    insert=False,
                    trade_date=trade_date,
                    settlement_date=settlement_date,
                )
                with self.assertRaisesRegex(ValidationError, message):
                    transaction.insert()

    def test_sale_equal_to_position_and_same_day_purchase_is_allowed(self):
        bond = make_bond()
        portfolio = make_portfolio()
        purchase = make_transaction(bond, portfolio)
        sale = make_transaction(
            bond,
            portfolio,
            transaction_type="Sale",
            quantity_face_value=purchase.quantity_face_value,
        )

        self.assertEqual(get_position(bond.name, sale.settlement_date, portfolio.name), 0)

    def test_backdating_or_reducing_purchase_cannot_break_later_ledger(self):
        bond = make_bond()
        portfolio = make_portfolio()
        purchase = make_transaction(
            bond,
            portfolio,
            trade_date="2025-06-01",
            settlement_date="2025-06-02",
        )
        make_transaction(
            bond,
            portfolio,
            transaction_type="Sale",
            trade_date="2025-07-01",
            settlement_date="2025-07-02",
            quantity_face_value=10,
        )

        purchase.quantity_face_value = 9
        with self.assertRaisesRegex(ValidationError, "position negative"):
            purchase.save()

        purchase.reload()
        purchase.quantity_face_value = 10
        purchase.trade_date = "2025-08-01"
        purchase.settlement_date = "2025-08-02"
        with self.assertRaisesRegex(ValidationError, "position negative"):
            purchase.save()

    def test_purchase_cannot_be_deleted_or_moved_when_a_sale_depends_on_it(self):
        bond = make_bond()
        portfolio = make_portfolio()
        purchase = make_transaction(bond, portfolio)
        make_transaction(
            bond,
            portfolio,
            transaction_type="Sale",
            trade_date="2026-01-01",
            settlement_date="2026-01-02",
            quantity_face_value=10,
        )

        with self.assertRaisesRegex(ValidationError, "position negative"):
            purchase.delete()

        purchase.reload()
        purchase.portfolio_name = make_portfolio().name
        with self.assertRaisesRegex(ValidationError, "position negative"):
            purchase.save()

    def test_maturity_payment_position_is_inclusive_but_end_of_day_is_zero(self):
        bond = make_bond()
        portfolio = make_portfolio()
        make_transaction(
            bond,
            portfolio,
            trade_date=bond.maturity_date,
            settlement_date=bond.maturity_date,
        )

        self.assertEqual(get_position_for_payment(bond.name, bond.maturity_date, portfolio.name), 10)
        self.assertEqual(get_position(bond.name, bond.maturity_date, portfolio.name), 0)
