"""A small, dependency-free QR encoder (byte mode, ECC level L/M, versions
1-20) rendering to SVG. Enough for share links and TOTP URIs."""

# (ec_codewords_per_block, [(block_count, data_codewords_per_block), ...])
BLOCK_TABLE = {
    "L": {
        1: (7, [(1, 19)]), 2: (10, [(1, 34)]), 3: (15, [(1, 55)]), 4: (20, [(1, 80)]),
        5: (26, [(1, 108)]), 6: (18, [(2, 68)]), 7: (20, [(2, 78)]), 8: (24, [(2, 97)]),
        9: (30, [(2, 116)]), 10: (18, [(2, 68), (2, 69)]), 11: (20, [(4, 81)]),
        12: (24, [(2, 92), (2, 93)]), 13: (26, [(4, 107)]), 14: (30, [(3, 115), (1, 116)]),
        15: (22, [(5, 87), (1, 88)]), 16: (24, [(5, 98), (1, 99)]),
        17: (28, [(1, 107), (5, 108)]), 18: (30, [(5, 120), (1, 121)]),
        19: (28, [(3, 113), (4, 114)]), 20: (28, [(3, 107), (5, 108)]),
    },
    "M": {
        1: (10, [(1, 16)]), 2: (16, [(1, 28)]), 3: (26, [(1, 44)]), 4: (18, [(2, 32)]),
        5: (24, [(2, 43)]), 6: (16, [(4, 27)]), 7: (18, [(4, 31)]),
        8: (22, [(2, 38), (2, 39)]), 9: (22, [(3, 36), (2, 37)]),
        10: (26, [(4, 43), (1, 44)]), 11: (30, [(1, 50), (4, 51)]),
        12: (22, [(6, 36), (2, 37)]), 13: (22, [(8, 37), (1, 38)]),
        14: (24, [(4, 40), (5, 41)]), 15: (24, [(5, 41), (5, 42)]),
        16: (28, [(7, 45), (3, 46)]), 17: (28, [(10, 46), (1, 47)]),
        18: (26, [(9, 43), (4, 44)]), 19: (26, [(3, 44), (11, 45)]),
        20: (26, [(3, 41), (13, 42)]),
    },
}

ALIGNMENT = {
    1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34],
    7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46], 10: [6, 28, 50],
    11: [6, 30, 54], 12: [6, 32, 58], 13: [6, 34, 62], 14: [6, 26, 46, 66],
    15: [6, 26, 48, 70], 16: [6, 26, 50, 74], 17: [6, 30, 54, 78],
    18: [6, 30, 56, 82], 19: [6, 30, 58, 86], 20: [6, 34, 62, 90],
}

ECL_BITS = {"L": 0b01, "M": 0b00, "Q": 0b11, "H": 0b10}


class QRError(ValueError):
    pass


# --------------------------------------------------------------------------
# GF(256) arithmetic for Reed-Solomon
# --------------------------------------------------------------------------
_EXP = [0] * 512
_LOG = [0] * 256


def _init_tables():
    x = 1
    for i in range(255):
        _EXP[i] = x
        _LOG[x] = i
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
    for i in range(255, 512):
        _EXP[i] = _EXP[i - 255]


_init_tables()


def _gf_mul(a, b):
    if a == 0 or b == 0:
        return 0
    return _EXP[_LOG[a] + _LOG[b]]


def _rs_divisor(degree):
    """Coefficients of the degree-`degree` generator polynomial, highest power
    first with the monic leading term left implicit."""
    result = [0] * degree
    result[degree - 1] = 1
    root = 1
    for _ in range(degree):
        for j in range(degree):
            result[j] = _gf_mul(result[j], root)
            if j + 1 < degree:
                result[j] ^= result[j + 1]
        root = _gf_mul(root, 2)
    return result


def _rs_ecc(data, ec_count):
    divisor = _rs_divisor(ec_count)
    remainder = [0] * ec_count
    for byte in data:
        factor = byte ^ remainder[0]
        remainder = remainder[1:] + [0]
        for i in range(ec_count):
            remainder[i] ^= _gf_mul(divisor[i], factor)
    return remainder


# --------------------------------------------------------------------------
# encoding
# --------------------------------------------------------------------------
def _capacity(version, ecl):
    ec_per_block, groups = BLOCK_TABLE[ecl][version]
    return sum(count * size for count, size in groups)


def _pick_version(length, ecl):
    for version in range(1, 21):
        count_bits = 8 if version <= 9 else 16
        needed = (4 + count_bits + length * 8 + 7) // 8
        if needed <= _capacity(version, ecl):
            return version
    raise QRError("payload too large for a version-20 QR code (%d bytes)" % length)


def _bitstream(data, version, ecl):
    count_bits = 8 if version <= 9 else 16
    total_codewords = _capacity(version, ecl)
    bits = []

    def push(value, width):
        for i in range(width - 1, -1, -1):
            bits.append((value >> i) & 1)

    push(0b0100, 4)                 # byte mode
    push(len(data), count_bits)
    for byte in data:
        push(byte, 8)

    capacity_bits = total_codewords * 8
    push(0, min(4, capacity_bits - len(bits)))
    while len(bits) % 8:
        bits.append(0)

    codewords = [
        int("".join(str(b) for b in bits[i : i + 8]), 2) for i in range(0, len(bits), 8)
    ]
    pad = [0xEC, 0x11]
    i = 0
    while len(codewords) < total_codewords:
        codewords.append(pad[i % 2])
        i += 1
    return codewords


def _interleave(codewords, version, ecl):
    ec_count, groups = BLOCK_TABLE[ecl][version]
    blocks, ecc_blocks, offset = [], [], 0
    for count, size in groups:
        for _ in range(count):
            block = codewords[offset : offset + size]
            offset += size
            blocks.append(block)
            ecc_blocks.append(_rs_ecc(block, ec_count))

    out = []
    for i in range(max(len(b) for b in blocks)):
        for block in blocks:
            if i < len(block):
                out.append(block[i])
    for i in range(ec_count):
        for block in ecc_blocks:
            out.append(block[i])
    return out


# --------------------------------------------------------------------------
# matrix construction
# --------------------------------------------------------------------------
def _new_matrix(size):
    return [[None] * size for _ in range(size)]


def _place_finder(matrix, row, col):
    for dr in range(-1, 8):
        for dc in range(-1, 8):
            r, c = row + dr, col + dc
            if not (0 <= r < len(matrix) and 0 <= c < len(matrix)):
                continue
            inside = 0 <= dr <= 6 and 0 <= dc <= 6
            dark = inside and (
                dr in (0, 6) or dc in (0, 6) or (2 <= dr <= 4 and 2 <= dc <= 4)
            )
            matrix[r][c] = 1 if dark else 0


def _place_alignment(matrix, version):
    centers = ALIGNMENT[version]
    size = len(matrix)
    for row in centers:
        for col in centers:
            if (row < 8 and col < 8) or (row < 8 and col > size - 9) or (row > size - 9 and col < 8):
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    dark = max(abs(dr), abs(dc)) != 1
                    matrix[row + dr][col + dc] = 1 if dark else 0


def _place_timing(matrix):
    size = len(matrix)
    for i in range(8, size - 8):
        bit = 1 if i % 2 == 0 else 0
        if matrix[6][i] is None:
            matrix[6][i] = bit
        if matrix[i][6] is None:
            matrix[i][6] = bit


def _reserve_format(matrix):
    size = len(matrix)
    for i in range(9):
        if matrix[8][i] is None:
            matrix[8][i] = 0
        if matrix[i][8] is None:
            matrix[i][8] = 0
    for i in range(8):
        if matrix[8][size - 1 - i] is None:
            matrix[8][size - 1 - i] = 0
        if matrix[size - 1 - i][8] is None:
            matrix[size - 1 - i][8] = 0
    matrix[size - 8][8] = 1  # dark module


def _version_bits(version):
    remainder = version
    for _ in range(12):
        remainder = (remainder << 1) ^ ((remainder >> 11) * 0x1F25)
    return (version << 12) | remainder


def _place_version(matrix, version):
    if version < 7:
        return
    bits = _version_bits(version)
    size = len(matrix)
    for i in range(18):
        bit = (bits >> i) & 1
        row, col = i // 3, i % 3
        matrix[size - 11 + col][row] = bit
        matrix[row][size - 11 + col] = bit


def _format_bits(ecl, mask):
    data = (ECL_BITS[ecl] << 3) | mask
    remainder = data
    for _ in range(10):
        remainder = (remainder << 1) ^ ((remainder >> 9) * 0x537)
    return ((data << 10) | remainder) ^ 0x5412


def _place_format(matrix, ecl, mask):
    bits = _format_bits(ecl, mask)
    size = len(matrix)
    for i in range(15):
        bit = (bits >> i) & 1
        # first copy: down column 8, then left along row 8
        if i < 6:
            matrix[i][8] = bit
        elif i == 6:
            matrix[7][8] = bit
        elif i == 7:
            matrix[8][8] = bit
        elif i == 8:
            matrix[8][7] = bit
        else:
            matrix[8][14 - i] = bit
        # second copy: right end of row 8, then bottom of column 8
        if i < 8:
            matrix[8][size - 1 - i] = bit
        else:
            matrix[size - 15 + i][8] = bit
    matrix[size - 8][8] = 1


def _mask_fn(mask, row, col):
    if mask == 0:
        return (row + col) % 2 == 0
    if mask == 1:
        return row % 2 == 0
    if mask == 2:
        return col % 3 == 0
    if mask == 3:
        return (row + col) % 3 == 0
    if mask == 4:
        return (row // 2 + col // 3) % 2 == 0
    if mask == 5:
        return (row * col) % 2 + (row * col) % 3 == 0
    if mask == 6:
        return ((row * col) % 2 + (row * col) % 3) % 2 == 0
    return ((row + col) % 2 + (row * col) % 3) % 2 == 0


def _place_data(matrix, codewords, reserved):
    size = len(matrix)
    bits = []
    for byte in codewords:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    index = 0
    col = size - 1
    upward = True
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for row in rows:
            for offset in (0, 1):
                c = col - offset
                if reserved[row][c]:
                    continue
                matrix[row][c] = bits[index] if index < len(bits) else 0
                index += 1
        col -= 2
        upward = not upward


PENALTY_N1, PENALTY_N2, PENALTY_N3, PENALTY_N4 = 3, 3, 40, 10


def _finder_add_history(run_length, history, size):
    if history[0] == 0:
        run_length += size          # light border before the first run
    history.insert(0, run_length)
    history.pop()


def _finder_count(history):
    """How many 1:1:3:1:1 finder-like patterns end at this point."""
    n = history[1]
    core = (
        n > 0
        and history[2] == n
        and history[3] == n * 3
        and history[4] == n
        and history[5] == n
    )
    return (1 if core and history[0] >= n * 4 and history[6] >= n else 0) + (
        1 if core and history[6] >= n * 4 and history[0] >= n else 0
    )


def _finder_terminate(run_color, run_length, history, size):
    if run_color:                   # terminate a dark run first
        _finder_add_history(run_length, history, size)
        run_length = 0
    run_length += size              # light border after the final run
    _finder_add_history(run_length, history, size)
    return _finder_count(history)


def _penalty(matrix):
    """Mask penalty per ISO/IEC 18004 rules 1-4, borders included."""
    size = len(matrix)
    score = 0

    for lines in (matrix, list(zip(*matrix))):
        for line in lines:
            run_color, run_len = 0, 0
            history = [0] * 7
            for value in line:
                if value == run_color:
                    run_len += 1
                    if run_len == 5:
                        score += PENALTY_N1
                    elif run_len > 5:
                        score += 1
                else:
                    _finder_add_history(run_len, history, size)
                    if not run_color:
                        score += _finder_count(history) * PENALTY_N3
                    run_color = value
                    run_len = 1
            score += _finder_terminate(run_color, run_len, history, size) * PENALTY_N3

    for r in range(size - 1):
        row, below = matrix[r], matrix[r + 1]
        for c in range(size - 1):
            color = row[c]
            if color == row[c + 1] == below[c] == below[c + 1]:
                score += PENALTY_N2

    dark = sum(sum(row) for row in matrix)
    total = size * size
    k = (abs(dark * 20 - total * 10) + total - 1) // total - 1
    return score + k * PENALTY_N4


def encode(text, ecl="M"):
    """Return the QR matrix (list of rows of 0/1) for `text`."""
    if ecl not in BLOCK_TABLE:
        ecl = "M"
    data = text.encode("utf-8")
    try:
        version = _pick_version(len(data), ecl)
    except QRError:
        if ecl != "L":
            ecl = "L"
            version = _pick_version(len(data), ecl)
        else:
            raise

    codewords = _interleave(_bitstream(data, version, ecl), version, ecl)
    size = version * 4 + 17

    matrix = _new_matrix(size)
    _place_finder(matrix, 0, 0)
    _place_finder(matrix, 0, size - 7)
    _place_finder(matrix, size - 7, 0)
    _place_alignment(matrix, version)
    _place_timing(matrix)
    _reserve_format(matrix)
    _place_version(matrix, version)
    reserved = [[cell is not None for cell in row] for row in matrix]

    _place_data(matrix, codewords, reserved)

    best, best_score = None, None
    for mask in range(8):
        candidate = [row[:] for row in matrix]
        for r in range(size):
            for c in range(size):
                if not reserved[r][c] and _mask_fn(mask, r, c):
                    candidate[r][c] ^= 1
        _place_format(candidate, ecl, mask)
        score = _penalty(candidate)
        if best_score is None or score < best_score:
            best, best_score = candidate, score
    return best


def to_svg(text, ecl="M", scale=6, border=4, dark="#0f172a", light="#ffffff"):
    """Render `text` as a standalone SVG string."""
    matrix = encode(text, ecl)
    size = len(matrix)
    dimension = (size + border * 2) * scale
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
        'viewBox="0 0 %d %d" shape-rendering="crispEdges" role="img" '
        'aria-label="QR code">' % (dimension, dimension, dimension, dimension),
        '<rect width="%d" height="%d" fill="%s"/>' % (dimension, dimension, light),
        '<path fill="%s" d="' % dark,
    ]
    path = []
    for r, row in enumerate(matrix):
        run_start = None
        for c in range(size + 1):
            filled = c < size and row[c] == 1
            if filled and run_start is None:
                run_start = c
            elif not filled and run_start is not None:
                x = (run_start + border) * scale
                y = (r + border) * scale
                path.append("M%d %dh%dv%dh-%dz" % (x, y, (c - run_start) * scale, scale, (c - run_start) * scale))
                run_start = None
    parts.append("".join(path))
    parts.append('"/></svg>')
    return "".join(parts)


def to_text(text, ecl="M"):
    """Block-character rendering, for the shell menu."""
    matrix = encode(text, ecl)
    width = len(matrix) + 4
    blank = "\u2588\u2588" * width
    lines = [blank, blank]
    for row in matrix:
        lines.append(
            "\u2588\u2588\u2588\u2588"
            + "".join("  " if cell else "\u2588\u2588" for cell in row)
            + "\u2588\u2588\u2588\u2588"
        )
    lines.extend([blank, blank])
    return "\n".join(lines)
