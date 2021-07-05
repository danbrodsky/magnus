#!/usr/bin/env python3

import json
import os
import codecs
import setproctitle
import sys
from functools import lru_cache
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Keybinder", "3.0")
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf, Gio, Keybinder  # noqa: E402


class Main(object):

    WIN_SIZE_OPTIONS = [
        (640, 480),
        (1280, 720),
        (1600, 900),
        (1920, 1080),
        (2560, 1440),
        (3840, 2160),
    ]

    def __init__(self):
        self.zoomlevel = 1
        self.app = Gtk.Application.new(
            "org.mirrus", Gio.ApplicationFlags.HANDLES_COMMAND_LINE
        )
        self.app.connect("command-line", self.handle_commandline)
        self.resize_timeout = None
        self.window_metrics = None
        self.window_metrics_restored = False
        self.decorations_height = 0
        self.decorations_width = 0
        self.min_width = 1280
        self.min_height = 720
        self.refresh_interval = 16
        self.prev_pointer = None
        self.frozen = False
        self.cursor_color = 0x81A397  # fancy blue :3

    def handle_commandline(self, app, cmdline):
        args = cmdline.get_arguments()

        if "--help" in args:
            print("Options:")
            print("  --refresh-interval=120")
            print("    Set refresh interval in milliseconds (lower is faster)")

        # Override refresh rate on command line
        for arg in args:
            if arg.startswith("--refresh-interval="):
                parts = arg.split("=")
                if len(parts) == 2:
                    try:
                        rival = int(parts[1])
                        print("Refresh interval set to {}ms".format(rival))
                        self.refresh_interval = rival
                    except ValueError:
                        pass

        # First time startup
        self.start_everything_first_time()
        return 0

    def start_everything_first_time(self, on_window_map=None):
        GLib.set_application_name("Mirrus")

        # the window
        self.w = Gtk.ApplicationWindow.new(self.app)
        self.w.set_size_request(self.min_width, self.min_height)
        self.w.set_default_size(self.min_width, self.min_height)
        self.w.set_resizable(False)
        self.w.set_title("Mirrus")
        self.w.connect("destroy", lambda a: self.app.quit())
        self.w.connect("configure-event", self.read_window_size)
        self.w.connect("configure-event", self.window_configure)
        self.w.connect("size-allocate", self.read_window_decorations_size)
        self.w.set_keep_above(True)
        self.w.set_keep_below(False)
        self.w.set_type_hint(Gdk.WindowTypeHint.DOCK)
        self.w.set_type_hint(Gdk.WindowTypeHint.NORMAL)
        self.w.stick()
        devman = self.w.get_screen().get_display().get_device_manager()
        self.pointer = devman.get_client_pointer()

        # XXX: could not add support for images as cursor because GTK would not
        # enable transparency, so cursor could only be rectangular
        # self.pointer_image = GdkPixbuf.Pixbuf.new_from_file_at_scale(
        # "cursor.png", 32, 32, False) self.pointer_image =
        # self.pointer_image.add_alpha(True, 255, 255, 255)

        self.pointer_image = GdkPixbuf.Pixbuf.new(
            GdkPixbuf.Colorspace.RGB, False, 8, 16, 20
        )
        self.pointer_image.fill(self.cursor_color)

        # the headerbar
        head = Gtk.HeaderBar()
        head.set_show_close_button(True)
        head.props.title = "Mirrus"
        self.w.set_titlebar(head)

        # the window size chooser
        resolution = Gtk.ComboBoxText.new()
        self.resolution = resolution
        for res in self.WIN_SIZE_OPTIONS:
            res_opt = "{}×{}".format(res[0], res[1])
            resolution.append(res_opt, res_opt)
        resolution.set_active(0)
        resolution.connect("changed", self.set_resolution)
        head.pack_end(resolution)

        # the zoom chooser
        zoom = Gtk.ComboBoxText.new()
        self.zoom = zoom
        for i in range(10, 40, 2):
            zoom.append(str(i / 10.0), "{}×".format(i / 10.0))
        zoom.set_active(0)
        zoom.connect("changed", self.set_zoom)
        head.pack_end(zoom)

        # the box that contains everything
        self.img = Gtk.Image()
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.add(self.img)
        self.w.add(scrolled_window)

        # bind the zoom keyboard shortcuts
        Keybinder.init()
        if Keybinder.supported():
            Keybinder.bind("<Alt><Super>plus", self.zoom_in, zoom)
            Keybinder.bind("<Alt><Super>equal", self.zoom_in, zoom)
            Keybinder.bind("<Alt><Super>minus", self.zoom_out, zoom)
            Keybinder.bind("<Ctrl><Alt>F", self.toggle_freeze)

        # and, go
        self.w.show_all()

        self.width = 0
        self.height = 0
        self.window_x = 0
        self.window_y = 0
        GLib.timeout_add(250, self.read_window_size)

        # and, poll
        GLib.timeout_add(self.refresh_interval, self.poll)

        GLib.idle_add(self.load_config)

    def toggle_freeze(self, keypress):
        self.frozen = not self.frozen

    def zoom_out(self, keypress, zoom):
        current_index = zoom.get_active()
        if current_index == 0:
            return
        zoom.set_active(current_index - 1)
        self.set_zoom(zoom)

    def zoom_in(self, keypress, zoom):
        current_index = zoom.get_active()
        size = zoom.get_model().iter_n_children(None)
        if current_index == size - 1:
            return
        zoom.set_active(current_index + 1)
        self.set_zoom(zoom)

    def read_window_decorations_size(self, win, alloc):
        sz = self.w.get_size()
        self.decorations_width = alloc.width - sz.width
        self.decorations_height = alloc.height - sz.height

    def set_zoom(self, zoom):
        self.zoomlevel = float(zoom.get_active_text()[:-1])
        self.poll()
        self.serialise()

    def set_resolution(self, res):
        (res_x, res_y) = res.get_active_text().split("×")
        print("res: ", res_x, res_y)
        self.w.set_resizable(True)
        self.w.set_size_request(int(res_x), int(res_y))
        self.w.set_resizable(False)

    def read_window_size(self, *args):
        loc = self.w.get_size()
        self.width = loc.width
        self.height = loc.height

    @lru_cache()
    def makesquares(
        self, overall_width, overall_height, square_size, value_on, value_off
    ):
        on_sq = list(value_on) * square_size
        off_sq = list(value_off) * square_size
        on_row = []
        off_row = []
        while len(on_row) < overall_width * len(value_on):
            on_row += on_sq
            on_row += off_sq
            off_row += off_sq
            off_row += on_sq
        on_row = on_row[: overall_width * len(value_on)]
        off_row = off_row[: overall_width * len(value_on)]

        on_sq_row = on_row * square_size
        off_sq_row = off_row * square_size

        overall = []
        count = 0
        while len(overall) < overall_width * overall_height * len(value_on):
            overall += on_sq_row
            overall += off_sq_row
            count += 2
        overall = overall[: overall_width * overall_height * len(value_on)]
        return overall

    @lru_cache()
    def get_white_pixbuf(self, width, height):
        square_size = 16
        light = (153, 153, 153, 255)
        dark = (102, 102, 102, 255)
        whole = self.makesquares(width, height, square_size, light, dark)
        arr = GLib.Bytes.new(whole)
        return GdkPixbuf.Pixbuf.new_from_bytes(
            arr, GdkPixbuf.Colorspace.RGB, True, 8, width, height, width * len(light)
        )

    def poll(self):
        display = Gdk.Display.get_default()
        if self.frozen:
            (screen, x, y, modifier) = self.prev_pointer
        else:
            (screen, x, y, modifier) = display.get_pointer()
            self.prev_pointer = (screen, x, y, modifier)
        if (
            x > self.window_x
            and x <= (self.window_x + self.width + self.decorations_width)
            and y > self.window_y
            and y <= (self.window_y + self.height + self.decorations_height)
        ):
            # pointer is over our window, so make it an empty pixbuf
            white = self.get_white_pixbuf(self.width, self.height)
            self.img.set_from_pixbuf(white)
        else:
            root = Gdk.get_default_root_window()
            scaled_width = self.width // self.zoomlevel
            scaled_height = self.height // self.zoomlevel
            scaled_xoff = scaled_width // 2
            scaled_yoff = scaled_height // 2
            screenshot = Gdk.pixbuf_get_from_window(
                root, x - scaled_xoff, y - scaled_yoff, scaled_width, scaled_height
            )

            # draw pointer on window
            (screen, p_x, p_y, modifier) = display.get_pointer()
            scaled_pointer_x = p_x - (x - scaled_xoff)
            scaled_pointer_y = p_y - (y - scaled_yoff)
            self.pointer_image.copy_area(
                0, 0, 6, 6, screenshot, scaled_pointer_x, scaled_pointer_y
            )

            scaled_pb = screenshot.scale_simple(
                self.width, self.height, GdkPixbuf.InterpType.NEAREST
            )
            self.img.set_from_pixbuf(scaled_pb)
        return True

    def window_configure(self, window, ev):
        if not self.window_metrics_restored:
            return False
        if self.resize_timeout:
            GLib.source_remove(self.resize_timeout)
        self.resize_timeout = GLib.timeout_add_seconds(
            1,
            self.save_window_metrics_after_timeout,
            {"x": ev.x, "y": ev.y, "w": ev.width, "h": ev.height},
        )
        self.window_x = ev.x
        self.window_y = ev.y

    def save_window_metrics_after_timeout(self, props):
        GLib.source_remove(self.resize_timeout)
        self.resize_timeout = None
        self.save_window_metrics(props)

    def save_window_metrics(self, props):
        scr = self.w.get_screen()
        sw = float(scr.get_width())
        sh = float(scr.get_height())
        # We save window dimensions as fractions of the screen dimensions,
        # to cope with screen resolution changes while we weren't running
        self.window_metrics = {
            "ww": props["w"] / sw,
            "wh": props["h"] / sh,
            "wx": props["x"] / sw,
            "wy": props["y"] / sh,
        }
        self.serialise()

    def restore_window_metrics(self, metrics):
        scr = self.w.get_screen()
        sw = float(scr.get_width())
        sh = float(scr.get_height())
        self.w.set_size_request(self.min_width, self.min_height)
        self.w.resize(int(sw * metrics["ww"]), int(sh * metrics["wh"]))
        self.w.move(int(sw * metrics["wx"]), int(sh * metrics["wy"]))

    def get_cache_file(self):
        return os.path.join(GLib.get_user_cache_dir(), "mirrus.json")

    def serialise(self, *args, **kwargs):
        # yeah, yeah, supposed to use Gio's async file stuff here. But it was
        # writing corrupted files, and I have no idea why; probably the Python
        # var containing the data was going out of scope or something. Anyway,
        # we're only storing a small JSON file, so life's too short to hammer
        # on this; we'll write with Python and take the hit.
        fp = codecs.open(self.get_cache_file(), encoding="utf8", mode="w")
        data = {"zoom": self.zoomlevel}
        if self.window_metrics:
            data["metrics"] = self.window_metrics
        json.dump(data, fp, indent=2)
        fp.close()

    def load_config(self):
        f = Gio.File.new_for_path(self.get_cache_file())
        f.load_contents_async(None, self.finish_loading_history)

    def finish_loading_history(self, f, res):
        try:
            success, contents, _ = f.load_contents_finish(res)
        except GLib.Error as e:
            print(
                ("couldn't restore settings (error: %s)" ", so assuming they're blank")
                % (e,)
            )
            contents = "{}"

        try:
            data = json.loads(contents)
        except Exception as e:
            print(
                (
                    "Warning: settings file seemed to be invalid json"
                    " (error: %s), so assuming blank"
                )
                % (e,)
            )
            data = {}
        zl = data.get("zoom")
        if zl:
            idx = 0
            for row in self.zoom.get_model():
                text, lid = list(row)
                if lid == str(zl):
                    self.zoom.set_active(idx)
                    self.zoomlevel = zl
                idx += 1
        metrics = data.get("metrics")
        if metrics:
            self.restore_window_metrics(metrics)
        self.window_metrics_restored = True


def main():
    setproctitle.setproctitle("mirrus")
    m = Main()
    m.app.run(sys.argv)


if __name__ == "__main__":
    main()
