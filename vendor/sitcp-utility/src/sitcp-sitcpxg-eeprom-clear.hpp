#pragma once

#include "sitcp-sitcpxg-rbcp.hpp"

#include <cstdint>
#include <chrono>
#include <thread>
#include <vector>

namespace sitcp_sitcpxg {
namespace eeprom_clear {

inline void set_protection(rbcp::Client& client, bool protect) {
    const std::vector<uint8_t> value(1, protect ? 0xFF : 0x00);
    if (client.write(0xFFFFFCFFu, value).size() != value.size()) {
        throw rbcp::Error("unexpected RBCP ACK length setting EEPROM protection");
    }
}

inline void clear_and_verify(rbcp::Client& client) {
    const std::vector<uint8_t> erased_block(16, 0xFF);
    // The official clear path spaces write starts by approximately 500 ms,
    // including enable and protection. ACK time is part of that interval.
    auto next_write = std::chrono::steady_clock::now();
    const auto wait_for_write = [&next_write]() {
        std::this_thread::sleep_until(next_write);
        next_write = std::chrono::steady_clock::now() +
                     std::chrono::milliseconds(500);
    };
    try {
        wait_for_write();
        set_protection(client, false);
        for (uint32_t offset = 0; offset < 0x80; offset += 16) {
            wait_for_write();
            const std::vector<uint8_t> ack =
                client.write(0xFFFFFC00u + offset, erased_block);
            if (ack.size() != erased_block.size()) {
                throw rbcp::Error("short RBCP ACK while clearing EEPROM");
            }
        }
    } catch (...) {
        // An enable or data write may have occurred despite a lost ACK.
        // Do not retry it; attempt to restore protection and report failure.
        try {
            wait_for_write();
            set_protection(client, true);
        } catch (...) {
        }
        throw;
    }
    wait_for_write();
    set_protection(client, true);

    for (uint32_t offset = 0; offset < 0x80; offset += 8) {
        const std::vector<uint8_t> actual =
            rbcp::read_retry(client, 0xFFFFFC00u + offset, 8);
        if (actual != std::vector<uint8_t>(8, 0xFF)) {
            throw rbcp::Error("EEPROM clear read-back verification failed");
        }
    }
}

}  // namespace eeprom_clear
}  // namespace sitcp_sitcpxg
