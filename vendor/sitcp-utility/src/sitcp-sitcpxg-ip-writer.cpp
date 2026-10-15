#include "sitcp-sitcpxg-network-config.hpp"

#include <cstdint>
#include <iostream>
#include <string>

namespace {

namespace network_config = sitcp_sitcpxg::network_config;

uint16_t parse_port(const std::string& value) {
    if (value.empty() ||
        value.find_first_not_of("0123456789") != std::string::npos) {
        throw network_config::Error("port must be an integer from 1 to 65535");
    }
    const unsigned long number = std::stoul(value);
    if (number == 0 || number > 65535) {
        throw network_config::Error("port must be from 1 to 65535");
    }
    return static_cast<uint16_t>(number);
}

void usage(const char* program) {
    std::cerr
        << "Usage: " << program << " CURRENT_IP NEW_IP [options]" << std::endl
        << std::endl
        << "Options:" << std::endl
        << "  --eeprom      Write EEPROM IP (default)" << std::endl
        << "  --current     Write current/runtime IP, reconnect to NEW_IP, and verify"
        << std::endl
        << "  --port N      RBCP UDP port (default: "
        << network_config::DEFAULT_PORT << ")" << std::endl
        << "  --tcp-port N  Set TCP data port, 1..65535 (default: preserve)" << std::endl
        << "  --udp-port N  Set UDP/RBCP port, 1..65535 (default: preserve)" << std::endl
        << "  --timeout SEC RBCP timeout in seconds (default: "
        << network_config::DEFAULT_TIMEOUT << ")" << std::endl
        << "  -h, --help    Show this help" << std::endl;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        const bool show_help = argc == 2 &&
            (std::string(argv[1]) == "-h" ||
             std::string(argv[1]) == "--help");
        if (argc < 3 || show_help) {
            usage(argv[0]);
            return show_help ? 0 : 2;
        }

        const std::string host = argv[1];
        const std::string new_ip = argv[2];
        uint16_t port = network_config::DEFAULT_PORT;
        double timeout = network_config::DEFAULT_TIMEOUT;
        bool write_current = false;
        bool mode_explicit = false;
        uint16_t tcp_port = 0;
        uint16_t udp_port = 0;

        for (int i = 3; i < argc; ++i) {
            const std::string option = argv[i];
            if (option == "--eeprom") {
                if (mode_explicit && write_current) {
                    throw network_config::Error(
                        "--eeprom and --current are mutually exclusive");
                }
                write_current = false;
                mode_explicit = true;
            } else if (option == "--current") {
                if (mode_explicit && !write_current) {
                    throw network_config::Error(
                        "--eeprom and --current are mutually exclusive");
                }
                write_current = true;
                mode_explicit = true;
            } else if (option == "--port" && i + 1 < argc) {
                port = parse_port(argv[++i]);
            } else if (option == "--tcp-port" && i + 1 < argc) {
                tcp_port = parse_port(argv[++i]);
            } else if (option == "--udp-port" && i + 1 < argc) {
                udp_port = parse_port(argv[++i]);
            } else if (option == "--timeout" && i + 1 < argc) {
                timeout = std::stod(argv[++i]);
                if (timeout <= 0) {
                    throw network_config::Error(
                        "timeout must be positive");
                }
            } else if (option == "-h" || option == "--help") {
                usage(argv[0]);
                return 0;
            } else {
                throw network_config::Error(
                    "unknown option: " + option);
            }
        }

        (void)network_config::parse_ipv4(new_ip);
        network_config::show_compact(host, port, timeout, "before");
        if (write_current) {
            network_config::write_current_ip(
                host, new_ip, port, timeout, tcp_port, udp_port);
        } else {
            network_config::write_eeprom_ip(
                host, new_ip, port, timeout, tcp_port, udp_port);
        }
        network_config::show_compact(
            write_current ? new_ip : host,
            write_current && udp_port != 0 ? udp_port : port, timeout, "after");
        network_config::print_success();

        return 0;
    } catch (const std::exception& error) {
        std::cerr << "ERROR: " << error.what() << std::endl;
        return 1;
    }
}
