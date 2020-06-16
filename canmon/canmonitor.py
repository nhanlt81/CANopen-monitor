import curses
import time
from .bus import TheMagicCanBus
from .grid import Grid, Split
from .pane import Pane
import threading


class ErrorWindow:
    def __init__(self, parent, error, banner='fatal', color_pair=3):
        height, width = parent.getmaxyx()
        style = curses.color_pair(color_pair) | curses.A_REVERSE
        msg = error.split('\n')
        long = 0

        for m in msg:
            if(len(m) > long):
                long = len(m)

        window = curses.newwin(len(msg) + 2,
                               long + 2,
                               int((height - len(msg) + 2) / 2),
                               int((width - long + 2) / 2))
        window.attron(style)
        window.box()
        window.addstr(0, 1, banner + ":", curses.A_UNDERLINE | style)
        for i, m in enumerate(msg):
            window.addstr(1 + i, 1, m)
        window.attroff(style)

        window.refresh()
        parent.refresh()

        window.getch()
        curses.flushinp()
        window.clear()
        parent.clear()


class CanMonitor:
    def __init__(self, devices, table_schema, timeout=0.1, debug=False):
        # Monitor setup
        self.screen = curses.initscr()  # Initialize standard out
        self.screen.scrollok(True)      # Enable window scroll
        self.screen.keypad(True)        # Enable special key input
        self.screen.nodelay(True)       # Disable user-input blocking

        # App state things
        self.debug = debug

        # Bus things
        self.devices = devices
        self.bus = TheMagicCanBus(self.devices, timeout=timeout, debug=self.debug)

        # Pannel selection things
        self.pannel_index = 0       # Index to get to selected pannel
        self.pannel_flatlist = []   # List of all Panes contained in parent
        self.selected = None        # Reference to currently selected pane

        # Threading things
        self.screen_lock = threading.Lock()
        self.stop_listening = threading.Event()

        # Curses configuration
        curses.savetty()        # Save the terminal state
        # curses.raw()            # Enable raw input (DISABLES SIGNALS)
        curses.noecho()         # Disable user-input echo
        curses.cbreak()         # Disable line-buffering (less input delay)
        curses.curs_set(False)  # Disable the cursor display

        # Curses colors
        curses.start_color()
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(5, curses.COLOR_MAGENTA, curses.COLOR_BLACK)

        # Construct the grid(s)
        self.construct_grid(table_schema)

    def start(self):
        try:
            while not self.stop_listening.is_set():
                # Get CanBus input
                data = self.bus.receive()
                if(data is not None):
                    self.parent.add_frame(data)

                # Get user input
                self.read_input()

                # Draw the screen
                try:
                    self.screen_lock.acquire()
                    self.draw_banner()
                    self.parent.draw()
                    self.screen_lock.release()
                except Exception as e:
                    ErrorWindow(self.screen, e)
                    self.screen_lock.release()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self):
        # self.screen_lock.acquire()  # Acquire the screen lock
        curses.nocbreak()           # Re-enable line-buffering
        curses.echo()               # Enable user-input echo
        curses.curs_set(True)       # Enable the cursor
        curses.resetty()            # Restore the terminal state
        curses.endwin()             # Destroy the virtual screen
        # self.screen_lock.release()  # Release the screen lock
        self.stop_listening.set()   # Signal the bus threads to stop

        if(self.debug):  # Extra debug info
            print('stopping bus-listeners from the app-layer...')

        self.bus.stop_all()         # Wait for all CanBus threads to stop

        if(self.debug):  # Extra debug info
            print('stopped all bus-listeners!')

        threads = threading.enumerate().remove(threading.current_thread())
        if(self.debug):  # Extra debug info
            print('waiting for all app-threads to close...')

        # If app-layer threads exist wait for them to close
        if(threads is not None):
            for thread in threads:
                thread.join()
            if(self.debug):  # Extra debug info
                print('stopped all app-threads gracefully!')

        elif(self.debug):  # Extra debug info
            print('no child app-threads were spawned!')

    def read_input(self):
        # Grab new user input and immediately flush the buffer
        key = self.screen.getch()
        curses.flushinp()

        # Determine the key input
        if(key == curses.KEY_RESIZE):
            self.screen.clear()
            self.parent.clear()
            self.parent.resize(self.screen)
        elif((key == curses.KEY_SR or key == curses.KEY_SLEFT)
                and self.pannel_index > 0):
            self.pannel_index -= 1
            self.update_selected_pannel()
        elif((key == curses.KEY_SF or key == curses.KEY_SRIGHT)
                and self.pannel_index < len(self.pannel_flatlist) - 1):
            self.pannel_index += 1
            self.update_selected_pannel()
        elif(key == curses.KEY_UP):
            self.selected.scroll_up()
        elif(key == curses.KEY_DOWN):
            self.selected.scroll_down()

    def draw_banner(self):
        _, width = self.screen.getmaxyx()
        self.screen.addstr(0, 0, time.ctime(), curses.color_pair(0))
        self.screen.addstr(" | ")

        running = list(map(lambda x: x.ndev, self.bus.running()))
        for dev in self.devices:
            if(dev in running):
                color = 1
            else:
                color = 3

            self.screen.addstr(dev + " ", curses.color_pair(color))

        hottip = '<Ctrl+C> to quit'
        self.screen.addstr(0, width - len(hottip), hottip)

    def update_selected_pannel(self):
        if(self.selected is not None):
            self.selected.selected = False
        self.selected = self.pannel_flatlist[self.pannel_index]
        self.selected.selected = True

    def construct_grid(self, schema, parent=None):
        type = schema.get('type')
        split = schema.get('split')
        data = schema.get('data')
        split = {'horizontal': Split.HORIZONTAL,
                 'vertical': Split.VERTICAL}.get(split)

        if(parent is None):
            self.parent = Grid(parent=self.screen, split=split)

            for entry in data:
                self.construct_grid(entry, self.parent)
            self.pannel_flatlist = self.parent.flatten()
            self.update_selected_pannel()
        else:
            if(type == 'grid'):
                component = Grid(split=split)

                for entry in data:
                    self.construct_grid(entry, component)
            else:
                name = schema.get('name')
                fields = schema.get('fields')
                capacity = schema.get('capacity')
                stale_time = schema.get('stale_node_timeout')
                dead_time = schema.get('dead_node_timeout')
                frame_types = schema.get('frame_types')
                component = Pane(name,
                                 capacity=capacity,
                                 stale_time=stale_time,
                                 dead_time=dead_time,
                                 fields=fields,
                                 frame_types=frame_types)
            parent.add_pannel(component)
