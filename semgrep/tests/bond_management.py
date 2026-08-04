from decimal import Decimal

import frappe


def invalid_manual_transaction_boundaries():
    # ruleid: bond-management-no-manual-transaction-boundary
    frappe.db.commit()
    # ruleid: bond-management-no-manual-transaction-boundary
    frappe.db.rollback()


def valid_framework_transaction_boundary():
    return frappe.db.exists("Bond Master", "BOND-0001")


def invalid_binary_float_decimal_values():
    # ruleid: bond-management-decimal-from-float-literal
    positive = Decimal(0.1)  # noqa: RUF032
    # ruleid: bond-management-decimal-from-float-literal
    negative = Decimal(-1.25)  # noqa: RUF032
    return positive, negative


def valid_decimal_values():
    # ok: bond-management-decimal-from-float-literal
    from_string = Decimal("0.1")
    # ok: bond-management-decimal-from-float-literal
    from_normalized_value = Decimal(str(0.1))
    return from_string, from_normalized_value
