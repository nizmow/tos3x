#!/usr/bin/env python3
"""Execute the ROM's MonSTer routine on a 68000 with simulated MMIO/GEMDOS.

Usage: python3 test/monster_test.py ROM SYMBOLS [--ram-mb 8]
Requires Unicorn 2.x. SYMBOLS is the output of bin/linux/cnm glue/tos.img.
This checks the assembled routine, not physical board timing or disk DMA.
"""

import argparse
from pathlib import Path
import struct
import unittest

from unicorn import (Uc, UcError, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN,
                     UC_HOOK_CODE, UC_HOOK_MEM_INVALID, UC_HOOK_MEM_READ,
                     UC_HOOK_MEM_WRITE, UC_PROT_READ)
from unicorn import m68k_const as m

REG = 0xfffffe00
JAR = 0x3000
END = 0x2000
FRB = 0x20000
MCH = 0x5f4d4348
FRB_ID = 0x5f465242
REGISTERS = [getattr(m, "UC_M68K_REG_D" + str(i)) for i in range(8)] + [
    getattr(m, "UC_M68K_REG_A" + str(i)) for i in range(7)]


class Machine:
    def __init__(self, *, present=True, machine=0, alt=False, capacity=16,
                 existing_frb=None, allocation=FRB, add_result=0, write_fault=False,
                 cpu=m.UC_CPU_M68K_M68000):
        self.uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        self.uc.ctl_set_cpu_model(cpu)
        self.uc.mem_map(0, 0x1000000)
        self.uc.mem_write(0xe00000, ROM)
        if present:
            if write_fault:
                self.uc.mem_map(0xfffff000, 0x1000, UC_PROT_READ)
            else:
                self.uc.mem_map(0xfffff000, 0x1000)
        self.calls = []
        self.writes = []
        self.reads = []
        self.faults = 0
        self.pending_fault = False
        self.allocation = allocation
        self.add_result = add_result
        self.write32(8, 0x43210)
        self.write32(0x5a0, JAR)
        cookies = [(MCH, machine)]
        if existing_frb is not None:
            cookies.append((FRB_ID, existing_frb))
        cookies.append((0, capacity))
        for i, (key, value) in enumerate(cookies):
            self.write32(JAR + i * 8, key)
            self.write32(JAR + i * 8 + 4, value)
        self.uc.mem_write(SYMBOLS['_shifty'], bytes([8 if alt else 0]))
        self.uc.reg_write(m.UC_M68K_REG_SR, 0x2300)
        for i, reg in enumerate(REGISTERS):
            self.uc.reg_write(reg, 0x123400 + 4*i)
        self.initial_regs = [self.uc.reg_read(reg) for reg in REGISTERS]
        self.uc.reg_write(m.UC_M68K_REG_A7, 0x10000)
        self.write32(0x10000, END)
        self.uc.hook_add(UC_HOOK_MEM_INVALID, self.invalid)
        self.uc.hook_add(UC_HOOK_MEM_READ, self.read, begin=REG, end=REG+1)
        self.uc.hook_add(UC_HOOK_MEM_WRITE, self.write, begin=REG, end=REG+1)
        self.uc.hook_add(UC_HOOK_CODE, self.code)

    def read32(self, address):
        return struct.unpack('>I', self.uc.mem_read(address, 4))[0]

    def write32(self, address, value):
        self.uc.mem_write(address, struct.pack('>I', value & 0xffffffff))

    def invalid(self, uc, access, address, size, value, data):
        if address != REG:
            raise AssertionError(f'unexpected invalid access: {address:#x}')
        self.pending_fault = True
        return False

    def read(self, uc, access, address, size, value, data):
        self.reads.append(size)

    def write(self, uc, access, address, size, value, data):
        self.writes.append((size, value))

    def code(self, uc, address, size, data):
        sp = uc.reg_read(m.UC_M68K_REG_A7)
        if address == SYMBOLS['_xmxalloc']:
            mode = struct.unpack('>H', uc.mem_read(sp + 8, 2))[0]
            self.calls.append(('alloc', self.read32(sp + 4), mode))
            result = self.allocation
        elif address == SYMBOLS['_xmaddalt']:
            self.calls.append(('add', self.read32(sp + 4), self.read32(sp + 8)))
            result = self.add_result
        elif address == SYMBOLS['_xmfree']:
            self.calls.append(('free', self.read32(sp + 4)))
            result = 0
        else:
            return
        # Simulate caller-saved register clobbering, as the actual C code may do.
        for reg in (m.UC_M68K_REG_D1, m.UC_M68K_REG_D2,
                    m.UC_M68K_REG_A0, m.UC_M68K_REG_A1):
            uc.reg_write(reg, 0xbadcafe)
        uc.reg_write(m.UC_M68K_REG_D0, result & 0xffffffff)
        uc.reg_write(m.UC_M68K_REG_PC, self.read32(sp))
        uc.reg_write(m.UC_M68K_REG_A7, sp + 4)

    def run(self):
        pc = SYMBOLS['_monster_init']
        for _ in range(3):
            try:
                self.uc.emu_start(pc, END, count=10000)
                break
            except UcError:
                if not self.pending_fault:
                    raise
                self.pending_fault = False
                self.faults += 1
                # Simulate a bus-error frame. The handler must discard it and
                # restore the saved SP, independent of the CPU's frame length.
                sp = self.uc.reg_read(m.UC_M68K_REG_A7)
                self.uc.reg_write(m.UC_M68K_REG_A7, sp - 58)
                pc = self.read32(8)
        assert self.uc.reg_read(m.UC_M68K_REG_PC) == END, 'routine did not return'
        assert self.uc.reg_read(m.UC_M68K_REG_A7) == 0x10004, 'stack not restored'
        assert self.read32(8) == 0x43210, 'bus-error vector not restored'
        assert self.uc.reg_read(m.UC_M68K_REG_SR) & 0xff00 == 0x2300
        assert [self.uc.reg_read(r) for r in REGISTERS] == self.initial_regs
        return self


class MonSTerTests(unittest.TestCase):
    def assert_added(self, state, size):
        self.assertIn(('add', 0x400000, size * 0x100000), state.calls)
        self.assertEqual(state.writes, [(2, size), (2, size)])

    def test_st(self):
        state = Machine().run()
        self.assert_added(state, RAM_MB)
        self.assertEqual(state.calls[0], ('alloc', 65536, 0))
        self.assertEqual(state.read32(JAR + 8), FRB_ID)
        self.assertEqual(state.read32(JAR + 12), FRB)
        self.assertEqual(state.read32(JAR + 16), 0)
        self.assertEqual(state.read32(JAR + 20), 16)

    def test_ste(self):
        self.assert_added(Machine(machine=0x10000).run(), RAM_MB)

    def test_megaste(self):
        self.assert_added(Machine(machine=0x10010).run(), min(6, RAM_MB))

    def test_absent(self):
        state = Machine(present=False).run()
        self.assertEqual(state.faults, 1)
        self.assertEqual(state.calls, [])

    def test_write_bus_error(self):
        state = Machine(write_fault=True).run()
        self.assertEqual(state.faults, 1)
        self.assertEqual(state.calls, [])

    def test_alt_bypass(self):
        state = Machine(alt=True).run()
        self.assertEqual((state.reads, state.writes, state.calls), ([], [], []))

    def test_existing_buffer(self):
        state = Machine(existing_frb=0x24000).run()
        self.assert_added(state, RAM_MB)
        self.assertEqual(len(state.calls), 1)
        self.assertEqual(state.read32(JAR + 12), 0x24000)

    def test_invalid_existing_buffer(self):
        self.assertEqual(Machine(existing_frb=0).run().calls, [])

    def test_full_cookie_jar(self):
        self.assertEqual(Machine(capacity=2).run().calls, [])

    def test_allocation_failure(self):
        for result in (0, -39):
            state = Machine(allocation=result).run()
            self.assertEqual(state.calls, [('alloc', 65536, 0)])
            self.assertEqual(state.read32(JAR + 8), 0)

    def test_registration_failure(self):
        state = Machine(add_result=-1).run()
        self.assertEqual(state.calls[-1], ('free', FRB))
        self.assertEqual(state.read32(JAR + 8), 0)

    def test_68030_absent(self):
        self.assertEqual(Machine(present=False, cpu=m.UC_CPU_M68K_M68030).run().calls, [])


def run_checker(*, available=True, corrupt=False):
    """Load/relocate the actual hardware checker and simulate its DOS calls."""
    program = CHECKER.read_bytes()
    magic, text, data, bss, symbols, _, flags, absolute = struct.unpack('>H6IH', program[:28])
    assert magic == 0x601a
    assert flags == 1, 'hardware checker must load and allocate in ST-RAM'
    base = 0x10000
    image = bytearray(program[28:28 + text + data])
    if not absolute:
        pos = 28 + text + data + symbols
        offset = struct.unpack_from('>I', program, pos)[0]
        pos += 4
        while offset:
            value = struct.unpack_from('>I', image, offset)[0]
            struct.pack_into('>I', image, offset, value + base)
            while True:
                step = program[pos]
                pos += 1
                if step == 1:
                    offset += 254
                    continue
                break
            if not step:
                break
            offset += step
    uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
    uc.ctl_set_cpu_model(m.UC_CPU_M68K_M68000)
    uc.mem_map(0, 0x1000000)
    uc.mem_write(base, bytes(image))
    uc.reg_write(m.UC_M68K_REG_A7, 0x30000)
    output = []
    finished = []
    freed = []

    def trap(uc, address, size, userdata):
        if bytes(uc.mem_read(address, 2)) != b'\x4e\x41':
            return
        sp = uc.reg_read(m.UC_M68K_REG_A7)
        function = struct.unpack('>H', uc.mem_read(sp, 2))[0]
        result = 0
        if function == 9:
            ptr = struct.unpack('>I', uc.mem_read(sp + 2, 4))[0]
            message = bytes(uc.mem_read(ptr, 256)).split(b'\0')[0]
            output.append(message.decode('ascii'))
        elif function == 0x44:
            amount = struct.unpack('>I', uc.mem_read(sp + 2, 4))[0]
            result = (4096 if amount == 0xffffffff else 0x400000) if available else 0
        elif function == 0x49:
            freed.append(struct.unpack('>I', uc.mem_read(sp + 2, 4))[0])
        elif function == 7:
            result = 65
        elif function == 0:
            finished.append(True)
            uc.emu_stop()
            return
        else:
            raise AssertionError(f'unexpected DOS function {function:#x}')
        uc.reg_write(m.UC_M68K_REG_D0, result)
        uc.reg_write(m.UC_M68K_REG_PC, address + 2)

    def bad_memory(uc, access, address, size, value, userdata):
        if corrupt:
            uc.mem_write(address, b'\0' * size)

    uc.hook_add(UC_HOOK_CODE, trap)
    uc.hook_add(UC_HOOK_MEM_READ, bad_memory, begin=0x400050, end=0x400053)
    uc.emu_start(base, 0, count=200000)
    assert finished, 'checker did not terminate'
    assert freed == ([0x400000] if available else [])
    return ''.join(output)


class HardwareCheckerTests(unittest.TestCase):
    def setUp(self):
        if CHECKER is None:
            self.skipTest('no --checker program provided')

    def test_pass(self):
        self.assertIn('PASS\r\n', run_checker())

    def test_bad_ram(self):
        self.assertIn('FAIL: memory readback mismatch', run_checker(corrupt=True))

    def test_no_ram(self):
        self.assertIn('No alternate RAM available', run_checker(available=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rom', type=Path)
    parser.add_argument('symbols', type=Path)
    parser.add_argument('--ram-mb', type=int, default=8)
    parser.add_argument('--checker', type=Path)
    args = parser.parse_args()
    ROM = args.rom.read_bytes()
    SYMBOLS = {}
    for line in args.symbols.read_text().splitlines():
        fields = line.split()
        if len(fields) == 3:
            SYMBOLS[fields[2]] = int(fields[0], 16)
    RAM_MB = args.ram_mb
    CHECKER = args.checker
    unittest.main(argv=['monster_test.py'], verbosity=2)
