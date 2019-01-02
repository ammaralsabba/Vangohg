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

class hr_employee(models.Model):
    _inherit = 'hr.employee'

    loan_ids = fields.One2many('hr.loan', 'employee_id', string='Loans')
    loans_count = fields.Integer(compute='_compute_loans_count', string='Loans')

    def _compute_loans_count(self):
        loan_data = self.env['hr.loan'].sudo().read_group([('employee_id', 'in', self.ids)], ['employee_id'], ['employee_id'])
        result = dict((data['employee_id'][0], data['employee_id_count']) for data in loan_data)
        for employee in self:
            employee.loans_count = result.get(employee.id, 0)

class hr_loan(models.Model):
    _name = 'hr.loan'
    _description = 'Employees Loan'
    _inherit = 'mail.thread'

    @api.depends('loan_ids.amount', 'amount')
    def _balance(self):
        for line in self:
            if line.state == 'new':
                continue
            amount = 0
            for lines in line.loan_ids:
                amount =  lines.amount + amount
            line.paid = amount
            line.balance = line.amount - line.paid
            if line.balance<=0:
                line.state = 'paid'
    name = fields.Char(string='Description', readonly=True, track_visibility='onchange', states={'new': [('readonly', False)]}, required=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', readonly=True, track_visibility='onchange', states={'new': [('readonly', False)]}, required=True)
    date = fields.Date(string='Date', readonly=True, track_visibility='onchange', copy=False, states={'new': [('readonly', False)]}, required=True)
    amount = fields.Float(string='Amount', digits=dp.get_precision('Payroll'), readonly=True, track_visibility='onchange', copy=False, states={'new': [('readonly', False)]}, required=True)
    paid = fields.Float(compute='_balance', string='Paid', digits=dp.get_precision('Payroll'), readonly=True, copy=False)
    balance = fields.Float(compute='_balance', string='Amount Due', digits=dp.get_precision('Payroll'), readonly=True, copy=False)
    state = fields.Selection([('new', 'New'), ('open', 'Running'), ('paid', 'Paid'), ('reject', 'Rejected'), ('cancel','Cancelled')], string='State', default='new', readonly=True, track_visibility='onchange', copy=False)
    installment = fields.Float(string='Installment', digits=dp.get_precision('Payroll'), readonly=True, track_visibility='onchange', copy=False, states={'new': [('readonly', False)]}, required=True)
    move_id = fields.Many2one('account.move', 'Accounting Entry', readonly=True, copy=False)
    journal_id = fields.Many2one('account.journal', 'Loan Journal', readonly=True, required=True, states={'new': [('readonly', False)]}, default=lambda self: self.env['account.journal'].search([('type', '=', 'general')], limit=1))
    payment_id = fields.Many2one('account.journal', string='Payment From', required=True, domain=[('type', 'in', ('bank', 'cash'))], readonly=True, states={'new': [('readonly', False)]})
    company_id = fields.Many2one('res.company', related='journal_id.company_id', string='Company', readonly=True)
    loan_ids = fields.One2many('hr.loan.lines', 'loan_id', 'Lines', readonly=True, copy=False)

    @api.multi
    def action_reject(self):
        for rec in self:

            if rec.state != 'new':
                raise UserError(_("Only an new loan can be reject."))
            rec.write({'state': 'reject'})
        return True

    @api.multi
    def action_draft(self):
        for rec in self:

            if rec.state not in ('reject', 'cancel'):
                raise UserError(_("Only a cancel or reject loan can be set to new."))
            rec.write({'state': 'new'})
        return True

    @api.multi
    def action_cancel(self):
        for rec in self:

            if rec.state != 'new':
                raise UserError(_("Only an new loan can be cancel."))
            rec.write({'state': 'cancel'})
        return True

    @api.multi
    def action_confirm(self):
        for rec in self:

            if rec.state != 'new':
                raise UserError(_("Only an new loan can be confirm."))

            move = rec._create_payment_entry(rec.amount)

            rec.write({'state': 'open', 'move_id': move.id})
        return True

    def _create_payment_entry(self, amount):
        aml_obj = self.env['account.move.line'].with_context(check_move_validity=False)

        debit, credit, amount_currency, currency_id = aml_obj.with_context(date=self.date).compute_amount_fields(amount, self.company_id.currency_id, self.company_id.currency_id, False)

        move = self.env['account.move'].create(self._get_move_vals())

        #Write line corresponding to invoice payment
        counterpart_aml_dict = self._get_shared_move_line_vals(debit, credit, amount_currency, move.id, False)
        counterpart_aml_dict.update(self._get_counterpart_move_line_vals(False))
        counterpart_aml_dict.update({'currency_id': currency_id})
        counterpart_aml = aml_obj.create(counterpart_aml_dict)

        #Write counterpart lines
        if not self.company_id.currency_id.is_zero(self.amount):
            amount_currency = 0
            liquidity_aml_dict = self._get_shared_move_line_vals(credit, debit, -amount_currency, move.id, False)
            liquidity_aml_dict.update(self._get_liquidity_move_line_vals(-amount))
            aml_obj.create(liquidity_aml_dict)

        #validate the payment
        move.post()

        return move

    def _get_shared_move_line_vals(self, debit, credit, amount_currency, move_id, invoice_id=False):
        return {
            'partner_id': self.employee_id.address_home_id and self.employee_id.address_home_id.id or False,
            'invoice_id': False,
            'move_id': move_id,
            'debit': debit,
            'credit': credit,
            'amount_currency': False,
            'payment_id': False,
        }

    def _get_move_vals(self, journal=None):
        journal = journal or self.journal_id
        if not journal.sequence_id:
            raise UserError(_('Configuration Error !'), _('The journal %s does not have a sequence, please specify one.') % journal.name)
        if not journal.sequence_id.active:
            raise UserError(_('Configuration Error !'), _('The sequence of journal %s is deactivated.') % journal.name)
        name = self.move_id.name or journal.with_context(ir_sequence_date=self.date).sequence_id.next_by_id()
        return {
            'name': name,
            'date': self.date,
            'ref': self.name or '',
            'company_id': self.company_id.id,
            'journal_id': journal.id,
        }

    def _get_liquidity_move_line_vals(self, amount):
        name = self.name
        vals = {
            'name': name,
            'account_id': self.payment_id.default_debit_account_id.id or self.payment_id.default_credit_account_id.id,
            'partner_id': self.employee_id.address_home_id and self.employee_id.address_home_id.id or False,
            'journal_id': self.journal_id.id,
            'currency_id': False,
        }

        return vals

    def _get_counterpart_move_line_vals(self, invoice=False):
        name = self.name
        return {
            'name': name,
            'account_id': self.journal_id.default_debit_account_id.id,
            'journal_id': self.journal_id.id,
            'partner_id': self.employee_id.address_home_id and self.employee_id.address_home_id.id or False,
            'currency_id': False,
        }

    @api.multi
    def unlink(self):
        if any(bool(rec.move_id) for rec in self):
            raise UserError(_("You can not delete a loan that is already running"))
        if any(rec.state in ('open','paid') for rec in self):
            raise UserError(_('It is not allowed to delete a loan that already confirmed.'))
        return super(hr_loan, self).unlink()

class hr_loan_lines(models.Model):
    _name = 'hr.loan.lines'
    _description = 'Employees Loan Lines'

    payslip_id = fields.Many2one('hr.payslip', string='Payslip')
    date = fields.Date(string='Date')
    amount = fields.Float(string='Amount', digits=dp.get_precision('Payroll'))
    loan_id = fields.Many2one('hr.loan', 'Loan')

class hr_payslip(models.Model):
    _inherit = 'hr.payslip'

    @api.multi
    def action_payslip_done(self):
        for payslip in self:
            amount = 0
            for line in payslip.line_ids:
                if line.code == 'LO':
                    amount += line.amount
        loans = self.env['hr.loan'].search([('employee_id','=',self.employee_id.id), ('installment','>',0), ('balance','>',0), ('state','=','open')])
        for loan in loans:
            if loan.installment>=(amount*-1):
                if loan.balance>=loan.installment:
                    loan.loan_ids = [(0, 0, {'payslip_id': self.id, 'date': self.date_to, 'amount':amount*-1})]
                    amount = 0
                elif loan.balance<loan.installment and loan.balance>=(amount*-1):
                    loan.loan_ids = [(0, 0, {'payslip_id': self.id, 'date': self.date_to, 'amount':amount*-1})]
                    amount = 0
                else:
                    amount += loan.balance
                    loan.loan_ids = [(0, 0, {'payslip_id': self.id, 'date': self.date_to, 'amount':loan.balance})]
            elif loan.installment<(amount*-1):
                if loan.balance<=loan.installment:
                    loan.loan_ids = [(0, 0, {'payslip_id': self.id, 'date': self.date_to, 'amount':loan.balance})]
                    amount += loan.balance
                elif loan.balance>loan.installment:
                    loan.loan_ids = [(0, 0, {'payslip_id': self.id, 'date': self.date_to, 'amount':loan.installment})]
                    amount += loan.installment
        return super(hr_payslip, self).action_payslip_done()

    @api.model
    def get_inputs(self, contracts, date_from, date_to):
        res = super(hr_payslip, self).get_inputs(contracts, date_from, date_to)
        loans = self.env['hr.loan'].search([('employee_id','=',self.employee_id.id), ('installment','>',0), ('balance','>',0), ('state','=','open')])
        loan = 0
        for l in loans:
            loan += l.installment
        res += [{'name': 'Loan', 'code': 'Loan', 'contract_id': self.contract_id.id, 'amount':loan*-1}]
        return res
