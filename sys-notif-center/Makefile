CC ?= gcc
CFLAGS ?= -O2 -Wall -Wextra `pkg-config --cflags gtk+-3.0`
LIBS = `pkg-config --libs gtk+-3.0`

TARGET = sys-notif-center
SRC = sys-notif-center.c

all: $(TARGET)

$(TARGET): $(SRC)
	$(CC) $(CFLAGS) -o $(TARGET) $(SRC) $(LIBS)

install: $(TARGET)
	install -m 755 $(TARGET) /home/vibecoder/.local/bin/$(TARGET)

clean:
	rm -f $(TARGET)

.PHONY: all install clean
