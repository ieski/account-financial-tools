# -*- coding: utf-8 -*-
##############################################################################
#
#    Author Joel Grand-Guillaume. Copyright 2012 Camptocamp SA
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp import models, api
from openerp.tools.translate import _


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.multi
    def _authorized_reconcile(self, vals):
        """ Check if only reconcile_id and/or reconcile_partial_id are altered.
        We cannot change other vals, but we should be able to write or unlink
        those field (e.g. when you want to manually unreconcile an entry
        generated by an invoice).
        """
        if not vals:
            return False
        rec_keys = set(["reconcile_id", "reconcile_partial_id"])
        write_keys = set(vals)
        return rec_keys.issuperset(write_keys)

    @api.multi
    def _check_invoice_related_move(self, vals=None):
        for line in self:
            if line.invoice:
                if self._authorized_reconcile(vals):
                    return True
                err_msg = (_('Invoice name (id): %s (%s)') %
                            (line.invoice.name, line.invoice.id))
                raise models.except_orm(
                    _('Error'),
                    _('You cannot do this on an entry generated by an invoice.'
                      'You must '
                      'change the related invoice directly.\n%s.') % err_msg)
        return True

    @api.multi
    def _check_statement_related_move(self, vals=None):
        for line in self:
            if line.statement_id:
                if self._authorized_reconcile(vals):
                    return True
                err_msg = (_('Bank statement name (id): %s (%s)') %
                            (line.statement_id.name, line.statement_id.id))
                raise models.except_orm(
                    _('Error'),
                    _('You cannot do this on an entry generated by a bank'
                      ' statement. '
                      'You must change the related bank statement'
                      ' directly.\n%s.') % err_msg)
        return True

    @api.cr_uid_ids_context
    def unlink(self, cr, uid, ids, context=None, check=True):
        """ Add the following checks:

        - Is the move related to an invoice
        - Is the move related to a bank statement
        - Is other values than reconcile_partial_id and/or reconcile_id
          modified

        In that case, we forbid the move to be deleted even if draft. We
        should never delete directly a move line related or generated by
        another object.  This is mandatory if you use the module setting
        all moves in draft (module: account_default_draft_move)
        """
        if not context.get('from_parent_object', False):
            self._check_invoice_related_move(cr, uid, ids)
            self._check_statement_related_move(cr, uid, ids)
        return super(AccountMoveLine, self).unlink(cr, uid, ids,
                                                   context=context,
                                                   check=check)

    @api.cr_uid_ids_context
    def write(self, cr, uid, ids, vals, context=None, check=True,
              update_check=True):
        """ Add the following checks:

        - Is the move related to an invoice
        - Is the move related to a bank statement
        - Is other values than reconcile_partial_id and/or reconcile_id
        modified

        In that case, we forbid the move to be modified even if draft.
        We should never update directly a move line related or generated
        by another object.  This is mandatory if you use the module
        setting all moves in draft (module: account_default_draft_move)
        """
        if not context.get('from_parent_object', False):
            self._check_invoice_related_move(cr, uid, ids, vals)
            self._check_statement_related_move(cr, uid, ids, vals)
        return super(AccountMoveLine, self).write(cr, uid, ids, vals,
                                                  context=context,
                                                  check=check,
                                                  update_check=update_check)

    @api.multi
    def _check_currency_and_amount(self):
        for l in self:
            # we check zero amount line
            if not (l.debit and l.credit):
                continue
            if bool(l.currency_id) != bool(l.amount_currency):
                return False
        return True

    @api.multi
    def _check_currency_amount(self):
        for l in self:
            if l.amount_currency:
                if ((l.amount_currency > 0.0 and l.credit > 0.0) or
                        (l.amount_currency < 0.0 and l.debit > 0.0)):
                    return False
        return True

    @api.multi
    def _check_currency_company(self):
        for l in self:
            if l.currency_id.id == l.company_id.currency_id.id:
                return False
        return True

    _constraints = [
        (_check_currency_and_amount,
         "You cannot create journal items with a secondary currency "
         "without recording both 'currency' and 'amount currency' field.",
         ['currency_id', 'amount_currency']),

        (_check_currency_amount,
         "The amount expressed in the secondary currency must be positive "
         "when journal item are debit and negatif when journal item are "
         "credit.",
         ['amount_currency']),

        (_check_currency_company,
         "You can't provide a secondary currency if "
         "the same than the company one.",
         ['currency_id']),
    ]
