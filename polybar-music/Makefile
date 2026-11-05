CC ?= gcc
CFLAGS ?= -O2 -Wall -Wextra $(shell pkg-config --cflags gio-2.0 glib-2.0)
LIBS ?= $(shell pkg-config --libs gio-2.0 glib-2.0)
TARGET = PolybarMusic
SRC = polybar-music.c
PREFIX ?= $(HOME)/.local/bin
BSPWM_BIN ?= $(HOME)/.config/bspwm/bin

all: $(TARGET)

$(TARGET): $(SRC)
	$(CC) $(CFLAGS) -o $(TARGET) $(SRC) $(LIBS)

install: $(TARGET)
	install -d $(PREFIX)
	install -m 755 $(TARGET) $(PREFIX)/$(TARGET)
	install -d $(BSPWM_BIN)
	install -m 755 $(TARGET) $(BSPWM_BIN)/$(TARGET)

clean:
	rm -f $(TARGET)

.PHONY: all install clean
