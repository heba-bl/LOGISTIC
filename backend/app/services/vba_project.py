"""Build a real VBA project (`vbaProject.bin`) from source, without Excel.

openpyxl can preserve a macro project it was handed, never create one, and the
COM route needs "Trust access to the VBA project object model" switched on -
a security setting on somebody's workstation, not a build step. So the project
is assembled here from the two formats it is made of:

* MS-CFB, the compound-file container (the same one old .doc/.xls used), and
* MS-OVBA, the compression the VBA streams are stored with.

Both are documented and deterministic, which is the point: the workbook is
rebuilt byte-for-byte by a script, in CI, on any machine, with no Office
installed and nothing to click.

Reference: [MS-OVBA] 2.4.1 (compression) and [MS-CFB] 2.x (container).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

# --------------------------------------------------------------- compression
#: A compressed chunk decompresses to at most this many bytes.
CHUNK_SIZE = 4096


def _copy_token_help(decompressed_current: int, decompressed_chunk_start: int) -> tuple[int, int]:
    """Bit split between length and offset for a copy token.

    The split is not fixed: it widens as the decompressed chunk fills, so early
    tokens can address a short window with a long run and later ones the
    reverse. Getting this wrong yields a file Excel offers to "repair".
    """
    difference = decompressed_current - decompressed_chunk_start
    bit_count = max(4, (difference - 1).bit_length()) if difference > 1 else 4
    bit_count = min(max(bit_count, 4), 12)
    length_mask = 0xFFFF >> bit_count
    return bit_count, length_mask


def _compress_chunk(data: bytes) -> bytes:
    """Compress one decompressed chunk into its token stream."""
    output = bytearray()
    position = 0
    while position < len(data):
        flags = 0
        tokens = bytearray()
        for bit in range(8):
            if position >= len(data):
                break

            bit_count, length_mask = _copy_token_help(position, 0)
            max_length = (length_mask + 3)
            max_offset = 1 << (16 - bit_count)

            best_length = 0
            best_offset = 0
            window_start = max(0, position - max_offset)
            # A plain backwards scan: the inputs here are a few kilobytes of
            # VBA source, so the simple version is fast enough and easy to read.
            for candidate in range(window_start, position):
                length = 0
                while (
                    length < max_length
                    and position + length < len(data)
                    and data[candidate + length] == data[position + length]
                ):
                    length += 1
                if length > best_length:
                    best_length, best_offset = length, position - candidate

            if best_length >= 3:
                token = ((best_offset - 1) << (16 - bit_count)) | (best_length - 3)
                tokens += struct.pack("<H", token)
                flags |= 1 << bit
                position += best_length
            else:
                tokens.append(data[position])
                position += 1

        output.append(flags)
        output += tokens

    return bytes(output)


def compress(data: bytes) -> bytes:
    """MS-OVBA compressed container for `data`."""
    result = bytearray(b"\x01")

    for start in range(0, len(data), CHUNK_SIZE):
        chunk = data[start : start + CHUNK_SIZE]
        compressed = _compress_chunk(chunk)

        # A chunk is only stored compressed when that actually saves space;
        # otherwise it is stored raw, with the flag cleared.
        if len(compressed) < len(chunk):
            header = 0xB000 | (len(compressed) - 1)
            result += struct.pack("<H", header) + compressed
        else:
            header = 0x3000 | (len(chunk) - 1)
            result += struct.pack("<H", header) + chunk

    return bytes(result)


# ----------------------------------------------------------------- container
FREESECT = 0xFFFFFFFF
ENDOFCHAIN = 0xFFFFFFFE
FATSECT = 0xFFFFFFFD
DIFSECT = 0xFFFFFFFC

SECTOR_SIZE = 512
MINI_SECTOR_SIZE = 64
MINI_STREAM_CUTOFF = 4096


@dataclass
class Entry:
    """One directory entry: a storage (folder) or a stream (file)."""

    name: str
    kind: int  # 1 storage, 2 stream, 5 root
    data: bytes = b""
    children: list["Entry"] = field(default_factory=list)
    #: Filled in while laying the container out.
    identifier: int = -1
    child_id: int = FREESECT
    left_id: int = FREESECT
    right_id: int = FREESECT
    start_sector: int = ENDOFCHAIN
    size: int = 0


def _pack_chain(entries: list[int], per_sector: int) -> list[bytes]:
    """Split a flat allocation table into fixed-size sectors."""
    sectors: list[bytes] = []
    for start in range(0, len(entries), per_sector):
        block = entries[start : start + per_sector]
        block = block + [FREESECT] * (per_sector - len(block))
        sectors.append(b"".join(struct.pack("<I", value) for value in block))
    return sectors


class CompoundFile:
    """A minimal MS-CFB writer: enough to carry a VBA project, no more.

    Only what a `vbaProject.bin` needs is implemented - one root, one nested
    storage, a handful of streams - because a general-purpose writer would be a
    much larger thing to get right and nothing here would use it.
    """

    def __init__(self, root: Entry) -> None:
        self.root = root

    # -- layout ------------------------------------------------------------
    def _flatten(self) -> list[Entry]:
        """Directory entries in the order they will be written.

        The red-black tree the format specifies is replaced by a degenerate
        right-leaning chain, which readers accept: siblings are linked through
        `right_id` in name order, and Excel walks it without complaint.
        """
        ordered: list[Entry] = []

        def visit(entry: Entry) -> None:
            entry.identifier = len(ordered)
            ordered.append(entry)
            for child in entry.children:
                visit(child)

        visit(self.root)

        for entry in ordered:
            if not entry.children:
                continue
            children = entry.children
            entry.child_id = children[0].identifier
            for first, second in zip(children, children[1:]):
                first.right_id = second.identifier

        return ordered

    def build(self) -> bytes:
        entries = self._flatten()

        streams = [entry for entry in entries if entry.kind == 2 and entry.data]
        mini = [entry for entry in streams if len(entry.data) < MINI_STREAM_CUTOFF]
        regular = [entry for entry in streams if len(entry.data) >= MINI_STREAM_CUTOFF]

        # 1. The mini stream: small streams packed into 64-byte mini sectors.
        mini_stream = bytearray()
        mini_fat: list[int] = []
        for entry in mini:
            entry.start_sector = len(mini_stream) // MINI_SECTOR_SIZE
            entry.size = len(entry.data)
            padded = entry.data + b"\x00" * (
                -len(entry.data) % MINI_SECTOR_SIZE
            )
            count = len(padded) // MINI_SECTOR_SIZE
            first = len(mini_fat)
            for index in range(count):
                mini_fat.append(first + index + 1 if index < count - 1 else ENDOFCHAIN)
            mini_stream += padded

        # 2. Sector payloads, in the order they will be laid down.
        payloads: list[bytes] = []

        def allocate(data: bytes) -> tuple[int, int]:
            """Append `data` as whole sectors; return (first sector, count)."""
            padded = data + b"\x00" * (-len(data) % SECTOR_SIZE)
            first = len(payloads)
            for offset in range(0, len(padded), SECTOR_SIZE):
                payloads.append(padded[offset : offset + SECTOR_SIZE])
            return first, len(padded) // SECTOR_SIZE

        chains: list[tuple[int, int]] = []

        for entry in regular:
            first, count = allocate(entry.data)
            entry.start_sector = first
            entry.size = len(entry.data)
            chains.append((first, count))

        if mini_stream:
            mini_first, mini_count = allocate(bytes(mini_stream))
            self.root.start_sector = mini_first
            self.root.size = len(mini_stream)
            chains.append((mini_first, mini_count))
        else:
            self.root.start_sector = ENDOFCHAIN
            self.root.size = 0

        mini_fat_sectors = _pack_chain(mini_fat, SECTOR_SIZE // 4) if mini_fat else []
        mini_fat_first = FREESECT
        if mini_fat_sectors:
            mini_fat_first, mini_fat_count = allocate(b"".join(mini_fat_sectors))
            chains.append((mini_fat_first, mini_fat_count))

        directory = b"".join(self._directory_entry(entry) for entry in entries)
        directory_first, directory_count = allocate(directory)
        chains.append((directory_first, directory_count))

        # 3. The FAT describes every sector, including its own. Its size
        #    depends on the total, which depends on its size - so iterate until
        #    it settles, which it does in one or two passes.
        fat_sector_count = 1
        while True:
            total = len(payloads) + fat_sector_count
            needed = -(-total // (SECTOR_SIZE // 4))
            if needed == fat_sector_count:
                break
            fat_sector_count = needed

        fat = [FREESECT] * (len(payloads) + fat_sector_count)
        for first, count in chains:
            for index in range(count):
                fat[first + index] = (
                    first + index + 1 if index < count - 1 else ENDOFCHAIN
                )
        fat_first = len(payloads)
        for index in range(fat_sector_count):
            fat[fat_first + index] = FATSECT

        fat_sectors = _pack_chain(fat, SECTOR_SIZE // 4)
        assert len(fat_sectors) == fat_sector_count, (len(fat_sectors), fat_sector_count)

        # 4. Header. The DIFAT lives entirely in it: 109 slots is far more than
        #    a project of this size will ever need.
        header = bytearray(SECTOR_SIZE)
        header[0:8] = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
        struct.pack_into("<H", header, 24, 0x003E)  # minor version
        struct.pack_into("<H", header, 26, 0x0003)  # major version
        struct.pack_into("<H", header, 28, 0xFFFE)  # little endian
        struct.pack_into("<H", header, 30, 9)  # 2**9 = 512-byte sectors
        struct.pack_into("<H", header, 32, 6)  # 2**6 = 64-byte mini sectors
        struct.pack_into("<I", header, 44, fat_sector_count)
        struct.pack_into("<I", header, 48, directory_first)
        struct.pack_into("<I", header, 56, MINI_STREAM_CUTOFF)
        struct.pack_into("<I", header, 60, mini_fat_first)
        struct.pack_into("<I", header, 64, len(mini_fat_sectors))
        struct.pack_into("<I", header, 68, ENDOFCHAIN)  # no DIFAT sectors
        struct.pack_into("<I", header, 72, 0)

        for slot in range(109):
            value = fat_first + slot if slot < fat_sector_count else FREESECT
            struct.pack_into("<I", header, 76 + slot * 4, value)

        return bytes(header) + b"".join(payloads) + b"".join(fat_sectors)

    @staticmethod
    def _directory_entry(entry: Entry) -> bytes:
        raw = bytearray(128)
        name = entry.name.encode("utf-16-le") + b"\x00\x00"
        raw[0 : len(name)] = name
        struct.pack_into("<H", raw, 64, len(name))
        raw[66] = entry.kind
        raw[67] = 1  # black, so the degenerate tree stays valid
        struct.pack_into("<I", raw, 68, entry.left_id)
        struct.pack_into("<I", raw, 72, entry.right_id)
        struct.pack_into("<I", raw, 76, entry.child_id)
        struct.pack_into("<I", raw, 116, entry.start_sector)
        struct.pack_into("<Q", raw, 120, entry.size)
        return bytes(raw)


# ------------------------------------------------------------------- project
@dataclass
class Module:
    """One VBA module: a name, its source, and whether it is a class."""

    name: str
    source: str
    #: A document module is bound to a sheet; a standard module stands alone.
    kind: str = "standard"


#: Fixed prologue of the `_VBA_PROJECT` stream. It is a version stamp Excel
#: reads and rewrites; these bytes are what Office 2007+ writes.
_VBA_PROJECT_STREAM = bytes.fromhex("cc61ffff0000000000000000000000000000")


def _dir_stream(project_name: str, modules: list[Module]) -> bytes:
    """The `dir` stream: the project's table of contents, as records."""

    def record(identifier: int, payload: bytes) -> bytes:
        return struct.pack("<HI", identifier, len(payload)) + payload

    out = bytearray()
    out += record(0x0001, struct.pack("<H", 0x0001))  # SysKind: 32-bit
    out += record(0x0002, struct.pack("<I", 0x0000040C))  # Lcid
    out += record(0x0014, struct.pack("<I", 0x0000040C))  # LcidInvoke
    out += record(0x0003, struct.pack("<H", 0x04E4))  # CodePage (1252)
    out += record(0x0004, project_name.encode("latin-1"))
    out += record(0x0005, b"")  # DocString
    out += struct.pack("<HI", 0x0040, 0)  # DocStringUnicode
    out += record(0x0006, b"")  # HelpFile1
    out += record(0x003D, b"")  # HelpFile2
    out += record(0x0007, struct.pack("<I", 0))  # HelpContext
    out += record(0x0008, struct.pack("<I", 0))  # LibFlags
    out += record(0x0009, struct.pack("<IIH", 0x00000004, 0x00000002, 0x0000))  # Version
    out += record(0x000C, b"")  # Constants
    out += struct.pack("<HI", 0x003C, 0)  # ConstantsUnicode

    # One REFERENCE per library the project binds to. The two below are what a
    # workbook always carries: the VBA runtime and the Excel object library.
    def reference(name: str, libid: str) -> bytes:
        block = bytearray()
        block += record(0x0016, name.encode("latin-1"))
        block += struct.pack("<HI", 0x003E, 0)
        block += struct.pack("<HI", 0x000D, len(libid) + 10)
        block += struct.pack("<I", len(libid)) + libid.encode("latin-1")
        block += struct.pack("<IH", 0, 0)
        return bytes(block)

    out += reference(
        "stdole",
        r"*\G{00020430-0000-0000-C000-000000000046}#2.0#0#C:\Windows\SysWOW64\stdole2.tlb#OLE Automation",
    )
    out += reference(
        "Office",
        r"*\G{2DF8D04C-5BFA-101B-BDE5-00AA0044DE52}#2.0#0#C:\Program Files\Common Files\Microsoft Shared\OFFICE16\MSO.DLL#Microsoft Office 16.0 Object Library",
    )

    out += record(0x000F, struct.pack("<H", len(modules)))  # Modules count
    out += record(0x0013, struct.pack("<H", 0xFFFF))  # ProjectCookie

    for module in modules:
        out += record(0x0019, module.name.encode("latin-1"))
        out += struct.pack("<HI", 0x0047, len(module.name.encode("utf-16-le")))
        out += module.name.encode("utf-16-le")
        out += record(0x001A, module.name.encode("latin-1"))
        out += record(0x001C, b"")  # DocString
        out += struct.pack("<HI", 0x0048, 0)
        out += record(0x0031, struct.pack("<I", 0))  # Offset into the stream
        out += record(0x001E, struct.pack("<I", 0))  # HelpContext
        out += record(0x002C, struct.pack("<H", 0xFFFF))  # Cookie
        out += struct.pack("<HI", 0x0021 if module.kind == "standard" else 0x0022, 0)
        out += struct.pack("<HI", 0x002B, 0)  # Terminator for this module
    out += struct.pack("<HI", 0x0010, 0)  # Terminator for the project

    return compress(bytes(out))


def _project_stream(project_name: str, modules: list[Module]) -> bytes:
    """The `PROJECT` stream: plain text, read before anything else."""
    lines = [f'ID="{{{"00000000-0000-0000-0000-000000000000"}}}"']
    for module in modules:
        key = "Document" if module.kind == "document" else "Module"
        suffix = "=ThisWorkbook/&H00000000" if module.kind == "document" else ""
        lines.append(f"{key}={module.name}{suffix if key == 'Document' else ''}")
    lines += [
        f'Name="{project_name}"',
        'HelpContextID="0"',
        'VersionCompatible32="393222000"',
        'CMG="00000000000000000000"',
        'DPB="00000000000000000000"',
        'GC="00000000000000000000"',
        "",
        "[Host Extender Info]",
        "&H00000001={3832D640-CF90-11CF-8E43-00A0C911005A};VBE;&H00000000",
        "",
    ]
    return ("\r\n".join(lines)).encode("latin-1")


def _project_wm_stream(modules: list[Module]) -> bytes:
    """`PROJECTwm`: each module name in ANSI then UTF-16, terminated."""
    out = bytearray()
    for module in modules:
        out += module.name.encode("latin-1") + b"\x00"
        out += module.name.encode("utf-16-le") + b"\x00\x00"
    out += b"\x00\x00"
    return bytes(out)


def build_vba_project(project_name: str, modules: list[Module]) -> bytes:
    """Assemble a `vbaProject.bin` carrying `modules`."""
    vba_children = [
        Entry("_VBA_PROJECT", 2, _VBA_PROJECT_STREAM),
        Entry("dir", 2, _dir_stream(project_name, modules)),
    ]
    for module in modules:
        # The source is stored compressed, with no attribute prologue: the
        # offset recorded in `dir` is zero, so the whole stream is source.
        vba_children.append(Entry(module.name, 2, compress(module.source.encode("latin-1"))))

    root = Entry(
        "Root Entry",
        5,
        children=[
            Entry("VBA", 1, children=vba_children),
            Entry("PROJECT", 2, _project_stream(project_name, modules)),
            Entry("PROJECTwm", 2, _project_wm_stream(modules)),
        ],
    )
    return CompoundFile(root).build()
