#pragma once

#include "sitcp-sitcpxg-rbcp.hpp"
#include "sitcp-sitcpxg-eeprom-init.hpp"
#include "sitcp-sitcpxg-eeprom-clear.hpp"

#include <algorithm>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

namespace rbcp = sitcp_sitcpxg::rbcp;

constexpr uint16_t DEFAULT_PORT = rbcp::DEFAULT_PORT;
constexpr double DEFAULT_TIMEOUT = rbcp::DEFAULT_TIMEOUT;
constexpr uint32_t EEPROM_BASE = 0xFFFFFC00u;
constexpr uint32_t EEPROM_WRITE_ENABLE = 0xFFFFFCFFu;
constexpr int FIELD_WIDTH = 20;

using Error = rbcp::Error;
using RbcpClient = rbcp::Client;

std::vector<uint8_t> read_exact(RbcpClient& client, uint32_t address,
                                size_t length) {
    std::vector<uint8_t> data;
    for (size_t offset = 0; offset < length; offset += 8) {
        const size_t chunk_size = std::min<size_t>(8, length - offset);
        const std::vector<uint8_t> block = rbcp::read_retry(
            client, address + static_cast<uint32_t>(offset), chunk_size);
        data.insert(data.end(), block.begin(), block.end());
    }
    return data;
}

std::string hex_bytes(const std::vector<uint8_t>& data,
                      size_t begin = 0, size_t end = static_cast<size_t>(-1),
                      char separator = ' ') {
    end = std::min(end, data.size());

    std::ostringstream output;
    output << std::hex << std::setfill('0');
    for (size_t i = begin; i < end; ++i) {
        if (i != begin) {
            output << separator;
        }
        output << std::setw(2) << static_cast<unsigned>(data[i]);
    }
    return output.str();
}

std::string hex_address(uint32_t address) {
    std::ostringstream output;
    output << "0x" << std::hex << std::uppercase
           << std::setw(8) << std::setfill('0') << address;
    return output.str();
}

void field(const std::string& name, const std::string& value) {
    std::cout << std::left << std::setw(FIELD_WIDTH)
              << name << ": " << value << '\n';
}

bool valid_tag(std::vector<uint8_t> tag) {
    if (tag.size() != 7) {
        return false;
    }

    for (size_t i = 0; i < tag.size(); ++i) {
        uint8_t value = tag[i];
        if (value == 0 || value == ' ' || value == '-' ||
            (value >= '0' && value <= '9')) {
            continue;
        }

        value &= 0xDF;
        if (value < 'A' || value > 'Z') {
            return false;
        }
    }
    return true;
}

int classify(const std::vector<uint8_t>& payload) {
    if (payload.size() != 22) {
        return 0;
    }

    std::vector<uint8_t> normal_tag;
    std::vector<uint8_t> xg_tag;
    normal_tag.reserve(7);
    xg_tag.reserve(7);

    for (size_t i = 6; i < 13; ++i) {
        normal_tag.push_back(
            payload[i] ? static_cast<uint8_t>(payload[i] - 0x34) : 0);
    }
    for (size_t i = 0; i < 7; ++i) {
        xg_tag.push_back(
            payload[i] ? static_cast<uint8_t>(payload[i] - 0x2C) : 0);
    }

    if (valid_tag(normal_tag)) {
        return 2;
    }
    if (valid_tag(xg_tag)) {
        return 1;
    }
    return 0;
}

std::string type_name(int type) {
    if (type == 1) {
        return "MPCX (SiTCP-XG)";
    }
    if (type == 2) {
        return "MPC (normal SiTCP)";
    }
    return "unknown";
}

std::vector<uint8_t> payload_mac(const std::vector<uint8_t>& payload) {
    const int type = classify(payload);
    if (type == 1) {
        return std::vector<uint8_t>(payload.begin() + 16, payload.begin() + 22);
    }
    if (type == 2) {
        return std::vector<uint8_t>(payload.begin(), payload.begin() + 6);
    }
    throw Error("invalid/unknown 22-byte MPC/MPCX payload");
}

std::string mac_string(const std::vector<uint8_t>& mac) {
    return hex_bytes(mac, 0, mac.size(), ':');
}

std::vector<uint8_t> read_file(const std::string& path) {
    std::ifstream input(path.c_str(), std::ios::binary);
    if (!input) {
        throw Error("cannot open file: " + path);
    }

    return std::vector<uint8_t>(
        std::istreambuf_iterator<char>(input),
        std::istreambuf_iterator<char>());
}

uint32_t parse_u32(const std::string& text) {
    size_t position = 0;
    const unsigned long value = std::stoul(text, &position, 0);
    if (position != text.size() || value > 0xFFFFFFFFUL) {
        throw Error("invalid integer: " + text);
    }
    return static_cast<uint32_t>(value);
}

std::vector<uint8_t> parse_hex(std::string text) {
    for (size_t i = 0; i < text.size(); ++i) {
        if (text[i] == ',' || text[i] == ':') {
            text[i] = ' ';
        }
    }

    std::istringstream input(text);
    std::vector<uint8_t> data;
    std::string token;
    while (input >> token) {
        if (token.size() >= 2 &&
            (token.substr(0, 2) == "0x" || token.substr(0, 2) == "0X")) {
            token = token.substr(2);
        }

        size_t position = 0;
        const unsigned long value = std::stoul(token, &position, 16);
        if (position != token.size() || value > 255) {
            throw Error("invalid hex byte: " + token);
        }
        data.push_back(static_cast<uint8_t>(value));
    }

    if (data.empty()) {
        throw Error("no hex bytes supplied");
    }
    return data;
}

struct TargetArgs {
    std::string ip;
    uint16_t port;
    double timeout;

    TargetArgs()
        : port(DEFAULT_PORT), timeout(DEFAULT_TIMEOUT) {}
};

TargetArgs parse_target(int argc, char** argv, int start) {
    if (start >= argc) {
        throw Error("missing IP address");
    }

    TargetArgs target;
    target.ip = argv[start++];

    for (int i = start; i < argc; ++i) {
        const std::string option = argv[i];
        if (option == "--port" && i + 1 < argc) {
            const unsigned long value = std::stoul(argv[++i]);
            if (value == 0 || value > 65535) {
                throw Error("invalid port");
            }
            target.port = static_cast<uint16_t>(value);
        } else if (option == "--timeout" && i + 1 < argc) {
            target.timeout = std::stod(argv[++i]);
            if (target.timeout <= 0) {
                throw Error("timeout must be positive");
            }
        } else {
            throw Error("unknown option: " + option);
        }
    }
    return target;
}

TargetArgs parse_target_with_trailing_options(
    const std::string& program, const std::string& ip,
    int argc, char** argv, int option_start) {
    std::vector<std::string> arguments;
    arguments.push_back(program);
    arguments.push_back(ip);
    for (int i = option_start; i < argc; ++i) {
        arguments.push_back(argv[i]);
    }

    std::vector<char*> argument_pointers;
    for (size_t i = 0; i < arguments.size(); ++i) {
        argument_pointers.push_back(&arguments[i][0]);
    }

    return parse_target(static_cast<int>(argument_pointers.size()),
                        &argument_pointers[0], 1);
}

void usage(const char* program) {
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
        << "  write IP FILE [--port N] [--timeout SEC]"
           "  (use mpc-mpcx-ip-writer)\n\n"
        << "Defaults:\n"
        << "  --port N       RBCP UDP port (default: "
        << DEFAULT_PORT << ")\n"
        << "  --timeout SEC  RBCP timeout in seconds (default: "
        << DEFAULT_TIMEOUT << ")\n"
        << "  probe LENGTH   bytes to read (default: 1)\n";
}

}  // namespace

inline int run_mpc_mpcx_command(int argc, char** argv) {
    try {
        if (argc < 2 || std::string(argv[1]) == "-h" ||
            std::string(argv[1]) == "--help") {
            usage(argv[0]);
            return argc < 2 ? 2 : 0;
        }

        const std::string command = argv[1];

        if (command == "inspect") {
            if (argc != 3) {
                throw Error("usage: inspect MPC_OR_MPCX_FILE");
            }

            const std::vector<uint8_t> payload = read_file(argv[2]);
            const int type = classify(payload);
            field("command", "inspect");
            field("file", argv[2]);
            field("size", std::to_string(payload.size()) + " bytes");
            field("payload type", type_name(type));
            field("writer type", std::to_string(type));
            if (type != 0) {
                field("MAC", mac_string(payload_mac(payload)));
            }
            field("payload", hex_bytes(payload));
            return type != 0 ? 0 : 2;
        }

        if (command == "mac") {
            if (argc != 3) {
                throw Error("usage: mac MPC_OR_MPCX_FILE");
            }

            const std::vector<uint8_t> payload = read_file(argv[2]);
            const int type = classify(payload);
            if (type == 0) {
                throw Error("invalid/unknown 22-byte MPC/MPCX payload");
            }

            field("command", "mac");
            field("file", argv[2]);
            field("payload type", type_name(type));
            field("MAC", mac_string(payload_mac(payload)));
            return 0;
        }

        if (command == "read") {
            const TargetArgs target = parse_target(argc, argv, 2);
            RbcpClient client(target.ip, target.port, target.timeout);
            const std::vector<uint8_t> eeprom =
                read_exact(client, EEPROM_BASE, 0x50);

            field("command", "read");
            field("target",
                  target.ip + ":" + std::to_string(target.port));
            field("EEPROM FC00..FC4F", hex_bytes(eeprom));
            field("status", "READ OK");
            return 0;
        }

        if (command == "probe") {
            if (argc < 4) {
                throw Error("usage: probe IP ADDRESS [LENGTH]");
            }

            const std::string ip = argv[2];
            const uint32_t address = parse_u32(argv[3]);
            size_t length = 1;
            int option_start = 4;
            if (option_start < argc &&
                std::string(argv[option_start]).find("--") != 0) {
                length = std::stoul(argv[option_start++], 0, 0);
            }

            const TargetArgs target = parse_target_with_trailing_options(
                argv[0], ip, argc, argv, option_start);
            RbcpClient client(target.ip, target.port, target.timeout);
            const std::vector<uint8_t> data = client.read(address, length);

            field("command", "probe");
            field("target",
                  target.ip + ":" + std::to_string(target.port));
            field("address", hex_address(address));
            field("data", hex_bytes(data));
            field("status", "RBCP REACHABLE");
            return 0;
        }

        if (command == "rbcp-read") {
            if (argc < 5) {
                throw Error("usage: rbcp-read IP ADDRESS LENGTH");
            }

            const std::string ip = argv[2];
            const uint32_t address = parse_u32(argv[3]);
            const size_t length = std::stoul(argv[4], 0, 0);
            const TargetArgs target = parse_target_with_trailing_options(
                argv[0], ip, argc, argv, 5);

            RbcpClient client(target.ip, target.port, target.timeout);
            const std::vector<uint8_t> data = client.read(address, length);

            field("command", "rbcp-read");
            field("address", hex_address(address));
            field("data", hex_bytes(data));
            return 0;
        }

        if (command == "rbcp-write") {
            if (argc < 5) {
                throw Error("usage: rbcp-write IP ADDRESS HEX-BYTES");
            }

            const std::string ip = argv[2];
            const uint32_t address = parse_u32(argv[3]);
            const std::vector<uint8_t> bytes = parse_hex(argv[4]);
            const TargetArgs target = parse_target_with_trailing_options(
                argv[0], ip, argc, argv, 5);

            RbcpClient client(target.ip, target.port, target.timeout);
            const std::vector<uint8_t> ack = client.write(address, bytes);
            if (ack.size() != bytes.size()) {
                throw Error("unexpected RBCP ACK length");
            }

            field("command", "rbcp-write");
            field("address", hex_address(address));
            field("data", hex_bytes(bytes));
            field("status", "WRITE OK");
            return 0;
        }

        if (command == "verify" || command == "mpcx-plan") {
            if (argc < 4) {
                throw Error("missing IP or FILE");
            }

            const std::string ip = argv[2];
            const std::string file = argv[3];
            const std::vector<uint8_t> payload = read_file(file);
            const int type = classify(payload);
            if (type == 0) {
                throw Error("invalid/unknown 22-byte MPC/MPCX payload");
            }

            const TargetArgs target = parse_target_with_trailing_options(
                argv[0], ip, argc, argv, 4);
            RbcpClient client(target.ip, target.port, target.timeout);
            const std::vector<uint8_t> eeprom =
                read_exact(client, EEPROM_BASE, 0x50);

            if (command == "mpcx-plan") {
                if (type != 1) {
                    throw Error("payload is not classified as SiTCP-XG");
                }

                const std::vector<uint8_t> identifier =
                    rbcp::read_retry(client, 0xFFFFFF08u, 4);
                const std::vector<uint8_t> xg_identifier = {0x58, 0x54, 0x43, 0x50};
                if (identifier != xg_identifier) {
                    throw Error("mpcx-plan requires a SiTCP-XG target");
                }
                bool initialized = false;
                const std::vector<uint8_t> expected =
                    sitcp_sitcpxg::eeprom_init::prepare_mpcx_image(
                        client, eeprom, payload, initialized);
                field("command", "mpcx-plan");
                field("EEPROM initialization", initialized
                      ? "current RAM settings" : "not needed; preserve EEPROM");
                field("FC10..FC11 source", initialized ? "runtime" : "EEPROM");
                field("write range", initialized
                      ? "0xFFFFFC00..0xFFFFFC4F" : "0xFFFFFC00..0xFFFFFC17");
                field("EEPROM record", hex_bytes(expected));
                field("status", "NO WRITE PERFORMED");
                return 0;
            }

            bool matches = false;
            if (type == 1) {
                std::vector<uint8_t> expected(
                    eeprom.begin(), eeprom.begin() + 24);
                std::copy(payload.begin(), payload.begin() + 16,
                          expected.begin());
                std::copy(payload.begin() + 16, payload.end(),
                          expected.begin() + 18);
                matches = std::equal(
                    expected.begin(), expected.end(), eeprom.begin());
            } else {
                matches =
                    std::equal(payload.begin(), payload.begin() + 6,
                               eeprom.begin() + 0x12) &&
                    std::equal(payload.begin() + 6, payload.end(),
                               eeprom.begin() + 0x40);
            }

            field("command", "verify");
            field("file type", type_name(type));
            field("match", matches ? "YES" : "NO");
            field("status", matches ? "VERIFY OK" : "VERIFY FAILED");
            return matches ? 0 : 6;
        }

        if (command == "clear") {
            if (argc < 4 ||
                std::string(argv[3]) != "--yes-really-clear") {
                throw Error(
                    "clear is destructive; add --yes-really-clear "
                    "immediately after IP");
            }

            const std::string ip = argv[2];
            const TargetArgs target = parse_target_with_trailing_options(
                argv[0], ip, argc, argv, 4);
            RbcpClient client(target.ip, target.port, target.timeout);

            sitcp_sitcpxg::eeprom_clear::clear_and_verify(client);

            field("command", "clear");
            field("EEPROM area", "0xFFFFFC00..0xFFFFFC7F");
            field("read-back verify", "OK");
            field("EEPROM write protect", "ENABLED");
            field("status", "CLEAR OK");
            return 0;
        }

        if (command == "write") {
            std::cerr
                << "Use mpc-mpcx-ip-writer for the verified "
                   "high-level write path.\n";
            return 8;
        }

        throw Error("unknown command: " + command);
    } catch (const std::exception& error) {
        std::cerr << "ERROR: " << error.what() << '\n';
        return 1;
    }
}
