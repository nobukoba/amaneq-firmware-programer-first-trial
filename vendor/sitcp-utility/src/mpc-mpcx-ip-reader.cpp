#include "sitcp-sitcpxg-register-report.hpp"
#include "sitcp-sitcpxg-rbcp.hpp"

#include <algorithm>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

void unified_usage(const char* program) {
    std::cerr
        << "Usage: " << program << " IP [options]\n\n"
        << "Reads runtime (SiTCP: 64 / XG: 80 bytes) and EEPROM (80 bytes), including\n"
        << "current/EEPROM MAC/IP and decimal/hex register values.\n\n"
        << "Options:\n"
        << "  --port N       RBCP UDP port (default: "
        << sitcp_sitcpxg::network_config::DEFAULT_PORT << ")\n"
        << "  --timeout SEC  RBCP timeout in seconds (default: "
        << sitcp_sitcpxg::network_config::DEFAULT_TIMEOUT << ")\n"
        << "  -h, --help     Show this help\n";
}

}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc < 2 ||
            (argc == 2 &&
             (std::string(argv[1]) == "-h" ||
              std::string(argv[1]) == "--help"))) {
            unified_usage(argv[0]);
            return argc < 2 ? 2 : 0;
        }

        const std::string host = argv[1];
        uint16_t port = sitcp_sitcpxg::network_config::DEFAULT_PORT;
        double timeout = sitcp_sitcpxg::network_config::DEFAULT_TIMEOUT;

        for (int i = 2; i < argc; ++i) {
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
            } else if (option == "-h" || option == "--help") {
                unified_usage(argv[0]);
                return 0;
            } else {
                throw std::runtime_error("unknown option: " + option);
            }
        }

        const bool complete =
            sitcp_sitcpxg::register_report::show(host, port, timeout);
        return complete ? 0 : 3;
    } catch (const std::exception& error) {
        std::cerr << "ERROR: " << error.what() << '\n';
        return 1;
    }
}
