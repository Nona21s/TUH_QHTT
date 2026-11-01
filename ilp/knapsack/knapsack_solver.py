
import math
from collections import deque


# =====================================================
# 1. DOC DU LIEU
# =====================================================

def load_data(filename):
    capacity = None
    items = []

    with open(filename, "r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            parts = line.split()

            if parts[0].upper() == "CAPACITY":
                if len(parts) != 2:
                    raise ValueError(
                        f"Dong {line_number}: CAPACITY khong hop le."
                    )
                capacity = int(parts[1])

            elif parts[0].upper() == "ITEM":
                if len(parts) != 4:
                    raise ValueError(
                        f"Dong {line_number}: ITEM phai co dang ITEM id value weight."
                    )

                item_id = int(parts[1])
                value = int(parts[2])
                weight = int(parts[3])

                items.append({
                    "id": item_id,
                    "v": value,
                    "p": weight
                })

            else:
                raise ValueError(
                    f"Dong {line_number}: Khong nhan dien duoc du lieu."
                )

    if capacity is None:
        raise ValueError("Khong tim thay CAPACITY.")

    if capacity < 0:
        raise ValueError("CAPACITY phai khong am.")

    if not items:
        raise ValueError("Danh sach vat pham dang rong.")

    for item in items:
        if item["p"] <= 0:
            raise ValueError("Trong luong vat pham phai lon hon 0.")

        if item["v"] < 0:
            raise ValueError("Gia tri vat pham phai khong am.")

    return capacity, items


# =====================================================
# 2. NUT CAY BRANCH AND BOUND
# =====================================================

class Node:
    def __init__(self, level, value, weight, bound, decisions):
        self.level = level
        self.value = value
        self.weight = weight
        self.bound = bound
        self.decisions = decisions


# =====================================================
# 3. BRANCH AND BOUND CHO KNAPSACK 0/1
# =====================================================

class TreeVisualizer:

    def __init__(self, capacity, items):
        self.capacity = capacity

        self.items = sorted(
            items,
            key=lambda item: item["v"] / item["p"],
            reverse=True
        )

        self.best_value = 0
        self.best_weight = 0
        self.best_solution = []

    def calculate_bound(self, node):
        if node.weight >= self.capacity:
            if node.weight == self.capacity:
                return node.value
            return 0

        bound = node.value
        total_weight = node.weight
        level = node.level

        while (
            level < len(self.items)
            and total_weight + self.items[level]["p"]
            <= self.capacity
        ):
            total_weight += self.items[level]["p"]
            bound += self.items[level]["v"]
            level += 1

        if level < len(self.items):
            remaining = self.capacity - total_weight

            bound += (
                remaining
                * self.items[level]["v"]
                / self.items[level]["p"]
            )

        return bound

    def solve(self):
        root = Node(
            level=0,
            value=0,
            weight=0,
            bound=0,
            decisions=[]
        )

        root.bound = self.calculate_bound(root)

        queue = deque([root])

        while queue:
            node = queue.popleft()

            if node.bound <= self.best_value:
                continue

            if node.level >= len(self.items):
                continue

            item = self.items[node.level]

            # Nhanh 1: Chon vat hien tai
            new_weight = node.weight + item["p"]
            new_value = node.value + item["v"]

            if new_weight <= self.capacity:
                decisions = node.decisions + [1]

                if new_value > self.best_value:
                    self.best_value = new_value
                    self.best_weight = new_weight
                    self.best_solution = decisions

                child = Node(
                    level=node.level + 1,
                    value=new_value,
                    weight=new_weight,
                    bound=0,
                    decisions=decisions
                )

                child.bound = self.calculate_bound(child)

                if child.bound > self.best_value:
                    queue.append(child)

            # Nhanh 2: Khong chon vat hien tai
            decisions = node.decisions + [0]

            child = Node(
                level=node.level + 1,
                value=node.value,
                weight=node.weight,
                bound=0,
                decisions=decisions
            )

            child.bound = self.calculate_bound(child)

            if child.bound > self.best_value:
                queue.append(child)

        # Bo sung cac quyet dinh 0 con thieu
        self.best_solution += (
            [0] * (len(self.items) - len(self.best_solution))
        )

        return (
            self.best_value,
            self.best_weight,
            self.best_solution
        )

    def display_result(self):
        value, weight, solution = self.solve()

        print("\n========== KNAPSACK 0/1 ==========")
        print("Gia tri toi uu:", value)
        print("Trong luong su dung:", weight)
        print("Suc chua:", self.capacity)

        print("\nCac vat duoc chon:")

        for i, selected in enumerate(solution):
            if selected == 1:
                item = self.items[i]

                print(
                    f"Vat {item['id']}: "
                    f"Gia tri = {item['v']}, "
                    f"Trong luong = {item['p']}"
                )

        return value, weight, solution


# =====================================================
# 4. KNAPSACK NGUYEN KHONG GIOI HAN
# =====================================================

class KnapsackProblem:

    def __init__(self, capacity, items):
        self.capacity = capacity
        self.items = items

        self.items_sorted = sorted(
            items,
            key=lambda item: item["v"] / item["p"],
            reverse=True
        )

    # -------------------------------------------------
    # Knapsack 0/1: Can duoi va can tren
    # -------------------------------------------------

    def solve_binary_detailed(self):
        # Can duoi: tham lam chon vat theo ty le v/p
        remaining = self.capacity
        lower_bound = 0
        selected = []

        for item in self.items_sorted:
            if item["p"] <= remaining:
                remaining -= item["p"]
                lower_bound += item["v"]
                selected.append(item["id"])

        # Can tren: cho phep lay mot phan vat cuoi cung
        remaining = self.capacity
        upper_bound = 0

        for item in self.items_sorted:
            if item["p"] <= remaining:
                remaining -= item["p"]
                upper_bound += item["v"]
            else:
                upper_bound += (
                    remaining * item["v"] / item["p"]
                )
                break

        print("\n========== CAN DUOI / CAN TREN 0/1 ==========")
        print("Can duoi:", lower_bound)
        print("Can tren:", upper_bound)
        print("Vat duoc chon theo tham lam:", selected)

        return lower_bound, upper_bound

    # -------------------------------------------------
    # Knapsack nguyen khong gioi han: Quy hoach dong
    # -------------------------------------------------

    def solve_integer_detailed(self):
        capacity = self.capacity

        if int(capacity) != capacity or capacity < 0:
            raise ValueError(
                "Suc chua phai la so nguyen khong am."
            )

        for item in self.items:
            if int(item["p"]) != item["p"] or item["p"] <= 0:
                raise ValueError(
                    "Trong luong phai la so nguyen duong."
                )

            if int(item["v"]) != item["v"] or item["v"] < 0:
                raise ValueError(
                    "Gia tri phai la so nguyen khong am."
                )

        capacity = int(capacity)

        # dp[c]: Gia tri toi uu voi suc chua toi da c
        dp = [0] * (capacity + 1)

        # Luu vat duoc chon cuoi cung
        trace = [-1] * (capacity + 1)

        for c in range(1, capacity + 1):
            for i, item in enumerate(self.items):
                p = int(item["p"])
                v = int(item["v"])

                if p <= c and dp[c - p] + v > dp[c]:
                    dp[c] = dp[c - p] + v
                    trace[c] = i

        # Truy vet nghiem
        counts = [0] * len(self.items)

        c = capacity

        while c > 0 and trace[c] != -1:
            i = trace[c]

            counts[i] += 1
            c -= int(self.items[i]["p"])

        total_weight = sum(
            counts[i] * int(self.items[i]["p"])
            for i in range(len(self.items))
        )

        total_value = dp[capacity]

        print("\n========== KNAPSACK NGUYEN ==========")
        print("Suc chua:", capacity)
        print("Trong luong su dung:", total_weight)

        print("\nCac vat duoc chon:")

        for i, count in enumerate(counts):
            if count > 0:
                item = self.items[i]

                print(
                    f"Vat {item['id']}: "
                    f"Chon {count} lan"
                )

        print("Gia tri toi uu:", total_value)

        return total_value, total_weight, counts


# =====================================================
# 5. SINH LAT CAT GOMORY
# =====================================================

class GomoryKnapsackInteger:

    def __init__(self, capacity, items):
        self.capacity = capacity
        self.items = items

    @staticmethod
    def fractional_part(number):
        return number - math.floor(number)

    def solve_and_generate_cut(self):
        if int(self.capacity) != self.capacity:
            raise ValueError(
                "Gomory hien tai yeu cau suc chua nguyen."
            )

        for item in self.items:
            if int(item["p"]) != item["p"] or item["p"] <= 0:
                raise ValueError(
                    "Gomory hien tai yeu cau trong luong nguyen duong."
                )

        # Chon bien co ty le gia tri/trong luong lon nhat
        items_sorted = sorted(
            self.items,
            key=lambda item: item["v"] / item["p"],
            reverse=True
        )

        base_item = items_sorted[0]
        base_weight = base_item["p"]

        rhs = self.capacity / base_weight
        frac_rhs = self.fractional_part(rhs)

        print("\n========== GOMORY CUT ==========")
        print("Bien co ban:", f"x{base_item['id']}")
        print("RHS:", rhs)
        print("Phan le RHS:", frac_rhs)

        if math.isclose(frac_rhs, 0, abs_tol=1e-9):
            print(
                "RHS la so nguyen, hang tableau nay "
                "khong tao ra lat cat Gomory phan le."
            )
            return None

        # Hang tableau:
        # x_base + sum(p_i/p_base * x_i)
        #        + (1/p_base)*s = C/p_base
        #
        # Lat cat:
        # sum(frac(a_j) * x_j) >= frac(RHS)

        cut_terms = []

        print("\nCac he so trong lat cat:")

        for item in items_sorted:
            if item["id"] == base_item["id"]:
                continue

            coefficient = item["p"] / base_weight
            frac_coefficient = self.fractional_part(
                coefficient
            )

            if not math.isclose(
                frac_coefficient, 0, abs_tol=1e-9
            ):
                cut_terms.append(
                    (item["id"], frac_coefficient)
                )

                print(
                    f"x{item['id']}: "
                    f"{coefficient} -> {frac_coefficient}"
                )

        # Bien slack s = C - sum(p_i*x_i)
        slack_coefficient = 1 / base_weight
        frac_slack = self.fractional_part(
            slack_coefficient
        )

        if not math.isclose(frac_slack, 0, abs_tol=1e-9):
            cut_terms.append(("s", frac_slack))

        print(
            f"s: {slack_coefficient} -> {frac_slack}"
        )

        print("\nLat cat Gomory:")

        if not cut_terms:
            print("Khong co he so phan le trong lat cat.")
            return None

        expression = " + ".join(
            f"{coefficient:.6g}*{variable}"
            for variable, coefficient in cut_terms
        )

        print(
            f"{expression} >= {frac_rhs:.6g}"
        )

        print(
            "\nLuu y: Chuong trinh moi chi sinh va in lat cat, "
            "chua them lat cat vao mo hinh de lap lai giai."
        )

        return cut_terms, frac_rhs


# =====================================================
# 6. KIEM TRA KET QUA
# =====================================================

def check_coincidence(capacity, items):
    binary_solver = TreeVisualizer(capacity, items)
    binary_value, binary_weight, binary_solution = (
        binary_solver.solve()
    )

    integer_solver = KnapsackProblem(capacity, items)
    integer_value, integer_weight, integer_counts = (
        integer_solver.solve_integer_detailed()
    )

    print("\n========== SO SANH ==========")
    print("Knapsack 0/1:")
    print("  Gia tri:", binary_value)
    print("  Trong luong:", binary_weight)

    print("Knapsack nguyen khong gioi han:")
    print("  Gia tri:", integer_value)
    print("  Trong luong:", integer_weight)

    if binary_value <= integer_value:
        print(
            "Kiem tra: Gia tri Knapsack 0/1 "
            "khong vuot qua Knapsack nguyen."
        )
    else:
        print(
            "Can kiem tra lai ket qua: "
            "Knapsack 0/1 vuot Knapsack nguyen."
        )


# =====================================================
# 7. CHUONG TRINH CHINH
# =====================================================

def main():
    filename = "knapsack.txt"

    try:
        capacity, items = load_data(filename)

    except (OSError, ValueError) as error:
        print("Loi doc du lieu:", error)
        return

    print("========== DU LIEU KNAPSACK ==========")
    print("Suc chua:", capacity)

    for item in items:
        print(
            f"Vat {item['id']}: "
            f"Gia tri = {item['v']}, "
            f"Trong luong = {item['p']}, "
            f"Ty le = {item['v'] / item['p']:.4f}"
        )

    # 1. Can duoi va can tren cho bai toan 0/1
    problem = KnapsackProblem(capacity, items)
    problem.solve_binary_detailed()

    # 2. Branch and Bound cho bai toan 0/1
    binary_solver = TreeVisualizer(capacity, items)
    binary_solver.display_result()

    # 3. Knapsack nguyen khong gioi han
    integer_solver = KnapsackProblem(capacity, items)
    integer_solver.solve_integer_detailed()

    # 4. Sinh lat cat Gomory
    gomory = GomoryKnapsackInteger(capacity, items)
    gomory.solve_and_generate_cut()

    # 5. So sanh hai bai toan
    check_coincidence(capacity, items)


if __name__ == "__main__":
    main()
