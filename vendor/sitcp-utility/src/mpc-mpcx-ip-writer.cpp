#include "sitcp-sitcpxg-network-config.hpp"
#include "sitcp-sitcpxg-eeprom-init.hpp"
#include "sitcp-sitcpxg-eeprom-clear.hpp"
#include "sitcp-sitcpxg-rbcp.hpp"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace {
constexpr double DEFAULT_TIMEOUT = sitcp_sitcpxg::rbcp::DEFAULT_TIMEOUT;
constexpr uint16_t DEFAULT_PORT = sitcp_sitcpxg::rbcp::DEFAULT_PORT;
constexpr uint32_t EEPROM_BASE = 0xFFFFFC00u;
constexpr uint32_t EEPROM_WRITE_ENABLE = 0xFFFFFCFFu;
constexpr uint32_t XG_IDENTIFIER = 0xFFFFFF08u;
constexpr size_t EEPROM_READ_SIZE = 0x50;
constexpr size_t MPC_FILE_SIZE = 22;
constexpr int FIELD_WIDTH = 20;
constexpr int EEPROM_WRITE_SETTLE_MS = 500;
constexpr size_t DEFAULT_WRITE_CHUNK_SIZE = 0;  // Entire prepared image.

namespace rbcp = sitcp_sitcpxg::rbcp;
using RbcpClient = rbcp::Client;
using RbcpError = rbcp::Error;
using RbcpTimeout = rbcp::Timeout;
using RbcpBusError = rbcp::BusError;

size_t parse_write_chunk_size(const std::string& value) {
    if (value == "official") {
        return DEFAULT_WRITE_CHUNK_SIZE;
    }
    if (value.empty() ||
        value.find_first_not_of("0123456789") != std::string::npos) {
        throw std::runtime_error("write chunk size must be an integer from 1 to 255 bytes");
    }
    const unsigned long size = std::stoul(value);
    if (size == 0 || size > 255) {
        throw std::runtime_error("write chunk size must be from 1 to 255 bytes");
    }
    return static_cast<size_t>(size);
}

std::vector<uint8_t> read_exact(
    RbcpClient& client, uint32_t address, size_t length,
    size_t chunk_size = 8) {
    std::vector<uint8_t> data;
    for (size_t offset = 0; offset < length; offset += chunk_size) {
        const size_t block_size =
            std::min(chunk_size, length - offset);
        const std::vector<uint8_t> block = rbcp::read_retry(
            client, address + static_cast<uint32_t>(offset), block_size);
        data.insert(data.end(), block.begin(), block.end());
    }
    return data;
}

void settle_eeprom_write() {
    // Wait after the ACK as well: this conservatively guarantees at least
    // 500 ms between writes, even when the previous transaction was slow.
    std::this_thread::sleep_for(
        std::chrono::milliseconds(EEPROM_WRITE_SETTLE_MS));
}

void write_exact(
    RbcpClient& client, uint32_t address,
    const std::vector<uint8_t>& data, size_t chunk_size) {
    for (size_t offset = 0; offset < data.size(); offset += chunk_size) {
        const size_t block_size =
            std::min(chunk_size, data.size() - offset);
        const std::vector<uint8_t> block(
            data.begin() + offset,
            data.begin() + offset + block_size);
        const std::vector<uint8_t> ack = client.write(
            address + static_cast<uint32_t>(offset), block);
        settle_eeprom_write();
        if (ack.size() != block_size) {
            throw RbcpError(
                "short RBCP ACK while writing EEPROM");
        }
    }
}

void field(const std::string& name, const std::string& value) {
    std::cout << std::left << std::setw(FIELD_WIDTH)
              << name << ": " << value << '\n';
}

bool valid_tag(const std::vector<uint8_t>& tag) {
    if (tag.size() != 7) {
        return false;
    }

    for (size_t i = 0; i < tag.size(); ++i) {
        const uint8_t value = tag[i];
        if (value == 0 || value == 0x20 || value == '-' ||
            (value >= '0' && value <= '9')) {
            continue;
        }

        const uint8_t uppercase =
            static_cast<uint8_t>(value & 0xDF);
        if (uppercase >= 'A' && uppercase <= 'Z') {
            continue;
        }
        return false;
    }
    return true;
}

std::vector<uint8_t> decode_nonzero(const std::vector<uint8_t>& d, size_t begin,
                                    size_t len, uint8_t delta) {
    std::vector<uint8_t> out;
    out.reserve(len);
    for (size_t i = 0; i < len; ++i) {
        const uint8_t b = d[begin + i];
        out.push_back(b ? static_cast<uint8_t>(b - delta) : 0);
    }
    return out;
}

int classify_payload(const std::vector<uint8_t>& data) {
    if (data.size() != MPC_FILE_SIZE) {
        return 0;
    }
    if (valid_tag(decode_nonzero(data, 6, 7, 0x34))) {
        return 2;
    }
    if (valid_tag(decode_nonzero(data, 0, 7, 0x2C))) {
        return 1;
    }
    return 0;
}

int detect_target(RbcpClient& c, std::string& why) {
    try {
        const auto identifier = rbcp::read_retry(c, XG_IDENTIFIER, 4);
        const std::vector<uint8_t> expected = {0x58, 0x54, 0x43, 0x50};
        if (identifier == expected) {
            why = "SiTCP-XG identifier: 0x58544350";
            return 1;
        }
        why = "SiTCP-XG identifier mismatch";
        return 2;
    } catch (const RbcpBusError&) {
        why = "SiTCP-XG identifier register: not supported";
        return 2;
    } catch (const RbcpTimeout&) {
        why = "SiTCP-XG identifier register: timeout";
        return -1;
    }
}

std::vector<uint8_t> read_file(const std::string& path) {
    std::ifstream input(path.c_str(), std::ios::binary);
    if (!input) {
        throw std::runtime_error("cannot open file: " + path);
    }

    return std::vector<uint8_t>(
        std::istreambuf_iterator<char>(input),
        std::istreambuf_iterator<char>());
}

void set_write_enable(RbcpClient& c, bool enabled) {
    const auto ack = c.write(EEPROM_WRITE_ENABLE,
                             {static_cast<uint8_t>(enabled ? 0x00 : 0xFF)});
    settle_eeprom_write();
    if (ack.size() != 1) {
        throw RbcpError("unexpected RBCP ACK length for EEPROM write-enable");
    }
}

std::vector<uint8_t> program(
    RbcpClient& client, const std::vector<uint8_t>& payload, int type,
    const std::vector<uint8_t>& eeprom, size_t requested_chunk_size,
    bool allow_fallback, bool force_initialization) {
    std::vector<uint8_t> image;
    bool initialized = false;
    std::vector<std::pair<uint32_t, std::vector<uint8_t>>> extensions;
    uint32_t programming_base = EEPROM_BASE;
    if (type == 1) {
        image = sitcp_sitcpxg::eeprom_init::prepare_mpcx_image(
            client, eeprom, payload, initialized, force_initialization);
    } else {
        image = sitcp_sitcpxg::eeprom_init::prepare_mpc_image(
            client, eeprom, payload, allow_fallback);
        programming_base = EEPROM_BASE + 0x10;
    }
    const size_t write_chunk_size =
        requested_chunk_size == DEFAULT_WRITE_CHUNK_SIZE
            ? image.size() : requested_chunk_size;

    try {
        set_write_enable(client, true);
        write_exact(client, programming_base, image, write_chunk_size);
        if (type == 1 && initialized) {
            for (uint32_t offset = 0x50; offset < 0x80; offset += 16) {
                std::vector<uint8_t> block;
                try {
                    block = rbcp::read_retry(client, 0xFFFFFF00u + offset, 16);
                } catch (const RbcpError&) {
                    // Optional source: preserve EEPROM if this block cannot be read.
                    continue;
                }
                const uint32_t address = EEPROM_BASE + offset;
                write_exact(
                    client, address, block,
                    requested_chunk_size == 0 ? 16 : requested_chunk_size);
                extensions.push_back(std::make_pair(address, block));
            }
        }
    } catch (...) {
        // An unacknowledged data write may have been accepted. Allow settling,
        // then attempt protection without repeating the data write.
        settle_eeprom_write();
        try {
            set_write_enable(client, false);
        } catch (...) {
        }
        throw;
    }
    set_write_enable(client, false);

    const auto actual = read_exact(client, programming_base, image.size());
    for (const auto& extension : extensions) {
        if (read_exact(client, extension.first, extension.second.size()) !=
            extension.second) {
            throw RbcpError("EEPROM extension read-back verification failed");
        }
    }
    if (actual != image) {
        size_t i = 0;
        while (i < image.size() && actual[i] == image[i]) {
            ++i;
        }
        std::ostringstream os;
        os << "EEPROM read-back verification failed";
        if (i < image.size()) {
            os << " at 0x" << std::hex << (programming_base + i)
               << ": expected 0x" << static_cast<unsigned>(image[i])
               << ", got 0x" << static_cast<unsigned>(actual[i]);
        }
        throw RbcpError(os.str());
    }
    return actual;
}

void usage(const char* argv0) {
    std::cerr << "Usage: " << argv0 << " <ip> <file> [options]\n\n"
              << "Options:\n"
              << "  --port N       RBCP UDP port (default: " << DEFAULT_PORT << ")\n"
              << "  --timeout SEC  RBCP timeout in seconds (default: " << DEFAULT_TIMEOUT << ")\n"
              << "  --no-fallback        Stop if normal-MPC initialization RAM is unreadable (default: off)\n"
              << "  --initialize-eeprom  Force XG initialization; normal MPC unchanged (default: off)\n"
              << "  --write-chunk-size N  1..255 bytes, or official (default: official)\n"
              << "                        (default: entire image; use 16 to split)\n"
              << "  -h, --help     Show this help\n";
}
}

inline int run_mpc_mpcx_writer(int argc, char** argv) {
    try {
        if (argc == 2 && (std::string(argv[1]) == "-h" || std::string(argv[1]) == "--help")) {
            usage(argv[0]);
            return 0;
        }
        if (argc < 3) {
            usage(argv[0]);
            return 2;
        }

        const std::string ip = argv[1];
        const std::string file_path = argv[2];
        uint16_t port = DEFAULT_PORT;
        double timeout = DEFAULT_TIMEOUT;
        size_t write_chunk_size = DEFAULT_WRITE_CHUNK_SIZE;
        bool allow_fallback = true;
        bool force_initialization = false;

        for (int i = 3; i < argc; ++i) {
            const std::string a = argv[i];
            if (a == "--port" && i + 1 < argc) {
                const unsigned long p = std::stoul(argv[++i]);
                if (p == 0 || p > 65535) {
                    throw std::runtime_error("invalid port");
                }
                port = static_cast<uint16_t>(p);
            } else if (a == "--timeout" && i + 1 < argc) {
                timeout = std::stod(argv[++i]);
                if (timeout <= 0) {
                    throw std::runtime_error("timeout must be positive");
                }
            } else if (a == "--no-fallback") {
                allow_fallback = false;
            } else if (a == "--initialize-eeprom") {
                force_initialization = true;
            } else if (a == "--write-chunk-size" && i + 1 < argc) {
                write_chunk_size = parse_write_chunk_size(argv[++i]);
            } else if (a == "-h" || a == "--help") {
                usage(argv[0]);
                return 0;
            } else {
                throw std::runtime_error("unknown option: " + a);
            }
        }

        const auto payload = read_file(file_path);
        const int file_type = classify_payload(payload);
        if (payload.size() != MPC_FILE_SIZE || !(file_type == 1 || file_type == 2)) {
            std::cerr << "ERROR: invalid/unknown 22-byte MPC payload (writer type "
                      << file_type << ")\n";
            return 2;
        }

        RbcpClient client(ip, port, timeout);
        std::string detection;
        const int target_type = detect_target(client, detection);

        if ((target_type == 1 || target_type == 2) && target_type != file_type) {
            field("status", "REFUSED: TARGET TYPE MISMATCH");
            return 7;
        }
        if (!(target_type == 1 || target_type == 2)) {
            field("status", "REFUSED: TARGET TYPE NOT DETECTED");
            return 7;
        }

        const uint32_t read_base = file_type == 1
            ? EEPROM_BASE : EEPROM_BASE + 0x10;
        const size_t read_size = file_type == 1 ? EEPROM_READ_SIZE : 64;
        const std::vector<uint8_t> eeprom =
            read_exact(client, read_base, read_size);
        program(client, payload, file_type, eeprom, write_chunk_size,
                allow_fallback, force_initialization);
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "ERROR: " << e.what() << "\n";
        return 1;
    }
}


namespace {

int check_device(const std::string& host, const std::string& file,
                 uint16_t port, double timeout) {
    int file_type = 0;
    std::string file_label;
    if (!file.empty()) {
        const std::vector<uint8_t> payload = read_file(file);
        file_type = classify_payload(payload);
        if (payload.size() != MPC_FILE_SIZE ||
            (file_type != 1 && file_type != 2)) {
            throw RbcpError("invalid/unknown 22-byte MPC/MPCX payload");
        }
        const std::vector<uint8_t> tag = decode_nonzero(
            payload, file_type == 1 ? 0 : 6, 7, file_type == 1 ? 0x2C : 0x34);
        for (size_t i = 0; i < tag.size() && tag[i] != 0; ++i) {
            file_label.push_back(static_cast<char>(tag[i]));
        }
        while (!file_label.empty() && file_label.back() == ' ') {
            file_label.pop_back();
        }
    }

    RbcpClient client(host, port, timeout);
    std::string detection;
    const int target_type = detect_target(client, detection);
    if (target_type != 1 && target_type != 2) {
        throw RbcpError("Check failed: " + detection);
    }
    const std::vector<uint8_t> control =
        rbcp::read_retry(client, EEPROM_BASE + 0x10, 1);
    std::cout << "MPC(X) File : "
              << (file.empty() ? "Not Selected." : file_label) << '\n';
    if (!file.empty()) {
        std::cout << "  Interface : "
                  << (file_type == 1 ? "10GbE" : "100/1000MbE") << '\n';
    }
    std::cout << "Device " << host << " : "
              << (target_type == 1 ? "SiTCP XG" : "SiTCP 100/1000M");
    if (!file.empty()) {
        std::cout << (file_type == target_type ? " - Matched" : " - Mismatch");
    }
    // Preserve the native GUI's wording, including its uninitialized-state typo.
    std::cout << '\n' << ((control[0] & 0x80u) != 0
              ? "EEOROM needs to be inbitialized."
              : "EEPROM was already initialized") << '\n';
    return !file.empty() && file_type != target_type ? 7 : 0;
}

void unified_usage(const char* program) {
    std::cerr
        << "Usage: " << program << " CURRENT_IP MPC_OR_MPCX_FILE [options]\n"
        << "       " << program << " CURRENT_IP --clear [--port N] [--timeout SEC]\n"
        << "       " << program << " CURRENT_IP [FILE] --check [--port N] [--timeout SEC]\n\n"
        << "Programs an MPC/MPCX file and optionally changes the SiTCP IP address.\n"
        << "For uninitialized MPCX EEPROM (FC10 bit7 set), restores settings\n"
        << "from complete runtime FF00..FF4F before overlaying the MPCX file.\n"
        << "If runtime cannot be read, stops before writing; no guessed defaults.\n\n"
        << "Normal MPC writes FC10..FC4F, sets control to 0x01 and restores\n"
        << "runtime FF18..FF3F if the first/last EEPROM IP octets are FF.\n"
        << "Unreadable normal-MPC runtime uses official defaults (IP 192.168.10.16).\n\n"
        << "Options:\n"
        << "  --check              Read-only target/EEPROM flag check; optional file type match (default: off)\n"
        << "  --initialize-eeprom  Force XG RAM-to-EEPROM initialization (default: off)\n"
        << "                       Requires a file; normal MPC keeps its automatic rule, as native GUI\n"
        << "  --clear              Clear only: erase EEPROM FC00..FC7F (default: off)\n"
        << "                       Deletes license/settings; no file or IP changes allowed\n"
        << "  --set-eeprom-ip IP   Set EEPROM/default IP address\n"
        << "  --set-current-ip IP  Set current/runtime IP address\n"
        << "  --no-fallback       Stop on unreadable normal-MPC initialization RAM (default: off)\n"
        << "  --write-chunk-size N 1..255 bytes, or official (default: official)\n"
        << "                       (default: entire image; MPC 64, MPCX 24 or 80 bytes)\n"
        << "                       Use official for native lengths, 16 to split; not valid with --clear\n"
        << "  --port N             RBCP UDP port (default: "
        << sitcp_sitcpxg::network_config::DEFAULT_PORT << ")\n"
        << "  --timeout SEC        RBCP timeout in seconds (default: "
        << sitcp_sitcpxg::network_config::DEFAULT_TIMEOUT << ")\n"
        << "  -h, --help           Show this help\n";
}

}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 2 &&
            (std::string(argv[1]) == "-h" ||
             std::string(argv[1]) == "--help")) {
            unified_usage(argv[0]);
            return 0;
        }

        if (argc < 3) {
            unified_usage(argv[0]);
            return 2;
        }

        const std::string host = argv[1];
        const bool has_file = std::string(argv[2]).find("--") != 0;
        const std::string file = has_file ? argv[2] : "";
        bool clear_only = false;
        bool check_only = false;
        bool has_chunk_option = false;

        bool has_eeprom_ip = false;
        bool has_current_ip = false;
        std::string eeprom_ip;
        std::string current_ip;
        uint16_t port = sitcp_sitcpxg::network_config::DEFAULT_PORT;
        double timeout = sitcp_sitcpxg::network_config::DEFAULT_TIMEOUT;
        size_t write_chunk_size = DEFAULT_WRITE_CHUNK_SIZE;
        bool allow_fallback = true;
        bool force_initialization = false;

        for (int i = has_file ? 3 : 2; i < argc; ++i) {
            const std::string option = argv[i];

            if (option == "--clear") {
                clear_only = true;
            } else if (option == "--check") {
                check_only = true;
            } else if (option == "--initialize-eeprom") {
                force_initialization = true;
            } else if (option == "--set-eeprom-ip" && i + 1 < argc) {
                eeprom_ip = argv[++i];
                has_eeprom_ip = true;
                (void)sitcp_sitcpxg::network_config::parse_ipv4(eeprom_ip);
            } else if (option == "--set-current-ip" && i + 1 < argc) {
                current_ip = argv[++i];
                has_current_ip = true;
                (void)sitcp_sitcpxg::network_config::parse_ipv4(current_ip);
            } else if (option == "--port" && i + 1 < argc) {
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
            } else if (option == "--no-fallback") {
                allow_fallback = false;
            } else if (option == "--write-chunk-size" && i + 1 < argc) {
                write_chunk_size = parse_write_chunk_size(argv[++i]);
                has_chunk_option = true;
            } else if (option == "-h" || option == "--help") {
                unified_usage(argv[0]);
                return 0;
            } else {
                throw std::runtime_error("unknown option: " + option);
            }
        }

        if (clear_only && (has_file || has_eeprom_ip || has_current_ip ||
                           has_chunk_option || !allow_fallback ||
                           force_initialization || check_only)) {
            throw std::runtime_error(
                "--clear is clear-only; do not specify a file, IP changes or programming options");
        }
        if (check_only && (has_eeprom_ip || has_current_ip || has_chunk_option ||
                           !allow_fallback || force_initialization)) {
            throw std::runtime_error("--check is read-only; no programming options allowed");
        }
        if (!clear_only && !check_only && !has_file) {
            throw std::runtime_error("an MPC/MPCX file, --clear or --check is required");
        }
        if (check_only) {
            return check_device(host, file, port, timeout);
        }

        sitcp_sitcpxg::network_config::show_compact(host, port, timeout, "before");

        if (clear_only) {
            rbcp::Client client(host, port, timeout);
            sitcp_sitcpxg::eeprom_clear::clear_and_verify(client);
            sitcp_sitcpxg::network_config::show_compact(host, port, timeout, "after");
            sitcp_sitcpxg::network_config::print_success();
            return 0;
        }

        std::vector<std::string> writer_args;
        writer_args.push_back(argv[0]);
        writer_args.push_back(host);
        writer_args.push_back(file);
        writer_args.push_back("--port");
        writer_args.push_back(std::to_string(port));
        writer_args.push_back("--timeout");
        writer_args.push_back(std::to_string(timeout));
        if (write_chunk_size != DEFAULT_WRITE_CHUNK_SIZE) {
            writer_args.push_back("--write-chunk-size");
            writer_args.push_back(std::to_string(write_chunk_size));
        }

        if (!allow_fallback) {
            writer_args.push_back("--no-fallback");
        }
        if (force_initialization) {
            writer_args.push_back("--initialize-eeprom");
        }

        std::vector<char*> writer_argv;
        for (std::vector<std::string>::iterator it = writer_args.begin();
             it != writer_args.end(); ++it) {
            writer_argv.push_back(&(*it)[0]);
        }

        const int writer_result = run_mpc_mpcx_writer(
            static_cast<int>(writer_argv.size()), &writer_argv[0]);
        if (writer_result != 0) {
            return writer_result;
        }

        if (has_eeprom_ip) {
            sitcp_sitcpxg::network_config::write_eeprom_ip(host, eeprom_ip, port, timeout);
        }

        std::string final_host = host;
        if (has_current_ip) {
            sitcp_sitcpxg::network_config::write_current_ip(host, current_ip, port, timeout);
            final_host = current_ip;
        }

        sitcp_sitcpxg::network_config::show_compact(final_host, port, timeout, "after");
        sitcp_sitcpxg::network_config::print_success();
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "ERROR: " << error.what() << '\n';
        return 1;
    }
}
