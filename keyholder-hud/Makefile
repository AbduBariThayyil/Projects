CC ?= gcc
CFLAGS ?= -O2 -Wall -Wextra -Wpedantic `pkg-config --cflags cairo pangocairo x11 xext glib-2.0`
LDFLAGS ?= `pkg-config --libs cairo pangocairo x11 xext glib-2.0`
C_PLAIN ?= -O2 -Wall -Wextra -Wpedantic

HUD_BIN = keyholder-hud
CLI_BIN = KeyHolder
TEST_BIN = test_keyholder
PREFIX ?= $(HOME)/.local

all: $(HUD_BIN) $(CLI_BIN)

$(HUD_BIN): keyholder-hud.c
	$(CC) $(CFLAGS) -o $(HUD_BIN) keyholder-hud.c $(LDFLAGS)

$(CLI_BIN): keyholder.c keyholder-core.c keyholder.h
	$(CC) $(C_PLAIN) -o $(CLI_BIN) keyholder.c keyholder-core.c

$(TEST_BIN): test_keyholder.c keyholder-core.c keyholder.h
	$(CC) -O2 -Wall -Wextra -Wpedantic -g -o $(TEST_BIN) test_keyholder.c keyholder-core.c

test: $(TEST_BIN)
	./$(TEST_BIN)

install: all
	install -d $(PREFIX)/bin $(HOME)/.config/bspwm/bin
	install -m 755 $(HUD_BIN) $(PREFIX)/bin/$(HUD_BIN)
	install -m 755 $(CLI_BIN) $(PREFIX)/bin/$(CLI_BIN)
	install -m 755 $(CLI_BIN) $(HOME)/.config/bspwm/bin/$(CLI_BIN)

clean:
	rm -f $(HUD_BIN) $(CLI_BIN) $(TEST_BIN)

.PHONY: all test install clean
