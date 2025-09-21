# -*- coding: utf-8 -*-
# Copyright (c) 2013, Michael Nooner
# All rights reserved.

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the copyright holder nor the names of its
#       contributors may be used to endorse or promote products derived from
#       this software without specific prior written permission

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""Minimal QR builder for the addon: version 5, level L, binary mode only.

Generates only the QR matrix (`QRCodeBuilder.code`).
- Version: 5 (size 37x37)
- Error correction: L
- Mode: binary (8-bit)
- Mask: 0 only

All writers and unused helpers removed.
"""
from __future__ import absolute_import, division, print_function, with_statement, unicode_literals

import io
import itertools
from copy import deepcopy

from . import tables


class QRCodeBuilder:
    """Build a QR code matrix for fixed configuration (v5/L/binary)."""

    def __init__(self, data, version, mode, error):
        self.data = data
        if mode != 'binary':
            raise ValueError('{0} is not a supported mode (expected binary).'.format(mode))
        if error != 'L':
            raise ValueError('{0} is not a supported error level (expected L).'.format(error))
        if version != 5:
            raise ValueError('Only version 5 is supported in this minimal build.')
        self.version = 5

        # Build data + ECC bitstream
        self.buffer = io.StringIO()
        self._build_data_stream()
        # Build final matrix
        self._build_matrix()

    # ------------------------ Bit helpers ------------------------
    def _b(self, data, length):
        return '{{0:0{0}b}}'.format(length).format(int(data))

    # ------------------------ Data encoding ---------------------
    def _build_data_stream(self):
        # Mode indicator: binary (0100)
        self.buffer.write('0100')
        # Length: 8 bits (fixed for our needs)
        self.buffer.write(self._b(len(self.data), 8))
        # Payload: 8-bit per char
        for ch in self.data:
            if isinstance(ch, int):
                self.buffer.write(self._b(ch, 8))
            else:
                self.buffer.write(self._b(ord(ch), 8))

        # Capacity for v5-L is 864 data bits (108 bytes)
        capacity_bits = 864
        s = self.buffer.getvalue()
        if len(s) > capacity_bits:
            raise ValueError('The supplied data will not fit within this version of a QR code.')

        # Terminator up to 4 bits
        short = capacity_bits - len(s)
        if short > 0:
            self.buffer.write(self._b(0, 4 if short >= 4 else short))

        # Pad to byte boundary
        bits_short = 8 - (len(self.buffer.getvalue()) % 8)
        if bits_short != 0 and bits_short != 8:
            self.buffer.write(self._b(0, bits_short))

        # Pad bytes to reach 108 data bytes
        total_data_bytes = 108
        data_bytes = len(self.buffer.getvalue()) // 8
        needed = total_data_bytes - data_bytes
        if needed > 0:
            pad_cycle = itertools.cycle(['11101100', '00010001'])
            self.buffer.write(''.join(next(pad_cycle) for _ in range(needed)))

        # Build data bytes array
        s = self.buffer.getvalue()
        data = [int(s[i:i+8], 2) for i in range(0, len(s), 8)]
        if len(data) != 108:
            raise ValueError('Unexpected data length; expected 108 bytes for version 5-L.')

        # Compute ECC (26 bytes)
        ecc = self._rs_ecc(data, 26)

        # Final payload = data then ecc
        out = io.StringIO()
        for b in data:
            out.write(self._b(b, 8))
        for b in ecc:
            out.write(self._b(b, 8))
        self.buffer = out

    # ------------------------ Reed–Solomon ECC ------------------
    def _rs_ecc(self, data_bytes, ecc_len):
        # message polynomial coefficients (copy)
        mp = list(data_bytes)
        # append ecc_len zeros
        mp.extend([0] * ecc_len)
        gen = tables.generator_polynomials[ecc_len]
        tmp = [0] * len(gen)

        # Process each data byte
        for _ in range(len(data_bytes)):
            coeff = mp.pop(0)
            if coeff == 0:
                continue
            alpha = tables.galois_antilog[coeff]
            for n in range(len(gen)):
                v = alpha + gen[n]
                if v > 255:
                    v %= 255
                tmp[n] = tables.galois_log[v]
                mp[n] ^= tmp[n]

        # Remaining first ecc_len entries are the ECC bytes
        return mp[:ecc_len]

    # ------------------------ Matrix construction ---------------
    def _build_matrix(self):
        size = 37  # version 5
        row = [' ' for _ in range(size)]
        template = [deepcopy(row) for _ in range(size)]

        # Patterns
        self._add_detection_pattern(template)
        self._add_position_pattern(template)
        # Version pattern not required for v<7

        # Create a single mask (index 0)
        self.code = self._make_mask0(template)

    def _add_detection_pattern(self, m):
        # Finder patterns and timing lines
        for i in range(7):
            inv = -(i+1)
            for j in [0, 6, -1, -7]:
                m[j][i] = 1
                m[i][j] = 1
                m[inv][j] = 1
                m[j][inv] = 1
        for i in range(1, 6):
            inv = -(i+1)
            for j in [1, 5, -2, -6]:
                m[j][i] = 0
                m[i][j] = 0
                m[inv][j] = 0
                m[j][inv] = 0
        for i in range(2, 5):
            for j in range(2, 5):
                inv = -(i+1)
                m[i][j] = 1
                m[inv][j] = 1
                m[j][inv] = 1
        for i in range(8):
            inv = -(i+1)
            for j in [7, -8]:
                m[i][j] = 0
                m[j][i] = 0
                m[inv][j] = 0
                m[j][inv] = 0
        for i in range(-8, 0):
            for j in range(-8, 0):
                m[i][j] = ' '
        bit = itertools.cycle([1, 0])
        for i in range(8, (len(m) - 8)):
            b = next(bit)
            m[i][6] = b
            m[6][i] = b
        m[-8][8] = 1

    def _add_position_pattern(self, m):
        # Fixed for version 5
        coords = [6, 30]
        min_c = 6
        max_c = 30
        for i in coords:
            for j in coords:
                if (i == min_c and j == min_c) or (i == min_c and j == max_c) or (i == max_c and j == min_c):
                    continue
                m[i][j] = 1
                for x in [-1, 1]:
                    m[i+x][j+x] = 0
                    m[i+x][j] = 0
                    m[i][j+x] = 0
                    m[i-x][j+x] = 0
                    m[i+x][j-x] = 0
                for x in [-2, 2]:
                    for y in [0, -1, 1]:
                        m[i+x][j+x] = 1
                        m[i+x][j+y] = 1
                        m[i+y][j+x] = 1
                        m[i-x][j+x] = 1
                        m[i+x][j-x] = 1

    def _add_type_pattern(self, m, type_bits):
        field = iter(type_bits)
        for i in range(7):
            bit = int(next(field))
            if i < 6:
                m[8][i] = bit
            else:
                m[8][i+1] = bit
            if -8 < -(i+1):
                m[-(i+1)][8] = bit
        for i in range(-8, 0):
            bit = int(next(field))
            m[8][i] = bit
            ii = -i
            if ii > 6:
                m[ii][8] = bit
            else:
                m[ii-1][8] = bit

    def _make_mask0(self, template):
        cur = deepcopy(template)
        # type bits for level L, mask 0
        self._add_type_pattern(cur, '111011111000100')
        pattern = lambda r, c: (r + c) % 2 == 0
        bits = iter(self.buffer.getvalue())
        row_start = itertools.cycle([len(cur)-1, 0])
        row_stop = itertools.cycle([-1, len(cur)])
        direction = itertools.cycle([-1, 1])
        for column in range(len(cur)-1, 0, -2):
            if column <= 6:
                column = column - 1
            column_pair = itertools.cycle([column, column-1])
            for row in range(next(row_start), next(row_stop), next(direction)):
                for _ in range(2):
                    col = next(column_pair)
                    if cur[row][col] != ' ':
                        continue
                    try:
                        bit = int(next(bits))
                    except StopIteration:
                        bit = 0
                    cur[row][col] = (bit ^ 1) if pattern(row, col) else bit
        return cur