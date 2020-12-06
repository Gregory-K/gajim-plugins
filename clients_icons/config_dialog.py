# This file is part of Gajim.
#
# Gajim is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk

from gajim.gui.settings import SettingsDialog
from gajim.gui.const import Setting
from gajim.gui.const import SettingKind
from gajim.gui.const import SettingType

from gajim.plugins.plugins_i18n import _


class ClientsIconsConfigDialog(SettingsDialog):
    def __init__(self, plugin, parent):

        self.plugin = plugin
        settings = [

            Setting(SettingKind.SWITCH, _('Show Icons in Tooltip'),
                    SettingType.VALUE, self.plugin.config['show_in_tooltip'],
                    callback=self._on_setting, data='show_in_tooltip'),

            Setting(SettingKind.SWITCH, _('Show Icon for Unknown Clients'),
                    SettingType.VALUE, self.plugin.config['show_unknown_icon'],
                    callback=self._on_setting, data='show_unknown_icon'),

            ]

        SettingsDialog.__init__(self, parent, _('Clients Icons Configuration'),
                                Gtk.DialogFlags.MODAL, settings, None)

    def _on_setting(self, value, data):
        self.plugin.config[data] = value
