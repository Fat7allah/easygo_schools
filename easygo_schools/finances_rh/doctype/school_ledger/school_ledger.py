import frappe
from frappe.model.document import Document
from frappe.utils import nowdate, flt, cint
from frappe import _


class SchoolLedger(Document):
    def validate(self):
        self.validate_amounts()
        self.set_account_name()
        self.validate_voucher()
        
    def validate_amounts(self):
        """Validate debit and credit amounts"""
        if not self.debit and not self.credit:
            frappe.throw(_("Either debit or credit amount is required"))
            
        if self.debit and self.credit:
            frappe.throw(_("Cannot have both debit and credit amounts"))
            
        if self.debit and self.debit < 0:
            frappe.throw(_("Debit amount cannot be negative"))
            
        if self.credit and self.credit < 0:
            frappe.throw(_("Credit amount cannot be negative"))
            
    def set_account_name(self):
        """Set account name from School Account"""
        if self.account:
            self.account_name = frappe.db.get_value("School Account", self.account, "account_name")
            
    def validate_voucher(self):
        """Validate voucher exists"""
        if self.voucher_type and self.voucher_no:
            if not frappe.db.exists(self.voucher_type, self.voucher_no):
                frappe.throw(_("Voucher {0} {1} does not exist").format(self.voucher_type, self.voucher_no))
                
    def before_submit(self):
        self.calculate_balance()
        
    def calculate_balance(self):
        """Calculate running balance"""
        # Get previous balance
        previous_balance = self.get_previous_balance()
        
        # Calculate new balance
        if self.debit:
            self.balance = flt(previous_balance) + flt(self.debit)
        else:
            self.balance = flt(previous_balance) - flt(self.credit)
            
    def get_previous_balance(self):
        """Get previous balance for the account"""
        previous_entry = frappe.db.sql("""
            SELECT balance
            FROM `tabSchool Ledger`
            WHERE account = %s AND posting_date <= %s
            AND docstatus = 1 AND name != %s
            ORDER BY posting_date DESC, creation DESC
            LIMIT 1
        """, (self.account, self.posting_date, self.name))
        
        if previous_entry:
            return previous_entry[0][0] or 0
        else:
            # Get opening balance from account
            opening_balance = frappe.db.get_value("School Account", self.account, "opening_balance")
            return opening_balance or 0
            
    def on_submit(self):
        self.update_account_balance()
        
    def on_cancel(self):
        self.update_account_balance()
        
    def update_account_balance(self):
        """Update account balance in School Account"""
        # Calculate current balance for the account
        balance = frappe.db.sql("""
            SELECT 
                SUM(CASE WHEN debit > 0 THEN debit ELSE -credit END) as balance
            FROM `tabSchool Ledger`
            WHERE account = %s AND docstatus = 1
        """, (self.account,))
        
        current_balance = balance[0][0] if balance and balance[0][0] else 0
        
        # Get opening balance
        opening_balance = frappe.db.get_value("School Account", self.account, "opening_balance") or 0
        total_balance = flt(opening_balance) + flt(current_balance)
        
        # Update account balance
        frappe.db.set_value("School Account", self.account, "balance", total_balance)


@frappe.whitelist()
def make_gl_entry(voucher_type, voucher_no, entries):
    """Create general ledger entries"""
    if isinstance(entries, str):
        import json
        entries = json.loads(entries)
        
    gl_entries = []
    
    for entry in entries:
        gl_entry = frappe.new_doc("School Ledger")
        gl_entry.account = entry.get("account")
        gl_entry.posting_date = entry.get("posting_date") or nowdate()
        gl_entry.voucher_type = voucher_type
        gl_entry.voucher_no = voucher_no
        gl_entry.debit = entry.get("debit", 0)
        gl_entry.credit = entry.get("credit", 0)
        gl_entry.against_account = entry.get("against_account")
        gl_entry.cost_center = entry.get("cost_center")
        gl_entry.party_type = entry.get("party_type")
        gl_entry.party = entry.get("party")
        gl_entry.remarks = entry.get("remarks")
        gl_entry.reference_type = entry.get("reference_type")
        gl_entry.reference_name = entry.get("reference_name")
        
        gl_entry.insert()
        gl_entry.submit()
        gl_entries.append(gl_entry.name)
        
    return gl_entries


@frappe.whitelist()
def get_account_balance(account, from_date=None, to_date=None):
    """Get account balance for specified period"""
    conditions = ["account = %s", "docstatus = 1"]
    values = [account]
    
    if from_date:
        conditions.append("posting_date >= %s")
        values.append(from_date)
        
    if to_date:
        conditions.append("posting_date <= %s")
        values.append(to_date)
        
    result = frappe.db.sql(f"""
        SELECT 
            SUM(debit) as total_debit,
            SUM(credit) as total_credit,
            SUM(CASE WHEN debit > 0 THEN debit ELSE -credit END) as net_balance
        FROM `tabSchool Ledger`
        WHERE {' AND '.join(conditions)}
    """, values, as_dict=True)
    
    if result:
        data = result[0]
        # Add opening balance if from_date is specified
        opening_balance = 0
        if from_date:
            opening_result = frappe.db.sql("""
                SELECT SUM(CASE WHEN debit > 0 THEN debit ELSE -credit END) as balance
                FROM `tabSchool Ledger`
                WHERE account = %s AND posting_date < %s AND docstatus = 1
            """, (account, from_date))
            
            if opening_result and opening_result[0][0]:
                opening_balance = opening_result[0][0]
            else:
                # Get account opening balance
                account_opening = frappe.db.get_value("School Account", account, "opening_balance")
                opening_balance = account_opening or 0
                
        return {
            "opening_balance": opening_balance,
            "total_debit": data.total_debit or 0,
            "total_credit": data.total_credit or 0,
            "net_movement": data.net_balance or 0,
            "closing_balance": opening_balance + (data.net_balance or 0)
        }
        
    return {
        "opening_balance": 0,
        "total_debit": 0,
        "total_credit": 0,
        "net_movement": 0,
        "closing_balance": 0
    }


@frappe.whitelist()
def get_trial_balance(from_date=None, to_date=None):
    """Get trial balance for all accounts"""
    conditions = ["docstatus = 1"]
    values = []
    
    if from_date:
        conditions.append("posting_date >= %s")
        values.append(from_date)
        
    if to_date:
        conditions.append("posting_date <= %s")
        values.append(to_date)
        
    accounts = frappe.db.sql(f"""
        SELECT 
            account,
            account_name,
            SUM(debit) as total_debit,
            SUM(credit) as total_credit,
            SUM(CASE WHEN debit > 0 THEN debit ELSE -credit END) as balance
        FROM `tabSchool Ledger`
        WHERE {' AND '.join(conditions)}
        GROUP BY account, account_name
        HAVING (total_debit > 0 OR total_credit > 0)
        ORDER BY account_name
    """, values, as_dict=True)
    
    # Add opening balances if from_date is specified
    for account in accounts:
        if from_date:
            opening_result = frappe.db.sql("""
                SELECT SUM(CASE WHEN debit > 0 THEN debit ELSE -credit END) as balance
                FROM `tabSchool Ledger`
                WHERE account = %s AND posting_date < %s AND docstatus = 1
            """, (account.account, from_date))
            
            opening_balance = 0
            if opening_result and opening_result[0][0]:
                opening_balance = opening_result[0][0]
            else:
                # Get account opening balance
                account_opening = frappe.db.get_value("School Account", account.account, "opening_balance")
                opening_balance = account_opening or 0
                
            account.opening_balance = opening_balance
            account.closing_balance = opening_balance + account.balance
        else:
            account.opening_balance = 0
            account.closing_balance = account.balance
            
    return accounts


@frappe.whitelist()
def get_ledger_analytics():
    """Get ledger analytics"""
    return {
        "total_entries": frappe.db.count("School Ledger", {"docstatus": 1}),
        "total_debit": frappe.db.sql("""
            SELECT SUM(debit) FROM `tabSchool Ledger` WHERE docstatus = 1
        """)[0][0] or 0,
        "total_credit": frappe.db.sql("""
            SELECT SUM(credit) FROM `tabSchool Ledger` WHERE docstatus = 1
        """)[0][0] or 0,
        "by_voucher_type": frappe.db.sql("""
            SELECT voucher_type, COUNT(*) as count, SUM(debit + credit) as amount
            FROM `tabSchool Ledger`
            WHERE docstatus = 1
            GROUP BY voucher_type
        """, as_dict=True),
        "by_account_type": frappe.db.sql("""
            SELECT sa.account_type, COUNT(sl.name) as entries, 
                   SUM(sl.debit + sl.credit) as amount
            FROM `tabSchool Ledger` sl
            JOIN `tabSchool Account` sa ON sl.account = sa.name
            WHERE sl.docstatus = 1
            GROUP BY sa.account_type
        """, as_dict=True),
        "recent_entries": frappe.db.sql("""
            SELECT account_name, posting_date, voucher_type, debit, credit
            FROM `tabSchool Ledger`
            WHERE docstatus = 1
            ORDER BY posting_date DESC, creation DESC
            LIMIT 10
        """, as_dict=True)
    }


def create_gl_entries_for_voucher(doc, method):
    """Hook to create GL entries when vouchers are submitted"""
    if hasattr(doc, 'make_gl_entries'):
        doc.make_gl_entries()


def cancel_gl_entries_for_voucher(doc, method):
    """Hook to cancel GL entries when vouchers are cancelled"""
    # Cancel all GL entries for this voucher
    gl_entries = frappe.get_all("School Ledger", {
        "voucher_type": doc.doctype,
        "voucher_no": doc.name,
        "docstatus": 1
    })
    
    for entry in gl_entries:
        gl_doc = frappe.get_doc("School Ledger", entry.name)
        gl_doc.cancel()
