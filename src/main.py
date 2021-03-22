from kivymd.uix.list import OneLineAvatarIconListItem
from kivymd.uix.navigationdrawer import NavigationLayout
from psutil import process_iter, NoSuchProcess, cpu_count, AccessDenied
from kivymd.app import MDApp
from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty, ListProperty, NumericProperty, BooleanProperty
from kivy.lang import Builder
from os.path import dirname, abspath
from os.path import join as p_join
from kivy.clock import mainthread, Clock
from time import sleep
from threading import Thread, Lock, Event
from kivymd.uix.boxlayout import MDBoxLayout
from kivy.metrics import dp
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDRaisedButton
from typing import Dict, List
import sys
from utils import icon_path, kill_proc_tree, kill  # noqa

processes = {}
processes_lock = Lock()

this_dir = getattr(sys, '_MEIPASS', abspath(dirname(__file__)))
Builder.load_file(p_join(this_dir, 'main.kv'))

cpus = cpu_count()


def update_processes():
    global processes
    temp_processes = {}
    for proc in process_iter(['pid', 'name', 'exe']):
        temp_processes[str(proc.info['pid'])] = proc

    processes_lock.acquire()
    for pid in [*processes]:
        if pid not in temp_processes:
            if pid in app.current_selection:
                app.current_selection.remove(pid)
            del processes[pid]

    for pid, proc in temp_processes.items():
        if pid in processes:
            if proc.info['name'] != processes[pid].info['name']:
                processes[pid] = proc
        else:
            processes[pid] = proc
    processes_lock.release()


def first_update_processes():
    global processes
    processes = {str(proc.info['pid']): proc for proc in process_iter(['pid', 'name', 'exe'])}


def always_updating_processes():
    while True:
        update_processes()
        sleep(1)


class Main(Screen):
    data_lock = Lock()
    answer_lock = Lock()
    answered = ordered = False
    reverse = False
    order_by = "proc_pid"
    visible_range = range(0)
    special_order_cells = []
    order_cells = []
    answerers = []
    last_search = None

    def __init__(self, **kw):
        self.key_func = self.key_func
        super().__init__(**kw)

    @staticmethod
    def key_func(c):
        return float(c["proc_pid"].replace('%', ''))

    @mainthread
    def assign_data(self, data):
        self.ids.rv.data = data

    @mainthread
    def set_multiple_select(self, active):
        self.ids.multiple_select.active = active

    def new_special_order_cell(self, proc, proc_pid, proc_name, cpu, mem):
        proc_cpu = proc_mem = "0.0000%"

        proc_exe = proc.info['exe']
        proc_icon = icon_path(proc_exe, proc_name)

        try:
            if cpu:
                proc_cpu = f'{proc.cpu_percent(1) / cpus:.4f}%'
            if mem:
                proc_mem = f'{proc.memory_percent():.4f}%'
        except NoSuchProcess:
            print(f'NoSuchProcess {proc_pid} in Main.new_special_order_cell')

        cell = {"proc_pid": proc_pid,
                "proc_icon": proc_icon,
                "proc_name": proc_name,
                "proc_cpu": proc_cpu,
                "proc_mem": proc_mem}

        self.special_order_cells.append(cell)

    def correct_special_order_cell(self, index, cpu, mem):
        cell = self.special_order_cells[index]
        proc_pid = cell['proc_pid']
        proc = processes[proc_pid]
        try:
            if cpu:
                cell["proc_cpu"] = f'{proc.cpu_percent(1) / cpus:.4f}%'
            if mem:
                cell["proc_mem"] = f'{proc.memory_percent():.4f}%'
        except NoSuchProcess:
            print(f'NoSuchProcess {proc_pid} in Main.correct_special_order_cell')
        finally:
            self.special_order_cells[index] = cell

    def special_order_update_data(self):
        search = self.ids.search_field.text.lower()
        existing_search = search != ''

        cpu = self.order_by == "proc_cpu"
        mem = self.order_by == "proc_mem"

        self.special_order_cells = []
        singles = []
        correct_singles = []

        processes_lock.acquire()

        for proc_pid, proc in processes.items():

            proc_name = proc.info['name']

            in_existent_search = existing_search and search in proc_pid + proc_name.lower()
            search_compatible = not existing_search or in_existent_search
            existent_process = proc_pid in processes

            if search_compatible and existent_process:
                singles.append(Thread(target=self.new_special_order_cell,
                                      args=(proc, proc_pid, proc_name, cpu, mem)))
                singles[-1].start()

        for single in singles:
            single.join()

        self.special_order_cells: List[Dict[str, str]] = \
            sorted(self.special_order_cells, key=self.key_func, reverse=self.reverse)
        data_max = len(self.special_order_cells)

        for index in self.visible_range:
            if index >= data_max:
                break
            correct_singles.append(Thread(target=self.correct_special_order_cell, args=(index, not cpu, not mem)))
            correct_singles[-1].start()
        for single in correct_singles:
            single.join()

        processes_lock.release()

        self.update_data_base(self.special_order_cells)

    def correct_order_cell(self, index, cpu=True, mem=True):
        cell = self.order_cells[index]
        proc_pid = cell['proc_pid']
        proc = processes[proc_pid]
        try:
            with proc.oneshot():
                if cpu:
                    cell["proc_cpu"] = f'{proc.cpu_percent(1) / cpus:.4f}%'
                if mem:
                    cell["proc_mem"] = f'{proc.memory_percent():.4f}%'
        except NoSuchProcess:
            print(f'NoSuchProcess {proc_pid} in Main.correct_order_cell')
        finally:
            self.order_cells[index] = cell

    def order_update_data(self):
        search = self.ids.search_field.text.lower()
        existing_search = search != ''

        self.order_cells = []
        correct_singles = []

        processes_lock.acquire()

        for proc_pid, proc in processes.items():
            proc_name = proc.info["name"]

            in_existent_search = existing_search and search in proc_pid + proc_name.lower()
            search_compatible = not existing_search or in_existent_search

            if search_compatible:
                proc_exe = proc.info["exe"]
                proc_icon = icon_path(proc_exe, proc_name)

                cell = {"proc_pid": proc_pid,
                        "proc_icon": proc_icon,
                        "proc_name": proc_name,
                        "proc_cpu": "0.0000%",
                        "proc_mem": "0.0000%"}

                self.order_cells.append(cell)

        self.order_cells = sorted(self.order_cells, key=self.key_func, reverse=self.reverse)
        data_max = len(self.order_cells)

        if self.last_search is not None and len(self.ids.search_field.text) < len(self.last_search):
            self.update_data_base(self.order_cells)
            self.last_search = None

        for index in self.visible_range:
            if index >= data_max:
                break
            correct_singles.append(Thread(target=self.correct_order_cell, args=(index, True, True)))
            correct_singles[-1].start()
        for single in correct_singles:
            single.join()

        processes_lock.release()

        self.update_data_base(self.order_cells)

    def first_update_data(self):
        order_cells = []

        processes_lock.acquire()
        for proc_pid, proc in processes.items():
            proc_name = proc.info["name"]
            proc_exe = proc.info["exe"]
            proc_icon = icon_path(proc_exe, proc_name)

            cell = {"proc_pid": proc_pid,
                    "proc_icon": proc_icon,
                    "proc_name": proc_name,
                    "proc_cpu": "0.0000%",
                    "proc_mem": "0.0000%"}

            order_cells.append(cell)
        processes_lock.release()

        order_cells = sorted(order_cells, key=self.key_func, reverse=self.reverse)

        self.assign_data(order_cells)

    def update_data_base(self, new_data):
        if not self.answer_lock.locked():
            if not self.answered and not self.ordered:
                with self.data_lock:
                    self.assign_data(new_data)
            else:
                self.answered = self.ordered = False

    def always_updating_data(self):
        while True:
            if self.order_by in ("proc_cpu", "proc_mem"):
                self.special_order_update_data()
            else:
                self.order_update_data()

    def order(self, order_by, reverse):
        def key_func(c):
            if order_by == "proc_name":
                return c[order_by].lower()
            else:
                return float(c[order_by].replace('%', ''))

        self.key_func = key_func
        self.reverse = reverse
        self.order_by = order_by

        if order_by not in ("proc_cpu", "proc_mem"):
            self.ordered = True
            with self.data_lock:
                temp_data = sorted(self.ids.rv.data, key=key_func, reverse=reverse)
                self.assign_data(temp_data)
            self.ordered = True

    def set_visible_range(self):
        try:
            top_pos = self.ids.rv.to_local(self.ids.rv.center_x, self.ids.rv.height)
            top_i = self.ids.rv.layout_manager.get_view_index_at(top_pos)
            bottom_pos = self.ids.rv.to_local(self.ids.rv.center_x, 0)
            bottom_i = self.ids.rv.layout_manager.get_view_index_at(bottom_pos)
            self.visible_range = range(top_i, bottom_i + 1)
        except TypeError:
            pass  # random kivy error

    def always_setting_visible_range(self):
        while True:
            self.set_visible_range()
            sleep(0.1)

    def fast_answer(self, search):
        if search == "":
            return
        if not self.answer_lock.locked():
            Thread(target=self.answerers_control).start()
        self.answerers.append([Thread(target=self.fast_answer_base, args=(search,)), Event()])
        self.answerers[-1][0].start()
        self.answerers[-1][1].set()

    def answerers_control(self):
        self.answer_lock.acquire()
        while len(self.answerers) == 0:
            pass
        while len(self.answerers) != 0:
            self.answerers[0][1].wait()
            self.answerers[0][0].join()
            del self.answerers[0]
        self.answered = True
        self.answer_lock.release()

    def fast_answer_base(self, search):
        temp_data = []
        for cell in self.ids.rv.data:
            search_compatible = search.lower() in cell["proc_pid"] + cell["proc_name"].lower()
            if search_compatible:
                temp_data.append(cell)
        self.assign_data(temp_data)
        self.last_search = search


class Killer(MDApp):
    version = StringProperty(None, allownone=True)
    update = StringProperty(None, allownone=True)
    current_selection = ListProperty()
    sorted_by = StringProperty("PID")
    selection_lock = Lock()
    # List[List[Union[str, bool, Set[str], Set[str]]]]
    selection_control = []

    from json import load
    killer_config_file = p_join(this_dir, 'killer_config.json')
    with open(killer_config_file, "r") as killer_read_file:
        killer_config = load(killer_read_file)
    del killer_read_file, load

    def update_config(self):
        from json import dump
        with open(self.killer_config_file, "w") as write_file:
            dump(self.killer_config, write_file)

    zooms = {'0.5x': (32, 'Body2'),
             '1x': (dp(48), 'Body1')}

    z = killer_config['zoom']
    zoom = StringProperty(z)
    proc_height = NumericProperty(zooms[z][0])
    proc_style = StringProperty(zooms[z][1])
    del z

    @staticmethod
    def on_zoom(self, value):
        self.proc_height, self.proc_style = self.zooms[value]
        self.killer_config['zoom'] = value
        Thread(target=self.update_config).start()

    dark = BooleanProperty(killer_config['dark'])

    @staticmethod
    def on_dark(self, value):
        self.theme_cls.theme_style = "Dark" if value else "Light"
        self.killer_config['dark'] = value
        Thread(target=self.update_config).start()

    def __init__(self, **kwargs):
        self.icon = p_join(this_dir, 'icons\\Killer.exe.png')
        super().__init__(**kwargs)
        self.navigator = Navigator()
        self.main = Main()
        self.navigator.ids.sm.add_widget(self.main)
        self.theme_cls.theme_style = "Dark" if self.dark else "Light"

    def build(self):
        return self.navigator

    def on_start(self):
        self.main.first_update_data()
        Clock.schedule_once(self.search_focus)
        Thread(target=self.main.always_updating_data, daemon=True).start()
        Thread(target=self.main.always_setting_visible_range, daemon=True).start()
        Thread(target=always_updating_processes, daemon=True).start()
        Thread(target=self.always_selecting, daemon=True).start()

    def check_for_updates(self, state):
        if state == "open":
            Thread(target=self.check_for_updates_base).start()

    def check_for_updates_base(self):
        if self.version is None:
            from utils import proc_version_tag, this_pid  # noqa
            self.version = proc_version_tag(processes[str(this_pid)])
        if self.version is not None:
            from utils import update_to  # noqa
            self.update = update_to(self.version, 'ntaraujo', 'killer')

    def search_focus(*args):
        args[0].main.ids.search_field.focus = True

    def always_selecting(self):
        while True:
            if len(self.main.ids.rv.data) == 0:
                self.main.set_multiple_select(False)
                sleep(1)
                continue

            state = True
            self.selection_lock.acquire()
            self.main.data_lock.acquire()
            for cell in self.main.ids.rv.data:
                if cell["proc_pid"] not in self.current_selection:
                    state = False
                    break
            self.main.data_lock.release()
            self.main.set_multiple_select(state)
            self.selection_lock.release()
            sleep(1)

    def update_selection_label(self):
        selection_strings = []
        lonely_ones = []
        searches = []
        exceptions = []
        # _search: what was the search when general checkbox was clicked, or empty if it wasn't clicked
        # _check: if general checkbox was clicked
        # _added: related PIDs
        # _removed: related PIDs but unmarked
        for _search, _check, _added, _removed in self.selection_control:
            if _check:
                searches.append(_search)
                for pid in _removed:
                    if pid not in exceptions:
                        exceptions.append(pid)
            else:
                for one_pid in _added:
                    lonely_ones.append(one_pid)

        lonely_ones_amount = len(lonely_ones)
        if lonely_ones_amount:
            lonely_ones = sorted(lonely_ones, key=lambda x: int(x))
            last_lonely = lonely_ones[-1]
            if lonely_ones_amount == 1:
                selection_strings.append(f'process {last_lonely}')
            else:
                lonely_string = "processes " + ', '.join(lonely_ones)
                lonely_string = lonely_string.replace(f', {last_lonely}', f' and {last_lonely}')
                selection_strings.append(lonely_string)

        searches_amount = len(searches)
        if searches_amount:
            searches = sorted(searches)
            last_search = searches[-1]
            if searches_amount == 1:
                if last_search == "":
                    selection_strings.append("all")
                else:
                    selection_strings.append(f'all with "{last_search}"')
            else:
                search_string = 'all with "{}"'.format('" or "'.join(searches))
                selection_strings.append(search_string)

        exceptions_amount = len(exceptions)
        if exceptions_amount:
            exceptions = sorted(exceptions, key=lambda x: int(x))
            last_exception = exceptions[-1]
            if exceptions_amount == 1:
                selection_strings.append(f"except process {last_exception}")
            else:
                exception_string = 'except processes ' + ', '.join(exceptions)
                exception_string = exception_string.replace(f', {last_exception}', f' and {last_exception}')
                selection_strings.append(exception_string)

        if selection_strings:
            self.main.ids.selection_label.text = f'Selected: {"; ".join(selection_strings)} '
        else:
            self.main.ids.selection_label.text = ''

    def select_row(self, pid, active):
        if active and pid not in self.current_selection:
            self.current_selection.append(pid)

            changed = False
            for _search, _check, _added, _removed in self.selection_control:
                if pid in _removed:
                    # pid was related to a search before and was unmarked, now its being remarked
                    _removed.remove(pid)
                    changed = True
            if not changed:  # pid was not related to a previous search
                self.selection_control.append(["", False, {pid}, set()])  # _search is "" bcs doesn't matter
            self.update_selection_label()
        elif not active and pid in self.current_selection:
            self.current_selection.remove(pid)

            for _search, _check, _added, _removed in [*self.selection_control]:
                if pid in _added:
                    _removed.add(pid)
                    if not _added - _removed:
                        # all related PIDs were unmarked, doesn't matter _check
                        # the set _removed is still linked bcs there wasn't a deepcopy, so:
                        self.selection_control.remove([_search, _check, _added, _removed])
            self.update_selection_label()

    def select_rows(self, active):
        if active:
            pids = set()
            self.main.data_lock.acquire()
            for cell in self.main.ids.rv.data:
                pid = cell['proc_pid']
                if pid not in self.current_selection:
                    self.current_selection.append(pid)
                pids.add(pid)
            self.main.data_lock.release()

            search = self.main.ids.search_field.text
            need_to_add = True
            for _search, _check, _added, _removed in [*self.selection_control]:
                # selected all
                # selected a group which includes all _added bcs _search was more specific or as specific as
                surely_include_all = not search or (_check and search in _search)
                # selected a pid lonely selected before
                iter_include_all = surely_include_all or (not _check and not _added.difference(pids))
                if iter_include_all:
                    self.selection_control.remove([_search, _check, _added, _removed])
                elif _removed:
                    # if there was exceptions
                    for pid in pids:
                        if pid in _removed:
                            # if a marked pid was in these exceptions
                            _removed.remove(pid)
                if _check and _search in search and not iter_include_all:
                    # if a previous search was less specific than, or as specific as now,
                    # and was not removed, it includes all PIDs and there is no need to be redundant
                    need_to_add = False
            if need_to_add:
                self.selection_control.append([search, True, pids, set()])
        else:
            self.current_selection = []
            self.selection_control = []
        self.update_selection_label()

    def sort_by(self, data_type, order):
        self.sorted_by = data_type
        self.main.ids.order.icon = order
        if data_type == "Process Name":
            key = "proc_name"
        elif data_type == "PID":
            key = "proc_pid"
        elif data_type == "Memory Usage":
            key = "proc_mem"
        else:
            key = "proc_cpu"
        desc = True if order == "arrow-up" else False
        Thread(target=self.main.order, args=(key, desc), daemon=True).start()

    def kill_selected(self):
        fails = []
        with processes_lock:
            for pid in self.current_selection:
                proc = processes[pid]
                if not kill(proc):
                    fails.append(proc)
        self.show_fails(fails)

    def kill_selected_and_children(self):
        fails = []
        with processes_lock:
            for pid in self.current_selection:
                fails.extend(kill_proc_tree(processes[pid]))
        self.show_fails(fails)

    def show_fails(self, fails):
        if len(fails) == 0:
            return

        items = []

        cell = MiniProcessCell()
        cell.proc_name = "Process Name"
        cell.proc_pid = "PID"
        cell.proc_user = "Owner"
        items.append(cell)

        for proc in fails:
            cell = MiniProcessCell()
            cell.proc_name = proc.info["name"]
            cell.proc_icon = icon_path('', cell.proc_name)
            cell.proc_pid = str(proc.info["pid"])
            cell.little_font = dp(10)
            try:
                cell.proc_user = proc.username()
            except AccessDenied:
                pass
            except NoSuchProcess:
                continue
            finally:
                items.append(cell)

        if len(items) == 1:
            return

        title = f"Was not possible to kill the following process{'es' if len(items) > 2 else ''}:"

        fails_dialog = MDDialog(
            title=title,
            items=items,
            type="simple",
            buttons=[MDRaisedButton(text="OK")]
        )

        fails_dialog.ids.title.color = self.theme_cls.opposite_bg_normal

        fails_dialog.open()


class MiniProcessCell(OneLineAvatarIconListItem):
    proc_pid = StringProperty()
    proc_icon = StringProperty()
    proc_name = StringProperty()
    proc_user = StringProperty()
    little_font = NumericProperty(None)


class ProcessCell(MDBoxLayout):
    proc_pid = StringProperty()
    proc_icon = StringProperty()
    proc_name = StringProperty()
    proc_cpu = StringProperty()
    proc_mem = StringProperty()


class Navigator(NavigationLayout):
    pass


if __name__ == '__main__':
    first_update_processes()

    from kivy.config import Config

    Config.set('input', 'mouse', 'mouse,multitouch_on_demand')

    app = Killer()
    app.run()
