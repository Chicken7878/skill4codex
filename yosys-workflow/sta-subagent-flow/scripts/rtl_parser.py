import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from sta_types import ClassifiedPorts, Port, StaFlowError


CLK_CANDIDATES = ("clk", "clock", "aclk")
RESET_TOKENS = ("reset", "rst", "resetn", "rst_n", "aresetn", "areset")
TEST_TOKENS = ("scan", "test", "mbist", "bist", "jtag", "dbg", "debug")


def strip_comments(text: str) -> str:
    text = re.sub(r"//.*?$", "", text, flags=re.MULTILINE)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return text


def rtl_files(rtl_dir: Path) -> List[Path]:
    files = sorted(
        path
        for pattern in ("*.v", "*.sv", "*.vh", "*.svh")
        for path in rtl_dir.rglob(pattern)
        if path.is_file()
    )
    if not files:
        raise StaFlowError("rtl_discovery", f"No RTL files found under {rtl_dir}")
    return files


def find_module_source(files: Sequence[Path], top: str) -> str:
    pattern = re.compile(rf"\bmodule\s+{re.escape(top)}\b", re.MULTILINE)
    for path in files:
        text = strip_comments(path.read_text())
        if pattern.search(text):
            return text
    raise StaFlowError("rtl_discovery", f"Top module '{top}' not found in RTL files")


def extract_module_text(source: str, top: str) -> str:
    module_re = re.compile(
        rf"module\s+{re.escape(top)}\b.*?endmodule",
        flags=re.DOTALL | re.MULTILINE,
    )
    match = module_re.search(source)
    if not match:
        raise StaFlowError(
            "rtl_parse", f"Unable to isolate full module body for '{top}'"
        )
    return match.group(0)


def normalize_width_tokens(tokens: str) -> Optional[str]:
    match = re.search(r"(\[[^\]]+\])", tokens or "")
    return match.group(1) if match else None


def parse_port_header_names(module_text: str, top: str) -> List[str]:
    header_re = re.compile(
        rf"module\s+{re.escape(top)}\s*(?:#\s*\(.*?\)\s*)?\((.*?)\)\s*;",
        flags=re.DOTALL | re.MULTILINE,
    )
    match = header_re.search(module_text)
    if not match:
        raise StaFlowError("rtl_parse", f"Unable to parse module header for '{top}'")
    header = " ".join(match.group(1).split())
    names = [item.strip() for item in header.split(",") if item.strip()]
    if not names:
        raise StaFlowError("rtl_parse", f"No port names found in header for '{top}'")

    cleaned: List[str] = []
    for item in names:
        item = re.sub(r"^(input|output|inout)\b", "", item).strip()
        item = re.sub(r"\b(?:wire|reg|logic|signed|unsigned)\b", "", item).strip()
        item = re.sub(r"\[[^\]]+\]", "", item).strip()
        if item:
            cleaned.append(item)
    return cleaned


def parse_ansi_ports(module_text: str, top: str) -> List[Port]:
    header_re = re.compile(
        rf"module\s+{re.escape(top)}\s*(?:#\s*\(.*?\)\s*)?\((.*?)\)\s*;",
        flags=re.DOTALL | re.MULTILINE,
    )
    match = header_re.search(module_text)
    if not match:
        raise StaFlowError("rtl_parse", f"Unable to parse header for '{top}'")

    header = match.group(1)
    ports: List[Port] = []
    current_direction: Optional[str] = None
    current_width: Optional[str] = None
    token_re = re.compile(
        r"^(?:(input|output|inout)\b\s*)?"
        r"((?:(?:wire|reg|logic|signed|unsigned)\s+|\[[^\]]+\]\s*)*)"
        r"([A-Za-z_]\w*)$",
        flags=re.DOTALL,
    )

    for raw_token in header.split(","):
        token = " ".join(raw_token.split())
        if not token:
            continue
        match_token = token_re.match(token)
        if not match_token:
            raise StaFlowError(
                "rtl_parse", f"Unsupported ANSI port fragment in '{top}': '{token}'"
            )

        direction = match_token.group(1) or current_direction
        qualifiers = match_token.group(2) or ""
        width = normalize_width_tokens(qualifiers)
        if match_token.group(1):
            current_direction = match_token.group(1)
            current_width = width
        elif width:
            current_width = width

        if not direction:
            raise StaFlowError(
                "rtl_parse", f"Unable to infer direction for port fragment: '{token}'"
            )
        ports.append(
            Port(direction=direction, name=match_token.group(3), width=current_width)
        )
    return ports


def parse_nonansi_ports(module_text: str, top: str) -> List[Port]:
    header_names = parse_port_header_names(module_text, top)
    decl_re = re.compile(
        r"\b(input|output|inout)\b\s*"
        r"((?:(?:wire|reg|logic|signed|unsigned)\s+|\[[^\]]+\]\s*)*)"
        r"([^;]+);",
        flags=re.MULTILINE,
    )
    decl_map: Dict[str, Port] = {}
    for match in decl_re.finditer(module_text):
        direction = match.group(1)
        qualifiers = match.group(2) or ""
        width = normalize_width_tokens(qualifiers)
        names = [part.strip() for part in match.group(3).split(",") if part.strip()]
        for name in names:
            cleaned = re.sub(r"\s*=.*$", "", name).strip()
            cleaned = re.sub(r"\[[^\]]+\]", "", cleaned).strip()
            if cleaned:
                decl_map[cleaned] = Port(direction=direction, name=cleaned, width=width)

    ports = [decl_map[name] for name in header_names if name in decl_map]
    if len(ports) != len(header_names):
        missing = [name for name in header_names if name not in decl_map]
        raise StaFlowError(
            "rtl_parse",
            f"Non-ANSI port declarations incomplete for '{top}', missing: {', '.join(missing)}",
        )
    return ports


def parse_ports(module_text: str, top: str) -> List[Port]:
    header_re = re.compile(
        rf"module\s+{re.escape(top)}\s*(?:#\s*\(.*?\)\s*)?\((.*?)\)\s*;",
        flags=re.DOTALL | re.MULTILINE,
    )
    match = header_re.search(module_text)
    if not match:
        raise StaFlowError("rtl_parse", f"Unable to parse module header for '{top}'")
    raw_header = match.group(1)
    if re.search(r"\b(input|output|inout)\b", raw_header):
        return parse_ansi_ports(module_text, top)
    return parse_nonansi_ports(module_text, top)


def choose_clock_port(ports: Sequence[Port], override: Optional[str]) -> str:
    inputs = [port.name for port in ports if port.direction == "input"]
    if override:
        if override not in inputs:
            raise StaFlowError(
                "constraint_inference",
                f"Clock port '{override}' is not a top-level input",
            )
        return override

    lowered = {name.lower(): name for name in inputs}
    for candidate in CLK_CANDIDATES:
        if candidate in lowered:
            return lowered[candidate]

    suffix_matches = [name for name in inputs if name.lower().endswith("_clk")]
    if len(suffix_matches) == 1:
        return suffix_matches[0]

    contains_matches = [name for name in inputs if "clk" in name.lower()]
    if len(contains_matches) == 1:
        return contains_matches[0]
    if len(contains_matches) > 1:
        raise StaFlowError(
            "constraint_inference",
            f"Multiple plausible clock ports found: {', '.join(contains_matches)}",
        )

    raise StaFlowError(
        "constraint_inference", "Unable to infer clock port. Use --clock-port."
    )


def port_is_reset(name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in RESET_TOKENS)


def port_is_test(name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in TEST_TOKENS)


def classify_ports(
    ports: Sequence[Port],
    clock_port: str,
    input_exclude: Sequence[str],
    output_exclude: Sequence[str],
    async_inputs: Sequence[str],
) -> ClassifiedPorts:
    input_exclude_set = set(input_exclude)
    output_exclude_set = set(output_exclude)
    async_set = set(async_inputs)

    port_map = {port.name: port for port in ports}
    unknown = [
        name
        for name in sorted(input_exclude_set | output_exclude_set | async_set)
        if name not in port_map
    ]
    if unknown:
        raise StaFlowError(
            "constraint_inference",
            f"Override ports not found in top interface: {', '.join(unknown)}",
        )

    resets: List[Port] = []
    test_inputs: List[Port] = []
    async_ports: List[Port] = []
    data_inputs: List[Port] = []
    data_outputs: List[Port] = []
    unconstrained_outputs: List[Port] = []

    for port in ports:
        if port.name == clock_port:
            continue
        if port.direction == "input":
            if port.name in async_set:
                async_ports.append(port)
            elif port_is_reset(port.name):
                resets.append(port)
            elif port_is_test(port.name):
                test_inputs.append(port)
            elif port.name in input_exclude_set:
                async_ports.append(port)
            else:
                data_inputs.append(port)
        elif port.direction == "output":
            if port.name in output_exclude_set:
                unconstrained_outputs.append(port)
            else:
                data_outputs.append(port)

    return ClassifiedPorts(
        clock=clock_port,
        resets=resets,
        test_inputs=test_inputs,
        async_inputs=async_ports,
        data_inputs=data_inputs,
        data_outputs=data_outputs,
        unconstrained_outputs=unconstrained_outputs,
    )
