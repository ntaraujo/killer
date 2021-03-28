from kivy.properties import StringProperty, NumericProperty
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.list import OneLineAvatarIconListItem
from kivymd.uix.navigationdrawer import NavigationLayout
from kivymd.uix.selectioncontrol import MDCheckbox


class MiniProcessCell(OneLineAvatarIconListItem):
    proc_pid = StringProperty()
    proc_icon = StringProperty()
    proc_name = StringProperty()
    proc_user = StringProperty()
    little_font = NumericProperty(None)


class Navigator(NavigationLayout):
    pass


class RVCheckBox(MDCheckbox):
    def on_state(self, instance, value):
        self.active = value == "down"
        self.update_icon()


class ProcessCell(MDBoxLayout):
    proc_pid = NumericProperty()
    proc_icon = StringProperty()
    proc_name = StringProperty()
    proc_cpu = NumericProperty()
    proc_mem = NumericProperty()
