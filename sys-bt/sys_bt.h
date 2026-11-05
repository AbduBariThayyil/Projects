/*
 * sys-bt: Smart On-Demand Bluetooth Manager & Power Daemon
 * Target: Arch Linux / BSPWM
 * Stack: C11, GIO / D-Bus (BlueZ org.bluez), rfkill
 */

#ifndef SYS_BT_H
#define SYS_BT_H

#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <unistd.h>
#include <time.h>
#include <signal.h>
#include <gio/gio.h>

#define SYS_BT_VERSION "1.0.0"
#define SYS_BT_DEFAULT_TIMEOUT 300 /* 5 minutes */

#define BLUEZ_BUS_NAME           "org.bluez"
#define BLUEZ_OBJ_PATH           "/"
#define BLUEZ_IFACE_OBJ_MANAGER  "org.freedesktop.DBus.ObjectManager"
#define BLUEZ_IFACE_PROPERTIES   "org.freedesktop.DBus.Properties"
#define BLUEZ_IFACE_ADAPTER      "org.bluez.Adapter1"
#define BLUEZ_IFACE_DEVICE       "org.bluez.Device1"

typedef struct {
    char *path;       /* e.g. "/org/bluez/hci0/dev_41_42_AC_2D_BA_0A" */
    char *address;    /* e.g. "41:42:AC:2D:BA:0A" */
    char *name;       /* e.g. "NB126A" */
    char *alias;      /* e.g. "NB126A" */
    char *icon;       /* e.g. "audio-headset" */
    gboolean paired;
    gboolean connected;
    gboolean trusted;
} BtDevice;

typedef struct {
    char *path;       /* e.g. "/org/bluez/hci0" */
    char *name;       /* e.g. "deadtheory" */
    char *alias;
    char *address;    /* e.g. "E8:39:DF:08:94:79" */
    gboolean powered;
    gboolean discovering;
} BtAdapter;

typedef struct {
    gboolean rfkill_blocked;
    gboolean has_adapter;
    BtAdapter adapter;
    GList *devices;   /* List of (BtDevice *) */
    int connected_count;

    /* Daemon state */
    gboolean daemon_active;
    pid_t daemon_pid;
    gboolean timer_armed;
    int timeout_seconds;
    gint64 deadline_epoch;
} BtSystemState;

/* Core RFKill & Notification Functions */
gboolean bt_is_rfkill_blocked(void);
void bt_rfkill_set_blocked(gboolean block);
void bt_notify(const char *summary, const char *body, const char *icon);

/* State & D-Bus Functions */
BtSystemState *bt_system_state_new(void);
void bt_system_state_free(BtSystemState *state);
gboolean bt_query_system_state(GDBusConnection *conn, BtSystemState *state);

/* Adapter & Device Operations */
gboolean bt_adapter_set_powered(GDBusConnection *conn, const char *adapter_path, gboolean powered);
gboolean bt_adapter_start_discovery(GDBusConnection *conn, const char *adapter_path);
gboolean bt_adapter_stop_discovery(GDBusConnection *conn, const char *adapter_path);
gboolean bt_device_connect(GDBusConnection *conn, const char *device_path, char **error_msg);
gboolean bt_device_disconnect(GDBusConnection *conn, const char *device_path, char **error_msg);

/* Runtime State File */
char *bt_get_state_file_path(void);
void bt_write_state_file(const BtSystemState *state);
gboolean bt_read_state_file(BtSystemState *state);
void bt_remove_state_file(void);

/* Subcommands */
int cmd_daemon(int timeout_seconds);
int cmd_on(void);
int cmd_off(void);
int cmd_toggle(void);
int cmd_status(gboolean json_mode);
int cmd_menu(void);
int cmd_polybar(void);

#endif /* SYS_BT_H */
