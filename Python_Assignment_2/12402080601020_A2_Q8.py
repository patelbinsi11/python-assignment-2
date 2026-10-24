import sys

MOD = 1_000_000_007
NEG = -(10 ** 18)           # marks a cell that cannot be reached


def parse_row(line, m):
    """Turn one input line into a list of ints, with None for a blocked cell (X)."""
    parts = line.split()
    if len(parts) != m:
        raise ValueError("each row must have exactly m values")
    row = []
    for p in parts:
        if p.upper() == "X":
            row.append(None)
        else:
            value = int(p)                          # raises ValueError if not a number
            if not -10 ** 6 <= value <= 10 ** 6:
                raise ValueError("score out of range")
            row.append(value)
    return row


def main():
    try:
        n, m = map(int, sys.stdin.readline().split())
        if not (1 <= n <= 2000 and 1 <= m <= 2000):
            raise ValueError
    except ValueError:
        print("Input error: first line must be 'n m' with 1 <= n, m <= 2000")
        return

    # Only the previous row is kept, so memory is O(m).
    prev_best = [NEG] * m       # best score of a path ending in each cell of the previous row
    prev_cnt = [0] * m          # how many paths reach that best score
    for i in range(n):
        try:
            row = parse_row(sys.stdin.readline(), m)
        except ValueError as e:
            print(f"Input error in row {i + 1}: {e}")
            return
        cur_best = [NEG] * m
        cur_cnt = [0] * m
        for j in range(m):
            cell = row[j]
            if cell is None:                        # blocked cell: stays unreachable
                continue
            if i == 0 and j == 0:                   # start cell
                cur_best[0], cur_cnt[0] = cell, 1
                continue
            best, ways = NEG, 0
            if i:                                   # from above
                v = prev_best[j]
                if v > best:
                    best, ways = v, prev_cnt[j]
                elif v == best:
                    ways += prev_cnt[j]
                if j:                               # from the diagonal (up-left)
                    v = prev_best[j - 1]
                    if v > best:
                        best, ways = v, prev_cnt[j - 1]
                    elif v == best:
                        ways += prev_cnt[j - 1]
            if j:                                   # from the left
                v = cur_best[j - 1]
                if v > best:
                    best, ways = v, cur_cnt[j - 1]
                elif v == best:
                    ways += cur_cnt[j - 1]
            if best == NEG:                         # no way to get here
                continue
            cur_best[j] = best + cell
            cur_cnt[j] = ways % MOD
        prev_best, prev_cnt = cur_best, cur_cnt

    if prev_best[m - 1] == NEG:
        print("IMPOSSIBLE")
    else:
        print(prev_best[m - 1], prev_cnt[m - 1] % MOD)


if __name__ == "__main__":
    main()