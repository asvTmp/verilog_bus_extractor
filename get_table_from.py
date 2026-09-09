import os

from parcer_port import read_file_lines, generate_markdown_table_bitwise, save_markdown_table, load_config
from parcer_port_destination import extract_assign_block,parse_assign_block_elements, parse_signal_declarations, build_mapping, json_to_markdown_table, save_markdown_to_file
from parcer_port_source import  filter_assigns_by_port, parse_assign_line_bitwise

def processing_main(port_filter_1, port_filter_2, total_width, file_src, file_dst):
    directory = os.path.dirname(file_dst)
    if not os.path.exists(directory):
        os.makedirs(directory)
    lines = read_file_lines(file_src)
    block = extract_assign_block(lines, port_filter_1)
    elements = parse_assign_block_elements(block)
    signal_widths = parse_signal_declarations(lines)
    actual_width, mapping = build_mapping(elements, signal_widths)
    output = {
        "port": port_filter_1,
        "width": actual_width,
        "mapping": mapping
    }
    save_markdown_to_file(output, file_dst)
    filtered = filter_assigns_by_port(lines, port_filter_2)
    parsed_results = []
    for line in filtered:
        parsed = parse_assign_line_bitwise(line, total_width, port_filter_2)
        if parsed:
            parsed_results.append(parsed)
    table = generate_markdown_table_bitwise(parsed_results, port_filter_2, total_width, mode="source")
    save_markdown_table(table, port_filter_2, file_dst, mode="source")


def main():

    config = load_config("./data/config_p.json")
    for cfg in config:
        param = config.get(cfg)
        file_src =          param.get("file_src")
        file_dst =          param.get("file_dst")
        port_filter_1 =     param.get("port_filter_1")
        port_filter_2 =     param.get("port_filter_2")
        total_width =       param.get("total_width")
        processing_main(
            file_src =       file_src,
            file_dst =       file_dst,
            port_filter_1 =  port_filter_1,
            port_filter_2 =  port_filter_2,
            total_width =    total_width
        )

if __name__ == "__main__":
    main()