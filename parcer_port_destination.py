# parcer_port_destination.py
import sys
import re
import json
import os
from parcer_port import read_file_lines, load_config


def extract_assign_block(lines, port_name):
    """Извлекает строки assign-блока для заданного порта."""
    start_pattern = re.compile(
        r'^\s*assign\s+' + re.escape(port_name) + r'\s*=\s*\{'
    )
    start_idx = None
    for i, line in enumerate(lines):
        if start_pattern.search(line):
            start_idx = i
            break
    if start_idx is None:
        return None

    block_lines = []
    depth = 0
    in_block = False
    for i in range(start_idx, len(lines)):
        line = lines[i].rstrip('\n')
        if not in_block:
            brace_pos = line.find('{')
            if brace_pos == -1:
                continue
            depth = 1
            rest = line[brace_pos + 1:]
            for ch in rest:
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        block_lines.append(line)
                        return block_lines
            block_lines.append(line)
            in_block = True
        else:
            for ch in line:
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        block_lines.append(line)
                        return block_lines
            block_lines.append(line)
    return block_lines if depth == 0 else None


def print_assign_block(block):
    """Выводит содержимое assign-блока."""
    if block is None:
        print("Блок не найден.")
        return
    for line in block:
        print(line)


def parse_signal_declarations(lines):
    """Собирает словарь ширин сигналов из объявлений."""
    signal_widths = {}
    pattern = re.compile(
        r'^\s*(?:input|output|inout|logic|wire|reg)\s*'
        r'(?:\[(\d+)\s*:\s*(\d+)\])?\s*'
        r'([a-zA-Z_]\w*)\s*;'
    )
    for line in lines:
        match = pattern.search(line)
        if match:
            msb = match.group(1)
            lsb = match.group(2)
            name = match.group(3)
            if msb is not None and lsb is not None:
                width = abs(int(msb) - int(lsb)) + 1
            else:
                width = 1
            signal_widths[name] = width
    return signal_widths


def parse_assign_block_elements(block_lines):
    """
    Разбирает строки assign-блока на отдельные элементы конкатенации.
    Каждый элемент – словарь с ключами 'expr' и 'comment'.
    """
    elements = []
    if not block_lines:
        return elements

    first_brace_line = last_brace_line = None
    for i, line in enumerate(block_lines):
        if '{' in line and first_brace_line is None:
            first_brace_line = i
        if '}' in line:
            last_brace_line = i
    if first_brace_line is None or last_brace_line is None:
        return elements

    for i, line in enumerate(block_lines):
        if i == first_brace_line:
            pos = line.find('{')
            line = line[pos+1:]
        elif i == last_brace_line:
            pos = line.find('}')
            line = line[:pos]

        line = line.strip()
        if not line:
            continue

        if '//' in line:
            code_part, _, comment = line.partition('//')
            comment = comment.strip()
        else:
            code_part = line
            comment = None

        code_part = code_part.strip()
        if not code_part:
            continue

        parts = [p.strip() for p in code_part.split(',') if p.strip()]
        for j, part in enumerate(parts):
            current_comment = comment if (j == len(parts)-1 and comment is not None) else None
            elements.append({"expr": part, "comment": current_comment})

    return elements


def build_mapping(elements, signal_widths):
    """
    Строит список mapping для каждого бита выходного порта.
    Возвращает (total_width, mapping).
    mapping – список словарей: {'bit': int, 'signal': str, 'comment': str}
    """
    temp_bits = []
    for elem in elements:
        expr = elem["expr"].strip()
        comment = elem["comment"] if elem["comment"] else "-"

        expr_clean = re.sub(r'\s+', '', expr)

        if "'" in expr_clean:
            m = re.match(r'(\d+)\s*\'', expr_clean)
            if m:
                width = int(m.group(1))
                for _ in range(width):
                    temp_bits.append(("0", "-"))
            else:
                temp_bits.append(("0", "-"))
            continue

        m = re.match(r'([a-zA-Z_]\w*)\[(\d+)(?::(\d+))?\]', expr_clean)
        if m:
            name = m.group(1)
            msb = int(m.group(2))
            if m.group(3) is not None:
                lsb = int(m.group(3))
                if msb >= lsb:
                    bit_indices = list(range(msb, lsb - 1, -1))
                else:
                    bit_indices = list(range(msb, lsb + 1))
            else:
                bit_indices = [msb]
            for b in bit_indices:
                temp_bits.append((f"{name}[{b}]", comment))
            continue

        name = expr_clean
        if name in signal_widths:
            width = signal_widths[name]
        else:
            width = 1
        for _ in range(width):
            temp_bits.append((name, comment))

    total_width = len(temp_bits)
    mapping = []
    for idx, (signal, comment) in enumerate(temp_bits):
        bit = total_width - 1 - idx
        mapping.append({
            "bit": bit,
            "signal": signal,
            "comment": comment
        })

    return total_width, mapping


def json_to_markdown_table(data):
    """
    Преобразует словарь с данными порта в markdown-таблицу и выводит её.
    """
    port = data.get("port", "")
    width = data.get("width", "")
    mapping = data.get("mapping", [])

    print(f"**Port:** {port}  ")
    print(f"**Width:** {width}  ")
    print()

    print("| Bit | Signal | Comment |")
    print("|-----|--------|---------|")

    for item in mapping:
        bit = item.get("bit", "")
        signal = item.get("signal", "")
        comment = item.get("comment", "")
        signal = str(signal).replace("|", "\\|")
        comment = str(comment).replace("|", "\\|")
        print(f"| {bit} | {signal} | {comment} |")


def save_markdown_to_file(data, source_file_path):
    """
    Сохраняет markdown таблицу в файл с именем порта (_dst.md) в каталоге исходного файла.
    """
    port = data.get("port", "unknown_port")
    width = data.get("width", "")
    mapping = data.get("mapping", [])

    filename = f"{port}_dst.md"
    directory = os.path.dirname(source_file_path)
    if not directory:
        directory = "."
    filepath = os.path.join(directory, filename)

    lines = []
    lines.append(f"**Port:** {port}  ")
    lines.append(f"**Width:** {width}  ")
    lines.append("")
    lines.append("| Bit | Signal | Comment |")
    lines.append("|-----|--------|---------|")

    for item in mapping:
        bit = item.get("bit", "")
        signal = item.get("signal", "")
        comment = item.get("comment", "")
        signal = str(signal).replace("|", "\\|")
        comment = str(comment).replace("|", "\\|")
        lines.append(f"| {bit} | {signal} | {comment} |")

    markdown_text = "\n".join(lines)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(markdown_text)

    print(f"Markdown сохранён в {filepath}")


def process_port_destination(lines, port_filter, total_width_cfg, file_src):
    """
    Обрабатывает один порт-назначение: извлекает assign-блок, парсит его,
    строит маппинг, выводит JSON, markdown и сохраняет markdown в файл.
    """
    print(f"\n=== Processing DESTINATION {port_filter} ===")

    block = extract_assign_block(lines, port_filter)
    # print_assign_block(block)

    if block is None:
        print(f"Блок assign для порта '{port_filter}' не найден.")
        return

    elements = parse_assign_block_elements(block)
    if not elements:
        print("Не удалось разобрать элементы блока.")
        return

    # Получаем словарь ширин сигналов (можно было бы кэшировать, но для простоты вычисляем здесь)
    signal_widths = parse_signal_declarations(lines)

    actual_width, mapping = build_mapping(elements, signal_widths)

    output = {
        "port": port_filter,
        "width": actual_width,
        "mapping": mapping
    }

    # print(json.dumps(output, indent=2))

    json_to_markdown_table(output)
    save_markdown_to_file(output, file_src)


def main():
    config = load_config("config.json")
    file_src = config.get("file_src")
    if not file_src:
        print("Ошибка: в config.json отсутствует ключ 'file_src'", file=sys.stderr)
        sys.exit(1)

    configs = config.get("configs", [])
    if not configs:
        print("Ошибка: в config.json отсутствует или пуст список 'configs'", file=sys.stderr)
        sys.exit(1)

    try:
        lines = read_file_lines(file_src)
    except FileNotFoundError:
        print(f"Ошибка: файл '{file_src}' не найден", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Ошибка при чтении файла: {e}", file=sys.stderr)
        sys.exit(1)

    for cfg in configs:
        port_filter = cfg.get("port_filter")
        total_width_cfg = cfg.get("total_width")
        if not port_filter:
            print("Пропуск элемента конфигурации без 'port_filter'", file=sys.stderr)
            continue
        process_port_destination(lines, port_filter, total_width_cfg, file_src)


if __name__ == "__main__":
    main()