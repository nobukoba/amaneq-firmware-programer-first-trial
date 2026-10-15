#include "sitcp-sitcpxg-register-report.hpp"
#include "sitcp-sitcpxg-mpc-mpcx.hpp"

#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {

namespace network_config = sitcp_sitcpxg::network_config;

void unified_usage(const char* program) {
    std::cerr
        << "Usage: " << program << " COMMAND ...\n\n"
        << "Commands:\n"
        << "  inspect MPC_OR_MPCX_FILE\n"
        << "  mac MPC_OR_MPCX_FILE\n"
        << "  read IP [--port N] [--timeout SEC]\n"
        << "  verify IP FILE [--port N] [--timeout SEC]\n"
        << "  mpcx-plan IP FILE [--port N] [--timeout SEC]\n"
        << "  probe IP ADDRESS [LENGTH] [--port N] [--timeout SEC]\n"
        << "  rbcp-read IP ADDRESS LENGTH [--port N] [--timeout SEC]\n"
        << "  rbcp-write IP ADDRESS HEX-BYTES [--port N] [--timeout SEC]\n"
        << "  clear IP --yes-really-clear [--port N] [--timeout SEC]\n"
        << "  ip-read IP [--port N] [--timeout SEC]\n"
        << "  ip-write CURRENT_IP NEW_IP [--eeprom|--current]"
           " [--port N] [--timeout SEC]\n"
        << "  write ...  Use mpc-mpcx-ip-writer\n\n"
        << "read/ip-read: runtime SiTCP 64 / XG 80 bytes; EEPROM 80 bytes.\n"
        << "Register values are shown in decimal and hexadecimal.\n\n"
        << "Defaults:\n"
        << "  --port N       RBCP UDP port (default: "
        << network_config::DEFAULT_PORT << ")\n"
        << "  --timeout SEC  RBCP timeout in seconds (default: "
        << network_config::DEFAULT_TIMEOUT << ")\n"
        << "  probe LENGTH   bytes to read (default: 1)\n"
        << "  ip-write       writes EEPROM IP unless --current is specified\n";
}

void parse_common_options(int argc, char** argv, int start,
                          uint16_t& port, double& timeout) {
    for (int i = start; i < argc; ++i) {
        const std::string option = argv[i];
        if (option == "--port" && i + 1 < argc) {
            const unsigned long value = std::stoul(argv[++i]);
            if (value == 0 || value > 65535) {
                throw std::runtime_error("invalid port");
            }
            port = static_cast<uint16_t>(value);
        } else if (option == "--timeout" && i + 1 < argc) {
            timeout = std::stod(argv[++i]);
            if (timeout <= 0) {
                throw std::runtime_error("timeout must be positive");
            }
        } else {
            throw std::runtime_error("unknown option: " + option);
        }
    }
}

}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc < 2 || std::string(argv[1]) == "-h" ||
            std::string(argv[1]) == "--help") {
            unified_usage(argv[0]);
            return 0;
        }

        const std::string command = argv[1];

        if (command == "ip-read") {
            if (argc < 3) {
                throw std::runtime_error("usage: ip-read IP [options]");
            }

            uint16_t port = network_config::DEFAULT_PORT;
            double timeout = network_config::DEFAULT_TIMEOUT;
            parse_common_options(argc, argv, 3, port, timeout);
            const bool complete =
                sitcp_sitcpxg::register_report::show(argv[2], port, timeout);
            return complete ? 0 : 3;
        }

        if (command == "ip-write") {
            if (argc < 4) {
                throw std::runtime_error(
                    "usage: ip-write CURRENT_IP NEW_IP "
                    "[--eeprom|--current] [options]");
            }

            const std::string host = argv[2];
            const std::string new_ip = argv[3];
            (void)network_config::parse_ipv4(new_ip);

            uint16_t port = network_config::DEFAULT_PORT;
            double timeout = network_config::DEFAULT_TIMEOUT;
            bool write_current = false;
            bool mode_explicit = false;

            for (int i = 4; i < argc; ++i) {
                const std::string option = argv[i];
                if (option == "--current") {
                    if (mode_explicit && !write_current) {
                        throw std::runtime_error(
                            "--eeprom and --current are mutually exclusive");
                    }
                    write_current = true;
                    mode_explicit = true;
                } else if (option == "--eeprom") {
                    if (mode_explicit && write_current) {
                        throw std::runtime_error(
                            "--eeprom and --current are mutually exclusive");
                    }
                    write_current = false;
                    mode_explicit = true;
                } else if (option == "--port" && i + 1 < argc) {
                    const unsigned long value = std::stoul(argv[++i]);
                    if (value == 0 || value > 65535) {
                        throw std::runtime_error("invalid port");
                    }
                    port = static_cast<uint16_t>(value);
                } else if (option == "--timeout" && i + 1 < argc) {
                    timeout = std::stod(argv[++i]);
                    if (timeout <= 0) {
                        throw std::runtime_error(
                            "timeout must be positive");
                    }
                } else {
                    throw std::runtime_error(
                        "unknown option: " + option);
                }
            }

            network_config::show_compact(host, port, timeout, "before");

            std::string final_host = host;
            if (write_current) {
                network_config::write_current_ip(
                    host, new_ip, port, timeout);
                final_host = new_ip;
            } else {
                network_config::write_eeprom_ip(
                    host, new_ip, port, timeout);
            }

            network_config::show_compact(final_host, port, timeout, "after");
            network_config::print_success();
            return 0;
        }

        if (command == "read") {
            if (argc < 3) {
                throw std::runtime_error("usage: read IP [options]");
            }

            uint16_t port = network_config::DEFAULT_PORT;
            double timeout = network_config::DEFAULT_TIMEOUT;
            parse_common_options(argc, argv, 3, port, timeout);

            const bool complete =
                sitcp_sitcpxg::register_report::show(argv[2], port, timeout);
            return complete ? 0 : 3;
        }

        if (command == "write") {
            std::cerr
                << "Use mpc-mpcx-ip-writer for the verified "
                   "high-level write path.\n";
            return 8;
        }

        return run_mpc_mpcx_command(argc, argv);
    } catch (const std::exception& error) {
        std::cerr << "ERROR: " << error.what() << '\n';
        return 1;
    }
}
