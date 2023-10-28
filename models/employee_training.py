# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2019-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    Author: Anusha @cybrosys(odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################

from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
from pytz import timezone

from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
NEW_DATE_FORMAT = "%d/%m/%Y"
NEW_TIME_FORMAT = "%H:%M:%S"
NEW_DATETIME_FORMAT = "%s %s" % (
    NEW_DATE_FORMAT,
    NEW_TIME_FORMAT)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    certificates = fields.Boolean(default=True, string="Certificates",groups="hr.group_hr_user")


class EmployeeTraining(models.Model):
    _name = 'employee.training'
    _rec_name = 'program_name'
    _description = "Employee Training"
    _inherit = 'mail.thread'

    program_name = fields.Char(string='Training Program', required=True)
    program_department_id = fields.Many2one('hr.department', string='Department', required=True)
    program_convener_id = fields.Many2one('res.users', string='Responsible User', size=32, required=True)
    training_ids = fields.One2many('hr.employee', string='Employee Details', compute="employee_details")
    note_id = fields.Text('Description')
    date_from = fields.Datetime(string="Date From")
    date_to = fields.Datetime(string="Date To")
    period_str = fields.Char(string="Time Period",compute='_compute_period_str')
    user_id = fields.Many2one('res.users', string='users', default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    external = fields.Boolean(string='External')

    state = fields.Selection([
        ('new', 'New'),
        ('confirm', 'Confirmed'),
        ('cancel', 'Canceled'),
        ('complete', 'Completed'),
        ('print', 'Print'),
    ], string='Status', readonly=True, copy=False, index=True, track_visibility='onchange', default='new')


    @api.depends('date_from','date_to')
    def _compute_period_str(self):
        for each in self:
            if each.date_from and each.date_to:
                date_from_tz = each.date_from.astimezone(timezone(each.env.context.get('tz')))
                date_to_tz = each.date_to.astimezone(timezone(each.env.context.get('tz')))
                date_from_str = datetime.strptime(date_from_tz.strftime(DEFAULT_SERVER_DATETIME_FORMAT), DEFAULT_SERVER_DATETIME_FORMAT).strftime(NEW_DATETIME_FORMAT)
                date_to_str = datetime.strptime(date_to_tz.strftime(DEFAULT_SERVER_DATETIME_FORMAT), DEFAULT_SERVER_DATETIME_FORMAT).strftime(NEW_DATETIME_FORMAT)
                each.period_str = _('%s to %s')%(date_from_str,date_to_str)

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for each in self:
            if each.date_from and each.date_to and each.date_from > each.date_to:
                raise ValidationError(_('Invalid period specified: start date must be earlier than end date.'))

    @api.depends('program_department_id')
    def employee_details(self):
        datas = self.env['hr.employee'].search([('department_id', '=', self.program_department_id.id)])
        self.training_ids = datas

    def print_event(self):
        self.ensure_one()
        started_date = datetime.strftime(self.create_date, "%Y-%m-%d ")
        duration = (self.write_date - self.create_date).days
        pause = relativedelta(hours=0)
        difference = relativedelta(self.write_date, self.create_date) - pause
        hours = difference.hours
        minutes = difference.minutes
        data = {
            'dept_id': self.program_department_id.id,
            'program_name': self.program_name,
            'company_name': self.company_id.name,
            'date_to': started_date,
            'duration': duration,
            'hours': hours,
            'minutes': minutes,
            'program_convener': self.program_convener_id.name,

        }
        return self.env.ref('employee_orientation.print_pack_certificates').report_action(self, data=data)

    def complete_event(self):
        self.write({'state': 'complete'})

    def confirm_event(self):
        self.write({'state': 'confirm'})

    def cancel_event(self):
        self.write({'state': 'cancel'})

    def confirm_send_mail(self):
        self.ensure_one()
        ir_model_data = self.env['ir.model.data']
        try:
            template_id = ir_model_data._xmlid_lookup('employee_orientation.orientation_training_mailer')[2]
        except ValueError:
            template_id = False
        try:
            compose_form_id = ir_model_data._xmlid_lookup('mail.email_compose_message_wizard_form')[2]
        except ValueError:
            compose_form_id = False
        ctx = dict(self.env.context or {})
        ctx.update({
            'default_model': 'employee.training',
            'default_res_id': self.ids[0],
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
        })

        return {
            'name': _('Compose Email'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form_id, 'form')],
            'view_id': compose_form_id,
            'target': 'new',
            'context': ctx,
        }
