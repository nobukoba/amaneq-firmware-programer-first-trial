#pragma once

#include "sitcp-sitcpxg-network-config.hpp"

#include <algorithm>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

namespace sitcp_sitcpxg {
namespace register_report {

namespace rbcp = sitcp_sitcpxg::rbcp;

constexpr uint32_t EEPROM_BASE = 0xFFFFFC00u;
constexpr uint32_t XG_IDENTIFIER = 0xFFFFFF08u;
constexpr int FIELD_WIDTH = 20;

struct RegisterImage {
    std::vector<uint8_t> bytes;
    std::vector<bool> readable;

    explicit RegisterImage(size_t length)
        : bytes(length, 0), readable(length, false) {}

    bool has(size_t offset, size_t length) const {
        for (size_t i = offset; i < offset + length; ++i) {
            if (!readable.at(i)) {
                return false;
            }
        }
        return true;
    }
};

inline std::string address_string(uint32_t address) {
    std::ostringstream output;
    output << "0x" << std::hex << std::uppercase
           << std::setfill('0') << std::setw(8) << address;
    return output.str();
}

inline RegisterImage read_image(rbcp::Client& client, uint32_t base,
                                size_t length) {
    RegisterImage image(length);
    for (size_t offset = 0; offset < image.bytes.size(); offset += 8) {
        const size_t chunk_size = std::min<size_t>(8, image.bytes.size() - offset);
        try {
            const std::vector<uint8_t> block = rbcp::read_retry(
                client, base + static_cast<uint32_t>(offset), chunk_size);
            std::copy(block.begin(), block.end(), image.bytes.begin() + offset);
            std::fill(image.readable.begin() + offset,
                      image.readable.begin() + offset + chunk_size, true);
        } catch (const rbcp::BusError&) {
            // A block may cross a reserved byte. Recover each readable byte.
            for (size_t i = offset; i < offset + chunk_size; ++i) {
                const uint32_t address = base + static_cast<uint32_t>(i);
                try {
                    image.bytes[i] = rbcp::read_retry(client, address, 1).at(0);
                    image.readable[i] = true;
                } catch (const rbcp::BusError&) {
                    std::cerr << "WARNING: RBCP bus error at "
                              << address_string(address) << " (shown as unreadable bytes)\n";
                } catch (const rbcp::Error& error) {
                    throw rbcp::Error(address_string(address) + ": " + error.what());
                }
            }
        } catch (const rbcp::Error& error) {
            throw rbcp::Error(address_string(base + static_cast<uint32_t>(offset)) +
                              ": " + error.what());
        }
    }
    return image;
}

inline std::vector<uint8_t> reconstruct_mpcx_payload(
    const std::vector<uint8_t>& eeprom) {
    std::vector<uint8_t> payload(eeprom.begin(), eeprom.begin() + 16);
    payload.insert(payload.end(), eeprom.begin() + 18, eeprom.begin() + 24);
    return payload;
}

inline std::vector<uint8_t> reconstruct_mpc_payload(
    const std::vector<uint8_t>& eeprom) {
    std::vector<uint8_t> payload(
        eeprom.begin() + 0x12, eeprom.begin() + 0x18);
    payload.insert(
        payload.end(), eeprom.begin() + 0x40, eeprom.begin() + 0x50);
    return payload;
}

inline std::string hex_bytes(const std::vector<uint8_t>& data,
                      size_t begin = 0, size_t end = static_cast<size_t>(-1),
                      char separator = ' ') {
    end = std::min(end, data.size());

    std::ostringstream output;
    output << std::hex << std::uppercase << std::setfill('0');
    for (size_t i = begin; i < end; ++i) {
        if (i != begin) {
            output << separator;
        }
        output << std::setw(2) << static_cast<unsigned>(data[i]);
    }
    return output.str();
}

inline void field(const std::string& name, const std::string& value) {
    std::cout << std::left << std::setw(FIELD_WIDTH)
              << name << ": " << value << '\n';
}

inline uint16_t be16(const std::vector<uint8_t>& data, size_t offset) {
    return static_cast<uint16_t>(
        (static_cast<uint16_t>(data[offset]) << 8) |
        static_cast<uint16_t>(data[offset + 1]));
}

inline std::string format_mac(const std::vector<uint8_t>& data, size_t offset) {
    return hex_bytes(data, offset, offset + 6, ':');
}

inline std::string format_ipv4(const std::vector<uint8_t>& data, size_t offset) {
    return network_config::ipv4_string(
        std::vector<uint8_t>(data.begin() + offset, data.begin() + offset + 4));
}

inline std::string decimal_hex(uint32_t value, int width = 4) {
    std::ostringstream output;
    output << std::dec << value << " (0x" << std::hex << std::uppercase
           << std::setfill('0') << std::setw(width) << value << ")";
    return output.str();
}

inline std::string numeric_value(const RegisterImage& image, size_t offset,
                                 const std::string& unit = "") {
    return image.has(offset, 2)
        ? decimal_hex(be16(image.bytes, offset)) + unit
        : "unavailable (RBCP bus error)";
}

inline std::string mac_value(const RegisterImage& image, size_t offset) {
    return image.has(offset, 6) ? format_mac(image.bytes, offset)
                              : "unavailable (RBCP bus error)";
}

inline std::string ip_value(const RegisterImage& image, size_t offset) {
    return image.has(offset, 4) ? format_ipv4(image.bytes, offset)
                              : "unavailable (RBCP bus error)";
}

inline void setting_field(const std::string& name, const std::string& value) {
    std::cout << std::left << std::setw(36)
              << name << ": " << value << '\n';
}

inline void control_flag(const RegisterImage& image, const std::string& name,
                         uint8_t mask) {
    setting_field(name, image.has(0x10, 1)
          ? ((image.bytes[0x10] & mask) ? "Enabled" : "Disabled")
          : "unavailable (RBCP bus error)");
}

inline void show_parameters(const RegisterImage& image, bool xg) {
    setting_field("TCP Port", numeric_value(image, 0x1C));
    setting_field("UDP Port", numeric_value(image, 0x22));
    if (!xg) {
        setting_field("TCP Command Port", numeric_value(image, 0x1E));
    }
    std::cout << "\nTCP settings:\n";
    setting_field("TCP Max Segment Size", numeric_value(image, 0x20, " bytes"));
    control_flag(image, "TCP Keep Alive Enabled", 0x04);
    setting_field("TCP Keep Alive(buffer not empty)", numeric_value(image, 0x24, " ms"));
    setting_field("TCP Keep Alive(buffer empty)", numeric_value(image, 0x26, " ms"));
    setting_field("TCP Timeout(Connecting)", numeric_value(image, 0x28, " ms"));

    std::ostringstream disconnect;
    disconnect << numeric_value(image, 0x2A);
    if (image.has(0x2A, 2)) {
        const double seconds =
            (be16(image.bytes, 0x2A) + (xg ? 1.0 : 0.0)) * 0.256;
        disconnect << " (" << std::fixed << std::setprecision(3)
                   << seconds << " s, " << std::setprecision(2)
                   << seconds / 60.0 << " min)";
    }
    setting_field("TCP Timeout(Disconnect)", disconnect.str());

    if (xg) {
        std::ostringstream msl;
        msl << numeric_value(image, 0x2C);
        if (image.has(0x2C, 2)) {
            msl << " (" << std::fixed << std::setprecision(1)
                << be16(image.bytes, 0x2C) * 0.5 << " ms)";
        }
        setting_field("TCP MSL", msl.str());
    } else {
        setting_field("TCP Re-Connect Interval", numeric_value(image, 0x2C, " ms"));
    }
    setting_field("TCP Re-Transmition Timer", numeric_value(image, 0x2E, " ms"));
    std::cout << "\nClient / server settings:\n";
    setting_field("server MAC", mac_value(image, xg ? 0x32 : 0x30));
    setting_field("server IP", ip_value(image, xg ? 0x38 : 0x36));
    setting_field("server TCP port", numeric_value(image, xg ? 0x3C : 0x3A));
    std::cout << "\nControl settings:\n";
    setting_field("control register", image.has(0x10, 1)
          ? decimal_hex(image.bytes[0x10], 2)
          : "unavailable (RBCP bus error)");
    control_flag(image, "reset bit", 0x80);
    if (xg) {
        control_flag(image, "window scaling", 0x10);
    } else {
        control_flag(image, "client ARP", 0x40);
        control_flag(image, "duplicate ACK", 0x20);
        control_flag(image, "MIF initializer", 0x10);
        control_flag(image, "MAC flow control", 0x08);
    }
    control_flag(image, "fast retransmission", 0x02);
    control_flag(image, "Nagle buffering", 0x01);
    std::cout << "\nTransmission settings:\n";
    if (!xg) {
        setting_field("transmission rate", "not supported (normal SiTCP)");
        setting_field("rate note", "link speed / throughput not measured");
        return;
    }
    if (!image.has(0x40, 2)) {
        setting_field("transmission rate", "unavailable (RBCP bus error)");
    } else {
        const uint16_t rate = be16(image.bytes, 0x40);
        if (rate >= 1 && rate <= 10000) {
            setting_field("transmission rate", decimal_hex(rate) + " Mbps");
            setting_field("rate note", "configured line-rate limit; not measured throughput");
        } else {
            setting_field("transmission rate raw", decimal_hex(rate) +
                  " (outside documented range 1..10000)");
            setting_field("rate note", "raw value; may contain data unrelated to XG rate");
        }
    }
}

inline std::string type_name(int type) {
    if (type == 1) {
        return "MPCX (SiTCP-XG)";
    }
    if (type == 2) {
        return "MPC (normal SiTCP)";
    }
    if (type == -1) {
        return "ambiguous";
    }
    return "unknown";
}

inline int detect_target(rbcp::Client& client, std::string& reason) {
    try {
        const std::vector<uint8_t> identifier =
            rbcp::read_retry(client, XG_IDENTIFIER, 4);
        const std::vector<uint8_t> expected = {
            0x58, 0x54, 0x43, 0x50
        };
        if (identifier == expected) {
            reason = "SiTCP-XG identifier: 0x58544350";
            return 1;
        }

        reason = "SiTCP-XG identifier mismatch";
        return 2;
    } catch (const rbcp::BusError&) {
        reason = "SiTCP-XG identifier register: not supported";
        return 2;
    } catch (const rbcp::Timeout&) {
        reason = "SiTCP-XG identifier register: timeout";
        return -1;
    }
}

inline void dump(uint32_t base, const RegisterImage& image) {
    for (size_t offset = 0; offset < image.bytes.size(); offset += 16) {
        std::ostringstream line;
        line << std::hex << std::uppercase << std::setfill('0')
             << std::setw(8) << (base + offset) << ":";
        for (size_t i = offset; i < std::min(offset + 16, image.bytes.size()); ++i) {
            line << ' ';
            if (image.readable[i]) {
                line << std::setw(2) << static_cast<unsigned>(image.bytes[i]);
            } else {
                line << "??";
            }
        }
        std::cout << line.str() << '\n';
    }
}

inline bool show(const std::string& host, uint16_t port, double timeout) {
    rbcp::Client client(host, port, timeout);
    std::string detection;
    const int target_type = detect_target(client, detection);
    if (target_type != 1 && target_type != 2) {
        throw rbcp::Error("cannot select runtime read range: " + detection);
    }
    const size_t runtime_length = target_type == 1 ? 0x50 : 0x40;
    const RegisterImage runtime = read_image(client, 0xFFFFFF00u, runtime_length);
    const RegisterImage eeprom = read_image(client, EEPROM_BASE, 0x50);

    field("target", host + ":" + std::to_string(port));
    field("detected type", type_name(target_type));
    field("detection", detection);
    std::cout << "\nRuntime registers (0xFFFFFF00.."
              << address_string(0xFFFFFF00u + static_cast<uint32_t>(runtime_length) - 1)
              << ", " << std::to_string(runtime_length) << " bytes):\n";
    std::cout << "General settings:\n";
    field("current MAC", mac_value(runtime, 0x12));
    field("current IP", ip_value(runtime, 0x18));
    std::cout << '\n';
    show_parameters(runtime, target_type == 1);
    std::cout << '\n';
    std::cout << (target_type == 1 ? "raw runtime FF00..FF4F:\n"
                                  : "raw runtime FF00..FF3F:\n");
    dump(0xFFFFFF00u, runtime);

    std::cout << "\nEEPROM (0xFFFFFC00..0xFFFFFC4F, 80 bytes):\n";
    std::cout << "General settings:\n";
    field("EEPROM MAC", mac_value(eeprom, 0x12));
    field("EEPROM IP", ip_value(eeprom, 0x18));
    std::cout << '\n';
    show_parameters(eeprom, target_type == 1);
    std::cout << '\n';
    std::cout << "raw EEPROM FC00..FC4F:\n";
    dump(EEPROM_BASE, eeprom);

    std::cout << "\nMPC/MPCX information (EEPROM):\n";
    std::vector<uint8_t> payload;
    if (target_type == 1 && eeprom.has(0, 16) && eeprom.has(18, 6)) {
        payload = reconstruct_mpcx_payload(eeprom.bytes);
    } else if (target_type == 2 && eeprom.has(0x12, 6) && eeprom.has(0x40, 16)) {
        payload = reconstruct_mpc_payload(eeprom.bytes);
    }
    if (!payload.empty()) {
        field("reconstructed payload", hex_bytes(payload));
    } else {
        field("reconstructed payload", "unavailable");
    }
    field("MAC", mac_value(eeprom, 0x12));
    if (target_type == 1) {
        field("MPCX FC00..FC0F", eeprom.has(0, 16)
              ? hex_bytes(eeprom.bytes, 0, 16) : "unavailable");
    } else if (target_type == 2) {
        field("MPC FC40..FC4F", eeprom.has(0x40, 16)
              ? hex_bytes(eeprom.bytes, 0x40, 0x50) : "unavailable");
    }
    const bool complete = runtime.has(0, runtime_length) && eeprom.has(0, 80);
    field("register report", complete ? "COMPLETE" : "PARTIAL (?? = unreadable)");
    return complete;
}

}  // namespace register_report
}  // namespace sitcp_sitcpxg
