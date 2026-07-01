# Copyright (c) 2026, Deepak Patel and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
# from frappe.tests.utils import IntegrationTestCase
from frappe.exceptions import ValidationError

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]



class IntegrationTestBondMaster(IntegrationTestCase):
    """
    Integration tests for BondMaster.
    Use this class for testing interactions between multiple components.
    """
    def test_maturity_before_issue_fails(self):
        doc = frappe.get_doc({
            "doctype": "Bond Master",
            "issue_date": "2024-01-10",
            "maturity_date": "2024-01-01"
        })
        self.assertRaises(ValidationError, doc.insert)

    def test_valid_dates_pass(self):
        doc = frappe.get_doc({
            "doctype": "Bond Master",
            "issue_date": "2024-01-01",
            "maturity_date": "2024-02-01"
        })
        doc.insert()  # should not raise

    def test_equal_dates_behavior(self):
        doc = frappe.get_doc({
            "doctype": "Bond Master",
            "issue_date": "2024-01-01",
            "maturity_date": "2024-01-01"
        })
        self.assertRaises(ValidationError, doc.insert)