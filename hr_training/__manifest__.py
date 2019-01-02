#-*- coding:utf-8 -*-
# This module is develop by Mast Information Technology
# Contact: +973-17382342, info@mast-it.com
{
    'name': 'Employees Training',
    'version': '1.0',
    'category': 'hr',
    'description': """
Add Employees Training Records
    """,
    'author':'Mast',
    'website': 'https://mast-it.com',
    'depends': ['hr'],
    'data': ['views/hr_training_view.xml', 'views/hr_training_view.xml', 'security/hr_security.xml', 'security/ir.model.access.csv'],
    'installable': True,
    'auto_install': False,
}
