CC ?= gcc
CFLAGS ?= -O2 -Wall -Wextra -Wpedantic -std=c99 -D_POSIX_C_SOURCE=200809L -D_DEFAULT_SOURCE -D_GNU_SOURCE
PREFIX ?= $(HOME)/.local
BINDIR ?= $(PREFIX)/bin

PKGS = x11 xrandr xinerama cairo pango pangocairo gio-2.0 gdk-pixbuf-2.0 xext
PKG_CFLAGS := $(shell pkg-config --cflags $(PKGS))
PKG_LIBS := $(shell pkg-config --libs $(PKGS)) -lpam -lpthread -lm

SRC = main.c grab.c blur.c wallpaper.c ui.c auth_pam.c auth_fprint.c
OBJ = $(SRC:.c=.o)
TARGET = sys-lock

TEST_SRC = test_sys_lock.c grab.c blur.c wallpaper.c ui.c
TEST_OBJ = test_sys_lock.o grab.o blur.o wallpaper.o ui.o
TEST_TARGET = test_sys_lock

all: $(TARGET)

$(TARGET): $(OBJ)
	$(CC) $(CFLAGS) -o $@ $(OBJ) $(PKG_LIBS)

%.o: %.c
	$(CC) $(CFLAGS) $(PKG_CFLAGS) -c $< -o $@

$(TEST_TARGET): $(TEST_OBJ)
	$(CC) $(CFLAGS) -o $@ $(TEST_OBJ) $(PKG_LIBS)

test: $(TEST_TARGET)
	@echo "Running sys-lock unit and headless integration tests..."
	xvfb-run -a ./$(TEST_TARGET)

install: $(TARGET)
	mkdir -p $(DESTDIR)$(BINDIR)
	install -m 755 $(TARGET) $(DESTDIR)$(BINDIR)/$(TARGET)

uninstall:
	rm -f $(DESTDIR)$(BINDIR)/$(TARGET)

clean:
	rm -f $(OBJ) $(TARGET) $(TEST_OBJ) $(TEST_TARGET)

.PHONY: all test install uninstall clean
