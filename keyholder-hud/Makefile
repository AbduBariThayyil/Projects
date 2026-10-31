CC ?= gcc
CFLAGS ?= -O2 -Wall -Wextra `pkg-config --cflags cairo pangocairo x11 glib-2.0`
LDFLAGS ?= `pkg-config --libs cairo pangocairo x11 glib-2.0`
TARGET = keyholder-hud
PREFIX ?= $(HOME)/.local

all: $(TARGET)

$(TARGET): keyholder-hud.c
	$(CC) $(CFLAGS) -o $(TARGET) keyholder-hud.c $(LDFLAGS)

install: $(TARGET)
	install -d $(PREFIX)/bin
	install -m 755 $(TARGET) $(PREFIX)/bin/$(TARGET)

clean:
	rm -f $(TARGET)

.PHONY: all install clean
