# -*- coding: utf-8 -*-

{
    'name': 'Employees Warning',
    'category': 'Human Resources',
    'version': '1.0',
    'description':'',
	'author': 'Mast',
    'depends': ['hr_payroll_account'],
    'auto_install': False,
    'data': ['data/hr_warning_data.xml', 'security/ir.model.access.csv', 'security/security.xml', 'views/hr_warning_view.xml', 'report/hr_warning_report.xml'],
    'qweb': [],
}
