import re
import sys
from collections import defaultdict

# username: letters, digits, + . _ -   |   domain must end in com / edu / org
EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9+._-])"                       # nothing username-like before
    r"([A-Za-z0-9+._-]+)"                         # group 1: username
    r"@"
    r"((?:[A-Za-z0-9-]+\.)+(?:com|edu|org))"      # group 2: domain
    r"(?![A-Za-z0-9-]|\.[A-Za-z0-9])",            # domain must end here
    re.IGNORECASE,
)

def extract(path):
    users = defaultdict(set)    # domain -> set of unique usernames
    smallest = {}               # domain -> lexicographically smallest email

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:                            # streaming: O(total characters)
            for m in EMAIL_RE.finditer(line):
                user, domain = m.group(1), m.group(2).lower()
                email = f"{user}@{domain}"
                users[domain].add(user)
                if domain not in smallest or email < smallest[domain]:
                    smallest[domain] = email
    return users, smallest

def main():
    path = input("Enter file path: ").strip()
    try:
        users, smallest = extract(path)
    except (FileNotFoundError, PermissionError) as e:
        print("Error:", e)
        sys.exit(1)

    for domain in sorted(users):
        print(domain, len(users[domain]), smallest[domain])

if __name__ == "__main__":
    main()