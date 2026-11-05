CC ?= cc
CFLAGS ?= -O2 -Wall -Wextra
LIBS = -lX11

PREFIX ?= $(HOME)
BINDIR ?= $(PREFIX)/.config/bspwm/bin
LOCALBIN ?= $(PREFIX)/.local/bin

all: xmodmap-watcher

xmodmap-watcher: xmodmap-watcher.c
	$(CC) $(CFLAGS) xmodmap-watcher.c -o xmodmap-watcher $(LIBS)

install: xmodmap-watcher
	mkdir -p $(BINDIR) $(LOCALBIN)
	install -m 755 xmodmap-watcher $(BINDIR)/XmodmapWatcher
	install -m 755 xmodmap-watcher $(LOCALBIN)/xmodmap-watcher

clean:
	rm -f xmodmap-watcher

.PHONY: all install clean
