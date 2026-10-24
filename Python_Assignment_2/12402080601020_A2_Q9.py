import sys
from decimal import Decimal, InvalidOperation
from functools import total_ordering


class InventoryError(Exception):
    """Base class for all inventory problems."""


class DuplicateProductError(InventoryError):
    pass


class ProductNotFoundError(InventoryError):
    pass


def to_decimal(text):
    """Parse a non-negative finite number, or raise InventoryError."""
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise InventoryError(f"'{text}' is not a number")
    if not value.is_finite() or value < 0:
        raise InventoryError(f"'{text}' must be a non-negative number")
    return value


def fmt(value):
    """Decimal('4.50') -> '4.5', Decimal('68') -> '68'"""
    if value == value.to_integral_value():
        return str(int(value))
    return format(value.normalize(), "f")


class Product:
    def __init__(self, pid, name, stock, purchase, selling):
        if stock < 0 or int(stock) != stock:
            raise InventoryError("stock must be a whole number >= 0")
        self.pid, self.name = pid, name
        self.stock = int(stock)
        self.purchase = Decimal(purchase)
        self.selling = Decimal(selling)

    @property
    def value(self):
        """Value of the stock at purchase price."""
        return self.stock * self.purchase

    def merged_with(self, other):
        """Same id: add the stock, keep the LOWER purchase and HIGHER selling price."""
        return Product(self.pid, self.name, self.stock + other.stock,
                       min(self.purchase, other.purchase),
                       max(self.selling, other.selling))

    def copy(self):
        return Product(self.pid, self.name, self.stock, self.purchase, self.selling)

    def __str__(self):
        return (f"{self.pid} {self.name} stock={self.stock} "
                f"purchase={fmt(self.purchase)} selling={fmt(self.selling)}")


@total_ordering
class Inventory:
    def __init__(self, label="Inventory"):
        self.label = label
        self._products = {}                    # product id -> Product

    # ----- normal operations -----
    def add(self, product):
        if product.pid in self._products:
            raise DuplicateProductError(f"product {product.pid} already exists")
        self._products[product.pid] = product

    def delete(self, pid):
        if pid not in self._products:
            raise ProductNotFoundError("product not found")
        del self._products[pid]

    def update_stock(self, pid, new_stock):
        if pid not in self._products:
            raise ProductNotFoundError("product not found")
        if new_stock < 0 or int(new_stock) != new_stock:
            raise InventoryError("stock must be a whole number >= 0")
        self._products[pid].stock = int(new_stock)

    @property
    def total_value(self):
        return sum((p.value for p in self._products.values()), Decimal(0))

    def summary(self):
        lines = [str(self._products[pid]) for pid in sorted(self._products)]
        lines.append(f"TOTAL_VALUE={fmt(self.total_value)}")
        return lines

    # ----- operator overloading -----
    def __add__(self, other):
        """inventory_a + inventory_b  ->  a NEW merged inventory (inputs are not changed)."""
        if not isinstance(other, Inventory):
            return NotImplemented
        merged = Inventory(f"{self.label}+{other.label}")
        for p in self._products.values():
            merged._products[p.pid] = p.copy()
        for p in other._products.values():
            if p.pid in merged._products:
                merged._products[p.pid] = merged._products[p.pid].merged_with(p)
            else:
                merged._products[p.pid] = p.copy()
        return merged

    def __eq__(self, other):
        if not isinstance(other, Inventory):
            return NotImplemented
        return self.total_value == other.total_value

    def __lt__(self, other):                   # @total_ordering builds >, <=, >= from this
        if not isinstance(other, Inventory):
            return NotImplemented
        return self.total_value < other.total_value

    def __len__(self):
        return len(self._products)

    def __contains__(self, pid):
        return pid in self._products


def parse_product(tokens):
    """tokens: id name... stock purchase selling   (the name may have several words)"""
    if len(tokens) < 5:
        raise InventoryError("expected: id name stock purchase selling")
    pid, name = tokens[0], " ".join(tokens[1:-3])
    try:
        stock = int(tokens[-3])
    except ValueError:
        raise InventoryError(f"stock '{tokens[-3]}' must be a whole number")
    return Product(pid, name, stock, to_decimal(tokens[-2]), to_decimal(tokens[-1]))


def load_inventory(path, label):
    inv = Inventory(label)
    with open(path, encoding="utf-8") as fh:
        for number, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                inv.add(parse_product(line.split()))
            except InventoryError as e:
                print(f"{path} line {number} skipped: {e}", file=sys.stderr)
    return inv


def run_operation(line, inventories):
    tokens = line.split()
    if not tokens:
        raise InventoryError("empty operation")
    cmd = tokens[0].upper()

    if cmd == "MERGE":
        merged = inventories["A"] + inventories["B"]          # uses __add__
        print(f"MERGE: OK ({len(merged)} products)")
        print("\n".join(merged.summary()))
        return
    if cmd == "COMPARE":
        a, b = inventories["A"], inventories["B"]
        sign = "<" if a < b else (">" if a > b else "==")      # uses __lt__ / __gt__
        print(f"COMPARE: A {sign} B (A={fmt(a.total_value)}, B={fmt(b.total_value)})")
        return

    if len(tokens) < 3 or tokens[1].upper() not in inventories:
        raise InventoryError("expected: <ADD|DELETE|UPDATE> <A|B> <id> ...")
    inv, pid = inventories[tokens[1].upper()], tokens[2]
    if cmd == "ADD":
        inv.add(parse_product(tokens[2:]))
    elif cmd == "DELETE":
        inv.delete(pid)
    elif cmd == "UPDATE":
        if len(tokens) != 4:
            raise InventoryError("expected: UPDATE <A|B> <id> <new_stock>")
        try:
            inv.update_stock(pid, int(tokens[3]))
        except ValueError:
            raise InventoryError(f"stock '{tokens[3]}' must be a whole number")
    else:
        raise InventoryError(f"unknown operation {cmd}")
    print(f"{cmd} {tokens[1].upper()} {pid}: OK")


def main():
    try:
        path_a = sys.stdin.readline().strip()
        path_b = sys.stdin.readline().strip()
        q = int(sys.stdin.readline())
        inventories = {"A": load_inventory(path_a, "A"), "B": load_inventory(path_b, "B")}
    except ValueError:
        print("Input error: expected path A, path B, then q")
        return
    except OSError as e:
        print("Cannot read inventory file:", e)
        return

    for _ in range(q):
        line = sys.stdin.readline()
        try:
            run_operation(line, inventories)
        except InventoryError as e:
            label = " ".join(line.split()[:3]) or "(empty)"
            print(f"{label}: ERROR {e}")


if __name__ == "__main__":
    main()