## Mirrus

![example](data/example.gif)

### What is this?

Ever wanted to share your Linux machine's screen to people but your 4K monitor being degraded to 720p made the quality too low for viewing? Well this tool allows you to show only a subsection of your screen inside a new window so you don't need to scale down your screen resolution.

### Usage

The ideal way to use this tool is to open it, set the screen resolution you want to share, and share the application window in Discord, Zoom, etc. Then hide the window off at the side and present whatever you want. By default the mirror will always follow your cursor, but you can also press Ctrl+Alt+F to freeze the mirror in place. You can also switch workspaces freely without worrying about losing the screen share as the mirror will always remain on your desktop.

### Installation

You'll need the following dependencies:

  * `gir1.2-gdkpixbuf-2.0`
  * `gir1.2-glib-2.0`
  * `gir1.2-gtk-3.0`
  * `gir1.2-keybinder-3.0`
  * `python3`
  * `python3-gi`
  * `python3-setproctitle`

Run `setup.py` to build and install:

```bash
sudo python3 setup.py install
```

or `pip` to install as a package only:
```bash
sudo pip install .
```

### Acknowledgements
All credit goes to original creator of ![Magnus](https://github.com/stuartlangridge/magnus), I just made some slight modifications for my use-case. :3
