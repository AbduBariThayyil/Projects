CC ?= cc
CFLAGS ?= -O2 -Wall -Wextra
LIBS = -lX11

all: xmodmap-watcher

xmodmap-watcher: xmodmap-watcher.c
	$(CC) $(CFLAGS) xmodmap-watcher.c -o xmodmap-watcher $(LIBS)

install: xmodmap-watcher
	install -m 755 xmodmap-watcher /home/vibecoder/.config/bspwm/bin/XmodmapWatcher

clean:
	rm -f xmodmap-watcher

.PHONY: all install clean
