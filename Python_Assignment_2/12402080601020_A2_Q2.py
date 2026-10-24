import re
import html

# Each product sits inside <div class="product"> ... </div>
BLOCK_RE = re.compile(r'<div[^>]*class="product"[^>]*>(.*?)</div>', re.I | re.S)
NAME_RE = re.compile(r'class="name"[^>]*>(.*?)<', re.I | re.S)
PRICE_RE = re.compile(r'class="price"[^>]*>(.*?)<', re.I | re.S)
RATING_RE = re.compile(r'class="rating"[^>]*>(.*?)<', re.I | re.S)
NUMBER_RE = re.compile(r'\d[\d,]*(?:\.\d+)?')


def clean_text(text):
    """Remove HTML codes like &amp; and extra spaces."""
    return " ".join(html.unescape(text).split())


def normalize_price(text):
    """'Rs. 1,299.00' -> 1299.0 ; returns None if no number found."""
    m = NUMBER_RE.search(html.unescape(text))
    if not m:
        return None
    return float(m.group().replace(",", ""))


def parse_rating(text):
    """Return rating as float between 0 and 5, else None."""
    try:
        r = float(text.strip())
    except ValueError:
        return None
    return r if 0 <= r <= 5 else None


def parse_page(path, products):
    """Read one HTML file and add its products to the dictionary."""
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    for block in BLOCK_RE.findall(content):
        n, p, r = NAME_RE.search(block), PRICE_RE.search(block), RATING_RE.search(block)
        if not (n and p and r):
            continue                      # incomplete product -> ignore
        name = clean_text(n.group(1))
        price = normalize_price(p.group(1))
        rating = parse_rating(r.group(1))
        if not name or price is None or rating is None:
            continue                      # invalid data -> ignore

        # duplicate handling: keep the better one (higher rating, then lower price)
        old = products.get(name)
        if old is None or (-rating, price) < (-old[1], old[0]):
            products[name] = (price, rating)


def format_price(price):
    return str(int(price)) if price == int(price) else f"{price:.2f}"


def main():
    try:
        p, k = map(int, input("Enter p and k: ").split())
    except ValueError:
        print("Error: enter two integers like: 2 2")
        return
    if not (1 <= p <= 5000 and 1 <= k <= 1000):
        print("Error: need 1 <= p <= 5000 and 1 <= k <= 1000")
        return

    products = {}                         # name -> (price, rating)
    for _ in range(p):
        path = input().strip()
        try:
            parse_page(path, products)
        except (FileNotFoundError, PermissionError) as e:
            print("Warning: skipping file ->", e)

    # sort: rating high first, then price low, then name A-Z
    ranked = sorted(products.items(), key=lambda x: (-x[1][1], x[1][0], x[0]))

    for name, (price, rating) in ranked[:k]:
        print(name, format_price(price), rating)


if __name__ == "__main__":
    main()