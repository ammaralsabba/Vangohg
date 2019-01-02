# -*- coding: utf-8 -*-

import time
from pytz import common_timezones
from odoo import tools
from odoo import api, fields, models, fields
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from odoo import netsvc
from odoo.addons import decimal_precision as dp
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT,DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.translate import _
from odoo.exceptions import UserError

import logging
_l = logging.getLogger(__name__)

class hr_employee(models.Model):

	_inherit = 'hr.contract'
	
	policy_id = fields.Many2one('hr.policy', string='Policy')


class hr_policy(models.Model):

    _name = 'hr.policy'

    name = fields.Char('Name', required=True)
    sign_in = fields.Integer('Late sign in', help="Minutes after which this policy applies")
    sign_out = fields.Integer('Early sign out', help="Minutes after which this policy applies")
    line_ids = fields.One2many('hr.policy.line', 'policy_id', 'Policy Lines')


class hr_policy_line(models.Model):

    _name = 'hr.policy.line'

    name = fields.Char('Name', required=True)
    policy_id = fields.Many2one('hr.policy', 'Policy')
    type = fields.Selection([('restday', 'Rest Day'),('holiday', 'Public Holiday')],'Type', required=True)
    active_after = fields.Integer('Active After', help="Minutes after which this policy applies")
    rate = fields.Float('Rate', required=True, help='Multiplier of employee wage.')
    starttime = fields.Float('Start Time', default='00.00')
    endtime = fields.Float('End Time', default='23.59')

class hr_employee(models.Model):

    _inherit = 'hr.employee'
    
    def get_worked_hours(self, contract, date_from, date_to):
        res=0
        if not contract.resource_calendar_id:
            return res
        day_from = datetime.strptime(date_from,"%Y-%m-%d")
        day_to = datetime.strptime(date_to,"%Y-%m-%d")
        nb_of_days = (day_to - day_from).days + 1
        for day in range(0, nb_of_days):
            datetime_day=day_from + timedelta(days=day)
            weekday = datetime_day.strftime("%w")
            for work in contract.resource_calendar_id.attendance_ids:
                if work.dayofweek==weekday:
                    start=(datetime_day + timedelta(hours=work.hour_from))
                    end=(datetime_day + timedelta(hours=work.hour_to))
                    res+=(end-start).seconds/3600.0
        return res
        
    def get_rest_rate(self, contract):
        res=0
        if not contract.policy_id:
            return res
        for line in contract.policy_id.line_ids:
            if line.type=='restday':
                res=line.rate
        return res
        
    def get_holiday_rate(self, contract):
        res=0
        if not contract.policy_id:
            return res
        for line in contract.policy_id.line_ids:
            if line.type=='holiday':
                res=line.rate
        return res
    
class hr_payslip(models.Model):
	_inherit="hr.payslip"
	
	def get_worked_day_lines(self, contract_ids, date_from, date_to):
		
		def was_on_leave(employee_id, datetime_day):
			res = False
			day = datetime_day.strftime("%Y-%m-%d")
			holiday_ids = self.env['hr.holidays'].search([('state','=','validate'),('employee_id','=',employee_id),('type','=','remove'),('date_from','<=',day),('date_to','>=',day)])
			if holiday_ids:
				res = holiday_ids[0].holiday_status_id.name
			return res
		
		def check_absent(contract, datetime_day):
			weekday = datetime_day.strftime("%w")
			if weekday=="0":
				weekday=str(6)
			else:
				weekday=str(int(weekday)-1)
			res = 0
			day = datetime_day.strftime("%Y-%m-%d")
			date_day=datetime.strftime(datetime_day, "%Y-%m-%d")
			holiday_ids = self.env['hr.holidays'].search([('state','=','validate'),('employee_id','=',contract.employee_id.id),('type','=','remove'),('date_from','<=',day),('date_to','>=',day)])
			if not holiday_ids:
				sday=datetime.strftime(datetime_day, "%Y-%m-%d 00:00:00")
				eday=datetime.strftime(datetime_day, "%Y-%m-%d 23:59:59")
				attendance_ids=self.env['hr.attendance'].search([('employee_id','=',contract.employee_id.id),('check_in','>=',sday),('check_out','<=',eday)],order='check_in ASC')
				if not attendance_ids:
					for work in contract.resource_calendar_id.attendance_ids:
						if work.dayofweek==weekday and (work.date_from==False or work.date_from<date_day) and (work.date_to==False or work.date_to>date_day):
							start=(datetime_day + timedelta(hours=work.hour_from))
							end=(datetime_day + timedelta(hours=work.hour_to))
							res+=(end-start).seconds/3600.0
			return res
		
		def check_attend(contract, datetime_day):
			weekday = datetime_day.strftime("%w")
			if weekday=="0":
				weekday=str(6)
			else:
				weekday=str(int(weekday)-1)
			res = 0
			day = datetime_day.strftime("%Y-%m-%d")
			date_day=datetime.strftime(datetime_day, "%Y-%m-%d")
			holiday_ids = self.env['hr.holidays'].search([('state','=','validate'),('employee_id','=',contract.employee_id.id),('type','=','remove'),('date_from','<=',day),('date_to','>=',day)])
			if not holiday_ids:
				sday=datetime.strftime(datetime_day, "%Y-%m-%d 00:00:00")
				eday=datetime.strftime(datetime_day, "%Y-%m-%d 23:59:59")
				attendance_ids=self.env['hr.attendance'].search([('employee_id','=',contract.employee_id.id),('check_in','>=',sday),('check_out','<=',eday)],order='check_in ASC')
				if attendance_ids:
					for work in contract.resource_calendar_id.attendance_ids:
						if work.dayofweek==weekday and (work.date_from==False or work.date_from<=date_day) and (work.date_to==False or work.date_to>=date_day):
							start=(datetime_day + timedelta(hours=work.hour_from))
							end=(datetime_day + timedelta(hours=work.hour_to))
							res+=(end-start).seconds/3600.0
			return res
		
		def check_late(contract, datetime_day, context=None):
			weekday = datetime_day.strftime("%w")
			if weekday=="0":
				weekday=str(6)
			else:
				weekday=str(int(weekday)-1)
			res = 0
			day = datetime_day.strftime("%Y-%m-%d")
			date_day=datetime.strftime(datetime_day, "%Y-%m-%d")
			holiday_ids = self.env['hr.holidays'].search([('state','=','validate'),('employee_id','=',contract.employee_id.id),('type','=','remove'),('date_from','<=',day),('date_to','>=',day)])
			if not holiday_ids:
				sday=datetime.strftime(datetime_day, "%Y-%m-%d 00:00:00")
				eday=datetime.strftime(datetime_day, "%Y-%m-%d 23:59:59")
				attendance_ids=self.env['hr.attendance'].search([('employee_id','=',contract.employee_id.id),('check_in','>=',sday),('check_out','<=',eday)],order='check_in ASC')
				for work in contract.resource_calendar_id.attendance_ids:
					if work.dayofweek==weekday and (work.date_from==False or work.date_from<date_day) and (work.date_to==False or work.date_to>date_day):
						start=(datetime_day + timedelta(hours=work.hour_from))
						end=(datetime_day + timedelta(hours=work.hour_to))
						for attendance_id in attendance_ids:
							attend=attendance_id
							now=datetime.strptime(attend.check_in,'%Y-%m-%d %H:%M:%S')+ timedelta(hours=3)
							if now>start and now<end and contract.policy_id.sign_in<=(now-start).seconds/60:
								res+=(now-start).seconds/3600.0
			return res
			
		def check_early(contract, datetime_day):
			weekday = datetime_day.strftime("%w")
			if weekday=="0":
				weekday=str(6)
			else:
				weekday=str(int(weekday)-1)
			res = 0
			day = datetime_day.strftime("%Y-%m-%d")
			date_day=datetime.strftime(datetime_day, "%Y-%m-%d")
			holiday_ids = self.env['hr.holidays'].search([('state','=','validate'),('employee_id','=',contract.employee_id.id),('type','=','remove'),('date_from','<=',day),('date_to','>=',day)])
			if not holiday_ids:
				sday=datetime.strftime(datetime_day, "%Y-%m-%d 00:00:00")
				eday=datetime.strftime(datetime_day, "%Y-%m-%d 23:59:59")
				attendance_ids=self.env['hr.attendance'].search([('employee_id','=',contract.employee_id.id),('check_in','>=',sday),('check_out','<=',eday)],order='check_in ASC')
				for work in contract.resource_calendar_id.attendance_ids:
					if work.dayofweek==weekday and (work.date_from==False or work.date_from<date_day) and (work.date_to==False or work.date_to>date_day):
						start=(datetime_day + timedelta(hours=work.hour_from))
						end=(datetime_day + timedelta(hours=work.hour_to))
						for attendance_id in attendance_ids:
							attend=attendance_id
							now=datetime.strptime(attend.check_out,'%Y-%m-%d %H:%M:%S')+ timedelta(hours=3)
							if now>start and now<end and contract.policy_id.sign_out<=(end-now).seconds/60:
								res+=(end-now).seconds/3600.0
			return res
			
		def holiday_overtime(contract, datetime_day):
			weekday = datetime_day.strftime("%w")
			if weekday=="0":
				weekday=str(6)
			else:
				weekday=str(int(weekday)-1)
			res = 0
			day = datetime_day.strftime(DEFAULT_SERVER_DATE_FORMAT)
			date_day=datetime.strftime(datetime_day, DEFAULT_SERVER_DATE_FORMAT)
			holiday_ids = self.env['hr.holidays'].search([('state','=','validate'),('employee_id','=',contract.employee_id.id),('type','=','remove'),('date_from','<=',day),('date_to','>=',day)])
			for holiday_id in holiday_ids:
				holiday = holiday_id
				sday=holiday.date_from
				eday=holiday.date_to
				attendance_ids=self.env['hr.attendance'].search([('employee_id','=',contract.employee_id.id),('check_in','>=',sday),('check_out','<=',eday)],order='check_in ASC')
				for attend in attendance_ids:
					active=0
					overtime = True
					for policy in contract.policy_id.line_ids:
						starttime = (day + " " + str(policy.starttime)).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
						endtime = (day + " " + str(policy.endtime)).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
						if policy.type=='holiday' and attend.check_in<=endtime and attend.check_out>=starttime:
							active = policy.active_after
							overtime = True
							worked_hours = 0
							if attend.check_in>=starttime and attend.check_out<=endtime:
								worked_hours = (attend.check_out - attend.check_in).seconds/60
							elif attend.check_in>=starttime and attend.check_out>endtime:
								worked_hours = (endtime - attend.check_in).seconds/60
							elif attend.check_in<starttime and attend.check_out<=endtime:
								worked_hours = (attend.check_out - starttime).seconds/60
							elif attend.check_in<starttime and attend.check_out>endtime:
								worked_hours = (endtime - starttime).seconds/60
							if worked_hours>=active:
								res += worked_hours
			if not holiday_ids:
				x=False
				for work in contract.resource_calendar_id.attendance_ids:
					if work.dayofweek==weekday and (work.date_from==False or work.date_from<date_day) and (work.date_to==False or work.date_to>date_day):
						x=True
				if x==False:
					sday=datetime.strftime(datetime_day, "%Y-%m-%d 00:00:00")
					eday=datetime.strftime(datetime_day, "%Y-%m-%d 23:59:59")
					attendance_ids=self.env['hr.attendance'].search([('employee_id','=',contract.employee_id.id),('check_in','>=',sday),('check_out','<=',eday)],order='check_in ASC')
					for attend in attendance_ids:
						active=0
						overtime = True
						for policy in contract.policy_id.line_ids:
							starttime = (day + " " + str(policy.starttime)).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
							endtime = (day + " " + str(policy.endtime)).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
							if policy.type=='holiday' and attend.check_in<=endtime and attend.check_out>=starttime:
								active = policy.active_after
								overtime = True
								worked_hours = 0
								if attend.check_in>=starttime and attend.check_out<=endtime:
									worked_hours = (attend.check_out - attend.check_in).seconds/60
								elif attend.check_in>=starttime and attend.check_out>endtime:
									worked_hours = (endtime - attend.check_in).seconds/60
								elif attend.check_in<starttime and attend.check_out<=endtime:
									worked_hours = (attend.check_out - starttime).seconds/60
								elif attend.check_in<starttime and attend.check_out>endtime:
									worked_hours = (endtime - starttime).seconds/60
								if worked_hours>=active:
									res += worked_hours
			return res
        	
		def rest_overtime(contract, datetime_day):
			weekday = datetime_day.strftime("%w")
			if weekday=="0":
				weekday=str(6)
			else:
				weekday=str(int(weekday)-1)
			res = 0
			active=0
			date_day=datetime.strftime(datetime_day, DEFAULT_SERVER_DATE_FORMAT)
			day = datetime_day.strftime(DEFAULT_SERVER_DATE_FORMAT)
			holiday_ids = self.env['hr.holidays'].search([('state','=','validate'),('employee_id','=',contract.employee_id.id),('type','=','remove'),('date_from','<=',day),('date_to','>=',day)])
			if not holiday_ids:
				sday=datetime.strftime(datetime_day, "%Y-%m-%d 00:00:00")
				eday=datetime.strftime(datetime_day, "%Y-%m-%d 23:59:59")
				attendance_ids=self.env['hr.attendance'].search([('employee_id','=',contract.employee_id.id),('check_in','>=',sday),('check_out','<=',eday)],order='check_in ASC')
				time = {}
				for work in contract.resource_calendar_id.attendance_ids:
					if work.dayofweek==weekday and (work.date_from==False or work.date_from<date_day) and (work.date_to==False or work.date_to>date_day):
						if str(datetime_day + timedelta(hours=work.hour_from)) not in time:
							time[str(datetime_day + timedelta(hours=work.hour_from))]={'start':(datetime_day + timedelta(hours=work.hour_from)),'end':(datetime_day + timedelta(hours=work.hour_to))}
				
				if time:
					for attendance_id in attendance_ids:
						attend=attendance_id
						if attend.check_out:
							y=0.0
							now=datetime.strptime(attend.check_out,DEFAULT_SERVER_DATETIME_FORMAT)+ timedelta(hours=3)
							for key,value in sorted(time.items()):
								start=value['start']
								end=value['end']
								for policy in contract.policy_id.line_ids:
									starttime = (day + " " + str(policy.starttime)).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
									endtime = (day + " " + str(policy.endtime)).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
									if policy.type=='restday':
										active = policy.active_after
										overtime = True
										worked_hours = 0
										if attend.check_in>=starttime and attend.check_in<start and attend.check_in<=endtime:
											worked_hours += (start - attend.check_in).seconds/60
										if attend.check_out<=endtime and attend.check_out>=starttime and attend.check_out>end:
											worked_hours += (attend.check_out - end).seconds/60
										if worked_hours>=active:
											res+=worked_hours
			return res
		res = []
		for contract in contract_ids:
			if not contract.resource_calendar_id:
				continue
			absents = {}
			attends = {}
			lates = {}
			earlys = {}
			holidays = {}
			rests = {}
			leaves= {}
			day_from = datetime.strptime(date_from,DEFAULT_SERVER_DATE_FORMAT)
			day_to = datetime.strptime(date_to,DEFAULT_SERVER_DATE_FORMAT)
			nb_of_days = (day_to - day_from).days + 1
			for day in range(0, nb_of_days):
				absent = check_absent(contract, day_from + timedelta(days=day))
				attend = check_attend(contract, day_from + timedelta(days=day))
				late = check_late(contract, day_from + timedelta(days=day))
				early = check_early(contract, day_from + timedelta(days=day))
				holiday = holiday_overtime(contract, day_from + timedelta(days=day))
				rest = rest_overtime(contract, day_from + timedelta(days=day))
				working_hours_on_day = contract.resource_calendar_id._get_day_work_intervals((day_from + timedelta(days=day)).date())
				if working_hours_on_day:
					#the employee had to work
					leave_type = was_on_leave(contract.employee_id.id, day_from + timedelta(days=day))
					if leave_type:
						hours = 0
						for w in working_hours_on_day:
							hours +=(w.end_datetime - w.start_datetime)
						#if he was on leave, fill the leaves dict
						leave_type = leave_type.replace(' ','_')
						if leave_type in leaves:
							leaves[leave_type]['number_of_days'] += 1.0
							leaves[leave_type]['number_of_hours'] += hours
						else:
							leaves[leave_type] = {
                                'name': leave_type,
                                'sequence': 5,
                                'code': leave_type,
                                'number_of_days': 1.0,
                                'number_of_hours': hours,
                                'contract_id': contract.id,
                            }
				if absent:
					if 'Absents' in absents:
						absents['Absents']['number_of_days'] += 1.0
						absents['Absents']['number_of_hours'] += absent
					else:
						absents['Absents'] = {'name': 'Absent Days','sequence': 5,'code': 'Absents','number_of_days': 1.0,'number_of_hours': absent,'contract_id': contract.id,}
				if attend:
					if 'Attends' in attends:
						attends['Attends']['number_of_days'] += 1.0
						attends['Attends']['number_of_hours'] += attend
					else:
						attends['Attends'] = {'name': 'Attend Days','sequence': 5,'code': 'Attends','number_of_days': 1.0,'number_of_hours': attend,'contract_id': contract.id,}
				if late:
					if 'Lates' in lates:
						lates['Lates']['number_of_days'] += 0
						lates['Lates']['number_of_hours'] += late
						attends['Attends']['number_of_hours'] -= late
					else:
						lates['Lates'] = {'name': 'Delay Sign in','sequence': 5,'code': 'Lates','number_of_days': 0,'number_of_hours': late,'contract_id': contract.id,}
				if early:
					if 'Earlys' in earlys:
						earlys['Earlys']['number_of_days'] += 0
						earlys['Earlys']['number_of_hours'] += early
						attends['Attends']['number_of_hours'] -= early
					else:
						earlys['Earlys'] = {'name': 'Early Sign out','sequence': 5,'code': 'Earlys','number_of_days': 0,'number_of_hours': early,'contract_id': contract.id,}
				if holiday:
					if 'Holidays' in holidays:
						holidays['Holidays']['number_of_days'] += 0
						holidays['Holidays']['number_of_hours'] += holiday
					else:
						holidays['Holidays'] = {'name': 'Overtime Holidays','sequence': 5,'code': 'Holidays','number_of_days': 0,'number_of_hours': holiday,'contract_id': contract.id,}
				if rest:
					if 'Rests' in rests:
						rests['Rests']['number_of_days'] += 0
						rests['Rests']['number_of_hours'] += rest
					else:
						rests['Rests'] = {'name': 'Overtime Normal Day','sequence': 5,'code': 'Rests','number_of_days': 0,'number_of_hours': rest,'contract_id': contract.id,}
			absents = [value for key,value in absents.items()]
			attends = [value for key,value in attends.items()]
			lates = [value for key,value in lates.items()]
			earlys = [value for key,value in earlys.items()]
			holidays = [value for key,value in holidays.items()]
			rests = [value for key,value in rests.items()]
			leaves = [value for key,value in leaves.items()]
			res += absents + attends + lates + earlys + holidays + rests + leaves
		return res