import re
import sys
from collections import deque

# timestamp  user  ip  status      e.g.  00:07 u1 2.2.2.2 SUCCESS   (HH:MM or HH:MM:SS)
LOG_LINE = re.compile(
    r"^((\d{1,2}):(\d{2})(?::(\d{2}))?)\s+(\S+)\s+(\S+)\s+(FAIL|SUCCESS)\s*$",
    re.IGNORECASE,
)


def main():
    try:
        x, t = map(int, sys.stdin.readline().split())
        n = int(sys.stdin.readline())
        if not (1 <= n <= 2_000_000 and 1 <= x <= 100 and 1 <= t <= 1440):
            raise ValueError
    except ValueError:
        print("Input error: expected 'X T' then n (1<=X<=100, 1<=T<=1440)")
        return

    window = t * 60                 # window length in seconds
    failures = {}                   # user -> deque of (time, ip) for recent FAIL lines
    fail_ips = {}                   # user -> {ip: how many recent failures came from it}
    flagged = {}                    # user -> timestamp of first suspicious success

    def drop_old(user, now):
        """Sliding window: remove failures older than T minutes before 'now'."""
        dq, ips = failures[user], fail_ips[user]
        while dq and now - dq[0][0] > window:
            _, old_ip = dq.popleft()
            ips[old_ip] -= 1
            if ips[old_ip] == 0:
                del ips[old_ip]

    skipped = 0
    for _ in range(n):
        m = LOG_LINE.match(sys.stdin.readline())
        if not m:
            skipped += 1            # malformed line: ignore it
            continue
        stamp, hh, mm, ss, user, ip, status = m.groups()
        if int(hh) > 23 or int(mm) > 59 or (ss and int(ss) > 59):
            skipped += 1
            continue
        now = int(hh) * 3600 + int(mm) * 60 + int(ss or 0)

        if status.upper() == "FAIL":
            if user not in failures:
                failures[user], fail_ips[user] = deque(), {}
            drop_old(user, now)
            failures[user].append((now, ip))
            fail_ips[user][ip] = fail_ips[user].get(ip, 0) + 1
        elif user in failures and user not in flagged:
            drop_old(user, now)
            # enough recent failures AND this success comes from an IP not seen in them
            if len(failures[user]) >= x and ip not in fail_ips[user]:
                flagged[user] = stamp

    for user in sorted(flagged):
        print(user, flagged[user])
    if skipped:
        print(f"({skipped} malformed line(s) ignored)", file=sys.stderr)


if __name__ == "__main__":
    main()
