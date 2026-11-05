CC ?= gcc
CFLAGS ?= -O2 -Wall -Wextra -Wpedantic -std=c11
PKG_CFLAGS := $(shell pkg-config --cflags gio-2.0 glib-2.0)
PKG_LIBS := $(shell pkg-config --libs gio-2.0 glib-2.0)

ALL_CFLAGS = $(CFLAGS) $(PKG_CFLAGS)
ALL_LIBS = $(PKG_LIBS)

PREFIX ?= $(HOME)/.local
BINDIR = $(PREFIX)/bin

SRCS = bt_core.c bt_daemon.c bt_cli.c main.c
OBJS = $(SRCS:.c=.o)
TARGET = sys-bt

TEST_SRC = test_sys_bt.c bt_core.c bt_cli.c
TEST_TARGET = test_sys_bt

.PHONY: all clean install test

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $(OBJS) $(ALL_LIBS) -o $@

%.o: %.c sys_bt.h
	$(CC) $(ALL_CFLAGS) -c $< -o $@

test: $(TEST_TARGET)
	./$(TEST_TARGET)

$(TEST_TARGET): $(TEST_SRC) sys_bt.h
	$(CC) $(ALL_CFLAGS) -DTEST_BUILD $(TEST_SRC) $(ALL_LIBS) -o $@

install: $(TARGET)
	install -d $(BINDIR)
	install -m 755 $(TARGET) $(BINDIR)/$(TARGET)

clean:
	rm -f $(OBJS) $(TARGET) $(TEST_TARGET) *.tmp.*
