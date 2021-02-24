from kivymd.uix.list import OneLineAvatarIconListItem
from psutil import process_iter, NoSuchProcess, cpu_count, AccessDenied
from kivymd.app import MDApp
from kivy.uix.screenmanager import Screen
from src.utils import icon_path, kill_proc_tree, kill
from kivy.properties import StringProperty, ListProperty, NumericProperty
from kivy.lang import Builder
from os.path import dirname, abspath
from os.path import join as p_join
from kivy.clock import mainthread
from time import sleep
from threading import Thread, Lock, Event
from kivymd.uix.boxlayout import MDBoxLayout
from kivy.metrics import dp
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDRaisedButton
from time import perf_counter
from typing import Dict, List

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
            if pid in app.current_selection:
                app.current_selection.remove(pid)
            del processes[pid]

    for pid, proc in temp_processes.items():
        if pid in processes:
            if proc.info['name'] != processes[pid].info['name']:
                processes[pid] = proc
        elif pid != "0":
            processes[pid] = proc
    processes_lock.release()


def always_updating_processes():
    while True:
        update_processes()
        sleep(1)


funcs_results = dict()


def timer(function):
    def new_func(*args, **kwargs):
        tic = perf_counter()
        function(*args, **kwargs)
        tac = perf_counter()
        print(f'Function {function.__qualname__} done')
        if function in funcs_results:
            toe = (tac - tic + funcs_results[function]) / 2
        else:
            toe = tac - tic
        funcs_results[function] = toe
    return new_func


class Main(Screen):
    data_lock = Lock()
    answer_lock = Lock()
    answered = ordered = False
    reverse = False
    order_by = "proc_pid"
    visible_range = range(0)
    special_order_cells = list()
    order_cells = list()
    answerers = list()

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

        if not self.answer_lock.locked():
            if not self.answered and not self.ordered:
                with self.data_lock:
                    self.assign_data(self.special_order_cells)
            else:
                self.answered = self.ordered = False

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

        self.order_cells = list()
        correct_singles = list()

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

                if self.ids.multiple_select.active and proc_pid not in app.current_selection:
                    self.set_multiple_select(False)

        self.order_cells = sorted(self.order_cells, key=self.key_func, reverse=self.reverse)
        data_max = len(self.order_cells)

        for index in self.visible_range:
            if index >= data_max:
                break
            correct_singles.append(Thread(target=self.correct_order_cell, args=(index, True, True)))
            correct_singles[-1].start()
        for single in correct_singles:
            single.join()

        processes_lock.release()

        if not self.answer_lock.locked():
            if not self.answered and not self.ordered:
                with self.data_lock:
                    self.assign_data(self.order_cells)
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
        top_pos = self.ids.rv.to_local(self.ids.rv.center_x, self.ids.rv.height)
        top_i = self.ids.rv.layout_manager.get_view_index_at(top_pos)
        bottom_pos = self.ids.rv.to_local(self.ids.rv.center_x, 0)
        bottom_i = self.ids.rv.layout_manager.get_view_index_at(bottom_pos)

        self.visible_range = range(top_i, bottom_i + 1)

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
            print("Waiting for first internal answerer")
        while len(self.answerers) != 0:
            self.answerers[0][1].wait()
            self.answerers[0][0].join()
            del self.answerers[0]
            print(f"Answered. Now {len(self.answerers)} answerers.")
        self.answered = True
        self.answer_lock.release()

    def fast_answer_base(self, search):
        temp_data = list()
        for cell in self.ids.rv.data:
            search_compatible = search.lower() in cell["proc_pid"] + cell["proc_name"]
            if search_compatible:
                temp_data.append(cell)
        self.assign_data(temp_data)


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
        Thread(target=self.main.order, args=(key, desc), daemon=True).start()

    def kill_selected(self):
        fails = list()
        with processes_lock:
            for pid in self.current_selection:
                proc = processes[pid]
                if not kill(proc):
                    fails.append(proc)
        self.show_fails(fails)

    def kill_selected_and_children(self):
        fails = list()
        with processes_lock:
            for pid in self.current_selection:
                fails.extend(kill_proc_tree(processes[pid]))
        self.show_fails(fails)

    @staticmethod
    def show_fails(fails):
        if len(fails) == 0:
            return

        items = list()

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
        text = f"Please, run Killer as Administrator if you want to try again. " \
               f"But even so, Windows can still stop you from doing it."

        fails_dialog = MDDialog(
            title=title,
            text=text,
            items=items,
            type="simple",
            buttons=[MDRaisedButton(text="OK")]
        )

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


if __name__ == '__main__':
    update_processes()
    app = Killer()
    app.run()

    for func, result in funcs_results.items():
        print(f'Function {func.__qualname__} is taking about {result:.5f} seconds.')
