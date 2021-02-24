from psutil import NoSuchProcess, AccessDenied
from win32con import SM_CXICON
from win32api import GetSystemMetrics
from os.path import dirname, abspath
from os.path import join as p_join
from os.path import exists as p_exists
from win32ui import CreateDCFromHandle, CreateBitmap
from win32gui import ExtractIconEx, DestroyIcon, GetDC
from PIL import Image
from subprocess import Popen, PIPE
from os import PathLike, getpid
from typing import Union
from pywintypes import error # noqa
from bisect import bisect_left, bisect_right
import sys

this_dir = getattr(sys, '_MEIPASS', abspath(dirname(__file__)))
this_pid = getpid()
path_type = Union[str, bytes, PathLike]
default_icon_path = p_join(this_dir, 'icons', 'default.png')


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


def keyring_bisect_left(seq, item, key_func, reverse=False):
    k = key_func(item)
    keys = [key_func(e) for e in seq]
    return ordering_bisect_left(keys, k, reverse)


def ordering_bisect_left(seq, e, reverse, lo=None, hi=None):
    """Find first index, starting from left, to insert e."""
    lo = lo or 0
    hi = hi or len(seq)
    if reverse:
        return len(seq) - bisect_right(seq[::-1], e, lo, hi)
    else:
        return bisect_left(seq, e, lo, hi)


def kill_proc_tree(parent, include_parent=True):
    fails = list()
    try:
        children = parent.children(recursive=True)
    except NoSuchProcess:
        children = list()
    if include_parent:
        children.append(parent)
    for p in children:
        if not kill(p):
            fails.append(p)
    return fails


def kill(proc):
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
