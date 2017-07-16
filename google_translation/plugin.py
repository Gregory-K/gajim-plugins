# -*- coding: utf-8 -*-
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim.  If not, see <http://www.gnu.org/licenses/>.
##
'''
Google Translation plugin.

Translates (currently only incoming) messages using Google Translate.

:note: consider this as proof-of-concept
:author: Mateusz Biliński <mateusz@bilinski.it>
:since: 25th August 2008
:copyright: Copyright (2008) Mateusz Biliński <mateusz@bilinski.it>
:                     (2012) mrDoctorWho <mrdoctorwho@gmail.com>
:license: GPL
'''

import json
import urllib
from gi.repository import Gtk
from sys import getfilesystemencoding

from gajim import chat_control
from gajim import groupchat_control

from gajim.plugins import GajimPlugin
from gajim.plugins.helpers import log_calls
from gajim.common import ged

languages = {
    _('Afrikaans'): 'af',
    _('Albanian'): 'sq',
    _('Armenian'): 'hy',
    _('Azerbaijani'): 'az',
    _('Arabic'): 'ar',
    _('Basque'): 'eu',
    _('Belarusian'): 'be',
    _('Bulgarian'): 'bg',
    _('Catalan'): 'ca',
    _('Chinese (Simplified)'): 'zh-cn',
    _('Chinese (Traditional)'): 'zh-tw',
    _('Croatian'): 'hr',
    _('Czech'): 'cs',
    _('Danish'): 'da',
    _('Dutch'): 'nl',
    _('English'): 'en',
    _('Estonian'): 'et',
    _('Filipino'): 'tl',
    _('Finnish'): 'fi',
    _('French'): 'fr',
    _('Galician'): 'gl',
    _('Georgian'): 'ka',
    _('German'): 'de',
    _('Greek'): 'el',
    _('Haitian Creole'): 'ht',
    _('Hebrew'): 'iw',
    _('Hindi'): 'hi',
    _('Hungarian'): 'hu',
    _('Icelandic'): 'is',
    _('Indonesian'): 'id',
    _('Italian'): 'it',
    _('Irish'): 'da',
    _('Japanese'): 'ja',
    _('Korean'): 'ko',
    _('Latvian'): 'lv',
    _('Lithuanian'): 'lt',
    _('Macedonian'): 'mk',
    _('Malay'): 'ml',
    _('Maltese'): 'mt',
    _('Norwegian'): 'no',
    _('Persian'): 'fa',
    _('Polish'): 'pl',
    _('Portuguese'): 'pt-BR',
    _('Romanian'): 'ro',
    _('Russian'): 'ru',
    _('Serbian'): 'sr',
    _('Slovak'): 'sk',
    _('Slovenian'): 'sl',
    _('Spanish'): 'es',
    _('Swahili'): 'sw',
    _('Swedish'): 'sv',
    _('Thai'): 'th',
    _('Turkish'): 'tr',
    _('Ukrainian'): 'uk',
    _('Urdu'): 'ur',
    _('Vietnamese'): 'vi',
    _('Welsh'): 'cy',
    _('Yiddish'): 'yi',
}

class GoogleTranslationPlugin(GajimPlugin):

    @log_calls('GoogleTranslationPlugin')
    def init(self):
        self.description = _('Translates (currently only incoming)'
            'messages using Google Translate.')
        self.config_dialog = None

        self.config_default_values = {
            'per_jid_config': ({}, ''),
        }

        self.events_handlers = {'decrypted-message-received': (ged.PREGUI,
            self._nec_decrypted_message_received)}

        self.gui_extension_points = {
            'chat_control_base' : (self.connect_with_control,
                self.disconnect_from_control),
        }

        self.controls = []

    @log_calls('GoogleTranslationPlugin')
    def translate_text(self, account, text, from_lang, to_lang):
        data = {"client": "x",
                "tl": to_lang,
                "sl": from_lang,
                "text": text}
        url = "http://translate.google.ru/translate_a/t"
        url = "%s?%s" % (url, urllib.parse.urlencode(data))
        request = urllib.request.Request(url)
        request.add_header("User-Agent",
            "Mozilla/5.0 (X11; Linux i686; rv:16.0) Gecko/20120815 Firefox/16.0")
        response = urllib.request.urlopen(request).read().decode('utf-8')
        if response:
            data = json.loads(response)
            return data["sentences"][0]["trans"]
        return text

    @log_calls('GoogleTranslationPlugin')
    def _nec_decrypted_message_received(self, obj):
        if not obj.msgtxt:
            return
        if obj.jid not in self.config['per_jid_config']:
            return
        if not self.config['per_jid_config'][obj.jid]['enabled']:
            return
        from_lang = self.config['per_jid_config'][obj.jid]['from']
        to_lang = self.config['per_jid_config'][obj.jid]['to']
        translated_text = self.translate_text(obj.conn.name, obj.msgtxt,
            from_lang, to_lang)
        if translated_text:
            obj.msgtxt = translated_text + '\n/' + _('Original text:') + '/ ' +\
                obj.msgtxt

    @log_calls('GoogleTranslationPlugin')
    def activate(self):
        pass

    @log_calls('GoogleTranslationPlugin')
    def deactivate(self):
        pass

    @log_calls('GoogleTranslationPlugin')
    def connect_with_control(self, control):
        base = Base(self, control)
        self.controls.append(base)

    @log_calls('GoogleTranslationPlugin')
    def disconnect_from_control(self, chat_control):
        for base in self.controls:
            base.disconnect_from_control()
            self.controls = []

class Base(object):
    def __init__(self, plugin, control):
        self.plugin = plugin
        self.control = control
        self.contact = control.contact
        self.account = control.account
        self.jid = self.contact.jid
        if self.jid in self.plugin.config['per_jid_config']:
            self.config = self.plugin.config['per_jid_config'][self.jid]
        else:
            self.config = {'from': '', 'to': 'en', 'enabled': False}
        self.create_buttons()

    def create_buttons(self):
        if isinstance(self.control, chat_control.ChatControl):
            vbox = self.control.xml.get_object('vbox106')
        elif isinstance(self.control, groupchat_control.GroupchatControl):
            vbox = self.control.xml.get_object('gc_textviews_vbox')
        else:
            return

        self.expander = Gtk.Expander(label=_('Google translation'))
        hbox = Gtk.HBox(spacing=6)
        self.expander.add(hbox)
        label = Gtk.Label(_('Translate from'))
        hbox.pack_start(label, False, False, 0)
        liststore1 = Gtk.ListStore(str, str)
        liststore2 = Gtk.ListStore(str, str)
        cb1 = Gtk.ComboBox.new_with_model(liststore1)
        cb2 = Gtk.ComboBox.new_with_model(liststore2)
        cell = Gtk.CellRendererText()
        cb1.pack_start(cell, True)
        cb1.add_attribute(cell, 'text', 0)
        cell = Gtk.CellRendererText()
        cb2.pack_start(cell, True)
        cb2.add_attribute(cell, 'text', 0)
        #Language to translate from
        liststore1.append([_('Auto'), ''])
        if self.config['from'] == '':
            cb1.set_active(0)
        if self.config['from'] == '':
            cb1.set_active(0)
        i = 0
        ls = sorted(languages.items())
        for l in ls:
            liststore1.append(l)
            if l[1] == self.config['from']:
                cb1.set_active(i+1)
            liststore2.append(l)
            if l[1] == self.config['to']:
                cb2.set_active(i)
            i += 1

        hbox.pack_start(cb1, False, False, 0)
        label = Gtk.Label(_('to'))
        hbox.pack_start(label, False, False, 0)
        hbox.pack_start(cb2, False, False, 0)

        cb = Gtk.CheckButton(_('enable'))
        if self.config['enabled']:
            cb.set_active(True)
        hbox.pack_start(cb, False, False, 0)
        vbox.pack_start(self.expander, False, False, 0)
        vbox.reorder_child(self.expander, 1)

        cb1.connect('changed', self.on_cb_changed, 'from')
        cb2.connect('changed', self.on_cb_changed, 'to')
        cb.connect('toggled', self.on_cb_toggled)
        self.expander.show_all()

    def on_cb_changed(self, widget, option):
        model = widget.get_model()
        it = widget.get_active_iter()
        self.config[option] = model[it][1]
        self.plugin.config['per_jid_config'][self.jid] = self.config
        self.plugin.config.save()

    def on_cb_toggled(self, widget):
        self.config['enabled'] = widget.get_active()
        self.plugin.config['per_jid_config'][self.jid] = self.config
        self.plugin.config.save()

    def disconnect_from_control(self):
        if isinstance(self.control, chat_control.ChatControl):
            vbox = self.control.xml.get_object('vbox106')
        elif isinstance(self.control, groupchat_control.GroupchatControl):
            vbox = self.control.xml.get_object('gc_textviews_vbox')
        else:
            return

        vbox.remove(self.expander)
