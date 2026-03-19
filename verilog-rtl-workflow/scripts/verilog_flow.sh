#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  verilog_flow.sh lint --top <top_module> [--files "a.v b.sv"] [--filelist rtl.f] [--incdir rtl/include] [--define FOO=1]
  verilog_flow.sh sim --top <top_module> --tb <tb_module> [--files "rtl.v tb.sv"] [--filelist sim.f] [--incdir rtl/include] [--define FOO=1] [--out build/sim.out] [--wave-file build/tb.vcd] [--waves]

Behavior:
  lint: prefer verilator --lint-only, otherwise fallback to iverilog -Wall
  sim: compile with iverilog and run with vvp, passing a default waveform path under build/
EOF
}

die() {
  echo "error: $*" >&2
  exit 1
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

mode="${1:-}"
if [[ "${mode}" == "-h" || "${mode}" == "--help" ]]; then
  usage
  exit 0
fi
if [[ -z "${mode}" ]]; then
  usage
  exit 1
fi
shift

top=""
tb=""
files=""
out="build/verilog_sim.out"
wave_file=""
waves=0
filelists=()
incdirs=()
defines=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --top)
      top="${2:-}"
      shift 2
      ;;
    --tb)
      tb="${2:-}"
      shift 2
      ;;
    --files)
      files="${2:-}"
      shift 2
      ;;
    --filelist)
      filelists+=("${2:-}")
      shift 2
      ;;
    --incdir)
      incdirs+=("${2:-}")
      shift 2
      ;;
    --define)
      defines+=("${2:-}")
      shift 2
      ;;
    --out)
      out="${2:-}"
      shift 2
      ;;
    --wave-file)
      wave_file="${2:-}"
      shift 2
      ;;
    --waves)
      waves=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown argument: $1"
      ;;
  esac
done

[[ -n "${top}" ]] || die "--top is required"

read -r -a file_array <<< "${files}"
if [[ -z "${files}" && ${#filelists[@]} -eq 0 ]]; then
  die "provide --files and/or at least one --filelist"
fi

common_args=()
for incdir in "${incdirs[@]}"; do
  [[ -n "${incdir}" ]] || die "empty value passed to --incdir"
  common_args+=("-I" "${incdir}")
done

for define in "${defines[@]}"; do
  [[ -n "${define}" ]] || die "empty value passed to --define"
  common_args+=("-D" "${define}")
done

for filelist in "${filelists[@]}"; do
  [[ -f "${filelist}" ]] || die "filelist not found: ${filelist}"
  common_args+=("-f" "${filelist}")
done

source_desc=()
if [[ ${#file_array[@]} -gt 0 ]]; then
  source_desc+=("${file_array[@]}")
fi
for filelist in "${filelists[@]}"; do
  source_desc+=("-f" "${filelist}")
done
[[ ${#source_desc[@]} -gt 0 ]] || die "no source inputs resolved"

case "${mode}" in
  lint)
    if have_cmd verilator; then
      echo "+ verilator --lint-only -Wall --top-module ${top} ${source_desc[*]}"
      exec verilator --lint-only -Wall --top-module "${top}" "${common_args[@]}" "${file_array[@]}"
    fi

    if have_cmd iverilog; then
      echo "+ iverilog -g2012 -Wall -s ${top} ${source_desc[*]}"
      exec iverilog -g2012 -Wall -s "${top}" "${common_args[@]}" "${file_array[@]}"
    fi

    die "neither verilator nor iverilog is installed"
    ;;
  sim)
    [[ -n "${tb}" ]] || die "--tb is required for sim"
    have_cmd iverilog || die "iverilog is required for sim"
    have_cmd vvp || die "vvp is required for sim"

    if [[ -z "${wave_file}" ]]; then
      wave_file="build/${tb}.vcd"
    fi

    mkdir -p "$(dirname "${out}")"
    mkdir -p "$(dirname "${wave_file}")"
    echo "+ iverilog -g2012 -Wall -s ${tb} -o ${out} ${source_desc[*]}"
    iverilog -g2012 -Wall -s "${tb}" -o "${out}" "${common_args[@]}" "${file_array[@]}"

    if [[ "${waves}" -eq 1 ]]; then
      echo "note: --waves is kept for compatibility; testbenches should dump waves by default"
    fi

    echo "+ vvp ${out} +wave_path=${wave_file}"
    exec vvp "${out}" "+wave_path=${wave_file}"
    ;;
  *)
    usage
    die "unknown mode: ${mode}"
    ;;
esac
