#pragma once

#include "sitcp-sitcpxg-rbcp.hpp"

#include <arpa/inet.h>
#include <algorithm>
#include <chrono>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

namespace sitcp_sitcpxg {
namespace network_config {

using rbcp::Client;
using rbcp::Error;
using rbcp::Timeout;

constexpr uint16_t DEFAULT_PORT = rbcp::DEFAULT_PORT;
constexpr double DEFAULT_TIMEOUT = rbcp::DEFAULT_TIMEOUT;

constexpr uint32_t CURRENT_MAC = 0xFFFFFF12u;
constexpr uint32_t CURRENT_IP = 0xFFFFFF18u;
constexpr uint32_t EEPROM_MAC = 0xFFFFFC12u;
constexpr uint32_t EEPROM_IP = 0xFFFFFC18u;
constexpr uint32_t EEPROM_WRITE_ENABLE = 0xFFFFFCFFu;

inline std::vector<uint8_t> parse_ipv4(const std::string& value) {
    in_addr address{};
    if (inet_pton(AF_INET, value.c_str(), &address) != 1) {
        throw Error("invalid IPv4 address: " + value);
    }

    const uint8_t* bytes =
        reinterpret_cast<const uint8_t*>(&address.s_addr);
    return {bytes[0], bytes[1], bytes[2], bytes[3]};
}

inline std::string ipv4_string(const std::vector<uint8_t>& data) {
    if (data.size() != 4) {
        throw Error("invalid IP read length");
    }

    std::ostringstream output;
    output << static_cast<unsigned>(data[0]) << '.'
           << static_cast<unsigned>(data[1]) << '.'
           << static_cast<unsigned>(data[2]) << '.'
           << static_cast<unsigned>(data[3]) << " (0x"
           << std::hex << std::uppercase << std::setfill('0');
    for (uint8_t byte : data) {
        output << std::setw(2) << static_cast<unsigned>(byte);
    }
    output << ')';
    return output.str();
}

inline std::string mac_string(const std::vector<uint8_t>& data) {
    if (data.size() != 6) {
        throw Error("invalid MAC read length");
    }

    std::ostringstream output;
    output << std::hex << std::uppercase << std::setfill('0');
    for (size_t i = 0; i < data.size(); ++i) {
        if (i != 0) {
            output << ':';
        }
        output << std::setw(2) << static_cast<unsigned>(data[i]);
    }
    return output.str();
}

struct Snapshot {
    std::vector<uint8_t> current_mac;
    std::vector<uint8_t> current_ip;
    std::vector<uint8_t> eeprom_mac;
    std::vector<uint8_t> eeprom_ip;
};

inline Snapshot read_snapshot(Client& client) {
    Snapshot snapshot;
    snapshot.current_mac = rbcp::read_retry(client, CURRENT_MAC, 6);
    snapshot.current_ip = rbcp::read_retry(client, CURRENT_IP, 4);
    snapshot.eeprom_mac = rbcp::read_retry(client, EEPROM_MAC, 6);
    snapshot.eeprom_ip = rbcp::read_retry(client, EEPROM_IP, 4);
    return snapshot;
}

inline void print_snapshot(const Snapshot& snapshot,
                           const std::string& prefix = "") {
    std::cout
        << prefix << "current MAC  : " << mac_string(snapshot.current_mac) << '\n'
        << prefix << "current IP   : " << ipv4_string(snapshot.current_ip) << '\n'
        << prefix << "EEPROM MAC   : " << mac_string(snapshot.eeprom_mac) << '\n'
        << prefix << "EEPROM IP    : " << ipv4_string(snapshot.eeprom_ip) << '\n';
}

inline void print_success() {
    std::cout << "\nSuccess! All operations completed and verified.\n\n";
}

inline void show_compact(const std::string& host, uint16_t port,
                         double timeout, const std::string& phase) {
    Client client(host, port, timeout);
    const Snapshot snapshot = read_snapshot(client);
    const std::string label = phase + (phase == "after" ? ":  " : ": ");
    std::cout << label << "runtime MAC " << mac_string(snapshot.current_mac)
              << ", IP " << ipv4_string(snapshot.current_ip) << '\n'
              << label << "EEPROM  MAC " << mac_string(snapshot.eeprom_mac)
              << ", IP " << ipv4_string(snapshot.eeprom_ip) << std::endl;
}

inline Snapshot show_all(const std::string& host, uint16_t port,
                         double timeout, const std::string& prefix = "") {
    Client client(host, port, timeout);
    const Snapshot snapshot = read_snapshot(client);
    print_snapshot(snapshot, prefix);
    return snapshot;
}

inline void set_eeprom_write_enable(Client& client, bool enabled) {
    const std::vector<uint8_t> value(
        1, static_cast<uint8_t>(enabled ? 0x00 : 0xFF));
    const std::vector<uint8_t> ack =
        client.write(EEPROM_WRITE_ENABLE, value);
    if (ack.size() != value.size()) {
        throw Error("unexpected RBCP ACK length for EEPROM write-enable");
    }
}

inline void write_eeprom_ip(const std::string& host,
                            const std::string& new_ip,
                            uint16_t port, double timeout,
                            uint16_t tcp_port = 0, uint16_t udp_port = 0) {
    Client client(host, port, timeout);
    const std::vector<uint8_t> bytes = parse_ipv4(new_ip);
    std::vector<uint8_t> settings = rbcp::read_retry(client, 0xFFFFFC00u, 64);
    std::copy(bytes.begin(), bytes.end(), settings.begin() + 0x18);
    if (tcp_port != 0) {
        settings[0x1C] = static_cast<uint8_t>(tcp_port >> 8);
        settings[0x1D] = static_cast<uint8_t>(tcp_port);
    }
    if (udp_port != 0) {
        settings[0x22] = static_cast<uint8_t>(udp_port >> 8);
        settings[0x23] = static_cast<uint8_t>(udp_port);
    }
    const std::vector<uint8_t> prefix(settings.begin(), settings.begin() + 17);
    const std::vector<uint8_t> parameters(settings.begin() + 0x18, settings.end());

    try {
        // A lost enable acknowledgement may still leave EEPROM writable.
        // Keep enable inside the cleanup scope, just like MPC programming.
        set_eeprom_write_enable(client, true);
        if (client.write(0xFFFFFC00u, prefix).size() != prefix.size()) {
            throw Error("unexpected RBCP ACK length for EEPROM settings prefix");
        }
        if (client.write(EEPROM_IP, parameters).size() != parameters.size()) {
            throw Error("unexpected RBCP ACK length for EEPROM settings parameters");
        }
    } catch (...) {
        try {
            set_eeprom_write_enable(client, false);
        } catch (...) {
        }
        throw;
    }
    set_eeprom_write_enable(client, false);

    if (rbcp::read_retry(client, 0xFFFFFC00u, 64) != settings) {
        throw Error("EEPROM settings read-back mismatch");
    }
}

inline void write_current_ip(const std::string& host,
                             const std::string& new_ip,
                             uint16_t port, double timeout,
                             uint16_t tcp_port = 0, uint16_t udp_port = 0) {
    const std::vector<uint8_t> bytes = parse_ipv4(new_ip);
    Client old_client(host, port, timeout);
    // The captured Utility refreshes the runtime settings twice before writing.
    rbcp::read_retry(old_client, 0xFFFFFF00u, 64);
    std::vector<uint8_t> settings = rbcp::read_retry(old_client, 0xFFFFFF00u, 64);
    std::copy(bytes.begin(), bytes.end(), settings.begin() + 0x18);
    if (tcp_port != 0) {
        settings[0x1C] = static_cast<uint8_t>(tcp_port >> 8);
        settings[0x1D] = static_cast<uint8_t>(tcp_port);
    }
    if (udp_port != 0) {
        settings[0x22] = static_cast<uint8_t>(udp_port >> 8);
        settings[0x23] = static_cast<uint8_t>(udp_port);
    }
    const std::vector<uint8_t> prefix(settings.begin(), settings.begin() + 17);
    const std::vector<uint8_t> parameters(settings.begin() + 0x18, settings.end());

    // Only the second block changes the address. A prefix failure is fatal.
    if (old_client.write(0xFFFFFF00u, prefix).size() != prefix.size()) {
        throw Error("unexpected RBCP ACK length for runtime settings prefix");
    }

    try {
        const std::vector<uint8_t> ack =
            old_client.write(CURRENT_IP, parameters);
        if (ack.size() != parameters.size()) {
            throw Error("unexpected RBCP ACK length for runtime settings parameters");
        }
    } catch (const Timeout&) {
        // The address may change before the UDP acknowledgement returns.
        // Do not retry this destructive write. Verify through the new address.
    }

    std::this_thread::sleep_for(std::chrono::milliseconds(200));

    Client new_client(new_ip, udp_port == 0 ? port : udp_port, timeout);
    if (rbcp::read_retry(new_client, 0xFFFFFF00u, 64) != settings) {
        throw Error("runtime settings read-back mismatch at new address " + new_ip);
    }
}

}  // namespace network_config
}  // namespace sitcp_sitcpxg
