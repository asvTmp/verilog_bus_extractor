import sys
import json
import os
import re


def read_file_lines(file_path):
    with open(file_path, 'r') as f:
        return f.readlines()


def load_config(config_file="data/config.json"):
    with open(config_file, 'r') as f:
        return json.load(f)


def filter_assigns_by_destination(lines, dest_name):
    result = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("assign"):
            continue
        if "=" in stripped:
            parts = stripped.split("=", 1)
            left_part = parts[0].strip()
            if dest_name in left_part:
                result.append(line)
    return result


def parse_dest_line_bitwise(line, total_width=16, dest_filter=None):
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
        "bits": {}
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
            if dest_filter and dest_filter in elem:
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

    for bit in range(total_width):
        result["bits"][bit] = "-"

    if result["target"] == dest_filter and result["target_range"]:
        rng = result["target_range"]
        if ':' in rng:
            msb, lsb = rng.split(':')
            msb, lsb = int(msb), int(lsb)
            if result["source_range"]:
                s_msb, s_lsb = result["source_range"].split(':')
                s_msb, s_lsb = int(s_msb), int(s_lsb)
                for i in range(abs(msb - lsb) + 1):
                    dest_bit = lsb + i if lsb <= msb else msb + i
                    src_bit = s_lsb + i if s_lsb <= s_msb else s_msb + i
                    if 0 <= dest_bit < total_width:
                        result["bits"][dest_bit] = f"{result['source']}[{src_bit}]"
            else:
                bit = int(rng) if ':' not in rng else lsb
                if 0 <= bit < total_width:
                    result["bits"][bit] = result["source"]
        else:
            bit = int(rng)
            if 0 <= bit < total_width:
                result["bits"][bit] = result["source"]

    return result


def print_pretty_parsed(parsed_list):
    for parsed in parsed_list:
        print("=" * 60)
        print("PARSING RESULT (DESTINATION)")
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
        print("=" * 60)
        print()


def generate_markdown_table_bitwise(parsed_results, dest_filter, total_width=16):
    lines = []
    lines.append(f"| {dest_filter} | source | comment |")
    lines.append("|-------|---------|---------|")

    bit_map = {}
    for item in parsed_results:
        if item["target"] == dest_filter:
            for bit, name in item["bits"].items():
                if name != "-":
                    bit_map[bit] = (name, item["comment"])

    for bit in range(total_width - 1, -1, -1):
        if bit in bit_map:
            name, comment = bit_map[bit]
            lines.append(f"| {bit} | {name} | {comment} |")
        else:
            lines.append(f"| {bit} | - | |")

    return "\n".join(lines)


def save_markdown_table(table, dest_filter, file_path):
    dir_name = os.path.dirname(file_path)
    if dir_name:
        output_file = os.path.join(dir_name, f"{dest_filter}_dest.md")
    else:
        output_file = f"{dest_filter}_dest.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(table)
    print(f"Table saved to: {output_file}")


def process_destination(lines, dest_filter, total_width, file_src):
    filtered = filter_assigns_by_destination(lines, dest_filter)

    parsed_results = []
    for line in filtered:
        parsed = parse_dest_line_bitwise(line, total_width, dest_filter)
        if parsed:
            parsed_results.append(parsed)

    print_pretty_parsed(parsed_results)
    print(json.dumps(parsed_results, indent=2, ensure_ascii=False))

    print("\n=== Markdown Table (Destination) ===")
    table = generate_markdown_table_bitwise(parsed_results, dest_filter, total_width)
    print(table)
    save_markdown_table(table, dest_filter, file_src)

    return parsed_results


def main():
    config = load_config("data/config.json")
    file_src = config["file_src"]
    configs = config["configs"]

    lines = read_file_lines(file_src)

    for cfg in configs:
        dest_filter = cfg["port_filter"]  # используем тот же порт, но смотрим на destination
        total_width = cfg["total_width"]

        print(f"\n=== Processing DESTINATION {dest_filter} (width {total_width}) ===")
        process_destination(lines, dest_filter, total_width, file_src)


if __name__ == "__main__":
    main()