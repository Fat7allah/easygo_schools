'''
Copyright (c) 2024, Fat7allah and contributors
For license information, please see license.txt
'''

import frappe

def execute(filters=None):
	columns, data = [], []
	
	columns = [
		_("Level") + ":Link/Level:150",
		_("Total Students") + ":Int:120",
		_("Success Rate") + ":Percent:120",
		_("Abandonment Rate") + ":Percent:120"
	]

	data = get_data(filters)
	
	return columns, data

def get_data(filters):
	conditions = ""
	if filters.get("academic_year"):
		conditions += f" AND e.academic_year = '{filters.get('academic_year')}'"
	if filters.get("level"):
		conditions += f" AND e.level = '{filters.get('level')}'"

	data = frappe.db.sql(f'''
		SELECT
			e.level,
			count(e.student) as total_students,
			(SUM(CASE WHEN rc.is_pass = 1 THEN 1 ELSE 0 END) * 100 / count(e.student)) as success_rate,
			(SUM(CASE WHEN s.status = 'Transferred' THEN 1 ELSE 0 END) * 100 / count(e.student)) as abandonment_rate
		FROM
			`tabEnrollment` e
		LEFT JOIN
			`tabReport Card` rc ON e.student = rc.student AND e.academic_year = rc.academic_year
		LEFT JOIN
			`tabStudent` s ON e.student = s.name
		WHERE 1=1
		{conditions}
		GROUP BY
			e.level
	''', as_list=1)

	return data

