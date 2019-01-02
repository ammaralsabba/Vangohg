# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


import time
from datetime import datetime, timedelta
from datetime import time as datetime_time
from dateutil import relativedelta

import babel

from odoo import api, fields, models, tools, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError, ValidationError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT,DEFAULT_SERVER_DATE_FORMAT

class hr_employee(models.Model):
    _inherit = 'hr.employee'

    warning_ids = fields.One2many('hr.warning', 'employee_id', string='Warnings')
    warnings_count = fields.Integer(compute='_compute_warning_count', string='Warnings')

    def _compute_warning_count(self):
        warning_data = self.env['hr.warning'].sudo().read_group([('employee_id', 'in', self.ids)], ['employee_id'], ['employee_id'])
        result = dict((data['employee_id'][0], data['employee_id_count']) for data in warning_data)
        for employee in self:
            employee.warnings_count = result.get(employee.id, 0)


class hr_warning_stage(models.Model):
    _name = 'hr.warning.stage'
    _description = 'Employees Warning Stages'

    name = fields.Char(string='Name', required=True)
    type = fields.Selection([('amount','Amount'), ('hour', 'Hours'), ('wage', 'Wage')], string='Type')
    fine = fields.Float(string='Fine')
    expiry_days = fields.Integer(string='Expiry After(Days)')
    stage_id = fields.Many2one('hr.warning.type', string='Type')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id)

class hr_warning_type(models.Model):
    _name = 'hr.warning.type'
    _description = 'Employees Warning Types'
    _inherit = 'mail.thread'

    name = fields.Char(string='Name', track_visibility='onchange', required=True)
    stage_ids = fields.One2many('hr.warning.stage', 'stage_id', string='Stages')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id)

class hr_warning(models.Model):
    _name = 'hr.warning'
    _description = 'Employees Warning'
    _inherit = 'mail.thread'

    @api.depends('paid', 'amount')
    def _balance(self):
        for line in self:
            line.balance =  line.amount - line.paid

    name = fields.Char(string='Description', readonly=True, track_visibility='onchange', states={'new': [('readonly', False)]}, required=True)
    type = fields.Many2one('hr.warning.type', string='Type', readonly=True, track_visibility='onchange', states={'new': [('readonly', False)]}, required=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', readonly=True, track_visibility='onchange', states={'new': [('readonly', False)]}, required=True)
    date = fields.Date(string='Date', default=datetime.today(), readonly=True, track_visibility='onchange', copy=False, states={'new': [('readonly', False)]}, required=True)
    amount = fields.Float(string='Amount', digits=dp.get_precision('Payroll'), readonly=True, track_visibility='onchange', copy=False)
    paid = fields.Float(string='Paid', digits=dp.get_precision('Payroll'), readonly=True, track_visibility='onchange', copy=False)
    balance = fields.Float(compute='_balance', string='Amount Due', digits=dp.get_precision('Payroll'), readonly=True, copy=False)
    expiry_date = fields.Date(string='Expiry Date', readonly=True, copy=False)
    state = fields.Selection([('new', 'New'), ('open', 'Running'), ('expire', 'Expired'), ('reject', 'Rejected'), ('cancel','Cancelled')], string='State', default='new', readonly=True, track_visibility='onchange', copy=False)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id)

    @api.model
    def check_expire(self):
        records = self.search(['|',('expiry_date','<',datetime.today().strftime(DEFAULT_SERVER_DATE_FORMAT)), ('expiry_date','=',False)])
        for record in records:
            record.state = 'expire'
        return True

    @api.multi
    def action_reject(self):
        for rec in self:
            if rec.state != 'new':
                raise UserError(_("Only an new warning can be reject."))
            rec.write({'state': 'reject'})
        return True

    @api.multi
    def action_draft(self):
        for rec in self:
            if rec.state not in ('reject', 'cancel'):
                raise UserError(_("Only a cancel or reject warning can be set to new."))
            rec.write({'state': 'new'})
        return True

    @api.multi
    def action_cancel(self):
        for rec in self:
            if rec.state != 'new':
                raise UserError(_("Only an new warning can be cancel."))
            rec.write({'state': 'cancel'})
        return True

    @api.multi
    def action_confirm(self):
        for rec in self:
            if rec.state != 'new':
                raise UserError(_("Only an new warning can be confirm."))
            rec.write({'state': 'open'})
            amount = 0
            warnings = self.search([('state','=','open'), ('type', '=', rec.type.id)])
            count = len(warnings) - 1
            if count>=0 and rec.type.stage_ids and rec.type.stage_ids[count]:
                if rec.type.stage_ids[count].type=='amount':
                    amount = rec.type.stage_id[count].fine
                elif rec.type.stage_ids[count].type=='hour':
                    amount = rec.employee_id.contract_id.wage*((12/365)/8)*rec.type.stage_ids[count].fine
                elif rec.type.stage_ids[count].type=='wage':
                    amount = rec.employee_id.contract_id.wage*rec.type.stage_ids[count].fine/100
                rec.expiry_date = fields.Date.from_string(rec.date) + timedelta(days=rec.type.stage_ids[count].expiry_days)
                rec.amount = amount
        return True

    @api.multi
    def unlink(self):
        if any(rec.state in ('open') for rec in self):
            raise UserError(_('It is not allowed to delete a warning that already confirmed.'))
        return super(hr_warning, self).unlink()

class hr_payslip(models.Model):
    _inherit = 'hr.payslip'

    @api.multi
    def action_payslip_done(self):
        for payslip in self:
            amount = 0
            for line in payslip.line_ids:
                if line.code == 'WA':
                    amount += line.amount
        warnings = self.env['hr.warning'].search([('employee_id','=',self.employee_id.id), ('state','in',['open','expire']), ('balance','>',0)])
        for warning in warnings:
            if warning.balance>=(amount*-1):
                warning.paid += (amount*-1)
                amount = 0
            elif warning.balance<(amount*-1):
                warning.paid += warning.balance
                amount += warning.balance
        return super(hr_payslip, self).action_payslip_done()

    @api.model
    def get_inputs(self, contracts, date_from, date_to):
        res = super(hr_payslip, self).get_inputs(contracts, date_from, date_to)
        warnings = self.env['hr.warning'].search([('employee_id','=',self.employee_id.id), ('balance','>',0), ('state','in',['open','expire'])])
        warning = 0
        for w in warnings:
            warning += w.amount
        res += [{'name': 'Warning', 'code': 'Warning', 'contract_id': self.contract_id.id, 'amount':warning*-1}]
        return res