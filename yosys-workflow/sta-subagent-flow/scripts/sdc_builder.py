import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from sta_types import ClassifiedPorts, Port, StaFlowError


MAKEFILE_TEMPLATE = """FLOW_HOME ?= {flow_home}
DESIGN_HOME := $(CURDIR)
DESIGN ?= {design}
RTL_DIR ?= $(DESIGN_HOME)/rtl
SDC_FILE ?= $(DESIGN_HOME)/constraint/default.sdc
CLK_FREQ_MHZ ?= 500
RESULT_DIR ?= $(DESIGN_HOME)/result/$(DESIGN)-$(CLK_FREQ_MHZ)MHz

include $(FLOW_HOME)/Makefile
"""


def run_cmd(
    cmd: Sequence[str],
    cwd: Path,
    check: bool = True,
    capture: bool = True,
    env: Optional[Dict[str, str]] = None,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        check=check,
        text=True,
        capture_output=capture,
        env=env,
    )


def read_flow_home_from_makefile(makefile_path: Path) -> Optional[str]:
    if not makefile_path.exists():
        return None
    text = makefile_path.read_text()
    match = re.search(r"^\s*FLOW_HOME\s*[:?]?=\s*(.+?)\s*$", text, flags=re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip()


def infer_flow_home() -> Optional[str]:
    env_flow_home = os.environ.get("FLOW_HOME")
    if env_flow_home:
        return env_flow_home
    skill_repo_makefile = Path(__file__).resolve().parents[2] / "Makefile"
    return read_flow_home_from_makefile(skill_repo_makefile)


def ensure_makefile(design_home: Path, top: str) -> Tuple[Path, bool]:
    makefile_path = design_home / "Makefile"
    if makefile_path.exists():
        return makefile_path, False

    flow_home = infer_flow_home()
    if not flow_home:
        raise StaFlowError(
            "make_setup",
            "Makefile is missing and FLOW_HOME could not be inferred. Set FLOW_HOME or create a project Makefile first.",
        )

    makefile_path.write_text(
        MAKEFILE_TEMPLATE.format(flow_home=flow_home, design=top)
    )
    return makefile_path, True


def parse_make_vars(
    design_home: Path, env: Optional[Dict[str, str]] = None
) -> Dict[str, str]:
    vars_map: Dict[str, str] = {}

    try:
        result = run_cmd(["make", "print-vars"], cwd=design_home, env=env)
        for line in result.stdout.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            vars_map[key.strip()] = value.strip()
    except subprocess.CalledProcessError:
        vars_map = {}

    required = ("RESULT_DIR", "SDC_FILE")
    if all(key in vars_map for key in required):
        return vars_map

    try:
        result = run_cmd(["make", "-pn"], cwd=design_home, env=env)
    except subprocess.CalledProcessError as exc:
        raise StaFlowError(
            "make_setup",
            f"`make print-vars` and `make -pn` both failed in {design_home}: {(exc.stderr or exc.stdout).strip()}",
        ) from exc

    vars_map = {}
    pattern = re.compile(r"^([A-Z_][A-Z0-9_]*)\s*(?::|[+?])?=\s*(.*)$")
    for line in result.stdout.splitlines():
        match = pattern.match(line)
        if not match:
            continue
        key, value = match.groups()
        vars_map[key.strip()] = value.strip()
    required = ("RESULT_DIR", "SDC_FILE")
    missing = [key for key in required if key not in vars_map]
    if missing:
        raise StaFlowError(
            "make_setup",
            f"Unable to resolve required make variables: {', '.join(missing)}",
        )
    return vars_map


def infer_clock_freq(clock_freq_mhz: Optional[float], make_vars: Dict[str, str]) -> float:
    if clock_freq_mhz is not None:
        return clock_freq_mhz
    if "CLK_FREQ_MHZ" in os.environ:
        return float(os.environ["CLK_FREQ_MHZ"])
    result_dir = make_vars.get("RESULT_DIR", "")
    match = re.search(r"-([0-9.]+)MHz/?$", result_dir)
    if match:
        return float(match.group(1))
    return 500.0


def expand_port_bits(port: Port) -> List[str]:
    if not port.width:
        return [port.name]
    match = re.match(r"\[\s*(\d+)\s*:\s*(\d+)\s*\]", port.width)
    if not match:
        return [port.name]
    msb = int(match.group(1))
    lsb = int(match.group(2))
    step = 1 if lsb <= msb else -1
    return [f"{port.name}_{idx}_" for idx in range(lsb, msb + step, step)]


def expand_port_list(ports: Sequence[Port]) -> List[str]:
    expanded: List[str] = []
    for port in ports:
        expanded.extend(expand_port_bits(port))
    return expanded


def add_get_ports_group(lines: List[str], var_name: str, names: Sequence[str]) -> None:
    if names:
        lines.append(f"set {var_name} [get_ports {{{' '.join(names)}}}]")


def write_sdc(
    sdc_path: Path,
    classified: ClassifiedPorts,
    false_path_from: Sequence[str],
    clock_freq_mhz: float,
    io_delay_ratio: float,
) -> Dict[str, object]:
    period_ns = 1000.0 / clock_freq_mhz
    io_delay_ns = period_ns * io_delay_ratio

    reset_bits = expand_port_list(classified.resets)
    test_bits = expand_port_list(classified.test_inputs)
    async_bits = expand_port_list(classified.async_inputs)
    data_input_bits = expand_port_list(classified.data_inputs)
    data_output_bits = expand_port_list(classified.data_outputs)

    lines = [
        "# Auto-generated by run_sta_flow.py",
        f"set CLK_PORT_NAME {classified.clock}",
        "if {[info exists env(CLK_PORT_NAME)]} {",
        "  set CLK_PORT_NAME $::env(CLK_PORT_NAME)",
        "}",
        f"set CLK_FREQ_MHZ {clock_freq_mhz:g}",
        "if {[info exists env(CLK_FREQ_MHZ)]} {",
        "  set CLK_FREQ_MHZ $::env(CLK_FREQ_MHZ)",
        "}",
        f"set clk_io_pct {io_delay_ratio:g}",
        "set clk_port [get_ports $CLK_PORT_NAME]",
        "create_clock -name core_clock -period [expr 1000.0 / $CLK_FREQ_MHZ] $clk_port",
        "set clk_period [expr 1000.0 / $CLK_FREQ_MHZ]",
        f"set io_delay_ns {io_delay_ns:.3f}",
        "",
    ]

    add_get_ports_group(lines, "reset_ports", reset_bits)
    add_get_ports_group(lines, "test_input_ports", test_bits)
    add_get_ports_group(lines, "async_input_ports", async_bits)
    add_get_ports_group(lines, "data_input_ports", data_input_bits)
    add_get_ports_group(lines, "data_output_ports", data_output_bits)
    add_get_ports_group(lines, "extra_false_path_from", false_path_from)
    if lines[-1] != "":
        lines.append("")

    if reset_bits:
        lines.append("set_false_path -from $reset_ports")
    if test_bits:
        lines.append("set_false_path -from $test_input_ports")
    if async_bits:
        lines.append("set_false_path -from $async_input_ports")
    if false_path_from:
        lines.append("set_false_path -from $extra_false_path_from")
    if reset_bits or test_bits or async_bits or false_path_from:
        lines.append("")

    if data_input_bits:
        lines.append("set_input_delay $io_delay_ns -clock core_clock $data_input_ports")
        lines.append("set_input_transition [expr $clk_period * 0.05] $data_input_ports")
    if data_output_bits:
        lines.append("set_output_delay $io_delay_ns -clock core_clock $data_output_ports")
        lines.append("set_load 0.05 $data_output_ports")
    lines.append("")

    sdc_path.parent.mkdir(parents=True, exist_ok=True)
    sdc_path.write_text("\n".join(lines))

    return {
        "clock_port": classified.clock,
        "reset_ports": [port.name for port in classified.resets],
        "test_inputs": [port.name for port in classified.test_inputs],
        "async_inputs": [port.name for port in classified.async_inputs],
        "data_inputs": [port.name for port in classified.data_inputs],
        "data_outputs": [port.name for port in classified.data_outputs],
        "unconstrained_outputs": [port.name for port in classified.unconstrained_outputs],
        "io_delay_ns": io_delay_ns,
        "period_ns": period_ns,
    }


def run_make_target(
    design_home: Path, target: str, env: Optional[Dict[str, str]] = None
) -> Tuple[int, str, str]:
    proc = subprocess.run(
        ["make", target],
        cwd=str(design_home),
        text=True,
        capture_output=True,
        env=env,
    )
    return proc.returncode, proc.stdout, proc.stderr
