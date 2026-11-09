CC ?= gcc
CFLAGS ?= -Wall -Wextra -O2 -Iinclude -I../core $(shell sdl2-config --cflags)
LDFLAGS ?= -lmgba $(shell sdl2-config --libs) -lpthread

SRCS = src/main.c src/emulator.c src/audio.c src/discovery.c src/hud.c src/config.c ../core/link_protocol.c ../core/turbo_sync.c
OBJS = $(SRCS:.c=.o)
TARGET = gba-crossplay

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) -o $@ $^ $(LDFLAGS)

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJS) $(TARGET)

.PHONY: all clean
