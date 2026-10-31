CC ?= gcc
CFLAGS ?= -O2 -Wall -Wextra `pkg-config --cflags glib-2.0 x11`
LDFLAGS ?= `pkg-config --libs glib-2.0 x11`
TARGET = sys-control
PREFIX ?= $(HOME)/.local

all: $(TARGET)

$(TARGET): sys-control.c
	$(CC) $(CFLAGS) -o $(TARGET) sys-control.c $(LDFLAGS)

install: $(TARGET)
	install -d $(PREFIX)/bin
	install -m 755 $(TARGET) $(PREFIX)/bin/$(TARGET)

clean:
	rm -f $(TARGET)

.PHONY: all install clean
