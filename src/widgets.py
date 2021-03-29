from kivy.animation import Animation
from kivy.base import EventLoop
from kivy.graphics.vertex_instructions import Rectangle
from kivy.properties import StringProperty, NumericProperty
from kivy.uix.textinput import FL_IS_LINEBREAK
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.list import OneLineAvatarIconListItem
from kivymd.uix.navigationdrawer import NavigationLayout
from kivymd.uix.selectioncontrol import MDCheckbox
from kivymd.uix.textfield import MDTextField


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


class MyTextInput(MDTextField):
    minimum_width = NumericProperty(0)

    def _split_smart(self, text):
        # modified to always split on newline only
        lines = text.split(u'\n')
        lines_flags = [0] + [FL_IS_LINEBREAK] * (len(lines) - 1)
        return lines, lines_flags

    def _refresh_text(self, text, *largs):
        # this is modified slightly just to calculate minimum_width

        # Refresh all the lines from a new text.
        # By using cache in internal functions, this method should be fast.
        mode = 'all'
        if len(largs) > 1:
            mode, start, finish, _lines, _lines_flags, len_lines = largs
            # start = max(0, start)
            cursor = None
        else:
            cursor = self.cursor_index()
            _lines, self._lines_flags = self._split_smart(text)
        _lines_labels = []
        _line_rects = []
        _create_label = self._create_line_label

        # calculate minimum width
        min_width = 0
        for x in _lines:
            lbl = _create_label(x)
            min_width = max(min_width, lbl.width)
            _lines_labels.append(lbl)
            _line_rects.append(Rectangle(size=lbl.size))
        self.minimum_width = min_width + self.padding[0] + self.padding[2]

        if mode == 'all':
            self._lines_labels = _lines_labels
            self._lines_rects = _line_rects
            self._lines = _lines
        elif mode == 'del':
            if finish > start:
                self._insert_lines(start,
                                   finish if start == finish else (finish + 1),
                                   len_lines, _lines_flags,
                                   _lines, _lines_labels, _line_rects)
        elif mode == 'insert':
            self._insert_lines(
                start,
                finish if (start == finish and not len_lines)
                else (finish + 1),
                len_lines, _lines_flags, _lines, _lines_labels,
                _line_rects)

        min_line_ht = self._label_cached.get_extents('_')[1]
        # with markup texture can be of height `1`
        self.line_height = max(_lines_labels[0].height, min_line_ht)
        # self.line_spacing = 2
        # now, if the text change, maybe the cursor is not at the same place as
        # before. so, try to set the cursor on the good place
        row = self.cursor_row
        self.cursor = self.get_cursor_from_index(self.cursor_index()
                                                 if cursor is None else cursor)
        # if we back to a new line, reset the scroll, otherwise, the effect is
        # ugly
        if self.cursor_row != row:
            self.scroll_x = 0
        # with the new text don't forget to update graphics again
        self._trigger_update_graphics()

    def on_text(self, instance, value):
        # added to update minimum width on each change
        cc, cr = self.cursor
        text = self._lines[cr]
        lbl = self._create_line_label(text)
        self.minimum_width = max(self.minimum_width, lbl.width + self.padding[0] + self.padding[2])

    def on_error(self, instance, value):
        _current_hint_text_color = _current_line_color = self.error_color if value else self.line_color_focus

        Animation(
            duration=0.2,
            _current_hint_text_color=_current_hint_text_color,
            _current_line_color=_current_line_color,
        ).start(self)


class RefreshInput(MyTextInput):
    def insert_text(self, substring, from_undo=False):
        if self.readonly or not substring or not self._lines:
            return

        if isinstance(substring, bytes):
            substring = substring.decode('utf8')

        if self.replace_crlf:
            substring = substring.replace(u'\r\n', u'\n')

        self._hide_handles(EventLoop.window)

        if not from_undo and self.multiline and self.auto_indent \
                and substring == u'\n':
            substring = self._auto_indent(substring)

        cc, cr = self.cursor
        sci = self.cursor_index
        ci = sci()
        text = self._lines[cr]
        len_str = len(substring)
        new_text = text[:cc] + substring + text[cc:]

        if new_text:
            try:
                number = float(new_text)
                if not (0 <= number <= 10):
                    return
            except ValueError:
                return

        self._set_line_text(cr, new_text)

        wrap = (self._get_text_width(
            new_text,
            self.tab_width,
            self._label_cached) > (self.width - self.padding[0] -
                                   self.padding[2]))
        if len_str > 1 or substring == u'\n' or wrap:
            # Avoid refreshing text on every keystroke.
            # Allows for faster typing of text when the amount of text in
            # TextInput gets large.

            start, finish, lines, lineflags, len_lines = \
                self._get_line_from_cursor(cr, new_text)
            # calling trigger here could lead to wrong cursor positioning
            # and repeating of text when keys are added rapidly in a automated
            # fashion. From Android Keyboard for example.
            self._refresh_text_from_property('insert', start, finish, lines,
                                             lineflags, len_lines)

        self.cursor = self.get_cursor_from_index(ci + len_str)
        # handle undo and redo
        self._set_unredo_insert(ci, ci + len_str, substring, from_undo)
