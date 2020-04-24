# -*- coding: utf-8 -*-
#
## plugins/triggers/triggers.py
##
## Copyright (C) 2011-2017 Yann Leboulanger <asterix AT lagaule.org>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##


import os

from gi.repository import Gtk

from gajim.common import app
from gajim.common import ged
from gajim.common import helpers
from gajim.plugins import GajimPlugin
from gajim.plugins.helpers import log_calls
from gajim.plugins.helpers import get_builder
from gajim.plugins.gui import GajimPluginConfigDialog
from gajim.plugins.plugins_i18n import _

from gajim.gtk.filechoosers import NativeFileChooserDialog, Filter

class SoundChooserDialog(NativeFileChooserDialog):

    _title = _('Choose Sound')
    _filters = [Filter(_('All files'), '*', False),
                Filter(_('WAV files'), '*.wav', True)]


class Triggers(GajimPlugin):
    @log_calls('TriggersPlugin')
    def init(self):
        self.description = _('Configure Gajim\'s behaviour with conditions for each contact')
        self.config_dialog = TriggersPluginConfigDialog(self)
        self.config_default_values = {}

        self.events_handlers = {'notification': (ged.PREGUI, self._nec_notif),
            'decrypted-message-received': (ged.PREGUI2,
            self._nec_decrypted_message_received),
            'gc-message-received': (ged.PREGUI2, self._nec_gc_message_received),
            'presence-received': (ged.PREGUI, self._nec_presence_received)}

    def _check_rule_recipients(self, obj, rule):
        rule_recipients = [t.strip() for t in rule['recipients'].split(',')]
        if rule['recipient_type'] == 'groupchat':
            if obj.jid in rule_recipients:
                return True
            return False
        if rule['recipient_type'] == 'contact' and obj.jid not in \
        rule_recipients:
            return False
        contact = app.contacts.get_first_contact_from_jid(obj.conn.name,
            obj.jid)
        if not contact:  # PM?
            return False
        contact_groups = contact.groups
        group_found = False
        for group in contact_groups:
            if group in rule_recipients:
                group_found = True
                break
        if rule['recipient_type'] == 'group' and not group_found:
            return False

        return True

    def _check_rule_status(self, obj, rule):
        rule_statuses = rule['status'].split()
        our_status = app.connections[obj.conn.name].status
        if rule['status'] != 'all' and our_status not in rule_statuses:
            return False

        return True

    def _check_rule_tab_opened(self, obj, rule):
        if rule['tab_opened'] == 'both':
            return True
        tab_opened = False
        if app.interface.msg_win_mgr.get_control(obj.jid, obj.conn.name):
            tab_opened = True
        if tab_opened and rule['tab_opened'] == 'no':
            return False
        elif not tab_opened and rule['tab_opened'] == 'yes':
            return False

        return True

    def _check_rule_has_focus(self, obj, rule):
        if rule['has_focus'] == 'both':
            return True
        if rule['tab_opened'] == 'no':
            # Does not apply in this case
            return True
        ctrl = app.interface.msg_win_mgr.get_control(obj.jid, obj.conn.name)
        if not ctrl:
            # Does not apply in this case
            return True
        has_focus = ctrl.parent_win.window.has_focus()
        if has_focus and rule['has_focus'] == 'no':
            return False
        elif not has_focus and rule['has_focus'] == 'yes':
            return False

        return True

    def check_rule_all(self, event, obj, rule):
        # Check notification type
        if rule['event'] != event:
            return False

        # notification type is ok. Now check recipient
        if not self._check_rule_recipients(obj, rule):
            return False

        # recipient is ok. Now check our status
        if not self._check_rule_status(obj, rule):
            return False

        # our_status is ok. Now check opened chat window
        if not self._check_rule_tab_opened(obj, rule):
            return False

        # tab_opened is ok. Now check opened chat window
        if not self._check_rule_has_focus(obj, rule):
            return False

        # All is ok
        return True

    def check_rule_apply_notif(self, obj, rule):
        # Check notification type
        notif_type = ''
        if obj.notif_type in ('msg', 'gc-msg'):
            notif_type = 'message_received'
        elif obj.notif_type == 'pres':
            if obj.base_event.old_show < 2 and obj.base_event.new_show > 1:
                notif_type = 'contact_connected'
            elif obj.base_event.old_show > 1 and obj.base_event.new_show < 2:
                notif_type = 'contact_disconnected'
            else:
                notif_type = 'contact_status_change'

        return self.check_rule_all(notif_type, obj, rule)

    def check_rule_apply_decrypted_msg(self, obj, rule):
        return self.check_rule_all('message_received', obj, rule)

    def check_rule_apply_connected(self, obj, rule):
        return self.check_rule_all('contact_connected', obj, rule)

    def check_rule_apply_disconnected(self, obj, rule):
        return self.check_rule_all('contact_disconnected', obj, rule)

    def check_rule_apply_status_changed(self, obj, rule):
        return self.check_rule_all('contact_status_change', obj, rule)

    def apply_rule_notif(self, obj, rule):
        if rule['sound'] == 'no':
            obj.do_sound = False
        elif rule['sound'] == 'yes':
            obj.do_sound = True
            obj.sound_event = ''
            obj.sound_file = rule['sound_file']

        if rule['popup'] == 'no' or obj.control_focused:
            obj.do_popup = False
        elif rule['popup'] == 'yes':
            obj.do_popup = True

        if rule['run_command']:
            obj.do_command = True
            obj.command = rule['command']
        else:
            obj.do_command = False

        if rule['systray'] == 'no':
            obj.show_in_notification_area = False
        elif rule['systray'] == 'yes':
            obj.show_in_notification_area = True

        if rule['roster'] == 'no':
            obj.show_in_roster = False
        elif rule['roster'] == 'yes':
            obj.show_in_roster = True

#        if rule['urgency_hint'] == 'no':
#            ?? not in obj actions
#        elif rule['urgency_hint'] == 'yes':

    def apply_rule_decrypted_message(self, obj, rule):
        if rule['auto_open'] == 'no':
            obj.popup = False
        elif rule['auto_open'] == 'yes':
            obj.popup = True

    def apply_rule_presence(self, obj, rule):
        if rule['auto_open'] == 'no':
            obj.popup = False
        elif rule['auto_open'] == 'yes':
            obj.popup = True

    def _nec_all(self, obj, check_func, apply_func):
        # check rules in order
        rules_num = [int(i) for i in self.config.keys()]
        rules_num.sort()
        to_remove = []
        for num in rules_num:
            rule = self.config[str(num)]
            if check_func(obj, rule):
                apply_func(obj, rule)
                if 'one_shot' in rule and rule['one_shot']:
                    to_remove.append(num)
                # Should we stop after first valid rule ?
                # break

        decal = 0
        num = 0
        while str(num) in self.config:
            if (num + decal) in to_remove:
                num2 = num
                while str(num2 + 1) in self.config:
                    self.config[str(num2)] = self.config[str(num2 + 1)].copy()
                    num2 += 1
                del self.config[str(num2)]
                decal += 1
            else:
                num += 1

    def _nec_notif(self, obj):
        self._nec_all(obj, self.check_rule_apply_notif, self.apply_rule_notif)

    def _nec_decrypted_message_received(self, obj):
        self._nec_all(obj, self.check_rule_apply_decrypted_msg,
            self.apply_rule_decrypted_message)

    def _nec_gc_message_received(self, obj):
        self._nec_all(obj, self.check_rule_apply_decrypted_msg,
            self.apply_rule_decrypted_message)

    def _nec_presence_received(self, obj):
        if obj.old_show < 2 and obj.new_show > 1:
            check_func = self.check_rule_apply_connected
        elif obj.old_show > 1 and obj.new_show < 2:
            check_func = self.check_rule_apply_disconnected
        else:
            check_func = self.check_rule_apply_status_changed
        self._nec_all(obj, check_func, self.apply_rule_presence)


class TriggersPluginConfigDialog(GajimPluginConfigDialog):
    # {event: widgets_to_disable, }
    events_list = {
        'message_received': [],
        'contact_connected': ['use_systray_cb', 'disable_systray_cb',
            'use_roster_cb', 'disable_roster_cb'],
        'contact_disconnected': ['use_systray_cb', 'disable_systray_cb',
            'use_roster_cb', 'disable_roster_cb'],
        'contact_status_change': ['use_systray_cb', 'disable_systray_cb',
            'use_roster_cb', 'disable_roster_cb']
        #, 'gc_msg_highlight': [], 'gc_msg': []}
    }
    recipient_types_list = ['contact', 'group', 'groupchat', 'all']
    config_options = ['event', 'recipient_type', 'recipients', 'status',
        'tab_opened', 'has_focus', 'sound', 'sound_file', 'popup', 'auto_open',
        'run_command', 'command', 'systray', 'roster', 'urgency_hint',
        'one_shot']

    def init(self):
        path = self.plugin.local_file_path('config_dialog.ui')
        self._ui = get_builder(path, widgets=['plugin_box', 'liststore1', 'liststore2'])

        box = self.get_content_area()
        box.pack_start(self._ui.plugin_box, True, True, 0)

        self._ui.connect_signals(self)
        self.connect('hide', self.on_hide)

    def on_run(self):
        # Fill window
        for w in ('conditions_treeview', 'config_box', 'event_combobox',
        'recipient_type_combobox', 'recipient_list_entry', 'delete_button',
        'online_cb', 'away_cb', 'xa_cb', 'dnd_cb',
        'use_sound_cb', 'disable_sound_cb', 'use_popup_cb',
        'disable_popup_cb', 'use_auto_open_cb', 'disable_auto_open_cb',
        'use_systray_cb', 'disable_systray_cb', 'use_roster_cb',
        'disable_roster_cb', 'tab_opened_cb', 'not_tab_opened_cb',
        'has_focus_cb', 'not_has_focus_cb', 'sound_entry', 'sound_file_box',
        'up_button', 'down_button', 'run_command_cb', 'command_entry',
        'one_shot_cb', 'use_urgency_hint_cb', 'disable_urgency_hint_cb'):
            self._ui.__dict__[w] = self._ui.get_object(w)

        self.config = {}
        for n in self.plugin.config:
            self.config[int(n)] = self.plugin.config[n]

        if not self._ui.conditions_treeview.get_column(0):
            # Window never opened
            model = Gtk.ListStore(int, str)
            model.set_sort_column_id(0, Gtk.SortType.ASCENDING)
            self._ui.conditions_treeview.set_model(model)

            # '#' Means number
            col = Gtk.TreeViewColumn(_('#'))
            self._ui.conditions_treeview.append_column(col)
            renderer = Gtk.CellRendererText()
            col.pack_start(renderer, expand=False)
            col.add_attribute(renderer, 'text', 0)

            col = Gtk.TreeViewColumn(_('Condition'))
            self._ui.conditions_treeview.append_column(col)
            renderer = Gtk.CellRendererText()
            col.pack_start(renderer, expand=True)
            col.add_attribute(renderer, 'text', 1)
        else:
            model = self._ui.conditions_treeview.get_model()

        model.clear()

        # Fill conditions_treeview
        num = 0
        while num in self.config:
            iter_ = model.append((num, ''))
            path = model.get_path(iter_)
            self._ui.conditions_treeview.set_cursor(path)
            self.active_num = num
            self.initiate_rule_state()
            self.set_treeview_string()
            num += 1

        # No rule selected at init time
        self._ui.conditions_treeview.get_selection().unselect_all()
        self.active_num = -1
        self._ui.config_box.set_sensitive(False)
        self._ui.delete_button.set_sensitive(False)
        self._ui.down_button.set_sensitive(False)
        self._ui.up_button.set_sensitive(False)

    def initiate_rule_state(self):
        """
        Set values for all widgets
        """
        if self.active_num < 0:
            return
        # event
        value = self.config[self.active_num]['event']
        if value:
            self._ui.event_combobox.set_active(list(self.events_list.keys()).index(
                value))
        else:
            self._ui.event_combobox.set_active(-1)
        # recipient_type
        value = self.config[self.active_num]['recipient_type']
        if value:
            self._ui.recipient_type_combobox.set_active(
                self.recipient_types_list.index(value))
        else:
            self._ui.recipient_type_combobox.set_active(-1)
        # recipient
        value = self.config[self.active_num]['recipients']
        if not value:
            value = ''
        self._ui.recipient_list_entry.set_text(value)
        # status
        value = self.config[self.active_num]['status']
        if value == 'all':
            self._ui.all_status_rb.set_active(True)
        else:
            self._ui.special_status_rb.set_active(True)
            values = value.split()
            for v in ('online', 'away', 'xa', 'dnd'):
                if v in values:
                    self._ui.__dict__[v + '_cb'].set_active(True)
                else:
                    self._ui.__dict__[v + '_cb'].set_active(False)

        self.on_status_radiobutton_toggled(self._ui.all_status_rb)

        # tab_opened
        value = self.config[self.active_num]['tab_opened']
        self._ui.tab_opened_cb.set_active(True)
        self._ui.not_tab_opened_cb.set_active(True)
        if value == 'no':
            self._ui.tab_opened_cb.set_active(False)
        elif value == 'yes':
            self._ui.not_tab_opened_cb.set_active(False)

        # has_focus
        if 'has_focus' not in self.config[self.active_num]:
            self.config[self.active_num]['has_focus'] = 'both'
        value = self.config[self.active_num]['has_focus']
        self._ui.has_focus_cb.set_active(True)
        self._ui.not_has_focus_cb.set_active(True)
        if value == 'no':
            self._ui.has_focus_cb.set_active(False)
        elif value == 'yes':
            self._ui.not_has_focus_cb.set_active(False)

        # sound_file
        value = self.config[self.active_num]['sound_file']
        self._ui.sound_entry.set_text(value)

        # sound, popup, auto_open, systray, roster
        for option in ('sound', 'popup', 'auto_open', 'systray', 'roster',
        'urgency_hint'):
            value = self.config[self.active_num][option]
            if value == 'yes':
                self._ui.__dict__['use_' + option + '_cb'].set_active(True)
            else:
                self._ui.__dict__['use_' + option + '_cb'].set_active(False)
            if value == 'no':
                self._ui.__dict__['disable_' + option + '_cb'].set_active(True)
            else:
                self._ui.__dict__['disable_' + option + '_cb'].set_active(False)

        # run_command
        value = self.config[self.active_num]['run_command']
        self._ui.run_command_cb.set_active(value)

        # command
        value = self.config[self.active_num]['command']
        self._ui.command_entry.set_text(value)

        # one shot
        if 'one_shot' in self.config[self.active_num]:
            value = self.config[self.active_num]['one_shot']
        else:
            value = False
        self._ui.one_shot_cb.set_active(value)

    def set_treeview_string(self):
        (model, iter_) = self._ui.conditions_treeview.get_selection().get_selected()
        if not iter_:
            return
        ind = self._ui.event_combobox.get_active()
        event = ''
        if ind > -1:
            event = self._ui.event_combobox.get_model()[ind][0]
        ind = self._ui.recipient_type_combobox.get_active()
        recipient_type = ''
        if ind > -1:
            recipient_type = self._ui.recipient_type_combobox.get_model()[ind][0]
        recipient = ''
        if recipient_type != 'everybody':
            recipient = self._ui.recipient_list_entry.get_text()
        if self._ui.all_status_rb.get_active():
            status = ''
        else:
            status = _('and I am: ')
            for st in ('online', 'away', 'xa', 'dnd'):
                if self._ui.__dict__[st + '_cb'].get_active():
                    status += helpers.get_uf_show(st) + ' '
        model[iter_][1] = _('When event: %(event)s for category: '
                            '%(recipient_type)s %(recipient)s %(status)s') % {
                                'event': event, 'recipient_type': recipient_type,
                                'recipient': recipient, 'status': status}

    def on_conditions_treeview_cursor_changed(self, widget):
        (model, iter_) = widget.get_selection().get_selected()
        if not iter_:
            self.active_num = ''
            return
        self.active_num = model[iter_][0]
        if self.active_num == 0:
            self._ui.up_button.set_sensitive(False)
        else:
            self._ui.up_button.set_sensitive(True)
        _max = self._ui.conditions_treeview.get_model().iter_n_children(None)
        if self.active_num == _max - 1:
            self._ui.down_button.set_sensitive(False)
        else:
            self._ui.down_button.set_sensitive(True)
        self.initiate_rule_state()
        self._ui.config_box.set_sensitive(True)
        self._ui.delete_button.set_sensitive(True)

    def on_new_button_clicked(self, widget):
        model = self._ui.conditions_treeview.get_model()
        num = self._ui.conditions_treeview.get_model().iter_n_children(None)
        self.config[num] = {'event': 'message_received', 'recipient_type': 'all',
            'recipients': '', 'status': 'all', 'tab_opened': 'both',
            'has_focus': 'both', 'sound': '', 'sound_file': '', 'popup': '',
            'auto_open': '', 'run_command': False, 'command': '', 'systray': '',
            'roster': '', 'one_shot': False, 'urgency_hint': False}
        iter_ = model.append((num, ''))
        path = model.get_path(iter_)
        self._ui.conditions_treeview.set_cursor(path)
        self.active_num = num
        self.set_treeview_string()
        self._ui.config_box.set_sensitive(True)

    def on_delete_button_clicked(self, widget):
        (model, iter_) = self._ui.conditions_treeview.get_selection().get_selected()
        if not iter_:
            return
        # up all others
        iter2 = model.iter_next(iter_)
        num = self.active_num
        while iter2:
            num = model[iter2][0]
            model[iter2][0] = num - 1
            self.config[num - 1] = self.config[num].copy()
            iter2 = model.iter_next(iter2)
        model.remove(iter_)
        del self.config[num]
        self.active_num = ''
        self._ui.config_box.set_sensitive(False)
        self._ui.delete_button.set_sensitive(False)
        self._ui.up_button.set_sensitive(False)
        self._ui.down_button.set_sensitive(False)

    def on_up_button_clicked(self, widget):
        (model, iter_) = self._ui.conditions_treeview.get_selection().get_selected()
        if not iter_:
            return
        conf = self.config[self.active_num].copy()
        self.config[self.active_num] = self.config[self.active_num - 1]
        self.config[self.active_num - 1] = conf

        model[iter_][0] = self.active_num - 1
        # get previous iter
        path = model.get_path(iter_)
        iter_ = model.get_iter((path[0] - 1,))
        model[iter_][0] = self.active_num
        self.on_conditions_treeview_cursor_changed(self._ui.conditions_treeview)

    def on_down_button_clicked(self, widget):
        (model, iter_) = self._ui.conditions_treeview.get_selection().get_selected()
        if not iter_:
            return
        conf = self.config[self.active_num].copy()
        self.config[self.active_num] = self.config[self.active_num + 1]
        self.config[self.active_num + 1] = conf

        model[iter_][0] = self.active_num + 1
        iter_ = model.iter_next(iter_)
        model[iter_][0] = self.active_num
        self.on_conditions_treeview_cursor_changed(self._ui.conditions_treeview)

    def on_event_combobox_changed(self, widget):
        if self.active_num < 0:
            return
        active = self._ui.event_combobox.get_active()
        if active == -1:
            return
        else:
            event = list(self.events_list.keys())[active]
        self.config[self.active_num]['event'] = event
        for w in ('use_systray_cb', 'disable_systray_cb', 'use_roster_cb',
        'disable_roster_cb'):
            self._ui.__dict__[w].set_sensitive(True)
        for w in self.events_list[event]:
            self._ui.__dict__[w].set_sensitive(False)
            self._ui.__dict__[w].set_state(False)
        self.set_treeview_string()

    def on_recipient_type_combobox_changed(self, widget):
        if self.active_num < 0:
            return
        recipient_type = self.recipient_types_list[
            self._ui.recipient_type_combobox.get_active()]
        self.config[self.active_num]['recipient_type'] = recipient_type
        if recipient_type == 'all':
            self._ui.recipient_list_entry.set_sensitive(False)
        else:
            self._ui.recipient_list_entry.set_sensitive(True)
        self.set_treeview_string()

    def on_recipient_list_entry_changed(self, widget):
        if self.active_num < 0:
            return
        recipients = widget.get_text()
        #TODO: do some check
        self.config[self.active_num]['recipients'] = recipients
        self.set_treeview_string()

    def set_status_config(self):
        if self.active_num < 0:
            return
        status = ''
        for st in ('online', 'away', 'xa', 'dnd'):
            if self._ui.__dict__[st + '_cb'].get_active():
                status += st + ' '
        if status:
            status = status[:-1]
        self.config[self.active_num]['status'] = status
        self.set_treeview_string()

    def on_status_radiobutton_toggled(self, widget):
        if self.active_num < 0:
            return
        if self._ui.all_status_rb.get_active():
            self._ui.status_expander.set_expanded(False)
            self.config[self.active_num]['status'] = 'all'
            # 'All status' clicked
            for st in ('online', 'away', 'xa', 'dnd'):
                self._ui.__dict__[st + '_cb'].set_sensitive(False)
        else:
            self._ui.status_expander.set_expanded(True)
            self.set_status_config()
            # 'special status' clicked
            for st in ('online', 'away', 'xa', 'dnd'):
                self._ui.__dict__[st + '_cb'].set_sensitive(True)

        self.set_treeview_string()

    def on_status_cb_toggled(self, widget):
        if self.active_num < 0:
            return
        self.set_status_config()

    # tab_opened OR (not xor) not_tab_opened must be active
    def on_tab_opened_cb_toggled(self, widget):
        if self.active_num < 0:
            return
        if self._ui.tab_opened_cb.get_active():
            self._ui.has_focus_cb.set_sensitive(True)
            self._ui.not_has_focus_cb.set_sensitive(True)
            if self._ui.not_tab_opened_cb.get_active():
                self.config[self.active_num]['tab_opened'] = 'both'
            else:
                self.config[self.active_num]['tab_opened'] = 'yes'
        else:
            self._ui.has_focus_cb.set_sensitive(False)
            self._ui.not_has_focus_cb.set_sensitive(False)
            self._ui.not_tab_opened_cb.set_active(True)
            self.config[self.active_num]['tab_opened'] = 'no'

    def on_not_tab_opened_cb_toggled(self, widget):
        if self.active_num < 0:
            return
        if self._ui.not_tab_opened_cb.get_active():
            if self._ui.tab_opened_cb.get_active():
                self.config[self.active_num]['tab_opened'] = 'both'
            else:
                self.config[self.active_num]['tab_opened'] = 'no'
        else:
            self._ui.tab_opened_cb.set_active(True)
            self.config[self.active_num]['tab_opened'] = 'yes'

    # has_focus OR (not xor) not_has_focus must be active
    def on_has_focus_cb_toggled(self, widget):
        if self.active_num < 0:
            return
        if self._ui.has_focus_cb.get_active():
            if self._ui.not_has_focus_cb.get_active():
                self.config[self.active_num]['has_focus'] = 'both'
            else:
                self.config[self.active_num]['has_focus'] = 'yes'
        else:
            self._ui.not_has_focus_cb.set_active(True)
            self.config[self.active_num]['has_focus'] = 'no'

    def on_not_has_focus_cb_toggled(self, widget):
        if self.active_num < 0:
            return
        if self._ui.not_has_focus_cb.get_active():
            if self._ui.has_focus_cb.get_active():
                self.config[self.active_num]['has_focus'] = 'both'
            else:
                self.config[self.active_num]['has_focus'] = 'no'
        else:
            self._ui.has_focus_cb.set_active(True)
            self.config[self.active_num]['has_focus'] = 'yes'

    def on_use_it_toggled(self, widget, oposite_widget, option):
        if widget.get_active():
            if oposite_widget.get_active():
                oposite_widget.set_active(False)
            self.config[self.active_num][option] = 'yes'
        elif oposite_widget.get_active():
            self.config[self.active_num][option] = 'no'
        else:
            self.config[self.active_num][option] = ''

    def on_disable_it_toggled(self, widget, oposite_widget, option):
        if widget.get_active():
            if oposite_widget.get_active():
                oposite_widget.set_active(False)
            self.config[self.active_num][option] = 'no'
        elif oposite_widget.get_active():
            self.config[self.active_num][option] = 'yes'
        else:
            self.config[self.active_num][option] = ''

    def on_use_sound_cb_toggled(self, widget):
        self.on_use_it_toggled(widget, self._ui.disable_sound_cb, 'sound')
        if widget.get_active():
            self._ui.sound_file_box.set_sensitive(True)
        else:
            self._ui.sound_file_box.set_sensitive(False)

    def on_browse_for_sounds_button_clicked(self, widget, data=None):
        self._new_filechooser()

    def _new_filechooser(self):
        if self.active_num < 0:
            return

        def on_ok(path_to_snd_file):
            self.config[self.active_num]['sound_file'] = path_to_snd_file
            self._ui.sound_entry.set_text(path_to_snd_file)

        path_to_snd_file = self._ui.sound_entry.get_text()
        path_to_snd_file = os.path.join(os.getcwd(), path_to_snd_file)
        SoundChooserDialog(on_ok,
                           path=path_to_snd_file,
                           transient_for=self)

    def on_play_button_clicked(self, widget):
        helpers.play_sound_file(self._ui.sound_entry.get_text())

    def on_disable_sound_cb_toggled(self, widget):
        self.on_disable_it_toggled(widget, self._ui.use_sound_cb, 'sound')

    def on_sound_entry_changed(self, widget):
        self.config[self.active_num]['sound_file'] = widget.get_text()

    def on_use_popup_cb_toggled(self, widget):
        self.on_use_it_toggled(widget, self._ui.disable_popup_cb, 'popup')

    def on_disable_popup_cb_toggled(self, widget):
        self.on_disable_it_toggled(widget, self._ui.use_popup_cb, 'popup')

    def on_use_auto_open_cb_toggled(self, widget):
        self.on_use_it_toggled(widget, self._ui.disable_auto_open_cb, 'auto_open')

    def on_disable_auto_open_cb_toggled(self, widget):
        self.on_disable_it_toggled(widget, self._ui.use_auto_open_cb, 'auto_open')

    def on_run_command_cb_toggled(self, widget):
        self.config[self.active_num]['run_command'] = widget.get_active()
        if widget.get_active():
            self._ui.command_entry.set_sensitive(True)
        else:
            self._ui.command_entry.set_sensitive(False)

    def on_command_entry_changed(self, widget):
        self.config[self.active_num]['command'] = widget.get_text()

    def on_use_systray_cb_toggled(self, widget):
        self.on_use_it_toggled(widget, self._ui.disable_systray_cb, 'systray')

    def on_disable_systray_cb_toggled(self, widget):
        self.on_disable_it_toggled(widget, self._ui.use_systray_cb, 'systray')

    def on_use_roster_cb_toggled(self, widget):
        self.on_use_it_toggled(widget, self._ui.disable_roster_cb, 'roster')

    def on_disable_roster_cb_toggled(self, widget):
        self.on_disable_it_toggled(widget, self._ui.use_roster_cb, 'roster')

    def on_one_shot_cb_toggled(self, widget):
        self.config[self.active_num]['one_shot'] = widget.get_active()
        self._ui.command_entry.set_sensitive(widget.get_active())

    def on_use_urgency_hint_cb_toggled(self, widget):
        self.on_use_it_toggled(widget, self._ui.disable_urgency_hint_cb,
            'uregency_hint')

    def on_disable_urgency_hint_cb_toggled(self, widget):
        self.on_disable_it_toggled(widget, self._ui.use_urgency_hint_cb,
            'uregency_hint')

    def on_hide(self, widget):
        # save config
        for n in list(self.plugin.config.keys()):
            del self.plugin.config[n]
        for n in self.config:
            self.plugin.config[str(n)] = self.config[n]
