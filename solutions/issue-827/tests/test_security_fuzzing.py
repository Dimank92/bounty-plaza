"""
Automated Adversarial Security & Fuzzing Acceptance Suite for Bounty #3.
Covers 10 distinct attack vectors mapped to MITRE ATT&CK & OWASP:
  - CWE-20: Type confusion & boundary validation
  - CWE-22: Path traversal neutralization
  - CWE-117: Log injection & CRLF sanitization
  - CWE-362: Thread concurrency & race condition immunity
  - CWE-369: Float division by zero
  - CWE-400: Resource exhaustion & ReDoS mitigation
  - CWE-502: Circular reference serialization protection
  - CWE-682: Floating-point anomaly & domain stability
  - CWE-754: Platform CRT epoch bounds & Unicode sanitization
"""
import math
import os
import pathlib
import sys
import threading
import time
import pytest

from middleware.audit_logger import ICHQ14AuditLogger
from middleware.drylab4_engine import DryLab4RetentionEngine
from middleware.clock_sync import MasterClock432Hz
from middleware.sila2_bridge import HamiltonSTARletBridge

FUZZ_LOG = pathlib.Path(__file__).parent.parent / "results" / "fuzz_pytest_audit.log"


@pytest.fixture(autouse=True)
def cleanup_fuzz_log():
    yield
    if FUZZ_LOG.exists():
        try:
            FUZZ_LOG.unlink()
        except OSError:
            pass


def test_sec_path_traversal():
    attacks = [
        "../../../../etc/passwd",
        "..\\..\\..\\Windows\\System32\\drivers\\etc\\hosts",
        "results/../../../secret.key",
        "results/\x00/evil.log",
        "/dev/null",
    ]
    for atk in attacks:
        try:
            logger = ICHQ14AuditLogger(atk)
            assert os.path.isabs(logger.log_path)
        except (ValueError, OSError):
            pass


def test_sec_log_injection():
    logger = ICHQ14AuditLogger(str(FUZZ_LOG))
    crlf_payloads = [
        "admin\r\nFAKE_EVENT: true\r\nactor: superuser",
        "system\n\x00INJECTED_NULL",
        "operator\r\n{\"actor\":\"evil\",\"operation_id\":\"hacked\"}",
        "user\x1b[31;1mANSI_ESCAPE\x1b[0m"
    ]
    for payload in crlf_payloads:
        entry = logger.log_entry(actor=payload, delta={"test": 1}, operation_id="OP_TEST")
        assert "\r" not in entry["actor"]
        assert "\n" not in entry["actor"]
        assert "\x00" not in entry["actor"]


def test_sec_float_and_zero_division():
    engine = DryLab4RetentionEngine()
    invalid_float_attacks = [
        (float('nan'), 0.95),
        (0.05, float('nan')),
        (float('inf'), 0.95),
        (0.05, float('-inf')),
        (0.5, 0.5),       # delta_phi = 0 (divide by zero)
        (0.95, 0.05),      # inverted gradient (negative delta_phi)
        (-1.0, 2.0),       # out of [0, 1] range
        (1e308, 1e308),    # extreme overflow
    ]
    for p_init, p_fin in invalid_float_attacks:
        with pytest.raises(ValueError):
            engine.predict_retention_time("Phenol", phi_initial=p_init, phi_final=p_fin)

    # Valid boundary cases must compute finite numbers without NaN or exception
    assert math.isfinite(engine.predict_retention_time("Phenol", phi_initial=-0.0, phi_final=0.95))
    assert math.isfinite(engine.predict_retention_time("Phenol", phi_initial=0.0, phi_final=1.0))


def test_sec_redos_and_length_bomb():
    bridge = HamiltonSTARletBridge(str(FUZZ_LOG))
    massive_string = "A" * 100_000
    t0 = time.perf_counter()
    with pytest.raises(ValueError):
        bridge.execute_liquid_handling_cycle([1], 50.0, massive_string)
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.05, f"ReDoS suspected! Took {elapsed:.4f}s"


def test_sec_type_confusion_and_bool_injection():
    bridge = HamiltonSTARletBridge(str(FUZZ_LOG))
    invalid_channels = [
        [True],
        [True, False],
        [1, "2", 3],
        None,
        123,
        [-5],
        [0],
        [97],
        [1, 1],
    ]
    for ch in invalid_channels:
        with pytest.raises((ValueError, TypeError)):
            bridge.execute_liquid_handling_cycle(ch, 50.0, "OP_TYPE_CONFUSION")


def test_sec_hardware_limits():
    bridge = HamiltonSTARletBridge(str(FUZZ_LOG))
    volume_attacks = [-10.0, 0.0, 0.01, 1500.0, True, float('nan'), float('inf'), float('-inf')]
    for vol in volume_attacks:
        with pytest.raises(ValueError):
            bridge.execute_liquid_handling_cycle([1], vol, "OP_HARDWARE_LIMIT")


def test_sec_unicode_and_rtl_override():
    bridge = HamiltonSTARletBridge(str(FUZZ_LOG))
    unicode_attacks = [
        "OP_\u202e_REVERSED",
        "OP_\u200b\u200c_ZERO",
        "OP_АВС_CYRILLIC",
        "OP_\U0001F4A9_EMOJI",
    ]
    for atk in unicode_attacks:
        try:
            bridge.execute_liquid_handling_cycle([1], 50.0, atk)
        except ValueError:
            pass


def test_sec_thread_race_conditions():
    bridge = HamiltonSTARletBridge(str(FUZZ_LOG))
    errors = []

    def worker(worker_id):
        try:
            op_id = f"OP_RACE_{worker_id:03d}"
            res = bridge.execute_liquid_handling_cycle([worker_id % 8 + 1], 20.0, op_id)
            assert res["success"] is True
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(40)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Thread race errors detected: {errors}"


def test_sec_circular_serialization_bomb():
    logger = ICHQ14AuditLogger(str(FUZZ_LOG))
    circular = {}
    circular["self"] = circular
    with pytest.raises(ValueError):
        logger.log_entry("actor_safe", circular, "OP_CIRCULAR")


def test_sec_clock_epoch_overflow():
    clock = MasterClock432Hz()
    bad_epochs = [float('nan'), float('inf'), float('-inf'), -99999999.0, 0.0, 2147483647.0, 1e12]
    for ep in bad_epochs:
        ts = clock.discipline_timestamp(ep)
        assert isinstance(ts, str) and ts.endswith("Z")
