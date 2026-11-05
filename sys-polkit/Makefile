CC ?= gcc
PREFIX ?= /home/vibecoder/.local
BINDIR ?= $(PREFIX)/bin

PKG_CONFIG ?= pkg-config
PACKAGES = polkit-agent-1 polkit-gobject-1 gtk+-3.0 gio-2.0 glib-2.0

CFLAGS ?= -O2 -Wall -Wextra -Wpedantic
CFLAGS += -DPOLKIT_AGENT_I_KNOW_API_IS_SUBJECT_TO_CHANGE
CFLAGS += $(shell $(PKG_CONFIG) --cflags $(PACKAGES))

LIBS = $(shell $(PKG_CONFIG) --libs $(PACKAGES))

TARGET = sys-polkit
TEST_TARGET = test_sys_polkit

SRCS = main.c sys-polkit-listener.c sys-polkit-dialog.c
OBJS = $(SRCS:.c=.o)

TEST_SRCS = test_sys_polkit.c sys-polkit-listener.c sys-polkit-dialog.c
TEST_OBJS = $(TEST_SRCS:.c=.o)

.PHONY: all clean install uninstall test

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) -o $@ $^ $(LIBS)

$(TEST_TARGET): $(TEST_OBJS)
	$(CC) $(CFLAGS) -o $@ $^ $(LIBS)

%.o: %.c sys-polkit.h sys-polkit-listener.h sys-polkit-dialog.h
	$(CC) $(CFLAGS) -c $< -o $@

test: $(TEST_TARGET)
	@echo "Running sys-polkit test suite under xvfb-run..."
	xvfb-run -a ./$(TEST_TARGET)

install: $(TARGET)
	install -d $(DESTDIR)$(BINDIR)
	install -m 755 $(TARGET) $(DESTDIR)$(BINDIR)/$(TARGET)

uninstall:
	rm -f $(DESTDIR)$(BINDIR)/$(TARGET)

clean:
	rm -f $(TARGET) $(TEST_TARGET) *.o
