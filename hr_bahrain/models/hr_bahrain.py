# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


import time
from datetime import datetime
from datetime import time as datetime_time
from dateutil import relativedelta

import babel

from odoo import api, fields, models, tools, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError, ValidationError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT

class Currency(models.Model):
    _inherit = "res.currency"

    # Note: 'code' column was removed as of v6.0, the 'name' should now hold the ISO code.
    name = fields.Char(string='Currency', size=3, required=True, help="Currency Code (ISO 4217)", translate=True)
    symbol = fields.Char(help="Currency sign, to be used when printing amounts.", required=True, translate=True)
    currency_unit_label = fields.Char(string="Currency Unit", help="Currency Unit Name", translate=True)
    currency_subunit_label = fields.Char(string="Currency Subunit", help="Currency Subunit Name", translate=True)


class hr_holidays(models.Model):
    _inherit = "hr.leave"

    def create_annual(self):
        contracts = self.env['hr.contract'].search([('state','in',['open','pending'])])
        for contract in contracts:
            annual = contract.holidays
            monthly = annual/12
            total_days = (datetime.utcnow().date() - datetime.strptime(contract.date_start, DEFAULT_SERVER_DATE_FORMAT).date()).days
            diff = annual/365.25
            totals = diff*total_days
            allocations = self.search([('state','=','validate'),('employee_id','=',contract.employee_id.id), ('holiday_status_id','=',1),('type','=','add')])
            allocation_days = 0
            for allocation in allocations:
                allocation_days += allocation.number_of_days_temp
            total = int(totals - allocation_days)
            if total>0:
               self.create({'name':'Auto Create Leaves', 'state':'validate', 'employee_id':contract.employee_id.id, 'holiday_status_id':1, 'type':'add','number_of_days_temp':total})

class hr_contract(models.Model):
    _inherit = 'hr.contract'

    holidays = fields.Float(string='Legal Leaves', help="Number of days of paid leaves the employee gets per year.", track_visibility="onchange")
    mobile = fields.Monetary(string="Mobile Allowance", track_visibility="onchange", help="The employee mobile subscription will be paid up to this amount.")
    commission_amount = fields.Monetary(string="Commission on Target", track_visibility="onchange", help="Monthly gross amount that the employee receives if the target is reached.")
    commission_percentage = fields.Float(string="Commission on Target", track_visibility="onchange", help="Monthly gross percentage that the employee receives if the target is reached.")
    transport = fields.Monetary(string="Transport Allowance", track_visibility="onchange", help="The employee transport subscription will be paid up to this amount.")
    house = fields.Monetary(string="House Allowance", track_visibility="onchange", help="The employee house subscription will be paid up to this amount.")
    other_allowances = fields.Monetary(string="Other Allowances", track_visibility="onchange")
    airticket = fields.Monetary(string="Airticket Allowance", track_visibility="onchange", help="The employee Air Ticket allowanace will be paid up to this amount.")
    indemnity = fields.Boolean(string="Indemnity", track_visibility="onchange", help="The employee End of Service.")
    gosi_employee = fields.Float(string="Gosi Employee", track_visibility="onchange", help="The employee insurance subscription will be paid up to this amount.")
    gosi_company = fields.Float(string="Gosi Company", track_visibility="onchange", help="The employee insurance subscription will be paid up to this amount.")
    lmra = fields.Monetary(string="LMRA", track_visibility="onchange", help="The employee LMRA subscription will be paid up to this amount.")

class ResourceResource(models.Model):
    _inherit = "resource.resource"

    name = fields.Char(required=True, translate=True)

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    name = fields.Char(related='resource_id.name', store=True, oldname='name_related', translate=True)
    disabled = fields.Boolean(string="Disabled", help="If the employee is declared disabled by law", groups="hr.group_hr_user")
    disabled_spouse_bool = fields.Boolean(string='Disabled Spouse', help='if recipient spouse is declared disabled by law', groups="hr.group_hr_user")
    disabled_children_bool = fields.Boolean(string='Disabled Children', help='if recipient children is/are declared disabled by law', groups="hr.group_hr_user")
    disabled_children_number = fields.Integer('Number of disabled children', groups="hr.group_hr_user")
    dependent_children = fields.Integer(compute='_compute_dependent_children', string='Considered number of dependent children', groups="hr.group_hr_user")
    other_dependent_people = fields.Boolean(string="Other Dependent People", help="If other people are dependent on the employee", groups="hr.group_hr_user")
    other_senior_dependent = fields.Integer('# seniors (>=65)', help="Number of seniors dependent on the employee, including the disabled ones", groups="hr.group_hr_user")
    other_disabled_senior_dependent = fields.Integer('# disabled seniors (>=65)', groups="hr.group_hr_user")
    other_juniors_dependent = fields.Integer('# people (<65)', help="Number of juniors dependent on the employee, including the disabled ones", groups="hr.group_hr_user")
    other_disabled_juniors_dependent = fields.Integer('# disabled people (<65)', groups="hr.group_hr_user")
    dependent_seniors = fields.Integer(compute='_compute_dependent_people', string="Considered number of dependent seniors", groups="hr.group_hr_user")
    dependent_juniors = fields.Integer(compute='_compute_dependent_people', string="Considered number of dependent juniors", groups="hr.group_hr_user")

    @api.onchange('disabled_children_bool')
    def _onchange_disabled_children_bool(self):
        self.disabled_children_number = 0

    @api.onchange('other_dependent_people')
    def _onchange_other_dependent_people(self):
        self.other_senior_dependent = 0.0
        self.other_disabled_senior_dependent = 0.0
        self.other_juniors_dependent = 0.0
        self.other_disabled_juniors_dependent = 0.0

    @api.depends('disabled_children_bool', 'disabled_children_number', 'children')
    def _compute_dependent_children(self):
        for employee in self:
            if employee.disabled_children_bool:
                employee.dependent_children = employee.children + employee.disabled_children_number
            else:
                employee.dependent_children = employee.children

    @api.depends('other_dependent_people', 'other_senior_dependent',
        'other_disabled_senior_dependent', 'other_juniors_dependent', 'other_disabled_juniors_dependent')
    def _compute_dependent_people(self):
        for employee in self:
            employee.dependent_seniors = employee.other_senior_dependent + employee.other_disabled_senior_dependent
            employee.dependent_juniors = employee.other_juniors_dependent + employee.other_disabled_juniors_dependent
