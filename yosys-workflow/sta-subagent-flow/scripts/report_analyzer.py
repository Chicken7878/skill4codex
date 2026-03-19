import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence


def parse_pipe_table_rows(text: str) -> List[List[str]]:
    rows = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if cells and any(cell for cell in cells):
            rows.append(cells)
    return rows


def safe_float(value: str) -> Optional[float]:
    if value in ("", "NA", "None"):
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", value)
    return float(match.group(0)) if match else None


def parse_main_rpt(rpt_path: Path) -> Dict[str, object]:
    text = rpt_path.read_text()
    rows = parse_pipe_table_rows(text)
    path_rows = []
    tns_rows = []
    for cells in rows:
        if len(cells) == 8 and cells[0] != "Endpoint":
            path_rows.append(cells)
        elif len(cells) == 3 and cells[0] != "Clock":
            tns_rows.append(cells)

    max_paths = [row for row in path_rows if row[2] == "max"]
    min_paths = [row for row in path_rows if row[2] == "min"]

    def worst_path(rows_subset: List[List[str]]) -> Optional[Dict[str, object]]:
        if not rows_subset:
            return None
        worst = min(
            rows_subset,
            key=lambda row: safe_float(row[6]) if safe_float(row[6]) is not None else float("inf"),
        )
        return {
            "endpoint": worst[0],
            "clock_group": worst[1],
            "delay_type": worst[2],
            "path_delay": safe_float(worst[3]),
            "path_required": safe_float(worst[4]),
            "slack": safe_float(worst[6]),
            "freq_mhz": safe_float(worst[7]),
        }

    return {
        "setup_wns": min(
            (safe_float(row[6]) for row in max_paths if safe_float(row[6]) is not None),
            default=None,
        ),
        "hold_wns": min(
            (safe_float(row[6]) for row in min_paths if safe_float(row[6]) is not None),
            default=None,
        ),
        "setup_tns": next((safe_float(row[2]) for row in tns_rows if row[1] == "max"), None),
        "hold_tns": next((safe_float(row[2]) for row in tns_rows if row[1] == "min"), None),
        "worst_setup_path": worst_path(max_paths),
        "worst_hold_path": worst_path(min_paths),
    }


def parse_synth_stat(stat_path: Path) -> Dict[str, object]:
    text = stat_path.read_text()
    stats: Dict[str, object] = {}
    patterns = {
        "ports": r"^\s*(\d+)\s+- ports$",
        "port_bits": r"^\s*(\d+)\s+- port bits$",
        "cells": r"^\s*(\d+)\s+[\d.]+\s+cells$",
        "chip_area": r"Chip area for module .*?:\s+([\d.]+)",
        "seq_area": r"of which used for sequential elements:\s+([\d.]+)\s+\(([\d.]+)%\)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text, flags=re.MULTILINE)
        if not match:
            continue
        if key == "seq_area":
            stats["sequential_area"] = float(match.group(1))
            stats["sequential_area_ratio_pct"] = float(match.group(2))
        elif key == "chip_area":
            stats[key] = float(match.group(1))
        else:
            stats[key] = int(match.group(1))
    return stats


def parse_synth_check(check_path: Path) -> Dict[str, object]:
    text = check_path.read_text()
    match = re.search(r"Found and reported\s+(\d+)\s+problems", text)
    return {"problems": int(match.group(1)) if match else None}


def parse_power(power_path: Path) -> Dict[str, object]:
    text = power_path.read_text()
    match = re.search(r"Total Power\s+==\s+([0-9.eE+-]+)\s+W", text)
    return {"total_power_w": float(match.group(1)) if match else None}


def parse_limit_table(path: Path, slack_column: str, value_column: str) -> Dict[str, object]:
    rows = parse_pipe_table_rows(path.read_text())
    if len(rows) < 2:
        return {}
    header = rows[0]
    if slack_column not in header or value_column not in header:
        return {}
    slack_idx = header.index(slack_column)
    value_idx = header.index(value_column)
    data_rows = [row for row in rows[1:] if len(row) > max(slack_idx, value_idx)]
    numeric_rows = [
        row
        for row in data_rows
        if safe_float(row[slack_idx]) is not None or safe_float(row[value_idx]) is not None
    ]
    if not numeric_rows:
        return {}
    worst = min(
        numeric_rows,
        key=lambda row: safe_float(row[slack_idx]) if safe_float(row[slack_idx]) is not None else float("inf"),
    )
    return {"object": worst[0], "value": worst[value_idx], "slack": worst[slack_idx]}


def parse_sta_log(log_path: Path) -> Dict[str, object]:
    text = log_path.read_text()
    unconstrained = sorted(
        set(re.findall(r"The (?:input|output) port ([A-Za-z_]\w*) is not constrained", text))
    )
    return {"unconstrained_ports": unconstrained}


def collect_reports(result_dir: Path, top: str) -> Dict[str, object]:
    report: Dict[str, object] = {"result_dir": str(result_dir)}
    rpt_path = result_dir / f"{top}.rpt"
    if rpt_path.exists():
        report.update(parse_main_rpt(rpt_path))
    stat_path = result_dir / "synth_stat.txt"
    if stat_path.exists():
        report.update(parse_synth_stat(stat_path))
    check_path = result_dir / "synth_check.txt"
    if check_path.exists():
        report.update(parse_synth_check(check_path))
    power_path = result_dir / f"{top}.pwr"
    if power_path.exists():
        report.update(parse_power(power_path))
    sta_log_path = result_dir / "sta.log"
    if sta_log_path.exists():
        report.update(parse_sta_log(sta_log_path))
    trans_path = result_dir / f"{top}.trans"
    if trans_path.exists():
        report["worst_transition"] = parse_limit_table(trans_path, "SlewSlack", "SlewTime")
    cap_path = result_dir / f"{top}.cap"
    if cap_path.exists():
        report["worst_capacitance"] = parse_limit_table(cap_path, "CapacitanceSlack", "Capacitance")
    fanout_path = result_dir / f"{top}.fanout"
    if fanout_path.exists():
        report["worst_fanout"] = parse_limit_table(fanout_path, "FanoutSlack", "Fanout")
    return report


def classify_make_failure(
    make_rc: int, stdout: str, stderr: str, result_dir: Path, top: str
) -> Dict[str, str]:
    merged = "\n".join([stdout, stderr])
    if make_rc == 0:
        return {"stage": "success", "message": "make completed successfully"}
    if "No rule to make target" in merged:
        return {"stage": "make_setup", "message": "Makefile dependency or input file is missing"}
    if "Aborted" in merged or "core dumped" in merged:
        return {"stage": "sta_runtime", "message": "STA engine aborted, likely due to malformed SDC or tool/runtime issue"}
    if "Error" in merged and "yosys" in merged.lower():
        return {"stage": "synthesis", "message": "Synthesis failed before STA"}
    if not (result_dir / f"{top}.netlist.v").exists():
        return {"stage": "synthesis", "message": "Netlist was not generated"}
    if not (result_dir / f"{top}.rpt").exists():
        return {"stage": "sta_runtime", "message": "STA report was not generated"}
    return {"stage": "make_run", "message": "make failed; inspect stdout/stderr tails"}


def build_recommendations(
    report: Dict[str, object], sdc_meta: Dict[str, object]
) -> List[str]:
    recs: List[str] = []
    unconstrained = report.get("unconstrained_ports") or []
    if unconstrained:
        recs.append(
            "存在未约束端口 "
            + ", ".join(unconstrained)
            + "，需要按接口时序意图补 `set_input_delay`/`set_output_delay` 或添加 false path/multicycle。"
        )
    if sdc_meta.get("test_inputs"):
        recs.append(
            "检测到测试类输入 "
            + ", ".join(sdc_meta["test_inputs"])
            + " 被默认设为 false path，签核前需要确认这些端口确实不参与功能模式时序。"
        )
    if sdc_meta.get("async_inputs"):
        recs.append(
            "检测到异步输入 "
            + ", ".join(sdc_meta["async_inputs"])
            + " 被默认设为 false path，后续应按 CDC/async 方案补完整约束。"
        )

    setup_wns = report.get("setup_wns")
    setup_tns = report.get("setup_tns")
    if (isinstance(setup_wns, (int, float)) and setup_wns < 0) or (
        isinstance(setup_tns, (int, float)) and setup_tns < 0
    ):
        recs.append("存在 setup 违例，优先沿最差 setup 路径做 pipeline、逻辑重构、驱动增强或适度下调目标频率。")

    hold_wns = report.get("hold_wns")
    hold_tns = report.get("hold_tns")
    if (isinstance(hold_wns, (int, float)) and hold_wns < 0) or (
        isinstance(hold_tns, (int, float)) and hold_tns < 0
    ):
        recs.append("存在 hold 违例，需要在短路径上增加 delay/buffer，并检查 clock gating 或 min delay 约束是否合理。")

    worst_transition = report.get("worst_transition") or {}
    if safe_float(str(worst_transition.get("slack", ""))) is not None and safe_float(str(worst_transition["slack"])) < 0:
        recs.append(
            f"transition 违例集中在 `{worst_transition.get('object', 'unknown')}`，建议优先检查该驱动链是否需要 buffer 或更高 drive strength。"
        )

    worst_capacitance = report.get("worst_capacitance") or {}
    if safe_float(str(worst_capacitance.get("slack", ""))) is not None and safe_float(str(worst_capacitance["slack"])) < 0:
        recs.append(
            f"capacitance 违例集中在 `{worst_capacitance.get('object', 'unknown')}`，建议降低负载、拆分接收端或局部重构网络。"
        )

    worst_fanout = report.get("worst_fanout") or {}
    fanout_slack = safe_float(str(worst_fanout.get("slack", "")))
    fanout_value = safe_float(str(worst_fanout.get("value", "")))
    if fanout_slack is not None and fanout_slack < 0:
        recs.append(
            f"fanout 违例集中在 `{worst_fanout.get('object', 'unknown')}`，建议复制 driver 或插入 buffer tree。"
        )
    elif fanout_value is not None and fanout_value >= 20:
        recs.append("检测到较高 fanout，后续频率继续上调时应优先检查 driver duplication 或 buffer tree。")

    problems = report.get("problems")
    if isinstance(problems, int) and problems > 0:
        recs.append(f"synth check 报告了 {problems} 个问题，应先修复结构性 RTL/综合网表问题，再继续做时序闭环。")

    if not recs:
        recs.append("当前未见明显 setup/hold 违例，下一步应把默认 SDC 替换为更贴近系统接口的真实约束。")
    return recs


def format_optional(value: object, digits: int = 3) -> str:
    if value is None:
        return "NA"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def write_summary(
    summary_path: Path,
    top: str,
    clock_freq_mhz: float,
    sdc_path: Path,
    sdc_meta: Dict[str, object],
    report: Dict[str, object],
    recommendations: Sequence[str],
    make_rc: int,
    failure: Dict[str, str],
) -> None:
    worst_setup = report.get("worst_setup_path") or {}
    worst_hold = report.get("worst_hold_path") or {}
    lines = [
        f"# STA Summary: {top}",
        "",
        "## Run Status",
        "",
        f"- make return code: `{make_rc}`",
        f"- flow stage: `{failure.get('stage', 'unknown')}`",
        f"- status note: `{failure.get('message', 'NA')}`",
        f"- top module: `{top}`",
        f"- clock port: `{sdc_meta.get('clock_port', 'NA')}`",
        f"- reset ports: `{', '.join(sdc_meta.get('reset_ports', [])) or 'none'}`",
        f"- async inputs: `{', '.join(sdc_meta.get('async_inputs', [])) or 'none'}`",
        f"- test inputs: `{', '.join(sdc_meta.get('test_inputs', [])) or 'none'}`",
        f"- unconstrained outputs: `{', '.join(sdc_meta.get('unconstrained_outputs', [])) or 'none'}`",
        f"- target frequency: `{clock_freq_mhz:g} MHz`",
        f"- generated sdc: `{sdc_path}`",
        "",
        "## Key Metrics",
        "",
        f"- setup WNS: `{format_optional(report.get('setup_wns'))}`",
        f"- setup TNS: `{format_optional(report.get('setup_tns'))}`",
        f"- hold WNS: `{format_optional(report.get('hold_wns'))}`",
        f"- hold TNS: `{format_optional(report.get('hold_tns'))}`",
        f"- cells: `{format_optional(report.get('cells'), 0)}`",
        f"- chip area: `{format_optional(report.get('chip_area'))}`",
        f"- sequential area ratio: `{format_optional(report.get('sequential_area_ratio_pct'))}%`",
        f"- total power: `{format_optional(report.get('total_power_w'), 6)} W`",
        f"- synth check problems: `{format_optional(report.get('problems'), 0)}`",
        "",
        "## Critical Findings",
        "",
        f"- worst setup endpoint: `{worst_setup.get('endpoint', 'NA')}` with slack `{format_optional(worst_setup.get('slack'))}` and freq `{format_optional(worst_setup.get('freq_mhz'))} MHz`",
        f"- worst hold endpoint: `{worst_hold.get('endpoint', 'NA')}` with slack `{format_optional(worst_hold.get('slack'))}`",
        f"- worst transition object: `{(report.get('worst_transition') or {}).get('object', 'NA')}` with slack `{format_optional((report.get('worst_transition') or {}).get('slack'))}`",
        f"- worst capacitance object: `{(report.get('worst_capacitance') or {}).get('object', 'NA')}` with slack `{format_optional((report.get('worst_capacitance') or {}).get('slack'))}`",
        f"- unconstrained ports from STA log: `{', '.join(report.get('unconstrained_ports', [])) or 'none'}`",
        "",
        "## Recommendations",
        "",
    ]
    lines.extend(f"- {item}" for item in recommendations)
    lines.extend(
        [
            "",
            "## Assumptions",
            "",
            "- This SDC is a bootstrap constraint, not full system signoff intent.",
            "- Multi-clock, CDC, scan, and protocol-specific timing still need manual confirmation.",
            "",
        ]
    )
    summary_path.write_text("\n".join(lines))
