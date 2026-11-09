CC ?= gcc
CFLAGS ?= -Wall -Wextra -O2 -I../core -I../linux/include -I/usr/include/SDL2
LDFLAGS ?= -lmgba -lSDL2

all: test_protocol test_turbo test_features
	./test_protocol
	./test_turbo
	./test_features

test_protocol: test_protocol.c ../core/link_protocol.c
	$(CC) $(CFLAGS) -o $@ $^

test_turbo: test_turbo.c ../core/turbo_sync.c ../core/link_protocol.c
	$(CC) $(CFLAGS) -o $@ $^

test_features: test_features.c ../linux/src/emulator.o ../linux/src/audio.o ../linux/src/hud.o ../core/link_protocol.o ../core/turbo_sync.o
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

clean:
	rm -f test_protocol test_turbo test_features

.PHONY: all clean
