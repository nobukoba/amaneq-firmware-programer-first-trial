#pragma once

#include <arpa/inet.h>
#include <cerrno>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <netdb.h>
#include <stdexcept>
#include <string>
#include <sys/select.h>
#include <sys/socket.h>
#include <unistd.h>
#include <utility>
#include <vector>

namespace sitcp_sitcpxg {
namespace rbcp {

constexpr uint16_t DEFAULT_PORT = 4660;
constexpr double DEFAULT_TIMEOUT = 3.0;

struct Error : std::runtime_error {
    using std::runtime_error::runtime_error;
};

struct Timeout : Error {
    using Error::Error;
};

struct BusError : Error {
    using Error::Error;
};

class Client {
public:
    Client(std::string host, uint16_t port = DEFAULT_PORT,
           double timeout = DEFAULT_TIMEOUT)
        : host_(std::move(host)),
          port_(port),
          timeout_(timeout) {
        if (!std::isfinite(timeout_) || timeout_ <= 0 || timeout_ > 86400) {
            throw Error("RBCP timeout must be finite and in (0, 86400] seconds");
        }
    }

    std::vector<uint8_t> read(uint32_t address, size_t length) {
        if (length == 0 || length > 255) {
            throw Error("invalid RBCP read length");
        }

        return transaction(
            0xC0, address, std::vector<uint8_t>(),
            static_cast<uint8_t>(length));
    }

    std::vector<uint8_t> write(
        uint32_t address, const std::vector<uint8_t>& data) {
        if (data.empty() || data.size() > 255) {
            throw Error("invalid RBCP write length");
        }

        return transaction(
            0x80, address, data, static_cast<uint8_t>(data.size()));
    }

private:
    std::vector<uint8_t> transaction(
        uint8_t command, uint32_t address,
        const std::vector<uint8_t>& payload, uint8_t length) {
        const uint8_t id = id_++;

        std::vector<uint8_t> packet;
        packet.reserve(8 + payload.size());
        packet.push_back(0xFF);
        packet.push_back(command);
        packet.push_back(id);
        packet.push_back(length);
        packet.push_back(static_cast<uint8_t>(address >> 24));
        packet.push_back(static_cast<uint8_t>(address >> 16));
        packet.push_back(static_cast<uint8_t>(address >> 8));
        packet.push_back(static_cast<uint8_t>(address));
        packet.insert(packet.end(), payload.begin(), payload.end());

        addrinfo hints = {};
        hints.ai_family = AF_INET;
        hints.ai_socktype = SOCK_DGRAM;

        addrinfo* result = NULL;
        const std::string port_string = std::to_string(port_);
        const int getaddrinfo_result = getaddrinfo(
            host_.c_str(), port_string.c_str(), &hints, &result);
        if (getaddrinfo_result != 0) {
            throw Error("cannot resolve RBCP target " + host_ + ": " + gai_strerror(getaddrinfo_result));
        }

        const int socket_fd = socket(
            result->ai_family, result->ai_socktype, result->ai_protocol);
        if (socket_fd < 0) {
            const int socket_errno = errno;
            freeaddrinfo(result);
            throw Error(strerror(socket_errno));
        }

        const int connected = connect(socket_fd, result->ai_addr, result->ai_addrlen);
        freeaddrinfo(result);
        if (connected < 0) {
            const int connect_errno = errno;
            close(socket_fd);
            throw Error("cannot reach RBCP target " + host_ + ": " + strerror(connect_errno));
        }
        const ssize_t sent = send(socket_fd, packet.data(), packet.size(), 0);

        if (sent != static_cast<ssize_t>(packet.size())) {
            const int send_errno = errno;
            close(socket_fd);
            throw Error("RBCP send failed to " + host_ + ": " + strerror(send_errno));
        }

        fd_set read_fds;
        FD_ZERO(&read_fds);
        FD_SET(socket_fd, &read_fds);

        timeval timeout_value = {};
        const long timeout_seconds = static_cast<long>(timeout_);
        timeout_value.tv_sec =
            static_cast<decltype(timeout_value.tv_sec)>(timeout_seconds);
        timeout_value.tv_usec =
            static_cast<decltype(timeout_value.tv_usec)>(
                (timeout_ - timeout_seconds) * 1000000.0);

        const int ready = select(
            socket_fd + 1, &read_fds, NULL, NULL, &timeout_value);
        if (ready == 0) {
            close(socket_fd);
            throw Timeout(
                "RBCP timeout from " + host_ + ":" +
                std::to_string(port_));
        }
        if (ready < 0) {
            const int select_errno = errno;
            close(socket_fd);
            throw Error(strerror(select_errno));
        }

        uint8_t reply[263];
        const ssize_t received = recvfrom(
            socket_fd, reply, sizeof(reply), 0, NULL, NULL);
        const int receive_errno = errno;
        close(socket_fd);

        if (received < 0) {
            throw Error("RBCP receive failed from " + host_ + ": " + strerror(receive_errno));
        }
        if (received < 8 || reply[0] != 0xFF || reply[2] != id) {
            throw Error("invalid RBCP reply");
        }
        if ((reply[1] & 0x01u) != 0) {
            throw BusError("RBCP bus error");
        }

        return std::vector<uint8_t>(reply + 8, reply + received);
    }

    std::string host_;
    uint16_t port_;
    double timeout_;
    uint8_t id_ = 0;
};

inline std::vector<uint8_t> read_retry(
    Client& client, uint32_t address, size_t length, int attempts = 3) {
    for (int attempt = 0; attempt < attempts; ++attempt) {
        try {
            const std::vector<uint8_t> data =
                client.read(address, length);
            if (data.size() != length) {
                throw Error("short RBCP read");
            }
            return data;
        } catch (const Timeout&) {
            if (attempt + 1 == attempts) {
                throw;
            }
        }
    }

    throw Timeout("RBCP timeout");
}

}  // namespace rbcp
}  // namespace sitcp_sitcpxg
