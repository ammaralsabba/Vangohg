# -*- coding: utf-8 -*-

{
    'name': 'Employees Loan',
    'category': 'Human Resources',
    'version': '1.0',
    'description':'',
	'author': 'Mast',
    'depends': ['hr_payroll_account', 'account_accountant'],
    'auto_install': False,
    'data': ['data/hr_loan_data.xml', 'security/ir.model.access.csv', 'security/security.xml', 'views/hr_loan_view.xml', 'report/hr_loan_report.xml'],
    'qweb': [],
}
