import csv
import os
import statistics
import sys

try:
    import matplotlib
    matplotlib.use("Agg")                 # draw straight into image files (no window needed)
    import matplotlib.pyplot as plt
except ImportError:
    raise SystemExit("matplotlib is missing. Run: pip install matplotlib")

MISSING_WORDS = {"", "na", "n/a", "nan", "null", "none", "-", "--"}
PASS_MARK = 40                            # a subject is passed with 40 or more
GRADES = [("A+", 90), ("A", 80), ("B", 70), ("C", 60), ("D", 50), ("F", 0)]   # on the average mark


def clean_mark(text):
    """Return a mark between 0 and 100, or None if it is missing or invalid."""
    text = text.strip()
    if text.lower() in MISSING_WORDS:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    return value if 0 <= value <= 100 else None      # NaN, inf and 110 all become None


def grade_for(average):
    for grade, lowest in GRADES:
        if average >= lowest:
            return grade


def num(value):
    """92.0 -> '92', 91.5 -> '91.5', 80.333 -> '80.33'"""
    return f"{value:.2f}".rstrip("0").rstrip(".")


def read_marks(path):
    """Return (subject names, students) where each student is [enrollment, name, marks]."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        if not header:
            raise ValueError("the CSV file is empty")
        cols = [h.strip() for h in header]
        lower = [c.lower() for c in cols]
        if "enrollment" not in lower or "name" not in lower:
            raise ValueError("the header must contain 'enrollment' and 'name' columns")
        ei, ni = lower.index("enrollment"), lower.index("name")
        subject_cols = [i for i in range(len(cols)) if i not in (ei, ni)]
        if not 1 <= len(subject_cols) <= 20:
            raise ValueError("the file must have 1 to 20 subject columns")
        students, seen, dropped = [], set(), 0
        for row in reader:
            if not any(cell.strip() for cell in row):
                continue                                  # blank line
            row = row + [""] * (len(cols) - len(row))     # short row: pad with missing values
            enrollment, name = row[ei].strip(), row[ni].strip()
            if not enrollment or enrollment in seen:
                dropped += 1                              # no enrollment, or a duplicate
                continue
            seen.add(enrollment)
            students.append([enrollment, name, [clean_mark(row[i]) for i in subject_cols]])
    return [cols[i] for i in subject_cols], students, dropped


def fill_missing(subjects, students):
    """Replace each missing mark with its subject average. Returns the count filled per subject."""
    filled = [0] * len(subjects)
    for j in range(len(subjects)):
        valid = [s[2][j] for s in students if s[2][j] is not None]
        mean = sum(valid) / len(valid) if valid else 0.0
        for s in students:
            if s[2][j] is None:
                s[2][j] = round(mean, 2)
                filled[j] += 1
    return filled


def write_cleaned(path, subjects, students):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["enrollment", "name"] + subjects + ["total", "average", "grade"])
        for enrollment, name, marks in students:
            total = sum(marks)
            avg = total / len(marks)
            w.writerow([enrollment, name] + [num(m) for m in marks]
                       + [num(total), num(avg), grade_for(avg)])


def write_summary(path, subjects, students, filled):
    stats = []
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["subject", "students", "missing_filled", "mean", "median",
                    "min", "max", "std_dev", "pass_percent"])
        for j, subject in enumerate(subjects):
            col = [s[2][j] for s in students]
            mean = sum(col) / len(col)
            passed = 100 * sum(1 for m in col if m >= PASS_MARK) / len(col)
            w.writerow([subject, len(col), filled[j], num(mean), num(statistics.median(col)),
                        num(min(col)), num(max(col)), num(statistics.pstdev(col)), num(passed)])
            stats.append(mean)
    return stats


# ---------------- charts ----------------
def chart_grades(path, students):
    order = [g for g, _ in GRADES]
    counts = {g: 0 for g in order}
    for _e, _n, marks in students:
        counts[grade_for(sum(marks) / len(marks))] += 1
    fig, ax = plt.subplots(figsize=(7, 4.5))
    bars = ax.bar(order, [counts[g] for g in order], color="#4C78A8")
    ax.bar_label(bars)
    ax.set_title("Grade Distribution")
    ax.set_xlabel("Grade (on average mark)")
    ax.set_ylabel("Number of students")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def chart_subject_average(path, subjects, means):
    fig, ax = plt.subplots(figsize=(max(6, len(subjects) * 0.9), 4.5))
    bars = ax.bar(subjects, means, color="#59A14F")
    ax.bar_label(bars, labels=[num(m) for m in means])
    ax.set_ylim(0, 100)
    ax.set_title("Subject-wise Average Marks")
    ax.set_ylabel("Average mark")
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def chart_top_performers(path, students, count=10):
    ranked = sorted(((sum(m) / len(m), e, n) for e, n, m in students),
                    key=lambda t: (-t[0], t[1]))[:count]
    labels = [f"{n} ({e})" for _a, e, n in ranked]
    values = [a for a, _e, _n in ranked]
    fig, ax = plt.subplots(figsize=(8, max(3, len(ranked) * 0.5 + 1.5)))
    bars = ax.barh(labels, values, color="#F28E2B")
    ax.bar_label(bars, labels=[num(v) for v in values], padding=3)
    ax.invert_yaxis()                                  # best student at the top
    ax.set_xlim(0, 100)
    ax.set_title(f"Top {len(ranked)} Performers (average mark)")
    ax.set_xlabel("Average mark")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    if len(sys.argv) >= 3:
        path, out_dir = sys.argv[1], sys.argv[2]
    else:
        path = input("Marks CSV path: ").strip()
        out_dir = input("Output folder: ").strip()
    try:
        subjects, students, dropped = read_marks(path)
        if not students:
            print("No valid student rows found.")
            return
        os.makedirs(out_dir, exist_ok=True)
        filled = fill_missing(subjects, students)
        write_cleaned(os.path.join(out_dir, "cleaned_marks.csv"), subjects, students)
        means = write_summary(os.path.join(out_dir, "summary.csv"), subjects, students, filled)
        chart_grades(os.path.join(out_dir, "grade_distribution.png"), students)
        chart_subject_average(os.path.join(out_dir, "subject_average.png"), subjects, means)
        chart_top_performers(os.path.join(out_dir, "top_performers.png"), students)
    except FileNotFoundError:
        print("File not found:", path)
        return
    except (ValueError, OSError, csv.Error) as e:
        print("Error:", e)
        return
    print(f"{len(students)} students, {len(subjects)} subjects, "
          f"{sum(filled)} missing value(s) filled, {dropped} row(s) dropped")
    for name in ("cleaned_marks.csv", "summary.csv", "grade_distribution.png",
                 "subject_average.png", "top_performers.png"):
        print(name)


if __name__ == "__main__":
    main()