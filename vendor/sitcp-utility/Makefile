CXX ?= g++
CXXFLAGS ?= -O2 -std=c++11 -Wall -Wextra -Wpedantic

PREFIX ?= $(CURDIR)
BINDIR ?= $(PREFIX)/bin
DESTDIR ?=

SRC_DIR := src
PROGRAMS := mpc-mpcx-ip-writer mpc-mpcx-ip-reader mpc-mpcx-ip-command \
            sitcp-sitcpxg-ip-writer sitcp-sitcpxg-ip-reader
TARGETS := $(addprefix $(SRC_DIR)/,$(PROGRAMS))
HEADERS := $(wildcard $(SRC_DIR)/*.hpp)

all: $(TARGETS)

$(SRC_DIR)/%: $(SRC_DIR)/%.cpp $(HEADERS)
	$(CXX) $(CXXFLAGS) $< -o $@

install: all
	install -d $(DESTDIR)$(BINDIR)
	for program in $(PROGRAMS); do install -m 0755 $(SRC_DIR)/$$program $(DESTDIR)$(BINDIR)/$$program; done

uninstall:
	for program in $(PROGRAMS); do rm -f $(DESTDIR)$(BINDIR)/$$program; done

clean:
	rm -f $(TARGETS)

.PHONY: all install uninstall clean
