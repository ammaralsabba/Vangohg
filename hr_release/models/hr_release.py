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

class hr_release_reason(models.Model):
    _name = 'hr.release.reason'
    _description = 'Employees Release Reasons'

    name = fields.Char(string='Name', required=True)

class hr_release(models.Model):
    _name = 'hr.release'
    _description = 'Employees Release'
    _inherit = 'mail.thread'

    name = fields.Char(string='Description', readonly=True, track_visibility='onchange', states={'new': [('readonly', False)]}, required=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', readonly=True, track_visibility='onchange', states={'new': [('readonly', False)]}, required=True)
    reason = fields.Many2one('hr.release.reason', string='Reason', readonly=True, track_visibility='onchange', states={'new': [('readonly', False)]}, required=True)
    note = fields.Text(string='Note', readonly=True, states={'new': [('readonly', False)]})
    date = fields.Date(string='Date', default=datetime.today(), readonly=True, track_visibility='onchange', copy=False, states={'new': [('readonly', False)]}, required=True)
    state = fields.Selection([('new', 'New'), ('approve', 'Approved'), ('reject', 'Rejected'), ('cancel','Cancelled')], string='State', default='new', readonly=True, track_visibility='onchange', copy=False)
    company_id = fields.Many2one('res.company', related='employee_id.company_id', string='Company', readonly=True)

    @api.multi
    def action_reject(self):
        for rec in self:
            if rec.state != 'new':
                raise UserError(_("Only an new release can be reject."))
            rec.write({'state': 'reject'})
        return True

    @api.multi
    def action_draft(self):
        for rec in self:
            if rec.state not in ('reject', 'cancel'):
                raise UserError(_("Only a cancel or reject release can be set to new."))
            rec.write({'state': 'new'})
        return True

    @api.multi
    def action_cancel(self):
        for rec in self:
            if rec.state != 'new':
                raise UserError(_("Only an new release can be cancel."))
            rec.write({'state': 'cancel'})
        return True

    @api.multi
    def action_confirm(self):
        for rec in self:
            if rec.state != 'new':
                raise UserError(_("Only an new release can be confirm."))
            loan = self.env['hr.loan'].search([('state','in',['new','open'])])
            if loan:
                raise UserError(_("You cannot approve release when there is a loan."))
            rec.write({'state': 'approve'})
            contracts = self.env['hr.contract'].search([('employee_id','=',rec.employee_id.id),('state','in',['close','cancel'])])
            for contract in contracts:
                if contract.date_end == False or contract.date_end>rec.date:
                    contract.write({'date_end':rec.date})
        return True

    @api.multi
    def unlink(self):
        if any(rec.state in ('approve') for rec in self):
            raise UserError(_('It is not allowed to delete a release that already approved.'))
        return super(hr_release, self).unlink()