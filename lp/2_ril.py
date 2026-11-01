
import numpy as np
import re
import os
from scipy.optimize import linprog
from fractions import Fraction

INPUT_FILE = "data.txt"

problem_direction = 'max'


def parse_number(value):
    """Chuyen so thap phan hoac phan so thanh float."""
    return float(Fraction(value.strip()))


def parse_input(filename):
    global problem_direction

    if not os.path.exists(filename):
        print(f"Khong tim thay file: {filename}")
        return None, None, None, None, None

    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    c_vec = None
    A_ub_rows = []
    b_ub_vec = []
    A_eq_rows = []
    b_eq_vec = []
    num_vars = 0

    # Doc ham muc tieu
    for line in lines:
        line = line.strip()

        if line.startswith("#") or not line:
            continue

        if re.search(r'\bmin\b', line, re.IGNORECASE):
            problem_direction = 'min'
        elif re.search(r'\bmax\b', line, re.IGNORECASE):
            problem_direction = 'max'

        if line.startswith("c:"):
            content = line.split(":", 1)[1]
            content = content.replace('[', '').replace(']', '')
            parts = [x.strip() for x in content.split(',') if x.strip()]

            try:
                c_vec = np.array([parse_number(x) for x in parts])
            except (ValueError, ZeroDivisionError):
                print("Loi: He so ham muc tieu khong hop le.")
                return None, None, None, None, None

            num_vars = len(c_vec)
            break

    print(f"Problem type: {problem_direction}")

    if num_vars == 0:
        print("Loi: Khong tim thay ham muc tieu c.")
        return None, None, None, None, None

    # Doc cac rang buoc
    for line_no, line in enumerate(lines, start=1):
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        if line.startswith(("c:", "B:")) or "target" in line.lower() or "[PUNTO]" in line:
            continue

        match = re.match(
            r'^\s*\d+\s*:\s*(.*?)\s*(<=|>=|=)\s*(.*?)\s*$',
            line
        )

        if not match:
            continue

        lhs = match.group(1).strip()
        relation = match.group(2)
        rhs_text = match.group(3).strip()

        try:
            rhs = parse_number(rhs_text)
        except (ValueError, ZeroDivisionError):
            raise ValueError(
                f"Loi RHS tai dong {line_no}: {rhs_text}"
            )

        row = np.zeros(num_vars)

        # Tach cac hang tu theo dau + va -
        terms = lhs.replace('-', '+-').split('+')

        for term in terms:
            term = term.strip()

            if not term:
                continue

            term_match = re.fullmatch(
                r'([+-]?)\s*(?:(\d+(?:\.\d*)?|\.\d+)\s*\*?\s*)?x(\d+)',
                term
            )

            if not term_match:
                raise ValueError(
                    f"Hang tu khong hop le tai dong {line_no}: {term}"
                )

            sign = -1 if term_match.group(1) == '-' else 1
            coefficient = float(term_match.group(2)) if term_match.group(2) else 1.0
            variable_index = int(term_match.group(3)) - 1

            if variable_index < 0 or variable_index >= num_vars:
                raise ValueError(
                    f"Bien x{variable_index + 1} vuot qua so bien da khai bao."
                )

            # Cong don neu bien xuat hien nhieu lan
            row[variable_index] += sign * coefficient

        # Phan loai rang buoc
        if relation == '<=':
            A_ub_rows.append(row)
            b_ub_vec.append(rhs)

        elif relation == '>=':
            A_ub_rows.append(-row)
            b_ub_vec.append(-rhs)

        elif relation == '=':
            A_eq_rows.append(row)
            b_eq_vec.append(rhs)

    # Chuyen sang numpy array
    A_ub = np.array(A_ub_rows, dtype=float).reshape(-1, num_vars)
    b_ub = np.array(b_ub_vec, dtype=float)

    A_eq = np.array(A_eq_rows, dtype=float).reshape(-1, num_vars)
    b_eq = np.array(b_eq_vec, dtype=float)

    return A_ub, b_ub, A_eq, b_eq, c_vec


def solve_relaxed(A_ub, b_ub, A_eq, b_eq, c):
    print("\n--- Continuous relaxed solution ---")

    # Chuyen bai toan MAX thanh MIN
    c_prog = -c if problem_direction == 'max' else c

    try:
        res = linprog(
            c_prog,
            A_ub=A_ub if len(A_ub) > 0 else None,
            b_ub=b_ub if len(b_ub) > 0 else None,
            A_eq=A_eq if len(A_eq) > 0 else None,
            b_eq=b_eq if len(b_eq) > 0 else None,
            bounds=[(0, None)] * len(c),
            method='highs'
        )

    except Exception as e:
        print(f"Loi khi chay bo giai: {e}")
        return

    # Kiem tra trang thai
    if res.status == 2:
        print("Bai toan vo nghiem.")
        return

    elif res.status == 3:
        print("Bai toan khong bi chan.")
        return

    elif not res.success:
        print(f"Loi bo giai: {res.message}")
        return

    # Tinh gia tri ham muc tieu
    z_val = -res.fun if problem_direction == 'max' else res.fun

    print("\nOptimal solution found!")
    print(f"Opt value: {z_val:,.4f}")

    print("\nVariables:")

    formatted_vals = []
    frac_vals = []

    for i, val in enumerate(res.x):
        print(f"  x{i+1}: {val:.4f}")

        if abs(val - round(val)) < 1e-3:
            formatted_vals.append(str(int(round(val))))
        else:
            formatted_vals.append(f"{val:.4f}")

        frac = Fraction(float(val)).limit_denominator(1000)
        frac_vals.append(str(frac))

    vec_str = ", ".join(formatted_vals)
    vec_frac_str = ", ".join(frac_vals)

    print(f"\nx = ({vec_frac_str}) = ({vec_str})")
    print("value:", z_val)

    # Luu ket qua
    output_file = "optim_sol.txt"

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("Optimal solution\n")
            f.write(f"Direction: {problem_direction.upper()}\n")
            f.write(f"Objective value: {z_val:.6f}\n")
            f.write(f"Variables: {vec_str}\n")
            f.write(f"Fraction: {vec_frac_str}\n")

        print(f"\nOutput SAVED to '{output_file}'")

    except Exception as e:
        print(f"WRITE ERROR: {e}")


if __name__ == "__main__":

    try:
        A_ub, b_ub, A_eq, b_eq, c = parse_input(INPUT_FILE)

        if c is not None:
            solve_relaxed(A_ub, b_ub, A_eq, b_eq, c)
        else:
            print("Parsing error.")

    except ValueError as e:
        print(f"Input error: {e}")
