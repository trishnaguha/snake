import vim
import inspect
from contextlib import contextmanager 
from functools import wraps, partial
import os
import sys
from os.path import expanduser, exists, abspath, join, dirname

command = vim.command

EMPTY_REGISTER = "Wt4jT@%jfeUf%@+3Vrrh6=Y92xzpasVyM55ghTy+48&k35BNXwxyGa8EFq"
NORMAL_MODE = "n"
VISUAL_MODE = "v"
INSERT_MODE = "i"
COMMAND_MODE = "c"

BUFFER_SCRATCH = 0

NS_GLOBAL = "g"
NS_BUFFER = "b"

_mapped_functions = {
}

def dispatch_mapped_function(key):
    """ this function will be called by any function mapped to a key in visual
    mode.  because we can't tell vim "hey, call this arbitrary, possibly
    anonymous, callable on key press", we have a single dispatch function to do
    that work for vim """
    try:
        fn = _mapped_functions[key]
    except KeyError:
        raise Exception("unable to find mapped function")
    else:
        return fn()

def generate_autocommand_name(fn):
    return inspect.getsourcefile(fn) + ":" + fn.__name__

def register_fn(fn):
    fn_key = id(fn)
    _mapped_functions[fn_key] = fn
    return "snake.dispatch_mapped_function(%s)" % fn_key

@contextmanager
def preserve_cursor():
    """ prevents change of cursor state """
    p = get_cursor_position()
    try:
        yield
    finally:
        set_cursor_position(p)

@contextmanager
def preserve_buffer():
    old_buffer = get_current_buffer()
    try:
        yield
    finally:
        set_buffer(old_buffer)

@contextmanager
def preserve_mode():
    """ prevents a change of vim mode state """
    yield
    return
    # TODO can't seem to get this to return the actual mode besides 'n'!!
    old_mode = get_mode()
    try:
        yield
    finally:
        return
        if old_mode == "n":
            set_normal_mode()
        elif old_mode == "v":
            set_visual_mode()

@contextmanager
def preserve_registers(*regs):
    """ prevents a change of register state """
    old_regs = {}

    special_regs = ('0', '"')
    regs = regs
    for reg in regs:
        contents = get_register(reg)
        old_regs[reg] = contents
        clear_register(reg)

    # we can't do a clear on the special registers, because setting one will
    # wipe out the other
    for reg in special_regs:
        contents = get_register(reg)
        old_regs[reg] = contents


    try:
        yield
    finally:
        for reg in regs + special_regs:
            old_contents = old_regs[reg]
            if old_contents is not None:
                set_register(reg, old_contents)

def abbrev(word, expansion, local=False):
    """ creates an abbreviation in insert mode.  expansion can be a string to
    expand to or a function that returns a value to serve as the expansion """

    cmd = "iabbrev"
    if local:
        cmd = cmd + " <buffer>"

    if callable(expansion):
        fn_str = register_fn(expansion)
        expansion = "<C-r>=pyeval('%s')<CR>" % escape_string_sq(fn_str)

    command("%s %s %s" % (cmd, word, expansion))

def expand(stuff):
    return vim.eval("expand('%s')" % escape_string_sq(stuff))
     
def get_current_dir():
    return dirname(get_current_file())

def get_current_file():
    return expand("%:p")

def get_mode():
    return vim.eval("mode(1)")


def get_cursor_position():
    return vim.current.window.cursor

def set_cursor_position(p):
    vim.current.window.cursor = p


def preserve_state():
    """ a general decorator for preserving most state, including cursor, mode,
    and basic special registers " and 0 """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            with preserve_cursor(), preserve_mode(), preserve_registers():
                return fn(*args, **kwargs)
        return wrapper
    return decorator

def escape_string_dq(s):
    s = s.replace('\\', '\\\\')
    s = s.replace('"', '\\"')
    return s

def escape_spaces(s):
    s = s.replace(" ", "\ ")
    return s

def escape_string_sq(s):
    s = s.replace('\\', '\\\\')
    s = s.replace("'", "\\'")
    return s

def set_normal_mode():
    keys("\<ESC>")

def set_visual_mode():
    keys("gv")

def multi_let(namespace, **name_values):
    """ convenience function for setting multiple globals at once in your
    .vimrc.py, all related to a plugin.  the first argument is a namespace to be
    appended to the front of each name/value pair. """
    for name, value in name_values.items():
        name = namespace + "_" + name
        let(name, value)

def _serialize_obj(obj):
    if isinstance(obj, basestring):
        obj = "'%s'" % escape_string_sq(obj)
    elif isinstance(obj, dict):
        obj = str(obj)
    return obj

def let_variable(name, value, namespace=None, scope=NS_GLOBAL):
    value = _serialize_obj(value)
    if namespace:
        name = namespace + "_" + name
    return command("let %s:%s=%s" % (scope, name, value))

def let(name, value, namespace=None):
    return let_variable(name, value, namespace, NS_GLOBAL)

def let_buffer_local(name, value, namespace=None):
    return let_variable(name, value, namespace, NS_BUFFER)

def get_global(name, namespace=None):
    if namespace:
        name = namespace + "_" + name
    try:
        val = vim.eval("g:%s" % name)
    except vim.error as e:
        if "Vim:E121" in e.message:
            val = None
        else:
            raise
    return val

def to_top():
    keys("gg")

def search(s, wrap=True, backwards=False, move=True):
    """ searches for string s, returning the (row, column) of the next match, or
    None if not found.  'move' moves the cursor to the match, 'backwards'
    specifies direction, 'wrap' for if searching should wrap around the end of
    the file """
    flags = []
    if wrap:
        flags.append("w")
    else:
        flags.append("W")

    if backwards:
        flags.append("b")

    s = escape_string_sq(s)

    def fn():
        line = int(vim.eval("search('%s', '%s')" % (s, "".join(flags))))
        match = line != 0

        if match:
            return get_cursor_position()
        else:
            return None

    if move:
        pos = fn()
    else:
        with preserve_cursor():
            pos = fn()

    return pos


def keys(k):
    """ feeds keys into vim as if you pressed them """
    k = escape_string_sq(k)
    command("execute 'normal! %s'" % k)

def get_register(name):
    val = vim.eval("@%s" % name)
    if val == EMPTY_REGISTER:
        val = None
    return val

def clear_register(name):
    set_register(name, EMPTY_REGISTER)

def set_register(name, val):
    val = escape_string_dq(val)
    command('let @%s = "%s"' % (name, val))

@preserve_state()
def get_word():
    keys("yiw")
    return get_register("0")

@preserve_state()
def delete_word():
    keys("diw")

@preserve_state()
def replace_word(rep):
    set_register('0', rep)
    keys("viwp")

@preserve_state()
def get_in_quotes():
    """ gets the string beneath the cursor that lies in either double or single
    quotes """
    keys("yi\"")
    val = get_register("0")
    if val is None:
        keys("yi'")
        val = get_register("0")
    return val


def key_map(key, maybe_fn=None, mode=NORMAL_MODE, recursive=False,
        local=False):

    # we're using key_map as a decorator
    if maybe_fn is None:
        def wrapper(fn):
            key_map(key, fn, mode=mode, recursive=recursive, local=local)
            return fn
        return wrapper

    map_command = "map"
    if not recursive:
        map_command = "nore" + map_command
    if mode:
        map_command = mode + map_command

    if local:
        map_command = map_command + " <buffer>"

    if callable(maybe_fn):
        fn = maybe_fn

        # if we're mapping in visual mode, we're going to assume that the
        # function takes the contents of the visual selection.  if the function
        # returns something, let's replace the visual selection with it.  i
        # think these are reasonable assumptions
        if mode == VISUAL_MODE:
            old_fn = fn
            @wraps(fn)
            def wrapped():
                sel = get_visual_selection()
                rep = old_fn(sel)
                if rep is not None:
                    replace_visual_selection(rep)
            fn = wrapped

        call = register_fn(fn)
        command("%s <silent> %s :python %s<CR>" % (map_command, key, call))

    else:
        command("%s %s %s" % (map_command, key, maybe_fn))


def visual_key_map(key, fn, recursive=False):
    return key_map(key, fn, mode=VISUAL_MODE, recursive=recursive)

def redraw():
    command("redraw!")

def set_buffer(buf):
    command("buffer %d" % buf)

def get_current_buffer():
    return int(vim.eval("bufnr('%')"))

def get_current_window():
    return int(vim.eval("winnr()"))

def get_num_windows():
    return int(vim.eval("winnr('$')"))

def get_window_of_buffer(buf):
    return int(vim.eval("bufwinnr(%d)" % buf))

def get_buffer_in_window(win):
    return int(vim.eval("winbufnr(%d)" % win))

def new_window(size=None, vertical=False):
    if vertical:
        cmd = "vsplit"
    else:
        cmd = "split"

    if size is not None:
        cmd = str(size) + cmd

    command(cmd)
    return get_current_window()


def toggle_option(name):
    command("set %s!" % name)

def multi_set_option(*names):
    """ convenience function for setting a ton of options at once, for example,
    in your .vimrc.py file.  regular strings are treated as options with no
    values, while list/tuple elements are considered name/value pairs"""
    for name in names:
        val = None
        if isinstance(name, (list, tuple)):
            name, val = name
        set_option(name, val)

def set_runtime_path(parts):
    rtp = ",".join(parts)
    set_option("rtp", rtp)

def get_runtime_path():
    rtp = get_option("rtp")
    return rtp.split(",")

def get_option(name):
    value = vim.eval("&%s" % name)
    return value

def set_option(name, value=None, local=False):
    cmd = "set"
    if local:
        cmd = "setlocal"

    if value is not None:
        command("%s %s=%s" % (cmd, name, value))
    else:
        command("%s %s" % (cmd, name))

def set_option_default(name):
    command("set %s&" % name)

def unset_option(name):
    command("set no%s" % name)

def set_local_option(name, value=None):
    if value is not None:
        command("setlocal %s=%s" % (name, value))
    else:
        command("setlocal %s" % name)

def new_buffer(name, type=BUFFER_SCRATCH):
    command("new")
    name = escape_string_sq(name)
    name = escape_spaces(name)
    command("file %s" % name)

    if type is BUFFER_SCRATCH:
        set_local("buftype", "nofile")
        set_local("bufhidden", "hide")
        set_local("noswapfile")

    buf = get_current_buffer()
    command("close!")
    return buf

@preserve_state()
def get_visual_selection():
    keys("gvy")
    val = get_register("0")
    return val

def replace_visual_selection(rep):
    with preserve_registers("a"):
        set_register("a", rep)
        keys("gvd")
        keys('"aP')

def set_buffer_contents(buf, s):
    set_buffer_lines(buf, s.split("\n"))

def set_buffer_lines(buf, l):
    b = vim.buffers[buf]
    b[:] = l

def get_buffer_contents(buf):
    contents = "\n".join(get_buffer_lines(buf))
    return contents

def get_buffer_lines(buf):
    b = vim.buffers[buf]
    return list(b)

def raw_input(prompt=""):
    """ designed to shadow python's raw_input function, because it behaves the
    same way, except in vim """
    command("call inputsave()")
    stuff = vim.eval("input('%s')" % escape_string_sq(prompt))
    command("call inputrestore()")
    return stuff

def multi_command(*cmds):
    """  convenience function for setting multiple commands at once in your
    .vimpy.rc, like "syntax on", "nohlsearch", etc """
    for cmd in cmds:
        command(cmd)


class AutoCommandContext(object):
    """ an object of this class is passed to functions decorated with one of our
    autocommand decorators.  its purpose is to give the decorated function
    access to buffer-local versions of our helper functions """

    def abbrev(self, *args, **kwargs):
        fn = partial(abbrev, local=True)
        return fn(*args, **kwargs)

    def let(self, *args, **kwargs):
        fn = partial(let, scope=NS_BUFFER)
        return fn(*args, **kwargs)

    def set_option(self, *args, **kwargs):
        fn = partial(set_option, local=True)
        return fn(*args, **kwargs)

    def key_map(self, *args, **kwargs):
        fn = partial(key_map, local=True)
        return fn(*args, **kwargs)


def file_is(filetype):
    """ a decorator for functions you wish to run when the buffer
    filetype=filetype.  your function will be passed an instance of
    AutoCommandContext, which contains on it *buffer-local* methods that would
    be useful to you.  this is useful if you want to set some keybindings for a
    python buffer that you just opened """

    def wrapped(fn):
        au_name = generate_autocommand_name(fn)
        command("augroup %s" % au_name)
        command("autocmd!")
        ctx = AutoCommandContext()
        call = register_fn(partial(fn, ctx))
        command("autocmd FileType %s :python %s" % (filetype, call))
        command("augroup END")
        return fn

    return wrapped


if "snake.plugin_loader" in sys.modules:
    plugin_loader = reload(plugin_loader)
else:
    import plugin_loader
