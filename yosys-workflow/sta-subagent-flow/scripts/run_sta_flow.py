#!/usr/bin/env python3

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from report_analyzer import (
    build_recommendations,
    classify_make_failure,
    collect_reports,
    write_summary,
)
from rtl_parser import (
    choose_clock_port,
    classify_ports,
    extract_module_text,
    find_module_source,
    parse_ports,
    rtl_files,
)
from sdc_builder import infer_clock_freq, parse_make_vars, run_make_target, write_sdc
from sdc_builder import ensure_makefile
from sta_types import StaFlowError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate default SDC, run make sta, and summarize reports."
    )
    parser.add_argument("--design-home", required=True, help="RTL project root")
    parser.add_argument("--top", required=True, help="Top module name")
    parser.add_argument("--clock-port", help="Override inferred clock port")
    parser.add_argument(
        "--clock-freq-mhz",
        type=float,
        help="Override target frequency in MHz. Falls back to Makefile/env.",
    )
    parser.add_argument(
        "--io-delay-ratio",
        type=float,
        default=0.2,
        help="Input/output delay ratio relative to the clock period",
    )
    parser.add_argument(
        "--input-delay-exclude",
        default="",
        help="Comma-separated top input ports to exclude from set_input_delay",
    )
    parser.add_argument(
        "--output-delay-exclude",
        default="",
        help="Comma-separated top output ports to exclude from set_output_delay",
    )
    parser.add_argument(
        "--async-inputs",
        default="",
        help="Comma-separated top input ports to mark as false-path async inputs",
    )
    parser.add_argument(
        "--false-path-from",
        default="",
        help="Comma-separated additional ports to mark as false path sources",
    )
    parser.add_argument(
        "--make-target",
        default="sta",
        help="Make target to run after generating SDC",
    )
    parser.add_argument(
        "--summary-name",
        default="sta_summary.md",
        help="Summary file written into RESULT_DIR",
    )
    return parser.parse_args()


def parse_csv_arg(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def build_payload(
    summary_path: Path,
    sdc_path: Path,
    result_dir: Path,
    clock_freq_mhz: float,
    ports: Sequence[object],
    sdc_meta: Dict[str, object],
    report: Dict[str, object],
    recommendations: Sequence[str],
    make_rc: int,
    failure: Dict[str, str],
    stdout: str,
    stderr: str,
    makefile_path: Path,
    makefile_generated: bool,
) -> Dict[str, object]:
    return {
        "summary_path": str(summary_path),
        "sdc_path": str(sdc_path),
        "result_dir": str(result_dir),
        "makefile_path": str(makefile_path),
        "makefile_generated": makefile_generated,
        "clock_freq_mhz": clock_freq_mhz,
        "ports": [asdict(port) for port in ports],
        "sdc_meta": sdc_meta,
        "make_return_code": make_rc,
        "failure": failure,
        "report": report,
        "recommendations": list(recommendations),
        "stdout_tail": stdout.splitlines()[-20:],
        "stderr_tail": stderr.splitlines()[-20:],
    }


def write_failure_summary(
    summary_path: Path, top: str, make_rc: int, stage: str, message: str
) -> None:
    summary_path.write_text(
        "\n".join(
            [
                f"# STA Summary: {top}",
                "",
                "## Run Status",
                "",
                f"- make return code: `{make_rc}`",
                f"- flow stage: `{stage}`",
                f"- status note: `{message}`",
                "",
            ]
        )
    )


def main() -> int:
    args = parse_args()
    design_home = Path(args.design_home).resolve()
    rtl_dir = design_home / "rtl"
    make_env = os.environ.copy()
    make_env["DESIGN"] = args.top
    if args.clock_freq_mhz is not None:
        make_env["CLK_FREQ_MHZ"] = f"{args.clock_freq_mhz:g}"
    if args.clock_port:
        make_env["CLK_PORT_NAME"] = args.clock_port

    stdout = ""
    stderr = ""
    make_rc = 1

    try:
        makefile_path, makefile_generated = ensure_makefile(design_home, args.top)
        make_vars = parse_make_vars(design_home, env=make_env)
        sdc_path = Path(make_vars["SDC_FILE"]).resolve()
        result_dir = Path(make_vars["RESULT_DIR"]).resolve()

        files = rtl_files(rtl_dir)
        module_source = find_module_source(files, args.top)
        module_text = extract_module_text(module_source, args.top)
        ports = parse_ports(module_text, args.top)

        clock_port = choose_clock_port(ports, args.clock_port)
        clock_freq_mhz = infer_clock_freq(args.clock_freq_mhz, make_vars)
        classified = classify_ports(
            ports=ports,
            clock_port=clock_port,
            input_exclude=parse_csv_arg(args.input_delay_exclude),
            output_exclude=parse_csv_arg(args.output_delay_exclude),
            async_inputs=parse_csv_arg(args.async_inputs),
        )
        sdc_meta = write_sdc(
            sdc_path=sdc_path,
            classified=classified,
            false_path_from=parse_csv_arg(args.false_path_from),
            clock_freq_mhz=clock_freq_mhz,
            io_delay_ratio=args.io_delay_ratio,
        )

        make_rc, stdout, stderr = run_make_target(
            design_home, args.make_target, env=make_env
        )
        failure = classify_make_failure(make_rc, stdout, stderr, result_dir, args.top)
        report = (
            collect_reports(result_dir, args.top)
            if result_dir.exists()
            else {"result_dir": str(result_dir)}
        )
        recommendations = build_recommendations(report, sdc_meta)

        summary_path = result_dir / args.summary_name
        result_dir.mkdir(parents=True, exist_ok=True)
        write_summary(
            summary_path=summary_path,
            top=args.top,
            clock_freq_mhz=clock_freq_mhz,
            sdc_path=sdc_path,
            sdc_meta=sdc_meta,
            report=report,
            recommendations=recommendations,
            make_rc=make_rc,
            failure=failure,
        )

        payload = build_payload(
            summary_path=summary_path,
            sdc_path=sdc_path,
            result_dir=result_dir,
            clock_freq_mhz=clock_freq_mhz,
            ports=ports,
            sdc_meta=sdc_meta,
            report=report,
            recommendations=recommendations,
            make_rc=make_rc,
            failure=failure,
            stdout=stdout,
            stderr=stderr,
            makefile_path=makefile_path,
            makefile_generated=makefile_generated,
        )
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if make_rc == 0 else make_rc

    except StaFlowError as exc:
        sdc_path = design_home / "constraint" / "default.sdc"
        result_dir = design_home / "result"
        summary_path = result_dir / args.summary_name
        result_dir.mkdir(parents=True, exist_ok=True)
        write_failure_summary(summary_path, args.top, make_rc, exc.stage, exc.message)
        payload = {
            "summary_path": str(summary_path),
            "sdc_path": str(sdc_path),
            "result_dir": str(result_dir),
            "makefile_path": str(design_home / "Makefile"),
            "makefile_generated": False,
            "make_return_code": make_rc,
            "failure": {"stage": exc.stage, "message": exc.message},
            "stdout_tail": stdout.splitlines()[-20:],
            "stderr_tail": stderr.splitlines()[-20:],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
