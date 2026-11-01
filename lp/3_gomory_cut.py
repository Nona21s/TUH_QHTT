
import numpy as np
import re
import os
import math
import fractions

from gurobipy import Model, GRB, quicksum

INPUT_FILE = "data.txt"
TOL = 1e-7


def format_frac(val):
    f = fractions.Fraction(float(val)).limit_denominator(1000)

    if f.denominator == 1:
        return str(f.numerator)

    return f"{f.numerator}/{f.denominator}"


def parse_number(value):
    return float(fractions.Fraction(value.strip()))


def get_fractional_part(val):
    nearest = round(val)

    if abs(val - nearest) < TOL:
        return 0.0

    return val - math.floor(val)


def lcm(a, b):
    return abs(a * b) // math.gcd(a, b)


def parse_input(data_filename):

    if not os.path.exists(data_filename):
        print(f"File {data_filename} not found.")
        return None, None, None, None, None

    with open(data_filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Xac dinh muc tieu
    content = ''.join(lines)

    sense = GRB.MAXIMIZE

    if re.search(r'\bmin\b', content, re.IGNORECASE):
        sense = GRB.MINIMIZE

    elif re.search(r'\bmax\b', content, re.IGNORECASE):
        sense = GRB.MAXIMIZE

    # Doc ham muc tieu
    c_match = re.search(r'c:\s*\[(.*?)\]', content, re.IGNORECASE)

    if not c_match:
        print("Error: Objective function c not found.")
        return None, None, None, None, None

    try:
        c = np.array([
            parse_number(x)
            for x in c_match.group(1).split(',')
            if x.strip()
        ], dtype=float)

    except (ValueError, ZeroDivisionError):
        print("Error: Invalid objective coefficients.")
        return None, None, None, None, None

    n_vars = len(c)

    if n_vars == 0:
        print("Error: No decision variables.")
        return None, None, None, None, None

    # Doc cac rang buoc
    A_rows = []
    b_vec = []
    signs = []

    constraint_pattern = re.compile(
        r'^\s*\d+\s*:\s*(.*?)\s*(<=|>=|=)\s*(.*?)\s*$'
    )

    for line_no, line in enumerate(lines, start=1):

        line = line.strip()

        if not line or line.startswith('#'):
            continue

        if line.startswith(('c:', 'B:')):
            continue

        if '[CONSTRAINTS]' in line or '[VINCOLI]' in line:
            continue

        if 'Non neg' in line or 'non neg' in line.lower():
            continue

        match = constraint_pattern.match(line)

        if not match:
            continue

        lhs = match.group(1).strip()
        sign = match.group(2)
        rhs_text = match.group(3).strip()

        try:
            rhs = parse_number(rhs_text)

        except (ValueError, ZeroDivisionError):
            raise ValueError(
                f"Invalid RHS at line {line_no}: {rhs_text}"
            )

        row = np.zeros(n_vars)

        # Tach cac hang tu
        terms = lhs.replace('-', '+-').split('+')

        for term in terms:

            term = term.strip()

            if not term:
                continue

            term_match = re.fullmatch(
                r'([+-]?)\s*'
                r'(?:(\d+(?:\.\d*)?|\.\d+|\d+/\d+)\s*\*?\s*)?'
                r'x(\d+)',
                term
            )

            if not term_match:
                raise ValueError(
                    f"Invalid term at line {line_no}: {term}"
                )

            sign_coef = -1 if term_match.group(1) == '-' else 1

            if term_match.group(2):
                coefficient = parse_number(term_match.group(2))
            else:
                coefficient = 1.0

            variable_index = int(term_match.group(3)) - 1

            if variable_index < 0 or variable_index >= n_vars:
                raise ValueError(
                    f"Variable x{variable_index + 1} "
                    f"exceeds the declared number of variables."
                )

            # Cong don he so neu bien xuat hien nhieu lan
            row[variable_index] += sign_coef * coefficient

        A_rows.append(row)
        b_vec.append(rhs)
        signs.append(sign)

    if len(A_rows) == 0:
        print("Error: No constraints found.")
        return None, None, None, None, None

    A = np.array(A_rows, dtype=float)
    b = np.array(b_vec, dtype=float)

    return A, b, signs, c, sense


def solve_gomory(A, b, signs, c, sense):

    m, n = A.shape

    # Gomory Pure Integer can he so A va b la so nguyen
    if not np.allclose(A, np.round(A), atol=TOL):
        print("Error: Gomory Pure Integer requires integer coefficients in A.")
        return

    if not np.allclose(b, np.round(b), atol=TOL):
        print("Error: Gomory Pure Integer requires integer RHS values.")
        return

    model = Model("lp")
    model.Params.OutputFlag = 0

    # Su dung Simplex de dam bao lay duoc co so
    model.Params.Method = 1

    # Bien quyet dinh
    x = model.addVars(
        n, lb=0,
        vtype=GRB.CONTINUOUS,
        name="x"
    )

    # Bien phu
    s = model.addVars(
        m, lb=0,
        vtype=GRB.CONTINUOUS,
        name="s"
    )

    model.setObjective(
        quicksum(c[i] * x[i] for i in range(n)),
        sense
    )

    # Dua rang buoc ve dang phuong trinh
    for i in range(m):

        expr = quicksum(
            A[i, j] * x[j]
            for j in range(n)
        )

        if signs[i] == '<=':
            model.addConstr(
                expr + s[i] == b[i],
                name=f"c{i+1}"
            )

        elif signs[i] == '>=':
            model.addConstr(
                expr - s[i] == b[i],
                name=f"c{i+1}"
            )

        else:
            model.addConstr(
                expr == b[i],
                name=f"c{i+1}"
            )

    model.optimize()

    if model.status == GRB.INFEASIBLE:
        print("Relaxed problem is infeasible.")
        return

    if model.status == GRB.UNBOUNDED:
        print("Relaxed problem is unbounded.")
        return

    if model.status != GRB.OPTIMAL:
        print("Could not find optimal relaxed solution.")
        return

    # Danh sach bien va cot ma tran
    names_list = (
        [f"x_{i+1}" for i in range(n)] +
        [f"s_{i+1}" for i in range(m)]
    )

    vars_gurobi = (
        [x[i] for i in range(n)] +
        [s[i] for i in range(m)]
    )

    # Lay bien co so va khong co so
    basis_idxs = []
    non_basis_idxs = []

    try:
        for idx, var in enumerate(vars_gurobi):

            if var.VBasis == 0:
                basis_idxs.append(idx)

            else:
                non_basis_idxs.append(idx)

    except Exception as e:
        print("Cannot retrieve Simplex basis:", e)
        return

    print("\nOPT BASIS FOR GOMORY")
    print("Basic variables:", [
        names_list[i] for i in basis_idxs
    ])

    if len(basis_idxs) != m:
        print("Basis dimension error.")
        return

    # Tao ma tran mo rong [A | S]
    S_mat = np.zeros((m, m))

    for i, sign in enumerate(signs):

        if sign == '<=':
            S_mat[i, i] = 1.0

        elif sign == '>=':
            S_mat[i, i] = -1.0

    A_total = np.hstack([A, S_mat])

    try:
        A_B = A_total[:, basis_idxs]
        A_N = A_total[:, non_basis_idxs]

        if A_B.shape != (m, m):
            print("Invalid basis matrix.")
            return

        if abs(np.linalg.det(A_B)) < TOL:
            print("Basis matrix is singular.")
            return

        A_B_inv = np.linalg.inv(A_B)

    except Exception as e:
        print("Matrix Error:", e)
        return

    # Tinh bang don hinh
    print("\n[1] A_B^-1")

    for row in A_B_inv:
        print("  " + "  ".join(
            f"{format_frac(v):>8}" for v in row
        ))

    non_basic_names = [
        names_list[i] for i in non_basis_idxs
    ]

    print("\n[2] A_N")

    print("     " + " ".join(
        f"{name:>8}" for name in non_basic_names
    ))

    for row in A_N:
        print("  " + "  ".join(
            f"{format_frac(v):>8}" for v in row
        ))

    # A~ = A_B^-1 * A_N
    A_tilde_N = A_B_inv @ A_N

    # b~ = A_B^-1 * b
    b_tilde = A_B_inv @ b

    print("\n[3] A_tilde = A_B^-1 * A_N")

    for row in A_tilde_N:
        print("  " + "  ".join(
            f"{format_frac(v):>8}" for v in row
        ))

    print("\n[4] b_tilde = A_B^-1 * b")

    for val in b_tilde:
        print("  ", format_frac(val))

    # Tao lat cat Gomory
    print("\n" + "=" * 60)
    print("          GOMORY CUT GENERATION")
    print("=" * 60)

    generated_cuts = []

    for i in range(m):

        basic_var_idx = basis_idxs[i]
        basic_var_name = names_list[basic_var_idx]

        val_b = b_tilde[i]
        f0 = get_fractional_part(val_b)

        if f0 <= TOL:
            continue

        print(
            f"\nROW {i+1}: {basic_var_name}"
        )

        print(
            f"b~ = {format_frac(val_b)}, "
            f"f0 = {format_frac(f0)}"
        )

        cut_lhs = []

        for j, coeff in enumerate(A_tilde_N[i]):

            fj = get_fractional_part(coeff)

            if fj > TOL:

                var_name = non_basic_names[j]

                print(
                    f"{var_name}: "
                    f"coefficient = {format_frac(coeff)}, "
                    f"fraction = {format_frac(fj)}"
                )

                cut_lhs.append((fj, non_basis_idxs[j]))

        # Khong bo qua lat cat rong
        cut = {
            'id': i + 1,
            'var': basic_var_name,
            'lhs': cut_lhs,
            'rhs': f0
        }

        generated_cuts.append(cut)

        if cut_lhs:

            cut_str = " + ".join(
                f"{format_frac(coef)} {names_list[idx]}"
                for coef, idx in cut_lhs
            )

        else:
            cut_str = "0"

        print("\nGENERATED GOMORY CUT:")
        print(f"{cut_str} >= {format_frac(f0)}")

        # Dua ve dang he so nguyen de hien thi
        denominators = []

        denominators.append(
            fractions.Fraction(f0).limit_denominator(1000).denominator
        )

        for coef, idx in cut_lhs:
            denominators.append(
                fractions.Fraction(coef).limit_denominator(1000).denominator
            )

        current_lcm = 1

        for d in denominators:
            current_lcm = lcm(current_lcm, d)

        int_lhs = []

        for coef, idx in cut_lhs:
            int_lhs.append(
                f"{round(coef * current_lcm)} {names_list[idx]}"
            )

        int_rhs = round(f0 * current_lcm)

        print(
            "Integer form:",
            (" + ".join(int_lhs) if int_lhs else "0"),
            ">=",
            int_rhs
        )

    if not generated_cuts:
        print("\nNo fractional basic variable.")
        print("The current LP solution is integer feasible.")
        return

    # Kiem tra nghiem nguyen bang Gurobi
    print("\n" + "=" * 60)
    print("          CHECK WITH INTEGER OPTIMUM")
    print("=" * 60)

    model_int = Model("ilp")
    model_int.Params.OutputFlag = 0

    xi = model_int.addVars(
        n,
        lb=0,
        vtype=GRB.INTEGER,
        name="x"
    )

    model_int.setObjective(
        quicksum(c[i] * xi[i] for i in range(n)),
        sense
    )

    for i in range(m):

        expr = quicksum(
            A[i, j] * xi[j]
            for j in range(n)
        )

        if signs[i] == '<=':
            model_int.addConstr(expr <= b[i])

        elif signs[i] == '>=':
            model_int.addConstr(expr >= b[i])

        else:
            model_int.addConstr(expr == b[i])

    model_int.optimize()

    if model_int.status == GRB.INFEASIBLE:
        print("Integer problem is infeasible.")
        return

    if model_int.status == GRB.UNBOUNDED:
        print("Integer problem is unbounded.")
        return

    if model_int.status != GRB.OPTIMAL:
        print("Could not find integer optimum.")
        return

    obj_int = model_int.ObjVal

    sol_int = [
        xi[i].X for i in range(n)
    ]

    print(f"Integer Optimum: {obj_int:.4f}")
    print(f"Integer Solution: {sol_int}")

    # Cho nguoi dung chon lat cat
    print("\nChoose a cut to verify:")

    for i, cut in enumerate(generated_cuts):

        print(
            f"{i+1}: Cut from Row "
            f"{cut['id']} ({cut['var']})"
        )

    try:

        inp = input("Number (Enter to skip): ")

        if inp.strip():

            choice = int(inp)

            if choice < 1 or choice > len(generated_cuts):
                print("Invalid choice.")
                return

            selected = generated_cuts[choice - 1]

            # Tao ve trai cua lat cat
            expr = quicksum(
                coef * vars_gurobi[idx]
                for coef, idx in selected['lhs']
            )

            model.addConstr(
                expr >= selected['rhs'],
                name="Gomory_Cut"
            )

            model.optimize()

            if model.status == GRB.OPTIMAL:

                new_opt = model.ObjVal

                print(
                    f"\nNew relaxed optimum: {new_opt:.4f}"
                )

                # So sanh theo chieu toi uu
                if abs(new_opt - obj_int) < 1e-4:

                    print(
                        "SUCCESS: Integer optimum reached!"
                    )

                else:

                    print(
                        "More Gomory cuts may be needed."
                    )

            elif model.status == GRB.INFEASIBLE:

                print("Problem became infeasible.")

            else:

                print("Could not solve after adding cut.")

    except ValueError:
        print("Invalid input.")


if __name__ == "__main__":

    try:

        A, b, signs, c, sense = parse_input(INPUT_FILE)

        if A is not None:

            solve_gomory(A, b, signs, c, sense)

        else:

            print("Parsing error.")

    except ValueError as e:

        print("Input error:", e)
