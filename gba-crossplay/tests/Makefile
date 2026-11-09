CC ?= gcc
CFLAGS ?= -Wall -Wextra -O2 -I../core

all: test_protocol test_turbo
	./test_protocol
	./test_turbo

test_protocol: test_protocol.c ../core/link_protocol.c
	$(CC) $(CFLAGS) -o $@ $^

test_turbo: test_turbo.c ../core/turbo_sync.c ../core/link_protocol.c
	$(CC) $(CFLAGS) -o $@ $^

clean:
	rm -f test_protocol test_turbo

.PHONY: all clean
