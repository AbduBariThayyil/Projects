#include "sys-polkit.h"
#include "sys-polkit-listener.h"
#include "sys-polkit-dialog.h"
#include <glib-unix.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>

static GMainLoop *s_main_loop = NULL;

static gboolean on_unix_signal(gpointer user_data) {
    GMainLoop *loop = (GMainLoop *)user_data;
    g_info("sys-polkit: Received termination signal, shutting down...");
    if (loop != NULL && g_main_loop_is_running(loop)) {
        g_main_loop_quit(loop);
    }
    return G_SOURCE_REMOVE;
}

static void print_usage(const char *progname) {
    g_print("Usage: %s [OPTIONS]\n\n"
            "SysPolkit - Lightweight Catppuccin Native Polkit Authentication Agent\n\n"
            "Options:\n"
            "  -r, --replace      Replace any existing authentication agent\n"
            "  -t, --test-dialog  Display authentication dialog in test mode and exit\n"
            "  -v, --version      Display version information\n"
            "  -h, --help         Display this help message\n\n",
            progname);
}

static void on_test_submit(const gchar *password, gpointer user_data) {
    (void)password;
    (void)user_data;
    g_print("sys-polkit: Test authentication submitted successfully.\n");
    if (s_main_loop != NULL && g_main_loop_is_running(s_main_loop)) {
        g_main_loop_quit(s_main_loop);
    }
}

static void on_test_cancel(gpointer user_data) {
    (void)user_data;
    g_print("sys-polkit: Test authentication cancelled.\n");
    if (s_main_loop != NULL && g_main_loop_is_running(s_main_loop)) {
        g_main_loop_quit(s_main_loop);
    }
}

static gboolean on_test_timeout(gpointer user_data) {
    (void)user_data;
    g_print("sys-polkit: Test authentication timed out (auto-dismissed).\n");
    if (s_main_loop != NULL && g_main_loop_is_running(s_main_loop)) {
        g_main_loop_quit(s_main_loop);
    }
    return G_SOURCE_REMOVE;
}

static int run_test_dialog(int argc, char *argv[]) {
    gtk_init_check(&argc, &argv);

    s_main_loop = g_main_loop_new(NULL, FALSE);

    PolkitIdentity *test_id = polkit_unix_user_new(getuid());
    GList *ids = g_list_append(NULL, test_id);

    SysPolkitDialogCallbacks cb = {
        .on_submit = on_test_submit,
        .on_cancel = on_test_cancel,
        .on_identity_changed = NULL,
        .user_data = NULL
    };

    SysPolkitDialog *dlg = sys_polkit_dialog_new(
        "org.freedesktop.policykit.exec",
        "Authentication is required to run '/usr/bin/sys-control' as super user",
        "security-high",
        NULL,
        ids,
        &cb
    );

    sys_polkit_dialog_show(dlg);

    /* Auto-dismiss in 3 seconds if non-interactive (e.g. CI or test mode) */
    g_timeout_add_seconds(3, on_test_timeout, NULL);

    g_main_loop_run(s_main_loop);

    sys_polkit_dialog_destroy(dlg);
    g_list_free_full(ids, g_object_unref);
    g_main_loop_unref(s_main_loop);
    s_main_loop = NULL;

    return 0;
}

static void kill_competing_agents(void) {
    /* Kill any legacy or competing polkit agents */
    const char *targets[] = {
        "polkit-gnome-authentication-agent-1",
        "cmd-polkit-agent",
        "dumb-polkit",
        "lxpolkit",
        "xfce-polkit"
    };
    for (size_t i = 0; i < sizeof(targets) / sizeof(targets[0]); i++) {
        char cmd[128];
        snprintf(cmd, sizeof(cmd), "killall -q -9 %s 2>/dev/null || true", targets[i]);
        if (system(cmd) != 0) {
            /* ignore */
        }
    }
}

int main(int argc, char *argv[]) {
    gboolean opt_replace = FALSE;
    gboolean opt_test_dialog = FALSE;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-h") == 0 || strcmp(argv[i], "--help") == 0) {
            print_usage(argv[0]);
            return 0;
        } else if (strcmp(argv[i], "-v") == 0 || strcmp(argv[i], "--version") == 0) {
            g_print("sys-polkit version %s (Catppuccin Mocha GTK3)\n", SYS_POLKIT_VERSION);
            return 0;
        } else if (strcmp(argv[i], "-r") == 0 || strcmp(argv[i], "--replace") == 0) {
            opt_replace = TRUE;
        } else if (strcmp(argv[i], "-t") == 0 || strcmp(argv[i], "--test-dialog") == 0) {
            opt_test_dialog = TRUE;
        } else {
            g_printerr("sys-polkit: Unknown option '%s'. Use --help for usage.\n", argv[i]);
            return 1;
        }
    }

    if (opt_test_dialog) {
        return run_test_dialog(argc, argv);
    }

    if (opt_replace) {
        kill_competing_agents();
    }

    /* Initialize GLib main loop */
    s_main_loop = g_main_loop_new(NULL, FALSE);

    /* Setup Unix signal handling for graceful shutdown */
    g_unix_signal_add(SIGINT, on_unix_signal, s_main_loop);
    g_unix_signal_add(SIGTERM, on_unix_signal, s_main_loop);
    g_unix_signal_add(SIGHUP, on_unix_signal, s_main_loop);

    /* Acquire session subject */
    GError *error = NULL;
    PolkitSubject *subject = polkit_unix_session_new_for_process_sync(getpid(), NULL, &error);
    if (subject == NULL) {
        g_warning("sys-polkit: Could not get unix session (%s), falling back to process subject",
                  error ? error->message : "unknown");
        g_clear_error(&error);
        subject = polkit_unix_process_new_for_owner(getpid(), 0, getuid());
    }

    /* Instantiate listener */
    PolkitAgentListener *listener = sys_polkit_listener_new();

    /* Register listener with Polkit Authority */
    gpointer reg_handle = polkit_agent_listener_register(
        listener,
        POLKIT_AGENT_REGISTER_FLAGS_NONE,
        subject,
        NULL, /* Default object path */
        NULL,
        &error
    );

    if (reg_handle == NULL) {
        g_printerr("sys-polkit: Failed to register listener with Polkit Authority: %s\n",
                   error ? error->message : "unknown");
        if (error != NULL && g_error_matches(error, POLKIT_ERROR, POLKIT_ERROR_FAILED)) {
            g_printerr("sys-polkit: Hint: Another agent may be running. Try 'sys-polkit --replace'.\n");
        }
        g_clear_error(&error);
        g_object_unref(listener);
        g_object_unref(subject);
        g_main_loop_unref(s_main_loop);
        return 1;
    }

    g_info("sys-polkit: Successfully registered Catppuccin Polkit agent for session %s (pid %d)",
           POLKIT_IS_UNIX_SESSION(subject) ? polkit_unix_session_get_session_id(POLKIT_UNIX_SESSION(subject)) : "process",
           getpid());

    /* Sit idle in GLib event loop until termination or auth requests */
    g_main_loop_run(s_main_loop);

    /* Cleanup */
    g_info("sys-polkit: Unregistering authentication agent...");
    polkit_agent_listener_unregister(reg_handle);
    g_object_unref(listener);
    g_object_unref(subject);
    g_main_loop_unref(s_main_loop);
    s_main_loop = NULL;

    return 0;
}
