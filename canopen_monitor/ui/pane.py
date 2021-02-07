from __future__ import annotations
import curses
from abc import ABC, abstractmethod


class Pane(ABC):
    """Abstract Pane Class, contains a PAD and a window

    :param v_height: The virtual height of the embedded pad
    :type v_height: int

    :param v_width: The virtual width of the embedded pad
    :type v_width: int

    :param d_height: The drawn height of the embedded pad
    :type d_height: int

    :param d_width: The drawn width of the embedded pad
    :type d_width: int

    :param border: A style option for drawing a border around the pane
    :type border: bool
    """

    def __init__(self: Pane,
                 parent: any = None,
                 height: int = 1,
                 width: int = 1,
                 border: bool = True,
                 color_pair: int = 0):
        """Abstract pane initialization

        :param border: Toggiling whether or not to draw a border
        :type border: bool
        :value border: True

        :param color_pair: The color pair bound in curses config to use
        :type color_pair: int
        :value color_pair: 4
        """
        # Set virtual dimensions
        self.v_height = height
        self.v_width = width

        # Set or create the parent window
        self.parent = parent or curses.newwin(self.v_height, self.v_width)
        self._pad = curses.newpad(self.v_height, self.v_width)
        self._pad.scrollok(True)

        # Set the draw dimensions
        self.__reset_draw_dimensions()

        # Pane style options and state details
        self.border = border
        self.selected = False
        self._style = curses.color_pair(color_pair)
        self.needs_refresh = False
        self.scroll_position_y = 0
        self.scroll_position_x = 0
        self.scroll_limit_y = 0
        self.scroll_limit_x = 0

    @abstractmethod
    def draw(self: Pane) -> None:
        """Abstract draw method, must be overwritten in child class
        draw should first resize the pad using: `super().resize(w, h)`
        then add content using: self._pad.addstr()
        then refresh using: `super().refresh()`

        abstract method will clear and handle border

        child class should also set _scroll_limit_x and _scroll_limit_y here
        """
        if self.needs_refresh:
            self.refresh()

        self.parent.attron(self._style)
        self._pad.attron(self._style)

        if(self.border):
            self._pad.box()

    def resize(self: Pane, height: int, width: int) -> None:
        """Resize the virtual pad and change internal variables to reflect that

        :param height: New virtual height
        :type height: int

        :param width: New virtual width
        :type width: int
        """
        self.v_height = height
        self.v_width = width
        self.__reset_draw_dimensions()
        self._pad.resize(self.v_height, self.v_width)

    def __reset_draw_dimensions(self: Pane):
        p_height, p_width = self.parent.getmaxyx()
        self.d_height = min(self.v_height, p_height - 1)
        self.d_width = min(self.v_width, p_width - 1)

    def clear(self: Pane) -> None:
        """Clear all contents of pad and parent window

        .. warning::

            This should only be used if an event that changes the draw layout
            of the entire pane happens. If used on every cycle, flickering will
            likely occur due to the slowness of the operation.
        """
        self._pad.clear()
        self.parent.clear()
        self.refresh()

    def clear_line(self: Pane, y: int, style: any = None) -> None:
        """Clears a single line of the Pane

        :param y: The line to clear
        :type y: int

        :param style: The style to clear the line with. Only the background
            color of the style will affect the line-clear.
        :type style: int
        """
        style = style or curses.color_pair(0)
        self._pad.attron(self._style | style)
        self._pad.move(y, 0)
        self._pad.clrtoeol()
        self._pad.attroff(self._style | style)
        if(self.border):
            self._pad.box()

    def refresh(self: Pane) -> None:
        """Refresh the pane based on configured draw dimensions
        """
        self._pad.refresh(0, 0, 0, 0, self.d_height, self.d_width)
        self.needs_refresh = False

    def scroll_up(self: Pane, rate: int = 1) -> bool:
        """Scroll pad upwards

        .. note::

            Scroll limit must be set by child class

        :param rate: number of lines to scroll by
        :type rate: int
        :value: 1

        :return: Indication of whether a limit was reached. False indicates a
            limit was reached and the pane cannot be scrolled further in that
            direction
        :rtype: bool
        """
        self.scroll_position_y -= rate
        if self.scroll_position_y < 0:
            self.scroll_position_y = 0
            return False
        return True

    def scroll_down(self: Pane, rate: int = 1) -> bool:
        """Scroll pad downwards

        .. note::

            Scroll limit must be set by child class

        :param rate: number of lines to scroll by
        :type rate: int
        :value: 1

        :return: Indication of whether a limit was reached. False indicates a
            limit was reached and the pane cannot be scrolled further in that
            direction
        :rtype: bool
        """
        self.scroll_position_y += rate
        if self.scroll_position_y > self.scroll_limit_y:
            self.scroll_position_y = self.scroll_limit_y
            return False
        return True

    def scroll_left(self: Pane, rate: int = 1):
        """Scroll pad left

        .. note::

            Scroll limit must be set by child class

        :param rate: number of lines to scroll by
        :type rate: int
        :value: 1

        :return: Indication of whether a limit was reached. False indicates a
            limit was reached and the pane cannot be scrolled further in that
            direction
        :rtype: bool
        """
        self.scroll_position_x -= rate
        if self.scroll_position_x < 0:
            self.scroll_position_x = 0
            return False
        return True

    def scroll_right(self: Pane, rate: int = 1):
        """Scroll pad right

        .. note::

            Scroll limit must be set by child class

        :param rate: number of lines to scroll by
        :type rate: int
        :value: 1

        :return: Indication of whether a limit was reached. False indicates a
            limit was reached and the pane cannot be scrolled further in that
            direction
        :rtype: bool
        """
        self.scroll_position_x += rate
        if self.scroll_position_x > self.scroll_limit_x:
            self.scroll_position_x = self.scroll_limit_x
            return False
        return True

    def add_line(self: Pane,
                 y: int,
                 x: int,
                 line: str,
                 bold: bool = False,
                 highlight: bool = False) -> None:
        """Adds a line of text to the Pane and if needed, it handles the
        process of resizing the embedded pad

        :param y: Line's row position
        :type y: int

        :param x: Line's collumn position
        :type x: int

        :param line: Text to write to the Pane
        :type line: str

        :param bold: A style option to bold the line written
        :type bold: bool

        :param highlight: A syle option to highlight the line writte
        :type highlight: bool
        """
        # Widen pad when necessary
        new_width = len(line) + x
        if(new_width > self.v_width):
            self.resize(self.v_height, new_width)

        # Heighten the pad when necessary
        if(y > self.v_height):
            self.resize(y + 1, self.v_width)

        # Enable style options
        if bold:
            self._pad.attron(self._style | curses.A_BOLD)
        if highlight:
            self._pad.attron(self._style | curses.A_REVERSE)

        # Add the line
        if(y < self.d_height):
            self._pad.addstr(y, x, line)

        # Disable style options
        if bold:
            self._pad.attroff(self._style | curses.A_BOLD)
        if highlight:
            self._pad.attroff(self._style | curses.A_REVERSE)
