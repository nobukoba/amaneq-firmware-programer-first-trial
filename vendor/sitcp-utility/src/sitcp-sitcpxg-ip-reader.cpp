#include "sitcp-sitcpxg-network-config.hpp"

#include <cstdint>
#include <iostream>
#include <string>

namespace {

namespace network_config = sitcp_sitcpxg::network_config;

void usage(const char* program) {
    std::cerr
        << "Usage: " << program << " IP [options]" << std::endl
        << std::endl
        << "Options:" << std::endl
        << "  --port N       RBCP UDP port (default: "
        << network_config::DEFAULT_PORT << ")" << std::endl
        << "  --timeout SEC  RBCP timeout in seconds (default: "
        << network_config::DEFAULT_TIMEOUT << ")" << std::endl
        << "  -h, --help     Show this help" << std::endl;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc < 2 ||
            (argc == 2 &&
             (std::string(argv[1]) == "-h" ||
              std::string(argv[1]) == "--help"))) {
            usage(argv[0]);
            return argc < 2 ? 2 : 0;
        }

        const std::string host = argv[1];
        uint16_t port = network_config::DEFAULT_PORT;
        double timeout = network_config::DEFAULT_TIMEOUT;

        for (int i = 2; i < argc; ++i) {
            const std::string option = argv[i];
            if (option == "--port" && i + 1 < argc) {
                const unsigned long value = std::stoul(argv[++i]);
                if (value == 0 || value > 65535) {
                    throw network_config::Error("invalid port");
                }
                port = static_cast<uint16_t>(value);
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

        std::cout
            << "target       : " << host << ':' << port
            << std::endl;
        network_config::show_all(host, port, timeout);
        std::cout << "status       : READ OK" << std::endl;
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "ERROR: " << error.what() << std::endl;
        return 1;
    }
}
