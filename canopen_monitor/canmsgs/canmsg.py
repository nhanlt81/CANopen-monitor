import datetime
from enum import Enum
import pyvit.can as pc


class MessageType(Enum):
    NMT = 0
    SYNC = 1
    TIME = 2
    EMER = 3
    PDO1_TX = 4
    PDO1_RX = 5
    PDO2_TX = 6
    PDO2_RX = 7
    PDO3_TX = 8
    PDO3_RX = 9
    PDO4_TX = 10
    PDO4_RX = 11
    SDO_TX = 12
    SDO_RX = 13
    HEARTBEAT = 14
    UKNOWN = 15

    def cob_id_to_type(cob_id: int):
        """
        A static function for turning a COB ID into a MessageType.

        Arguments
        ---------
        cob_id `int`: The COB ID of the message.

        Returns
        -------
        `MessageType`: The message type of the the message based on the COB ID.
        """
        node_ranges = [(0x0, 0x0),
                       (0x1, 0x7F),
                       (0x100, 0x100),
                       (0x80, 0x0FF),
                       (0x180, 0x1FF),
                       (0x200, 0x27F),
                       (0x280, 0x2FF),
                       (0x300, 0x37F),
                       (0x380, 0x3FF),
                       (0x400, 0x47F),
                       (0x480, 0x4FF),
                       (0x500, 0x57F),
                       (0x580, 0x5FF),
                       (0x600, 0x680),
                       (0x700, 0x7FF)]

        # Determine a node type the cob id fits into
        #   and return the matching type
        for i, range in enumerate(node_ranges):
            if(cob_id >= range[0] and cob_id <= range[1]):
                return MessageType(i)

        # If the cob id matched no range then return the unknown type
        return MessageType(15)

    def cob_id_to_node_id(cob_id: int) -> int:
        """
        A static function for turning a COB ID into a Node ID.

        Arguments
        ---------
        cob_id `int`: The COB ID of the message.

        Returns
        -------
        `int`: The Node ID of the message.
        """
        # Determine a node type the cob id fits into and return the node id
        for range in MessageType.NODE_RANGES:
            if(cob_id >= range[0] and cob_id <= range[1]):
                return cob_id - range[0]

        # If the cob id matched no range then return None
        return None

    def __str__(self) -> str:
        return self.name


class CANMsg(pc.Frame):
    """
    Models a raw CANopen Message recieved from the CAN Bus
    """

    def __init__(self,
                 src: pc.Frame,
                 interface: str,
                 stale_timeout: int = 6,
                 dead_timeout: int = 12):
        """
        CANMsg Frame initialization.abs($0)

        Arguments
        ----------

        src `pyvit.can.Frame`: The raw Frame read off of the CAN bus.
        interface `str`: The name of the interface that src was read from.
        """
        super().__init__(src.arb_id,
                         data=src.data,
                         frame_type=src.frame_type,
                         interface=interface,
                         timestamp=datetime.datetime.now(),
                         extended=src.is_extended_id)
        self.message_type = MessageType.cob_id_to_type(src.arb_id)
        self.stale_timeout = stale_timeout
        self.dead_timeout = dead_timeout
        self.node_name = hex(self.arb_id)

    def __str__(self):
        attrs = []
        for k, v in self.__dict__.items():
            attrs += ['{}={}'.format(k, v)]
        return "<CANMsg {} {} {}>".format(self.status(),
                                          self.message_type,
                                          self.arb_id)

    def __le__(self, operand) -> bool:
        """
        Arguments
        ----------
        operand `CANMsg`: The CAN message to comare this object against.

        Returns
        -------
        `bool`: An indication of whether or not this object has a lesser or
                equal COB ID than the specified operand.
        """
        return self.arb_id <= operand.arb_id

    def status(self) -> str:
        """
        Returns
        -------
        `str`: A string indication of the CAN message's current status.
        """
        if(self.is_dead()):
            return 'DEAD'
        elif(self.is_stale()):
            return 'STALE'
        else:
            return 'ALIVE'

    def is_stale(self) -> bool:
        """
        Returns
        -------
        `bool`: An indication of whether or not this message is older than the
                configured stale timeout time.
        """
        return (datetime.datetime.now() - self.timestamp) \
            .total_seconds() >= self.stale_timeout

    def is_dead(self) -> bool:
        """
        Returns
        -------
        `bool`: An indication of whether or not this message is older than the
                configured dead timeout time.
        """
        return (datetime.datetime.now() - self.timestamp) \
            .total_seconds() >= self.dead_timeout
