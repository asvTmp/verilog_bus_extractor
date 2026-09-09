# parcer_port.py - общие функции

import sys
import json
import os
import re


def read_file_lines(file_path):
    with open(file_path, 'r') as f:
        return f.readlines()


def load_config(config_file="config.json"):
    with open(config_file, 'r') as f:
        return json.load(f)


def print_pretty_parsed(parsed_list, mode="source"):
    for parsed in parsed_list:
        print("=" * 60)
        if mode == "source":
            print("PARSING RESULT (SOURCE)")
        else:
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


def generate_markdown_table_bitwise(parsed_results, port_filter, total_width=16, mode="source"):
    lines = []
    if mode == "source":
        lines.append(f"| {port_filter} | name | comment |")
        lines.append("|-------|---------|---------|")
    else:
        lines.append(f"| {port_filter} | source | comment |")
        lines.append("|-------|---------|---------|")

    bit_map = {}
    for item in parsed_results:
        if mode == "source":
            if item["source"] == port_filter:
                for bit, name in item["bits"].items():
                    if name != "-":
                        bit_map[bit] = (name, item["comment"])
        else:
            if item["target"] == port_filter:
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


def save_markdown_table(table, port_filter, file_path, mode="source"):
    dir_name = os.path.dirname(file_path)
    if mode == "source":
        filename = f"{port_filter}_src.md"
    else:
        filename = f"{port_filter}_dest.md"

    if dir_name:
        output_file = os.path.join(dir_name, filename)
    else:
        output_file = filename

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(table)
    print(f"Table saved to: {output_file}")
