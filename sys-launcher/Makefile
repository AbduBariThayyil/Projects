CC ?= gcc
CFLAGS ?= -O2 -Wall -Wextra -Wpedantic $(shell pkg-config --cflags gtk+-3.0 gio-2.0 gio-unix-2.0)
LDFLAGS ?= $(shell pkg-config --libs gtk+-3.0 gio-2.0 gio-unix-2.0)
TARGET = sys-launcher
PREFIX ?= $(HOME)/.local

all: $(TARGET)

$(TARGET): sys-launcher.c
	$(CC) $(CFLAGS) -o $(TARGET) sys-launcher.c $(LDFLAGS)

install: $(TARGET)
	install -d $(PREFIX)/bin
	install -m 755 $(TARGET) $(PREFIX)/bin/$(TARGET)

clean:
	rm -f $(TARGET)

.PHONY: all install clean
