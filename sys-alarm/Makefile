CC ?= gcc
CFLAGS ?= -O2 -Wall -Wextra $(shell pkg-config --cflags gtk+-3.0 json-glib-1.0 x11)
LIBS ?= $(shell pkg-config --libs gtk+-3.0 json-glib-1.0 x11) -lm
TARGET = sys-alarm
SRC = sys-alarm.c
PREFIX ?= $(HOME)/.local

all: $(TARGET)

$(TARGET): $(SRC)
	$(CC) $(CFLAGS) -o $(TARGET) $(SRC) $(LIBS)

install: $(TARGET)
	install -d $(PREFIX)/bin
	install -m 755 $(TARGET) $(PREFIX)/bin/$(TARGET)
	ln -sf $(PREFIX)/bin/$(TARGET) $(HOME)/.config/bspwm/bin/$(TARGET)

clean:
	rm -f $(TARGET)

.PHONY: all install clean
