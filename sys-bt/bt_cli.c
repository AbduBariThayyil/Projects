/*
 * bt_cli.c: Subcommands implementation for CLI, Polybar, and Rofi menu
 */

#include "sys_bt.h"
#include <sys/wait.h>

static GDBusConnection *get_system_bus_conn(void) {
    GError *error = NULL;
    GDBusConnection *conn = g_bus_get_sync(G_BUS_TYPE_SYSTEM, NULL, &error);
    if (!conn) {
        if (error) {
            g_printerr("Failed to connect to system D-Bus: %s\n", error->message);
            g_error_free(error);
        }
        return NULL;
    }
    return conn;
}

int cmd_on(void) {
    g_print("[sys-bt] Powering on Bluetooth radio...\n");

    /* 1. Unblock rfkill if blocked */
    if (bt_is_rfkill_blocked()) {
        bt_rfkill_set_blocked(FALSE);
        g_usleep(600000); /* 600ms for hardware ACPI & BlueZ to register */
    }

    GDBusConnection *conn = get_system_bus_conn();
    if (!conn) return 1;

    BtSystemState *state = bt_system_state_new();
    bt_query_system_state(conn, state);

    /* If adapter not yet detected, wait for kernel & BlueZ to register it */
    int retries = 15;
    while (!state->has_adapter && retries-- > 0) {
        g_usleep(100000); /* 100ms */
        bt_query_system_state(conn, state);
    }

    if (state->has_adapter) {
        if (!state->adapter.powered) {
            bt_adapter_set_powered(conn, state->adapter.path, TRUE);
        }
        g_print("[sys-bt] Adapter %s powered on.\n", state->adapter.name ? state->adapter.name : state->adapter.path);
    } else {
        g_printerr("[sys-bt] Warning: RFKill unblocked, but no BlueZ adapter detected.\n");
    }

    bt_notify("Bluetooth Enabled", "Radio hardware powered on", "bluetooth");

    bt_system_state_free(state);
    g_object_unref(conn);
    return 0;
}

int cmd_off(void) {
    g_print("[sys-bt] Powering down Bluetooth radio...\n");

    GDBusConnection *conn = get_system_bus_conn();
    if (conn) {
        BtSystemState *state = bt_system_state_new();
        bt_query_system_state(conn, state);

        if (state->has_adapter && state->adapter.powered) {
            bt_adapter_set_powered(conn, state->adapter.path, FALSE);
        }
        bt_system_state_free(state);
        g_object_unref(conn);
    }

    /* Soft block rfkill */
    bt_rfkill_set_blocked(TRUE);

    bt_notify("Bluetooth Disabled", "Radio hardware powered off to conserve battery", "bluetooth-disabled");
    g_print("[sys-bt] Bluetooth powered off and rfkill blocked.\n");
    return 0;
}

int cmd_toggle(void) {
    GDBusConnection *conn = get_system_bus_conn();
    gboolean is_on = FALSE;

    if (conn) {
        BtSystemState *state = bt_system_state_new();
        bt_query_system_state(conn, state);
        if (state->has_adapter && state->adapter.powered && !state->rfkill_blocked) {
            is_on = TRUE;
        }
        bt_system_state_free(state);
        g_object_unref(conn);
    }

    if (is_on) {
        return cmd_off();
    } else {
        return cmd_on();
    }
}

int cmd_status(gboolean json_mode) {
    GDBusConnection *conn = get_system_bus_conn();
    BtSystemState *state = bt_system_state_new();

    if (conn) {
        bt_query_system_state(conn, state);
    } else {
        state->rfkill_blocked = bt_is_rfkill_blocked();
        bt_read_state_file(state);
    }

    gboolean powered = (state->has_adapter && state->adapter.powered && !state->rfkill_blocked);
    int remaining = 0;
    if (state->timer_armed && state->deadline_epoch > 0) {
        remaining = (int)(state->deadline_epoch - (gint64)time(NULL));
        if (remaining < 0) remaining = 0;
    }

    if (json_mode) {
        g_print("{\n");
        g_print("  \"powered\": %s,\n", powered ? "true" : "false");
        g_print("  \"rfkill_blocked\": %s,\n", state->rfkill_blocked ? "true" : "false");
        g_print("  \"has_adapter\": %s,\n", state->has_adapter ? "true" : "false");
        if (state->has_adapter) {
            g_print("  \"adapter\": {\n");
            g_print("    \"path\": \"%s\",\n", state->adapter.path ? state->adapter.path : "");
            g_print("    \"name\": \"%s\",\n", state->adapter.name ? state->adapter.name : "");
            g_print("    \"alias\": \"%s\",\n", state->adapter.alias ? state->adapter.alias : "");
            g_print("    \"address\": \"%s\",\n", state->adapter.address ? state->adapter.address : "");
            g_print("    \"powered\": %s,\n", state->adapter.powered ? "true" : "false");
            g_print("    \"discovering\": %s\n", state->adapter.discovering ? "true" : "false");
            g_print("  },\n");
        } else {
            g_print("  \"adapter\": null,\n");
        }
        g_print("  \"connected_count\": %d,\n", state->connected_count);
        g_print("  \"connected_devices\": [");
        int c = 0;
        for (GList *l = state->devices; l != NULL; l = l->next) {
            BtDevice *dev = (BtDevice *)l->data;
            if (dev->connected) {
                g_print("%s\"%s\"", c > 0 ? ", " : "", dev->alias ? dev->alias : dev->address);
                c++;
            }
        }
        g_print("],\n");
        g_print("  \"paired_devices\": [\n");
        int p = 0;
        for (GList *l = state->devices; l != NULL; l = l->next) {
            BtDevice *dev = (BtDevice *)l->data;
            if (dev->paired) {
                if (p > 0) g_print(",\n");
                g_print("    {\"name\": \"%s\", \"address\": \"%s\", \"connected\": %s}",
                        dev->alias ? dev->alias : (dev->name ? dev->name : ""),
                        dev->address ? dev->address : "",
                        dev->connected ? "true" : "false");
                p++;
            }
        }
        if (p > 0) g_print("\n");
        g_print("  ],\n");
        g_print("  \"daemon\": {\n");
        g_print("    \"active\": %s,\n", state->daemon_active ? "true" : "false");
        g_print("    \"pid\": %d,\n", state->daemon_active ? (int)state->daemon_pid : 0);
        g_print("    \"timer_armed\": %s,\n", state->timer_armed ? "true" : "false");
        g_print("    \"idle_remaining_seconds\": %d\n", remaining);
        g_print("  }\n");
        g_print("}\n");
    } else {
        g_print("\033[1;34m[sys-bt]\033[0m Bluetooth System Status:\n");
        g_print("  Power:          %s\n", powered ? "\033[1;32mON\033[0m" : "\033[1;31mOFF\033[0m");
        g_print("  RFKill:         %s\n", state->rfkill_blocked ? "\033[1;31mBlocked\033[0m" : "\033[1;32mUnblocked\033[0m");
        if (state->has_adapter) {
            g_print("  Controller:     %s (%s - %s)\n",
                    state->adapter.name ? state->adapter.name : "hci0",
                    state->adapter.alias ? state->adapter.alias : "",
                    state->adapter.address ? state->adapter.address : "");
        } else {
            g_print("  Controller:     None\n");
        }

        if (state->connected_count > 0) {
            g_print("  Connected (%d):  ", state->connected_count);
            int idx = 0;
            for (GList *l = state->devices; l != NULL; l = l->next) {
                BtDevice *dev = (BtDevice *)l->data;
                if (dev->connected) {
                    g_print("%s%s (%s)", idx > 0 ? ", " : "", dev->alias ? dev->alias : dev->name, dev->address);
                    idx++;
                }
            }
            g_print("\n");
        } else {
            g_print("  Connected:      None\n");
        }

        if (state->daemon_active) {
            if (state->timer_armed) {
                g_print("  Auto-Powerdown: \033[1;33mArmed (%ds remaining until poweroff)\033[0m\n", remaining);
            } else if (state->connected_count > 0) {
                g_print("  Auto-Powerdown: \033[1;32mDisarmed (Active connection)\033[0m\n");
            } else {
                g_print("  Auto-Powerdown: Inactive (Radio off)\n");
            }
            g_print("  Daemon:         \033[1;32mActive (PID: %d)\033[0m\n", (int)state->daemon_pid);
        } else {
            g_print("  Daemon:         \033[1;33mNot running (Run: sys-bt daemon)\033[0m\n");
        }
    }

    bt_system_state_free(state);
    if (conn) g_object_unref(conn);
    return 0;
}

static void get_rice_colors(char **power_on_col, char **power_off_col) {
    *power_on_col = g_strdup("#bd93f9");  /* default purple/blue */
    *power_off_col = g_strdup("#4c566a"); /* default muted grey */

    const char *home = g_get_home_dir();
    if (!home) return;

    char *rice_file = g_build_filename(home, ".config", "bspwm", ".rice", NULL);
    char *rice_name = NULL;

    if (g_file_get_contents(rice_file, &rice_name, NULL, NULL)) {
        g_strstrip(rice_name);
        char *config_file = g_build_filename(home, ".config", "bspwm", "rices", rice_name, "config.ini", NULL);
        char *config_content = NULL;

        if (g_file_get_contents(config_file, &config_content, NULL, NULL)) {
            char **lines = g_strsplit(config_content, "\n", -1);
            for (int i = 0; lines[i] != NULL; i++) {
                char *line = g_strstrip(lines[i]);
                if (g_str_has_prefix(line, "blue =")) {
                    char *val = strchr(line, '=');
                    if (val) {
                        g_free(*power_on_col);
                        *power_on_col = g_strdup(g_strstrip(val + 1));
                    }
                } else if (g_str_has_prefix(line, "grey =")) {
                    char *val = strchr(line, '=');
                    if (val) {
                        g_free(*power_off_col);
                        *power_off_col = g_strdup(g_strstrip(val + 1));
                    }
                }
            }
            g_strfreev(lines);
            g_free(config_content);
        }
        g_free(config_file);
        g_free(rice_name);
    }
    g_free(rice_file);
}

int cmd_polybar(void) {
    char *color_on = NULL;
    char *color_off = NULL;
    get_rice_colors(&color_on, &color_off);

    /* Fast check: If rfkill is blocked, exit immediately */
    if (bt_is_rfkill_blocked()) {
        g_print("%%{F%s}󰂲%%{F-}\n", color_off);
        g_free(color_on);
        g_free(color_off);
        return 0;
    }

    GDBusConnection *conn = get_system_bus_conn();
    if (!conn) {
        g_print("%%{F%s}󰂲%%{F-}\n", color_off);
        g_free(color_on);
        g_free(color_off);
        return 0;
    }

    BtSystemState *state = bt_system_state_new();
    bt_query_system_state(conn, state);

    if (!state->has_adapter || !state->adapter.powered) {
        g_print("%%{F%s}󰂲%%{F-}\n", color_off);
    } else {
        /* Check if any device is connected */
        BtDevice *connected_dev = NULL;
        for (GList *l = state->devices; l != NULL; l = l->next) {
            BtDevice *dev = (BtDevice *)l->data;
            if (dev->connected) {
                connected_dev = dev;
                break;
            }
        }

        if (connected_dev) {
            const char *display_name = connected_dev->alias ? connected_dev->alias : connected_dev->name;
            if (!display_name) display_name = connected_dev->address;

            /* Truncate long device names if needed */
            char short_name[20];
            if (display_name && strlen(display_name) > 14) {
                g_snprintf(short_name, sizeof(short_name), "%.12s..", display_name);
                g_print("%%{F%s}󰂯 %s%%{F-}\n", color_on, short_name);
            } else {
                g_print("%%{F%s}󰂯 %s%%{F-}\n", color_on, display_name ? display_name : "Connected");
            }
        } else {
            /* Powered on, idle */
            g_print("%%{F%s}󰂯%%{F-}\n", color_on);
        }
    }

    bt_system_state_free(state);
    g_object_unref(conn);
    g_free(color_on);
    g_free(color_off);
    return 0;
}

int cmd_menu(void) {
    GDBusConnection *conn = get_system_bus_conn();
    if (!conn) return 1;

    BtSystemState *state = bt_system_state_new();
    bt_query_system_state(conn, state);

    gboolean powered = (state->has_adapter && state->adapter.powered && !state->rfkill_blocked);

    GString *menu_opts = g_string_new("");

    if (powered) {
        g_string_append(menu_opts, "󰂲  Turn Bluetooth Off\n");
        if (state->adapter.discovering) {
            g_string_append(menu_opts, "󰑐  Stop Device Discovery\n");
        } else {
            g_string_append(menu_opts, "󰍉  Scan for New Devices\n");
        }
    } else {
        g_string_append(menu_opts, "󰂯  Turn Bluetooth On\n");
    }

    g_string_append(menu_opts, "────────────────────────────────────────\n");

    /* Add paired devices */
    int paired_count = 0;
    for (GList *l = state->devices; l != NULL; l = l->next) {
        BtDevice *dev = (BtDevice *)l->data;
        if (dev->paired) {
            paired_count++;
            const char *name = dev->alias ? dev->alias : (dev->name ? dev->name : dev->address);
            if (dev->connected) {
                g_string_append_printf(menu_opts, "󰂱  Disconnect: %s  [%s]\n", name, dev->address);
            } else {
                g_string_append_printf(menu_opts, "󰂯  Connect: %s  [%s]\n", name, dev->address);
            }
        }
    }

    if (paired_count == 0) {
        g_string_append(menu_opts, "󰂲  (No paired devices)\n");
    }

    /* Spawn rofi */
    const char *home = g_get_home_dir();
    char *theme_path = g_build_filename(home, ".config", "bspwm", "config", "rofi-themes", "Bluetooth.rasi", NULL);
    gboolean has_theme = g_file_test(theme_path, G_FILE_TEST_EXISTS);

    GPtrArray *rofi_args = g_ptr_array_new();
    g_ptr_array_add(rofi_args, (gpointer)"rofi");
    if (has_theme) {
        g_ptr_array_add(rofi_args, (gpointer)"-theme");
        g_ptr_array_add(rofi_args, (gpointer)theme_path);
    }
    g_ptr_array_add(rofi_args, (gpointer)"-dmenu");
    g_ptr_array_add(rofi_args, (gpointer)"-p");
    g_ptr_array_add(rofi_args, (gpointer)"Bluetooth");
    g_ptr_array_add(rofi_args, (gpointer)"-i");
    g_ptr_array_add(rofi_args, NULL);

    int stdin_pipe[2];
    int stdout_pipe[2];
    if (pipe(stdin_pipe) != 0 || pipe(stdout_pipe) != 0) {
        g_string_free(menu_opts, TRUE);
        g_free(theme_path);
        g_ptr_array_free(rofi_args, TRUE);
        bt_system_state_free(state);
        g_object_unref(conn);
        return 1;
    }

    pid_t pid = fork();
    if (pid == 0) {
        /* Child */
        close(stdin_pipe[1]);
        close(stdout_pipe[0]);
        dup2(stdin_pipe[0], STDIN_FILENO);
        dup2(stdout_pipe[1], STDOUT_FILENO);
        close(stdin_pipe[0]);
        close(stdout_pipe[1]);

        execvp("rofi", (char *const *)rofi_args->pdata);
        _exit(127);
    }

    /* Parent */
    close(stdin_pipe[0]);
    close(stdout_pipe[1]);

    /* Write menu options to rofi */
    write(stdin_pipe[1], menu_opts->str, menu_opts->len);
    close(stdin_pipe[1]);

    /* Read user choice */
    char buffer[512];
    memset(buffer, 0, sizeof(buffer));
    ssize_t bytes_read = read(stdout_pipe[0], buffer, sizeof(buffer) - 1);
    close(stdout_pipe[0]);

    int wstatus;
    waitpid(pid, &wstatus, 0);

    g_string_free(menu_opts, TRUE);
    g_free(theme_path);
    g_ptr_array_free(rofi_args, TRUE);

    if (bytes_read <= 0) {
        /* User canceled / pressed Escape */
        bt_system_state_free(state);
        g_object_unref(conn);
        return 0;
    }

    char *choice = g_strstrip(g_strdup(buffer));

    if (g_str_has_prefix(choice, "󰂲  Turn Bluetooth Off")) {
        cmd_off();
    } else if (g_str_has_prefix(choice, "󰂯  Turn Bluetooth On")) {
        cmd_on();
        /* Re-open menu to allow connecting */
        g_free(choice);
        bt_system_state_free(state);
        g_object_unref(conn);
        return cmd_menu();
    } else if (g_str_has_prefix(choice, "󰍉  Scan for New Devices")) {
        if (state->has_adapter) {
            bt_adapter_start_discovery(conn, state->adapter.path);
            bt_notify("Bluetooth Scanning", "Discovering nearby devices...", "bluetooth");
            g_usleep(3000000); /* 3s discovery */
            bt_adapter_stop_discovery(conn, state->adapter.path);
        }
        g_free(choice);
        bt_system_state_free(state);
        g_object_unref(conn);
        return cmd_menu();
    } else if (g_str_has_prefix(choice, "󰑐  Stop Device Discovery")) {
        if (state->has_adapter) {
            bt_adapter_stop_discovery(conn, state->adapter.path);
            bt_notify("Bluetooth Scanning", "Discovery stopped", "bluetooth");
        }
        g_free(choice);
        bt_system_state_free(state);
        g_object_unref(conn);
        return cmd_menu();
    } else if (g_str_has_prefix(choice, "󰂱  Disconnect:")) {
        /* Find matching device */
        for (GList *l = state->devices; l != NULL; l = l->next) {
            BtDevice *dev = (BtDevice *)l->data;
            if (strstr(choice, dev->address)) {
                g_print("[sys-bt] Disconnecting %s (%s)...\n", dev->alias ? dev->alias : dev->name, dev->address);
                char *err = NULL;
                if (bt_device_disconnect(conn, dev->path, &err)) {
                    char *msg = g_strdup_printf("Disconnected from %s", dev->alias ? dev->alias : dev->name);
                    bt_notify("Bluetooth", msg, "bluetooth");
                    g_free(msg);
                } else {
                    char *msg = g_strdup_printf("Failed to disconnect: %s", err ? err : "unknown error");
                    bt_notify("Bluetooth Error", msg, "dialog-error");
                    g_free(msg);
                    g_free(err);
                }
                break;
            }
        }
    } else if (g_str_has_prefix(choice, "󰂯  Connect:")) {
        /* If off, turn on first */
        if (!powered) {
            cmd_on();
            /* Refresh state */
            bt_query_system_state(conn, state);
        }

        /* Find matching device */
        for (GList *l = state->devices; l != NULL; l = l->next) {
            BtDevice *dev = (BtDevice *)l->data;
            if (strstr(choice, dev->address)) {
                g_print("[sys-bt] Connecting to %s (%s)...\n", dev->alias ? dev->alias : dev->name, dev->address);
                char *conn_start_msg = g_strdup_printf("Connecting to %s...", dev->alias ? dev->alias : dev->name);
                bt_notify("Bluetooth", conn_start_msg, "bluetooth");
                g_free(conn_start_msg);

                char *err = NULL;
                if (bt_device_connect(conn, dev->path, &err)) {
                    char *msg = g_strdup_printf("Connected to %s", dev->alias ? dev->alias : dev->name);
                    bt_notify("Bluetooth Connected", msg, "bluetooth");
                    g_free(msg);
                } else {
                    char *msg = g_strdup_printf("Failed to connect: %s", err ? err : "Device unreachable or timeout");
                    bt_notify("Bluetooth Connection Failed", msg, "dialog-error");
                    g_free(msg);
                    g_free(err);
                }
                break;
            }
        }
    }

    g_free(choice);
    bt_system_state_free(state);
    g_object_unref(conn);
    return 0;
}
