# -*- coding: utf-8 -*-

from odoo import api, fields, models, fields
from odoo.tools.translate import _
from odoo.exceptions import UserError


class Hr_Training(models.Model):
    _name = "hr.training"
    _description = "HR Training"

    name = fields.Char(string='Program Name', required=True, translate=True)
    institute = fields.Many2one('res.partner', string='Institute Name')
    employee_id = fields.Many2one('hr.employee', string='Employee Name', required=True)
    description = fields.Text(string='Training Description')
    registration_date = fields.Date(string='Registration Date')
    start_date = fields.Date(string='Start Date')
    end_date = fields.Date(string='End Date')
    result = fields.Selection([('pass','Pass'), ('fail','Fail'), ('incomplete','Incomplete')], string='Result')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env['res.company']._company_default_get('hr.training'))
    
class Hr_Employee(models.Model):
    _inherit = "hr.employee"

    training_ids = fields.One2many('hr.training','employee_id', string='Trainings')
    trainings_count = fields.Integer(compute='_compute_trainings_count', string='Trainings')

    def _compute_trainings_count(self):
        training_data = self.env['hr.training'].sudo().read_group([('employee_id', 'in', self.ids)], ['employee_id'], ['employee_id'])
        result = dict((data['employee_id'][0], data['employee_id_count']) for data in training_data)
        for employee in self:
            employee.trainings_count = result.get(employee.id, 0)