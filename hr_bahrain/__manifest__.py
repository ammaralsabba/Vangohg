# -*- coding: utf-8 -*-

{
    'name': 'Bahrain HR',
    'category': 'Human Resources',
    'version': '1.0',
    'description':'',
	'author': 'Mast',
    'depends': ['hr_contract', 'hr_payroll', 'hr_holidays'],
    'auto_install': False,
    'data': ['views/hr_bahrain_views.xml', 'data/hr_bahrain_data.xml', 'report/hr_contract_report.xml'],
    'qweb': [],
}
