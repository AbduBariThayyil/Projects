CC ?= gcc
CFLAGS ?= -O2 -Wall -Wextra `pkg-config --cflags gio-2.0 gdk-pixbuf-2.0 x11 cairo pangocairo`
LIBS = `pkg-config --libs gio-2.0 gdk-pixbuf-2.0 x11 cairo pangocairo` -lm

TARGET = sys-notif
PREFIX ?= /home/vibecoder/.local

all: $(TARGET)

$(TARGET): sys-notif.c
	$(CC) $(CFLAGS) -o $(TARGET) sys-notif.c $(LIBS)

install: $(TARGET)
	install -Dm755 $(TARGET) $(PREFIX)/bin/$(TARGET)

clean:
	rm -f $(TARGET)

.PHONY: all install clean
