"""Verify deterministic packaging, action parity, reset and isolated execution."""

import argparse
import hashlib
import importlib.util
import inspect
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def load(path):
    spec = importlib.util.spec_from_file_location("verified_policy", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def memory_usage():
    """Separate current-image RSS accounting from pre-exec process history.

    Linux exec_mmap retains the preceding address space's high-water mark for
    getrusage, whereas proc VmHWM describes the current mm. Neither OS RSS
    accounting nor tracemalloc is an exact isolated policy-only allocation.

    Kernel accounting references (v6.8):
    https://github.com/torvalds/linux/blob/v6.8/fs/exec.c#L990
    https://github.com/torvalds/linux/blob/v6.8/fs/proc/task_mmu.c#L30-L60
    """
    import sys
    from pathlib import Path

    if sys.platform == "win32":
        import ctypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong), ("faults", ctypes.c_ulong)] + [
                (name, ctypes.c_size_t)
                for name in (
                    "peak_rss",
                    "rss",
                    "peak_paged",
                    "paged",
                    "peak_nonpaged",
                    "nonpaged",
                    "pagefile",
                    "peak_pagefile",
                )
            ]

        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        ctypes.windll.kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(Counters),
            ctypes.c_ulong,
        ]
        if not ctypes.windll.psapi.GetProcessMemoryInfo(
            handle, ctypes.byref(counters), counters.cb
        ):
            raise OSError("GetProcessMemoryInfo failed")
        return {
            "peak_rss_bytes": counters.peak_rss,
            "peak_rss_measure": "Windows PeakWorkingSetSize",
            "resource_peak_rss_bytes": None,
        }

    import resource

    historical = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (
        1 if sys.platform == "darwin" else 1024
    )
    result = {
        "peak_rss_bytes": historical,
        "peak_rss_measure": "resource.ru_maxrss; may include pre-exec history",
        "resource_peak_rss_bytes": historical,
    }
    if sys.platform.startswith("linux"):
        try:
            status = Path("/proc/self/status").read_text()
        except OSError:
            status = ""
        for line in status.splitlines():
            fields = line.split()
            if len(fields) == 3 and fields[0] == "VmHWM:" and fields[2] == "kB":
                value = int(fields[1])
                if value <= 0:
                    raise ValueError("Invalid proc VmHWM")
                result.update(
                    peak_rss_bytes=value * 1024,
                    peak_rss_measure="Linux /proc/self/status VmHWM; current-image RSS high-water estimate",
                )
                break
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=Path("submissions/20260909-v8/main.py"))
    parser.add_argument(
        "--source", type=Path, default=Path("src/kaggriculture/agent/competitive.py")
    )
    parser.add_argument("--output", type=Path, default=Path("reports/results/packaging.json"))
    args = parser.parse_args()
    from kaggle_environments import make

    source_path = args.source.resolve()
    artifact_path = args.artifact.resolve()
    assert artifact_path.read_bytes() == source_path.read_bytes().replace(b"\r\n", b"\n")
    source, packaged = load(source_path), load(artifact_path)
    samples = []
    matches = []
    checked_actions = 0
    for seed in (23, 31):
        for seat in (0, 1):
            environment = make("kaggriculture", configuration={"seed": seed})

            def policy(obs, config):
                nonlocal checked_actions
                expected = source.agent(obs, config)
                actual = packaged.agent(obs, config)
                assert actual == expected
                checked_actions += 1
                if obs.step % 53 == 0:
                    samples.append(json.loads(json.dumps(obs)))
                return actual

            agents = [policy, "starter"] if seat == 0 else ["starter", policy]
            environment.run(agents)
            assert all(s.status == "DONE" for s in environment.state)
            matches.append({"seed": seed, "seat": seat, "cash": environment.state[seat].reward})
    isolated_code = (
        inspect.getsource(memory_usage)
        + "\n"
        + """
import json, sys, tracemalloc
from pathlib import Path
tracemalloc.start()
namespace = {}
exec(compile(Path(sys.argv[1]).read_bytes(), 'main.py', 'exec'), namespace)
observations = json.load(sys.stdin)
actions = [namespace['agent'](obs) for obs in observations]
memory = memory_usage()
print(json.dumps({'actions': actions, 'peak_python_bytes': tracemalloc.get_traced_memory()[1], **memory}))
"""
    )
    with tempfile.TemporaryDirectory() as directory:
        # Repeat two independent interpreter lifetimes, with no site packages or
        # repository path. Repeated observations also verify in-process reset.
        payload = json.dumps(samples + samples[:4])
        results = []
        for _ in range(2):
            result = subprocess.run(
                [sys.executable, "-I", "-S", "-c", isolated_code, str(artifact_path)],
                cwd=directory,
                input=payload,
                text=True,
                capture_output=True,
                check=True,
            )
            results.append(json.loads(result.stdout))
        assert results[0]["actions"] == results[1]["actions"]
        assert results[0]["actions"] == [source.agent(obs) for obs in samples + samples[:4]]
    report = {
        "source": str(args.source),
        "artifact": str(args.artifact),
        "sha256": hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
        "trajectory_actions_compared": checked_actions,
        "matches": matches,
        "isolated_actions_compared": len(results[0]["actions"]),
        "fresh_processes": 2,
        "peak_python_bytes": max(result["peak_python_bytes"] for result in results),
        "peak_rss_bytes": max(result["peak_rss_bytes"] for result in results),
        "peak_rss_measure": sorted({result["peak_rss_measure"] for result in results}),
        "resource_peak_rss_bytes": max(
            (
                result["resource_peak_rss_bytes"]
                for result in results
                if result["resource_peak_rss_bytes"] is not None
            ),
            default=None,
        ),
        "memory_measure": "isolated executable-image OS RSS high-water estimate where available; historical resource peak retained separately; tracemalloc Python allocation peak",
        "memory_limitations": "RSS includes interpreter, observations, collected actions and tracing overhead. Linux proc accounting is approximate. A historical pre-exec resource peak is not the current policy's memory footprint.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
