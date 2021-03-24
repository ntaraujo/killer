from psutil import NoSuchProcess, AccessDenied, Process
from win32con import SM_CXICON
from win32api import GetSystemMetrics, GetFileVersionInfo, LOWORD, HIWORD
from os.path import dirname, abspath
from os.path import join as p_join
from os.path import exists as p_exists
from win32ui import CreateDCFromHandle, CreateBitmap
from win32gui import ExtractIconEx, DestroyIcon, GetDC  # noqa
from PIL import Image
from subprocess import Popen, PIPE
from os import PathLike, getpid
from typing import Union, Dict, Callable, Any, List, Optional, Type, Collection, Tuple
from pywintypes import error  # noqa
from bisect import bisect_left, bisect_right
import sys
from time import perf_counter
from requests import get as get_request

this_pid = getpid()
path_type = Union[str, bytes, PathLike]
this_dir: path_type = getattr(sys, '_MEIPASS', abspath(dirname(__file__)))
default_icon_path: path_type = p_join(this_dir, 'icons', 'default.png')


def get_version_number(exe: path_type) -> Optional[Tuple[int, int, int, int]]:
    try:
        info = GetFileVersionInfo(exe, "\\")
        ms = info['FileVersionMS']
        ls = info['FileVersionLS']
        return HIWORD(ms), LOWORD(ms), HIWORD(ls), LOWORD(ls)
    except error:
        return


def github_version_tag(xyz: Tuple[int, int, int, int]):
    versioned = []
    zero_removed = False
    for component in xyz[::-1]:
        if component >= 1 or zero_removed:
            zero_removed = True
            versioned.insert(0, str(component))
    return 'v' + '.'.join(versioned)


def proc_version_tag(proc: Process):
    exe = proc.__dict__.get("info", {}).get("exe", None)
    if exe is None:
        try:
            exe = proc.exe()
        except (NoSuchProcess, AccessDenied):
            return
    version = get_version_number(exe)
    if version is not None:
        return github_version_tag(version)


def latest_version(user: str, repo: str) -> str:
    return get_request(f"https://api.github.com/repos/{user}/{repo}/releases/latest").json()["tag_name"]


def update_to(version: str, user: str, repo: str):
    latest = latest_version(user, repo)
    if latest > version:
        return latest
    else:
        return


def icon_path(exe: path_type, name: str):
    id_file_name = f'{name}.png'
    id_path = p_join(this_dir, 'icons', id_file_name)

    if not p_exists(id_path):

        ico_x = GetSystemMetrics(SM_CXICON)

        try:
            large, small = ExtractIconEx(exe, 0)
        except error:
            return default_icon_path

        if not len(large):
            return default_icon_path

        if len(small):
            DestroyIcon(small[0])

        hdc = CreateDCFromHandle(GetDC(0))
        h_bmp = CreateBitmap()
        h_bmp.CreateCompatibleBitmap(hdc, ico_x, ico_x)
        hdc = hdc.CreateCompatibleDC()

        hdc.SelectObject(h_bmp)
        hdc.DrawIcon((0, 0), large[0])

        bmp_str = h_bmp.GetBitmapBits(True)
        img = Image.frombuffer(
            'RGBA',
            (32, 32),
            bmp_str, 'raw', 'BGRA', 0, 1
        )

        img.save(id_path)

        print(f'Icon of {exe} saved in {id_path}')

    return id_path


def is_responding(pid: int):
    cmd = f'tasklist /FI "PID eq {pid}" /FI "STATUS eq running"'
    status = Popen(cmd, stdout=PIPE).stdout.read()
    return str(pid) in str(status)


def keyring_bisect_left(seq: Collection, item, key_func: Callable[[Any], Any], reverse=False):
    k = key_func(item)
    keys = [key_func(e) for e in seq]
    return ordering_bisect_left(keys, k, reverse)


def ordering_bisect_left(seq: Collection, e, reverse: bool, lo: Optional[int] = None, hi: Optional[int] = None):
    """Find first index, starting from left, to insert e."""
    lo = lo or 0
    hi = hi or len(seq)
    if reverse:
        return len(seq) - bisect_right(seq[::-1], e, lo, hi)
    else:
        return bisect_left(seq, e, lo, hi)


def kill_proc_tree(parent: Process, include_parent=True):
    fails = []
    try:
        children = parent.children(recursive=True)
    except NoSuchProcess:
        children = []
    if include_parent:
        children.append(parent)
    for p in children:
        if not kill(p):
            fails.append(p)
    return fails


def kill(proc: Process):
    if proc.pid != this_pid:
        try:
            proc.kill()
            return True
        except NoSuchProcess:
            return True
        except AccessDenied:
            return False
    else:
        return False


funcs_results: Dict[Callable[[Any], Any], float] = {}
custom_results: Dict[str, List[Optional[Union[float, int]]]] = {}


def timer(function: Union[Callable[[Any], Any], str]) -> Optional[Callable[[Any], Any]]:
    if type(function) == str:
        if function in custom_results:
            tic = custom_results[function][0]
            toe = custom_results[function][1]
            if tic is None:
                custom_results[function][0] = perf_counter()
            elif toe is None:
                custom_results[function][1] = perf_counter() - tic
            else:
                custom_results[function][1] = (perf_counter() - tic + toe) / 2
            if tic is not None:
                custom_results[function][0] = None
                print(f'"{function}" is taking about {custom_results[function][1]:.5f} seconds.')
        else:
            custom_results[function] = [None, None]
        return

    def new_func(*args, **kwargs):
        _tic = perf_counter()
        to_return = function(*args, **kwargs)
        tac = perf_counter()
        if function in funcs_results:
            _toe = (tac - _tic + funcs_results[function]) / 2
        else:
            _toe = tac - _tic
        funcs_results[function] = _toe
        print(f'Function {function.__qualname__} is taking about {_toe:.5f} seconds.')
        return to_return

    return new_func
