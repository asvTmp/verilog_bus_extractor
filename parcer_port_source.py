import sys
import json
import os
import re


def read_file_lines(file_path):
    with open(file_path, 'r') as f:
        return f.readlines()


def filter_assigns_by_port(lines, port_name):
    result = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("assign"):
            continue
        if "=" in stripped:
            parts = stripped.split("=", 1)
            if port_name in parts[1]:
                result.append(line)
    return result


def parse_assign_line(line, total_width=16, port_filter=None):
    line = line.strip()
    if not line.startswith("assign"):
        return None

    body = line[6:].strip()
    if body.endswith(';'):
        body = body[:-1].strip()

    if '=' not in body:
        return None

    left, right = body.split('=', 1)
    target = left.strip()
    right = right.strip()

    result = {
        "full": line.strip(),
        "target": target,
        "source": "",
        "condition": "",
        "default": "",
        "target_range": "",
        "target_width": 1,
        "source_range": "",
        "source_width": 1,
        "comment": "",
        "not_used": []
    }

    comment = ""
    if '//' in right:
        right_part, comment = right.split('//', 1)
        right = right_part.strip()
        comment = comment.strip()
    result["comment"] = comment

    if '[' in target and ']' in target:
        name, range_part = target.split('[', 1)
        range_part = range_part.replace(']', '').strip()
        range_part = re.sub(r'[^\d:]', '', range_part)
        result["target_range"] = range_part
        if ':' in range_part:
            msb, lsb = range_part.split(':')
            result["target_width"] = abs(int(msb) - int(lsb)) + 1
        else:
            result["target_width"] = 1
        result["target"] = name.strip()
    else:
        result["target"] = target

    if right.startswith('{'):
        inner = right[1:].strip()
        depth = 0
        end_pos = -1
        for i, ch in enumerate(inner):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end_pos = i
                    break
        if end_pos != -1:
            inner = inner[:end_pos].strip()
        elements = [e.strip() for e in inner.split(',')]
        for elem in elements:
            if port_filter and port_filter in elem:
                elem_clean = re.sub(r'^[~!&|]', '', elem).strip()
                if '[' in elem_clean and ']' in elem_clean:
                    name, range_part = elem_clean.split('[', 1)
                    range_part = range_part.replace(']', '').strip()
                    range_part = re.sub(r'[^\d:]', '', range_part)
                    result["source"] = name.strip()
                    result["source_range"] = range_part
                    if ':' in range_part:
                        msb, lsb = range_part.split(':')
                        result["source_width"] = abs(int(msb) - int(lsb)) + 1
                    else:
                        result["source_width"] = 1
                else:
                    result["source"] = elem_clean
                    result["source_range"] = ""
                    result["source_width"] = 1
                break
    else:
        if '?' in right and ':' in right:
            question_pos = right.find('?')
            colon_pos = -1
            depth = 0
            for i, ch in enumerate(right):
                if ch == '[':
                    depth += 1
                elif ch == ']':
                    depth -= 1
                elif ch == ':' and depth == 0 and i > question_pos:
                    colon_pos = i
                    break

            if colon_pos != -1:
                condition_part = right[:question_pos].strip()
                source_part = right[question_pos + 1:colon_pos].strip()
                default_part = right[colon_pos + 1:].strip()
                result["condition"] = condition_part
                result["source"] = source_part
                result["default"] = default_part
            else:
                result["source"] = right
        else:
            result["source"] = right

        src = result["source"]
        src = src.rstrip(';')
        src = re.sub(r'^[~!&|]', '', src).strip()

        if '[' in src and ']' in src:
            name, range_part = src.split('[', 1)
            range_part = range_part.replace(']', '').strip()
            range_part = range_part.rstrip(';')
            range_part = re.sub(r'[^\d:]', '', range_part)
            result["source_range"] = range_part
            if ':' in range_part:
                msb, lsb = range_part.split(':')
                result["source_width"] = abs(int(msb) - int(lsb)) + 1
            else:
                result["source_width"] = 1
            result["source"] = name.strip()
        else:
            result["source"] = src

    if result["source"]:
        occupied = set()
        if result["source_range"]:
            rng = result["source_range"]
            if ':' in rng:
                msb, lsb = rng.split(':')
                for bit in range(int(lsb), int(msb) + 1):
                    occupied.add(bit)
            else:
                occupied.add(int(rng))

        free_bits = []
        current_range = None
        for bit in range(total_width - 1, -1, -1):
            if bit not in occupied:
                if current_range is None:
                    current_range = [bit, bit]
                else:
                    current_range[1] = bit
            else:
                if current_range is not None:
                    free_bits.append(current_range)
                    current_range = None
        if current_range is not None:
            free_bits.append(current_range)

        for msb, lsb in free_bits:
            if msb == lsb:
                result["not_used"].append(f"{msb}")
            else:
                result["not_used"].append(f"{msb}:{lsb}")

    return result


def print_pretty_parsed(parsed_list):
    for parsed in parsed_list:
        print("=" * 60)
        print("PARSING RESULT")
        print("=" * 60)
        print(f"Full string: {parsed['full']}")

        target_info = f"{parsed['target']}"
        if parsed['target_range']:
            target_info += f" [range: {parsed['target_range']}]"
        target_info += f" [width: {parsed['target_width']}]"
        print(f"Target: {target_info}")

        source_info = f"{parsed['source']}"
        if parsed['source_range']:
            source_info += f" [range: {parsed['source_range']}]"
        source_info += f" [width: {parsed['source_width']}]"
        print(f"Source: {source_info}")

        if parsed['condition']:
            print(f"Condition: {parsed['condition']}")
        if parsed['default']:
            print(f"Default: {parsed['default']}")
        if parsed['comment']:
            print(f"Comment: {parsed['comment']}")
        if parsed['not_used']:
            print(f"Not used bits: {', '.join(parsed['not_used'])}")
        print("=" * 60)
        print()


def generate_markdown_table(parsed_results, source_port, total_width=16):
    lines = []
    lines.append(f"| {source_port} | name | comment |")
    lines.append("|-------|---------|---------|")

    range_data = {}
    for item in parsed_results:
        if item["source"] == source_port:
            rng = item["source_range"] if item["source_range"] else "0"
            target_name = item["target"]
            target_range = item["target_range"]
            target_str = f"{target_name}[{target_range}]" if target_range else target_name
            comment = item.get("comment", "")
            range_data[rng] = (target_str, comment)

    occupied = set()
    for item in parsed_results:
        if item["source"] == source_port:
            rng = item["source_range"] if item["source_range"] else "0"
            if ':' in rng:
                msb, lsb = rng.split(':')
                for bit in range(int(lsb), int(msb) + 1):
                    occupied.add(bit)
            else:
                occupied.add(int(rng))

    free_ranges = []
    current_range = None
    for bit in range(total_width - 1, -1, -1):
        if bit not in occupied:
            if current_range is None:
                current_range = [bit, bit]
            else:
                current_range[1] = bit
        else:
            if current_range is not None:
                free_ranges.append(current_range)
                current_range = None
    if current_range is not None:
        free_ranges.append(current_range)

    table_rows = []
    for rng, (name, comment) in range_data.items():
        table_rows.append((rng, name, comment, False))
    for msb, lsb in free_ranges:
        if msb == lsb:
            table_rows.append((str(msb), "-", "", True))
        else:
            table_rows.append((f"{msb}:{lsb}", "-", "", True))

    def sort_key(row):
        rng = row[0]
        if ':' in rng:
            msb, lsb = rng.split(':')
            return int(msb)
        return int(rng)

    table_rows.sort(key=sort_key, reverse=True)
    for rng, name, comment, is_not_used in table_rows:
        lines.append(f"| {rng} | {name} | {comment} |")

    return "\n".join(lines)


def save_markdown_table(table, port_filter, file_path):
    dir_name = os.path.dirname(file_path)
    if dir_name:
        output_file = os.path.join(dir_name, f"{port_filter}.md")
    else:
        output_file = f"{port_filter}.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(table)
    print(f"Table saved to: {output_file}")

def load_config(config_file="config.json"):
    with open(config_file, 'r') as f:
        return json.load(f)

def main():
    config = load_config("./config.json")
    file_src = config["file_src"]
    configs = config["configs"]

    for cfg in configs:
        port_filter = cfg["port_filter"]
        total_width = cfg["total_width"]

        print(f"\n=== Processing {port_filter} (width {total_width}) ===")

        lines = read_file_lines(file_src)
        filtered = filter_assigns_by_port(lines, port_filter)

        parsed_results = []
        for line in filtered:
            parsed = parse_assign_line(line, total_width, port_filter)
            if parsed:
                parsed_results.append(parsed)

        print_pretty_parsed(parsed_results)
        print(json.dumps(parsed_results, indent=2, ensure_ascii=False))

        print("\n=== Markdown Table ===")
        table = generate_markdown_table(parsed_results, port_filter, total_width)
        print(table)
        save_markdown_table(table, port_filter, file_src)

if __name__ == "__main__":
    main()