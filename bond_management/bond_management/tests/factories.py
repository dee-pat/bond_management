import frappe


def unique_name(prefix):
    return f"{prefix}-{frappe.generate_hash(length=8)}"


def make_bond(**overrides):
    isin = unique_name("TEST-BOND")
    values = {
        "doctype": "Bond Master",
        "bond_name": isin,
        "isin": isin,
        "currency": "USD",
        "face_value_per_unit": 100,
        "coupon_rate": 7,
        "coupon_frequency": "2",
        "issue_date": "2025-01-01",
        "maturity_date": "2027-01-01",
        "first_coupon_date": "2025-07-01",
        "day_count_convention": "30E/360",
        "bond_type": "Kenya Treasury Bond",
        "principal_schedule": [{"repayment_date": "2027-01-01", "principal_units": 100}],
    }
    values.update(overrides)
    return frappe.get_doc(values).insert()


def make_portfolio(**overrides):
    portfolio_name = unique_name("TEST-PORTFOLIO")
    account_no = overrides.pop("account_no", unique_name("TEST-ACCOUNT"))
    values = {
        "doctype": "Bond Portfolio",
        "portfolio_name": portfolio_name,
        "account_no": account_no,
        "transaction_account_no": account_no,
        "statement_pdf_password": "test-password",
    }
    values.update(overrides)
    return frappe.get_doc(values).insert()


def make_statement(portfolio, statement_date="2025-12-31", *, insert=True, **overrides):
    values = {
        "doctype": "Bond Statement",
        "portfolio_name": portfolio.name,
        "statement_date": statement_date,
        "attachment": f"/private/files/{unique_name('test-statement')}.pdf",
    }
    values.update(overrides)
    statement = frappe.get_doc(values)
    statement.flags.ignore_statement_pdf = True
    return statement.insert() if insert else statement


def make_transaction(bond, portfolio, *, insert=True, **overrides):
    values = {
        "doctype": "Bond Transaction",
        "transaction_reference": unique_name("TEST-TRANSACTION"),
        "trade_date": "2025-12-30",
        "settlement_date": "2025-12-31",
        "isin": bond.name,
        "portfolio_name": portfolio.name,
        "transaction_type": "Purchase",
        "quantity_face_value": 10,
        "price": 105,
        "accrued_interest_paid": 1,
        "commission": 2,
        "face_value_per_unit": bond.face_value_per_unit,
        "currency": bond.currency,
        "issue_date": bond.issue_date,
        "maturity_date": bond.maturity_date,
    }
    values.update(overrides)
    document = frappe.get_doc(values)
    return document.insert() if insert else document


def make_market_date(bond, market_price=100, date="2025-12-30"):
    existing = frappe.qb.get_query(
        "Bond Market Date",
        fields=["name"],
        filters={"date": date},
        limit=1,
        ignore_permissions=False,
    ).run(pluck=True)
    if existing:
        market_date = frappe.get_doc("Bond Market Date", existing[0])
        market_date.append(
            "bond_market_prices",
            {"isin": bond.name, "market_price": market_price, "currency": bond.currency},
        )
        return market_date.save()

    return frappe.get_doc(
        {
            "doctype": "Bond Market Date",
            "date": date,
            "bond_market_prices": [
                {"isin": bond.name, "market_price": market_price, "currency": bond.currency}
            ],
        }
    ).insert()


def make_exchange_rate(
    portfolio,
    from_currency="KES",
    rate="0.00772499",
    rate_date="2025-12-30",
    **overrides,
):
    values = {
        "doctype": "Bond Exchange Rate",
        "portfolio_name": portfolio.name,
        "rate_date": rate_date,
        "from_currency": from_currency,
        "to_currency": "USD",
        "rate": rate,
    }
    values.update(overrides)
    return frappe.get_doc(values).insert()
