CC ?= gcc
CFLAGS ?= -O2 -Wall -Wextra -Wpedantic `pkg-config --cflags x11`
LDFLAGS ?= `pkg-config --libs x11`
TARGET = sys-input
TEST_BIN = test_sys_input
PREFIX ?= $(HOME)/.local

all: $(TARGET)

$(TARGET): sys-input.c sys-input-core.c sys-input-x11.c sys-input.h sys-input-x11.h
	$(CC) $(CFLAGS) -o $(TARGET) sys-input.c sys-input-core.c sys-input-x11.c $(LDFLAGS)

$(TEST_BIN): test_sys_input.c sys-input-core.c sys-input.h
	$(CC) -O2 -Wall -Wextra -Wpedantic -g -o $(TEST_BIN) test_sys_input.c sys-input-core.c

test: $(TEST_BIN)
	./$(TEST_BIN)

install: $(TARGET)
	install -d $(PREFIX)/bin
	install -m 755 $(TARGET) $(PREFIX)/bin/$(TARGET)

clean:
	rm -f $(TARGET) $(TEST_BIN)

.PHONY: all test install clean
