from __future__ import annotations
from .interface import Interface
from .message import Message
import queue
import threading as t


class MagicCANBus:
    """This is a macro-manager for multiple CAN interfaces

    :param interfaces: The list of serialized Interface objects the bus is
        managing
    :type interfaces: [Interface]
    """

    def __init__(self: MagicCANBus, if_names: [str]):
        self.interfaces = list(map(lambda x: Interface(x), if_names))
        self.keep_alive = t.Event()
        self.keep_alive.set()
        self.message_queue = queue.SimpleQueue()
        self.threads = None

    def start_handler(self: MagicCANBus, iface: Interface) -> t.Thread:
        tr = t.Thread(target=self.handler,
                      name=f'canopem-monitor-{iface.name}',
                      args=[iface],
                      daemon=True)
        tr.start()
        return tr

    def handler(self: MagicCANBus, iface: Interface) -> None:
        iface.start()

        # The outer loop exists to enable interface recovery, if the interface
        #   is either deleted or goes down, the handler will try to start it
        #   again and read messages as soon as possible
        while(self.keep_alive.is_set()):
            try:
                # The inner loop is the constant reading of the bus and loading
                #   of frames into a thread-safe queue. It is necessary to
                #   check `iface.is_up` in the inner loop as well, so that the
                #   handler will not block on bus reading if the MCB is trying
                #   to close all threads and destruct itself
                while(self.keep_alive.is_set() and iface.is_up):
                    frame = iface.recv()
                    if(frame is not None):
                        self.message_queue.put(frame, block=True)
                iface.restart()
            except OSError:
                iface.restart()
        iface.stop()

    def __enter__(self: MagicCANBus) -> MagicCANBus:
        self.threads = list(map(lambda x: self.start_handler(x),
                                self.interfaces))
        return self

    def __exit__(self: MagicCANBus,
                 etype: str,
                 evalue: str,
                 traceback: any) -> None:
        self.keep_alive.clear()
        for tr in self.threads:
            print(f'Waiting for thread {tr} to end...')
            tr.join()

    def __iter__(self: MagicCANBus) -> MagicCANBus:
        return self

    def __next__(self: MagicCANBus) -> Message:
        if(self.message_queue.empty()):
            raise StopIteration
        return self.message_queue.get(block=True)

    def __repr__(self: MagicCANBus) -> str:
        alive_threads = sum(map(lambda x: 1 if x.is_alive() else 0,
                                self.threads))
        return f"Magic Can Bus: {self.interfaces}," \
               f" pending messages: {self.message_queue.qsize()}" \
               f" threads: {alive_threads}," \
               f" keep-alive: {self.keep_alive.is_set()}"
