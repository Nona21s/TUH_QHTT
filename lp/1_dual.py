import re
import os
import numpy as np
from fractions import Fraction


def to_frac_str(value, max_denom=1000000):
    return str(Fraction(float(value)).limit_denominator(max_denom))


def parse_number(text):
    text = text.strip().replace(" ", "")
    if "/" in text:
        return float(Fraction(text))
    return float(text)


def parse_expression(expr):
    """
    Đọc biểu thức tuyến tính:
    500*x1 + 300*x2
    2x1 - x2
    x1 + 0.5*x2
    """
    expr = expr.replace(" ", "")
    if not expr:
        return {}

    if expr[0] not in "+-":
        expr = "+" + expr

    terms = re.findall(
        r'([+-])(?:(\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?)\*?)?x(\d+)',
        expr
    )

    coefficients = {}
    for sign, number, index in terms:
        coefficient = 1.0 if number == "" else parse_number(number)
        if sign == "-":
            coefficient *= -1
        index = int(index)
        coefficients[index] = coefficients.get(index, 0.0) + coefficient

    # Bảo đảm không bỏ sót phần văn bản không nhận dạng được
    cleaned = re.sub(
        r'([+-])(?:(\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?)\*?)?x\d+',
        '',
        expr
    )
    if cleaned:
        raise ValueError(f"Không đọc được biểu thức: {expr}")

    return coefficients


def parse_data(filename):
    with open(filename, "r", encoding="utf-8") as file:
        content = file.read()

    target_match = re.search(
        r'target\s*:\s*(max|min)\s*(.*)',
        content,
        re.IGNORECASE
    )
    if not target_match:
        raise ValueError("Không tìm thấy dòng target: max/min ...")

    objective_type = target_match.group(1).lower()
    objective_expr = target_match.group(2).splitlines()[0].strip()
    c_dict = parse_expression(objective_expr)

    # Số biến lấy từ hàm mục tiêu và các ràng buộc
    all_indices = [int(i) for i in re.findall(r'x(\d+)', content)]
    if not all_indices:
        raise ValueError("Không tìm thấy biến x1, x2, ...")
    num_vars = max(max(all_indices), max(c_dict.keys(), default=0))

    c = np.zeros(num_vars, dtype=float)
    for index, value in c_dict.items():
        c[index - 1] = value

    # Chỉ đọc các ràng buộc trong phần CONSTRAINTS
    constraint_match = re.search(
        r'\[CONSTRAINTS\](.*?)(?=\n\s*B\s*:|\Z)',
        content,
        re.IGNORECASE | re.DOTALL
    )
    if not constraint_match:
        raise ValueError("Không tìm thấy phần [CONSTRAINTS]")

    constraint_text = constraint_match.group(1)
    rows = {}
    rhs_values = {}
    senses = {}

    for line in constraint_text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue

        match = re.match(
            r'(\d+)\s*:\s*(.*?)\s*(<=|>=|=)\s*([+-]?\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?)\s*$',
            line
        )
        if not match:
            continue

        row_index = int(match.group(1))
        expression = match.group(2)
        sense = match.group(3)
        rhs = parse_number(match.group(4))
        coeff_dict = parse_expression(expression)

        # Các dòng khai báo x_i >= 0 trong phần # Non neg
        # là điều kiện dấu biến, không phải ràng buộc tạo biến đối ngẫu.
        is_nonnegative_declaration = (
            sense == ">="
            and abs(rhs) < 1e-12
            and len(coeff_dict) == 1
            and len(re.findall(r'x\d+', expression)) == 1
            and next(iter(coeff_dict.values())) > 0
        )
        if is_nonnegative_declaration:
            continue

        row = np.zeros(num_vars, dtype=float)
        for index, value in coeff_dict.items():
            if index < 1 or index > num_vars:
                raise ValueError(f"Ràng buộc {row_index}: biến x{index} không hợp lệ")
            row[index - 1] = value

        rows[row_index] = row
        rhs_values[row_index] = rhs
        senses[row_index] = sense

    if not rows:
        raise ValueError("Không tìm thấy ràng buộc thực tế nào.")

    basis_match = re.search(r'B\s*:\s*\[([^\]]*)\]', content, re.IGNORECASE)
    if not basis_match:
        raise ValueError("Không tìm thấy dòng B: [...]")

    basis_indices = [
        int(value.strip())
        for value in basis_match.group(1).split(",")
        if value.strip()
    ]

    return objective_type, c, rows, rhs_values, senses, basis_indices


def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(current_dir, "data.txt")
    output_file = os.path.join(current_dir, "dual.txt")

    try:
        objective_type, c, A_dict, b_dict, senses, B_indices = parse_data(input_file)
    except Exception as error:
        print(f"Lỗi đọc dữ liệu: {error}")
        return

    # Code này xây dựng đối ngẫu cho bài toán MAX/MIN với x >= 0.
    if objective_type not in ("max", "min"):
        print("Chỉ hỗ trợ target: max hoặc target: min.")
        return

    all_indices = sorted(A_dict.keys())
    num_vars = len(c)

    if len(B_indices) != num_vars:
        print(
            f"Cơ sở B phải có đúng {num_vars} chỉ số "
            f"(hiện tại có {len(B_indices)})."
        )
        return

    if len(set(B_indices)) != len(B_indices):
        print("Danh sách B có chỉ số bị lặp.")
        return

    missing = [index for index in B_indices if index not in A_dict]
    if missing:
        print(f"Các chỉ số cơ sở không tồn tại: {missing}")
        return

    A_B = np.array([A_dict[index] for index in B_indices], dtype=float)
    b_B = np.array([b_dict[index] for index in B_indices], dtype=float)

    try:
        # A_B x = b_B: nghiệm cơ sở của bài toán gốc
        x_basic = np.linalg.solve(A_B, b_B)

        # A_B^T y_B = c: nghiệm đối ngẫu ứng với cơ sở B
        y_basic = np.linalg.solve(A_B.T, c)
    except np.linalg.LinAlgError:
        print("Ma trận cơ sở A_B suy biến, không thể tính nghiệm.")
        return

    # Gán 0 cho các biến đối ngẫu ngoài cơ sở
    y = {index: 0.0 for index in all_indices}
    for index, value in zip(B_indices, y_basic):
        y[index] = float(value)

    # Kiểm tra tính khả thi của nghiệm gốc
    primal_feasible = np.all(x_basic >= -1e-8)
    for index in all_indices:
        lhs = float(A_dict[index] @ x_basic)
        rhs = b_dict[index]
        sense = senses[index]

        if sense == "<=" and lhs > rhs + 1e-7:
            primal_feasible = False
        elif sense == ">=" and lhs < rhs - 1e-7:
            primal_feasible = False
        elif sense == "=" and abs(lhs - rhs) > 1e-7:
            primal_feasible = False

    # Kiểm tra dấu các biến đối ngẫu theo loại bài toán gốc
    dual_sign_feasible = True
    for index in all_indices:
        if objective_type == "max":
            if senses[index] == "<=" and y[index] < -1e-8:
                dual_sign_feasible = False
            elif senses[index] == ">=" and y[index] > 1e-8:
                dual_sign_feasible = False
        else:
            if senses[index] == "<=" and y[index] > 1e-8:
                dual_sign_feasible = False
            elif senses[index] == ">=" and y[index] < -1e-8:
                dual_sign_feasible = False

    # Kiểm tra ràng buộc đối ngẫu theo dấu biến x >= 0
    A = np.array([A_dict[index] for index in all_indices], dtype=float)
    y_vector = np.array([y[index] for index in all_indices], dtype=float)
    dual_lhs = A.T @ y_vector

    if objective_type == "max":
        dual_constraint_feasible = np.all(dual_lhs >= c - 1e-7)
    else:
        dual_constraint_feasible = np.all(dual_lhs <= c + 1e-7)

    primal_value = float(c @ x_basic)
    dual_value = float(sum(b_dict[index] * y[index] for index in all_indices))

    print("=== KIỂM TRA NGHIỆM CƠ SỞ ===")
    print("B =", B_indices)
    print("x cơ sở =", [to_frac_str(value) for value in x_basic])
    print("y đối ngẫu =", [to_frac_str(y[index]) for index in all_indices])
    print(f"Giá trị hàm mục tiêu gốc = {primal_value:.8f}")
    print(f"Giá trị hàm mục tiêu đối ngẫu = {dual_value:.8f}")
    print("Khả thi primal:", primal_feasible)
    print("Khả thi dấu dual:", dual_sign_feasible)
    print("Khả thi ràng buộc dual:", dual_constraint_feasible)

    optimal = (
        primal_feasible
        and dual_sign_feasible
        and dual_constraint_feasible
        and abs(primal_value - dual_value) <= 1e-6
    )
    print("Kết luận:", "CƠ SỞ TỐI ƯU" if optimal else "CHƯA XÁC NHẬN TỐI ƯU")

    # Ghi mô hình đối ngẫu ra file
    with open(output_file, "w", encoding="utf-8") as file:
        file.write("=== DUAL PROBLEM ===\n")

        objective_terms = []
        for index in all_indices:
            coefficient = b_dict[index]
            if abs(coefficient) > 1e-12:
                objective_terms.append(f"({to_frac_str(coefficient)})*y{index}")

        dual_direction = "Min" if objective_type == "max" else "Max"
        file.write(f"{dual_direction} W = " + " + ".join(objective_terms) + "\n\n")

        file.write("Subject to:\n")
        for j in range(num_vars):
            terms = []
            for index in all_indices:
                coefficient = A_dict[index][j]
                if abs(coefficient) > 1e-12:
                    terms.append(f"({to_frac_str(coefficient)})*y{index}")

            lhs = " + ".join(terms) if terms else "0"
            relation = ">=" if objective_type == "max" else "<="
            file.write(f"{lhs} {relation} {to_frac_str(c[j])}\n")

        file.write("\nSign conditions of dual variables:\n")
        for index in all_indices:
            sense = senses[index]
            if sense == "=":
                sign_text = f"y{index} free"
            elif objective_type == "max":
                sign_text = f"y{index} >= 0" if sense == "<=" else f"y{index} <= 0"
            else:
                sign_text = f"y{index} <= 0" if sense == "<=" else f"y{index} >= 0"
            file.write(sign_text + "\n")

        file.write("\n=== DUAL SOLUTION FROM BASIS ===\n")
        file.write("Basis B = " + str(B_indices) + "\n")
        file.write("A_B inverse:\n")
        A_B_inv = np.linalg.inv(A_B)
        for row in A_B_inv:
            file.write(str([to_frac_str(value) for value in row]) + "\n")

        file.write("\ny = (")
        file.write(", ".join(to_frac_str(y[index]) for index in all_indices))
        file.write(")\n")

        file.write(f"Primal objective = {to_frac_str(primal_value)}\n")
        file.write(f"Dual objective = {to_frac_str(dual_value)}\n")
        file.write(f"Optimal basis verified = {optimal}\n")

    print(f"\nĐã lưu kết quả vào: {output_file}")


if __name__ == "__main__":
    main()
