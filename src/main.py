from kivy.uix.recycleview import RecycleView
from psutil import process_iter, NoSuchProcess, cpu_count
from kivymd.app import MDApp
from kivy.uix.screenmanager import Screen
from src.utils import icon_path, keyring_bisect_left
from kivymd.uix.list import OneLineIconListItem
from kivy.properties import StringProperty, ListProperty
from kivy.lang import Builder
from os.path import dirname, abspath
from os.path import join as p_join
from kivy.clock import Clock, mainthread
from time import sleep
from threading import Thread, Lock

from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivymd.uix.boxlayout import MDBoxLayout
from kivy.properties import BooleanProperty
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.behaviors import FocusBehavior
from kivy.uix.recycleview.layout import LayoutSelectionBehavior
from pprint import pprint
from copy import deepcopy

processes = dict()
processes_lock = Lock()

this_dir = dirname(abspath(__file__))
Builder.load_file(p_join(this_dir, 'main.kv'))

cpus = cpu_count()


def update_processes():
    global processes
    temp_processes = dict()
    for proc in process_iter(['pid', 'name', 'exe']):
        temp_processes[str(proc.info['pid'])] = proc

    processes_lock.acquire()
    for pid in list(processes):
        if pid not in temp_processes:
            del processes[pid]

    for pid, proc in temp_processes.items():
        if pid in processes:
            if proc.info['name'] != processes[pid].info['name']:
                processes[pid] = proc
        else:
            processes[pid] = proc
    processes_lock.release()


def always_updating_processes():
    while True:
        update_processes()
        sleep(1)


"""sample_data = [{"proc_pid": r,
                "proc_icon": icon_path('', 'default'),
                "proc_name": f'Sample Process {r}',
                "proc_cpu": '0.00%',
                "proc_mem": '0.00%'} for r in range(20)]"""


class Main(Screen):
    data_lock = Lock()
    keyfunc = reverse = order_by = None
    visible_range = (0, 0)
    special_order_cells = list()

    @mainthread
    def del_cell(self, c):
        try:
            self.ids.rv.data.remove(c)
        except ValueError:
            print('ValueError in Main.del_cell')

    @mainthread
    def add_cell(self, c):
        self.ids.rv.data.append(c)

    @mainthread
    def insert_cell(self, i, c):
        self.ids.rv.data.insert(i, c)

    @mainthread
    def assign_data(self, data):
        self.ids.rv.data = data

    @mainthread
    def update_cell(self, i, c):
        if len(self.ids.rv.data) > i:
            self.ids.rv.data[i] = c

    @mainthread
    def set_multiple_select(self, active):
        self.ids.multiple_select.active = active

    @mainthread
    def del_cell_by_index(self, i):
        if len(self.ids.rv.data) > i:
            del self.ids.rv.data[i]

    def new_special_order_cell(self, proc, proc_pid, proc_name, cpu, mem):
        proc_cpu = proc_mem = "0.00%"

        proc_exe = proc.info['exe']
        proc_icon = icon_path(proc_exe, proc_name)

        try:
            if cpu:
                proc_cpu = f'{proc.cpu_percent(1) / cpus:.2f}%'
            if mem:
                proc_mem = f'{proc.memory_percent():.2f}%'
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
                cell["proc_cpu"] = f'{proc.cpu_percent(1) / cpus:.2f}%'
            if mem:
                cell["proc_mem"] = f'{proc.memory_percent():.2f}%'
        except NoSuchProcess:
            print(f'NoSuchProcess {proc_pid} in Main.correct_special_order_cell')
        finally:
            self.special_order_cells[index] = cell

    def special_order_update_data(self):
        search = self.ids.search_field.text.lower()
        existing_search = search != ''

        cpu = self.order_by == "proc_cpu"
        mem = self.order_by == "proc_mem"

        self.special_order_cells = list()
        singles = list()
        correct_singles = list()

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

                if self.ids.multiple_select.active and proc_pid not in app.current_selection:
                    self.set_multiple_select(False)

        for single in singles:
            single.join()

        self.special_order_cells = sorted(self.special_order_cells, key=self.keyfunc, reverse=self.reverse)
        data_max = len(self.special_order_cells)

        for index in self.visible_range:
            if index >= data_max:
                break
            correct_singles.append(Thread(target=self.correct_special_order_cell, args=(index, not cpu, not mem)))
            correct_singles[-1].start()
        for single in correct_singles:
            single.join()

        processes_lock.release()

        with self.data_lock:
            self.assign_data(self.special_order_cells)

    def update_data(self):
        search = self.ids.search_field.text.lower()
        existing_search = search != ''

        self.data_lock.acquire()
        for cell in self.ids.rv.data:
            existent_process = cell['proc_pid'] in processes
            in_existent_search = existing_search and search in cell['proc_pid'] + cell['proc_name'].lower()
            search_compatible = not existing_search or in_existent_search

            if not existent_process or not search_compatible:
                self.del_cell(cell)

        existing_pids = [c['proc_pid'] for c in self.ids.rv.data]

        processes_lock.acquire()
        for proc_pid, proc in processes.items():

            proc_name = proc.info['name']

            in_data = proc_pid in existing_pids
            in_existent_search = existing_search and search in proc_pid + proc_name.lower()
            search_compatible = not existing_search or in_existent_search

            if not in_data and search_compatible:
                proc_exe = proc.info['exe']
                proc_icon = icon_path(proc_exe, proc_name)

                cell = {"proc_pid": proc_pid,
                        "proc_icon": proc_icon,
                        "proc_name": proc_name,
                        "proc_cpu": "0.00%",
                        "proc_mem": "0.00%"}

                if self.order_by is not None:
                    index = keyring_bisect_left(self.ids.rv.data, cell, self.keyfunc, self.reverse)
                    self.insert_cell(index, cell)
                else:
                    self.add_cell(cell)

                if self.ids.multiple_select.active and proc_pid not in app.current_selection:
                    self.set_multiple_select(False)
        processes_lock.release()
        self.data_lock.release()
        if self.order_by is None:
            self.order("proc_pid", False)

    def always_updating_data(self):
        while True:
            if self.order_by in ("proc_cpu", "proc_mem"):
                self.special_order_update_data()
            else:
                self.update_data()
            sleep(0.5)

    def order(self, order_by, reverse):
        def keyfunc(c):
            if order_by == "proc_name":
                return c[order_by].lower()
            else:
                return float(c[order_by].replace('%', ''))

        self.keyfunc = keyfunc
        self.reverse = reverse
        self.order_by = order_by
        with self.data_lock:
            temp_data = sorted(self.ids.rv.data, key=keyfunc, reverse=reverse)
            self.assign_data(temp_data)

    def set_visible_range(self):
        top_pos = self.ids.rv.to_local(self.ids.rv.center_x, self.ids.rv.height)
        top_i = self.ids.rv.layout_manager.get_view_index_at(top_pos)
        bottom_pos = self.ids.rv.to_local(self.ids.rv.center_x, 0)
        bottom_i = self.ids.rv.layout_manager.get_view_index_at(bottom_pos)

        self.visible_range = range(top_i, bottom_i + 1)

    def always_setting_visible_range(self):
        while True:
            self.set_visible_range()
            sleep(0.1)

    def update_visible(self):
        singles = []
        self.data_lock.acquire()
        for index in self.visible_range:
            singles.append(Thread(target=self.update_single, args=(index,)))
            singles[-1].start()
        for single in singles:
            single.join()
        self.data_lock.release()

    def update_single(self, index, cpu=True, mem=True):
        new_cell = self.ids.rv.data[index].copy()
        pid = new_cell['proc_pid']
        try:
            with processes[pid].oneshot():
                if cpu:
                    new_cell["proc_cpu"] = f'{processes[pid].cpu_percent(1) / cpus:.2f}%'
                if mem:
                    new_cell["proc_mem"] = f'{processes[pid].memory_percent():.2f}%'
        except NoSuchProcess:
            print(f"NoSuchProcess {pid} in Main.update_single")
        finally:
            self.update_cell(index, new_cell)

    def always_updating_visible(self):
        while True:
            if self.order_by not in ("proc_mem", "proc_cpu"):
                self.update_visible()
            sleep(0.5)


class Killer(MDApp):
    current_selection = ListProperty()
    sorted_by = StringProperty("PID")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.main = Main()

    def build(self):
        return self.main

    def on_start(self):
        Thread(target=always_updating_processes, daemon=True).start()
        Thread(target=self.main.always_updating_data, daemon=True).start()
        Thread(target=self.main.always_setting_visible_range, daemon=True).start()
        Thread(target=self.main.always_updating_visible, daemon=True).start()
        # Clock.schedule_interval(self.main.set_processes_list, 1)

    def select_row(self, pid, active):
        if active and pid not in self.current_selection:
            self.current_selection.append(pid)
        elif not active and pid in self.current_selection:
            self.current_selection.remove(pid)

    def select_rows(self, active):
        self.main.data_lock.acquire()
        if active:
            for cell in self.main.ids.rv.data:
                pid = cell['proc_pid']
                if pid not in self.current_selection:
                    self.current_selection.append(pid)
        else:
            self.current_selection = list()
        self.main.data_lock.release()

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
        print(f'Ordering by {key} in {"de" if desc else "a"}scendent order')
        Thread(target=self.main.order, args=(key, desc), daemon=True).start()


class SelectableRecycleBoxLayout(FocusBehavior, LayoutSelectionBehavior,
                                 RecycleBoxLayout):
    """ Adds selection and focus behaviour to the view. """


class CustomRecycleView(RecycleView):
    multiple_select_lock = Lock()

    def refresh_from_data(self, **kwargs):
        Thread(target=self.check_selections).start()
        return super().refresh_from_data(**kwargs)

    def check_selections(self):
        if not self.multiple_select_lock.locked():
            self.multiple_select_lock.acquire()
            for cell in self.data:
                if cell['proc_pid'] not in app.current_selection:
                    self.set_multiple_select(False)
            self.multiple_select_lock.release()

    @staticmethod
    @mainthread
    def set_multiple_select(active):
        app.main.ids.multiple_select.active = active


class ProcessCell(RecycleDataViewBehavior, MDBoxLayout):
    """ Add selection support to the Cell """
    proc_pid = StringProperty()
    proc_icon = StringProperty()
    proc_name = StringProperty()
    proc_cpu = StringProperty()
    proc_mem = StringProperty()

    def refresh_view_attrs(self, rv, index, data):
        """ Catch and handle the view changes """
        return super().refresh_view_attrs(
            rv, index, data)

    def on_touch_down(self, touch):
        """ Add selection on touch down """
        return super().on_touch_down(touch)

    def apply_selection(self, rv, index, is_selected):
        """ Respond to the selection of items in the view. """


if __name__ == '__main__':
    update_processes()
    app = Killer()
    app.run()
