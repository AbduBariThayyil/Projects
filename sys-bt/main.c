/*
 * main.c: sys-bt CLI entrypoint and argument parser
 */

#include "sys_bt.h"

static void print_usage(const char *progname) {
    g_print("Usage: %s <command> [options]\n\n", progname);
    g_print("Commands:\n");
    g_print("  daemon [-t, --timeout <sec>]   Run zero-polling event-driven background daemon\n");
    g_print("                                 (Auto-powers off radio after inactivity, default: %ds)\n", SYS_BT_DEFAULT_TIMEOUT);
    g_print("  on                             Unblock rfkill and power on Bluetooth adapter\n");
    g_print("  off                            Power off Bluetooth adapter and block rfkill\n");
    g_print("  toggle                         Toggle Bluetooth power state\n");
    g_print("  status [-j, --json]            Display Bluetooth adapter, connection & daemon status\n");
    g_print("  menu                           Open interactive Rofi Bluetooth connection menu\n");
    g_print("  polybar                        Output ultra-fast formatted status string for Polybar\n");
    g_print("  -h, --help                     Show this help message\n");
    g_print("  -v, --version                  Display version information\n");
}

int main(int argc, char *argv[]) {
    if (argc < 2) {
        print_usage(argv[0]);
        return 1;
    }

    const char *cmd = argv[1];

    if (g_strcmp0(cmd, "daemon") == 0) {
        int timeout = SYS_BT_DEFAULT_TIMEOUT;
        for (int i = 2; i < argc; i++) {
            if ((g_strcmp0(argv[i], "-t") == 0 || g_strcmp0(argv[i], "--timeout") == 0) && i + 1 < argc) {
                timeout = atoi(argv[i + 1]);
                if (timeout <= 0) timeout = SYS_BT_DEFAULT_TIMEOUT;
                i++;
            }
        }
        return cmd_daemon(timeout);
    } else if (g_strcmp0(cmd, "on") == 0) {
        return cmd_on();
    } else if (g_strcmp0(cmd, "off") == 0) {
        return cmd_off();
    } else if (g_strcmp0(cmd, "toggle") == 0) {
        return cmd_toggle();
    } else if (g_strcmp0(cmd, "status") == 0) {
        gboolean json_mode = FALSE;
        for (int i = 2; i < argc; i++) {
            if (g_strcmp0(argv[i], "-j") == 0 || g_strcmp0(argv[i], "--json") == 0) {
                json_mode = TRUE;
            }
        }
        return cmd_status(json_mode);
    } else if (g_strcmp0(cmd, "menu") == 0) {
        return cmd_menu();
    } else if (g_strcmp0(cmd, "polybar") == 0) {
        return cmd_polybar();
    } else if (g_strcmp0(cmd, "-h") == 0 || g_strcmp0(cmd, "--help") == 0 || g_strcmp0(cmd, "help") == 0) {
        print_usage(argv[0]);
        return 0;
    } else if (g_strcmp0(cmd, "-v") == 0 || g_strcmp0(cmd, "--version") == 0 || g_strcmp0(cmd, "version") == 0) {
        g_print("sys-bt version %s\n", SYS_BT_VERSION);
        return 0;
    } else {
        g_printerr("Unknown command: %s\n\n", cmd);
        print_usage(argv[0]);
        return 1;
    }
}
