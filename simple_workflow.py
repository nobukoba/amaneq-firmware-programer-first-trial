"""Validated network setup stages shared by the Simple desktop workflow."""

from dataclasses import dataclass
import network_operations as operations


@dataclass(frozen=True)
class NetworkPlan:
    host: str
    saved_ip: str
    check: tuple
    license_write: tuple
    license_read: tuple
    ip_write: tuple
    ip_read: tuple


def prepare_network(root, host, filename, saved_ip):
    """Resolve all executables and validate inputs before any device mutation."""
    host = operations.ipv4(host)
    saved_ip = operations.ipv4(saved_ip)
    if filename:
        operations.license_kind(filename)
    check = operations.utility_command(root, host, "Check", filename)
    license_write = (
        operations.utility_command(
            root, host, "Write MPC/MPCX", filename, initialize=True
        )
        if filename
        else []
    )
    license_read = operations.utility_command(root, host, "Read") if filename else []
    ip_write = operations.utility_command(
        root, host, "Write IP only", new_ip=saved_ip, current=False
    )
    ip_read = operations.utility_command(root, host, "Read IP")
    return NetworkPlan(
        host,
        saved_ip,
        tuple(check),
        tuple(license_write),
        tuple(license_read),
        tuple(ip_write),
        tuple(ip_read),
    )


def configure_network(plan, run_command, log, clock=operations.configure_clock):
    """Stop on the first failure; verified helpers perform their own readback."""
    run_command(list(plan.check))
    log(clock(plan.host, operations.DEFAULT_CLOCK_PRESET, persist=True))
    if plan.license_write:
        run_command(list(plan.license_write))
        run_command(list(plan.license_read))
    run_command(list(plan.ip_write))
    run_command(list(plan.ip_read))
    log("Network configuration and readback completed; EEPROM IP: " + plan.saved_ip)
