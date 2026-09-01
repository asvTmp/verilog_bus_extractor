import re
import sys
import json
import os

def parse_args():
    return sys.argv[1] if len(sys.argv) > 1 else "./data/tmp.v"

def read_file(file_path):
    try:
        with open(file_path, 'r') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Файл {file_path} не найден", file=sys.stderr)
        sys.exit(1)

def split_concat(inner):
    elements = []
    current = []
    depth = 0
    for ch in inner:
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
        elif ch == ',' and depth == 0:
            elements.append(''.join(current).strip())
            current = []
            continue
        current.append(ch)
    if current:
        elements.append(''.join(current).strip())
    return elements

def extract_signals(code):
    signals = []
    pattern = re.compile(
        r'(?:input|output|inout|logic|reg|wire)\s+'
        r'(?:\[\s*(\d+)\s*:\s*(\d+)\s*\]\s+)?'
        r'([a-zA-Z_][a-zA-Z0-9_,\s]+);',
        re.IGNORECASE | re.MULTILINE
    )
    for m in pattern.finditer(code):
        msb, lsb = m.group(1), m.group(2)
        if msb is not None:
            range_str = f"[{msb}:{lsb}]"
        else:
            range_str = "[0:0]"
        names_part = m.group(3)
        names = [n.strip() for n in names_part.split(',') if n.strip()]
        for name in names:
            if name.lower() in ['input', 'output', 'inout', 'logic', 'reg', 'wire']:
                continue
            signals.append({"range": range_str, "name": name})
    return signals

def find_assigns(code):
    assigns = []
    start_pattern = re.compile(r'assign\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*\{', re.IGNORECASE)
    pos = 0
    while True:
        m = start_pattern.search(code, pos)
        if not m:
            break
        signal = m.group(1)
        brace_depth = 0
        end = -1
        i = m.end() - 1
        while i < len(code):
            if code[i] == '{':
                brace_depth += 1
            elif code[i] == '}':
                brace_depth -= 1
            elif code[i] == ';' and brace_depth == 0:
                end = i
                break
            i += 1
        if end == -1:
            break
        expression = code[m.end():end].strip()
        assigns.append({"signal": signal, "expression": expression})
        pos = end + 1
    return assigns

def filter_assigns(assigns, prefix):
    return [a for a in assigns if a["signal"].startswith(prefix)]

def build_json_data(code, prefixes=["port"]):
    signals = extract_signals(code)
    all_assigns = find_assigns(code)
    filtered_items = []
    seen_signals = set()
    for prefix in prefixes:
        filtered = filter_assigns(all_assigns, prefix)
        for item in filtered:
            signal = item["signal"]
            if signal in seen_signals:
                continue
            seen_signals.add(signal)
            expr = item["expression"].rstrip()
            if expr.endswith('}'):
                expr = expr[:-1].rstrip()
            lines = expr.split('\n')
            elements_with_comments = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if line.startswith('//'):
                    continue
                comment = ""
                if '//' in line:
                    parts = line.split('//', 1)
                    wire_part = parts[0].strip()
                    comment = parts[1].strip() if len(parts) > 1 else ""
                else:
                    wire_part = line
                if wire_part.endswith(','):
                    wire_part = wire_part[:-1].strip()
                if not wire_part:
                    continue
                elements_with_comments.append({"wire": wire_part, "comment": comment})
            filtered_items.append({"signal": signal, "elements": elements_with_comments})
    return {
        "signals": signals,
        "all_assigns": all_assigns,
        "filtered_assigns": filtered_items
    }

def print_table(output, md_file_name=None):
    if not output.get("filtered_assigns"):
        print("Нет данных для отображения.")
        return
    lines = []
    for item in output["filtered_assigns"]:
        lines.append(f"## {item['signal']}")
        lines.append("| wire | comment |")
        lines.append("|------|---------|")
        for elem in item["elements"]:
            lines.append(f"| {elem['wire']} | {elem['comment']} |")
        lines.append("")
    if md_file_name:
        os.makedirs(os.path.dirname(md_file_name), exist_ok=True)
        with open(md_file_name, 'w') as f:
            f.write('\n'.join(lines))
    else:
        print('\n'.join(lines))

def main():
    file_path = parse_args()
    code = read_file(file_path)
    prefixes = ["port"]
    data = build_json_data(code, prefixes)
    output = {
        "all_assigns": data["all_assigns"],
        "filtered_assigns": data["filtered_assigns"]
    }
    # Вывод JSON на экран
    print(json.dumps(output, indent=2, ensure_ascii=False))
    # Сохранение таблицы в файл
    print_table(output, "./data/table.md")

if __name__ == "__main__":
    main()