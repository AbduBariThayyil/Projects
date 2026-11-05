#include "auth_fprint.h"
#include <gio/gio.h>
#include <pthread.h>

struct FprintContext {
    char username[64];
    char device_path[128];
    int pipe_fd;
    GDBusConnection *conn;
    GMainLoop *loop;
    GMainContext *main_ctx;
    pthread_t thread;
    guint sub_id;
    bool claimed;
    bool verifying;
    bool stopped;
};

static void send_ipc_msg(int pipe_fd, IpcMessageCode code, const char *text) {
    if (pipe_fd < 0) return;
    IpcMessage msg;
    memset(&msg, 0, sizeof(msg));
    msg.code = code;
    if (text) {
        snprintf(msg.text, sizeof(msg.text), "%s", text);
    }
    ssize_t written = write(pipe_fd, &msg, sizeof(msg));
    (void)written;
}

static void restart_verify_if_needed(FprintContext *ctx) {
    if (!ctx || ctx->stopped || !ctx->conn) return;

    GError *err = NULL;
    GVariant *res = g_dbus_connection_call_sync(
        ctx->conn,
        "net.reactivated.Fprint",
        ctx->device_path,
        "net.reactivated.Fprint.Device",
        "VerifyStart",
        g_variant_new("(s)", "any"),
        NULL,
        G_DBUS_CALL_FLAGS_NONE,
        3000,
        NULL,
        &err
    );

    if (res) {
        ctx->verifying = true;
        g_variant_unref(res);
    } else {
        if (err) g_error_free(err);
    }
}

static void on_verify_status_signal(GDBusConnection *conn,
                                   const gchar *sender_name,
                                   const gchar *object_path,
                                   const gchar *interface_name,
                                   const gchar *signal_name,
                                   GVariant *parameters,
                                   gpointer user_data) {
    (void)conn;
    (void)sender_name;
    (void)object_path;
    (void)interface_name;
    (void)signal_name;

    FprintContext *ctx = (FprintContext *)user_data;
    if (!ctx || ctx->stopped) return;

    const gchar *result = NULL;
    gboolean done = FALSE;
    g_variant_get(parameters, "(&sb)", &result, &done);

    if (!result) return;

    if (strcmp(result, "verify-match") == 0) {
        send_ipc_msg(ctx->pipe_fd, MSG_FPRINT_SUCCESS, "Fingerprint Recognized");
    } else if (strcmp(result, "verify-no-match") == 0) {
        send_ipc_msg(ctx->pipe_fd, MSG_FPRINT_FAILURE, "Fingerprint Not Recognized");
        if (done) {
            restart_verify_if_needed(ctx);
        }
    } else if (strcmp(result, "verify-swipe-too-short") == 0) {
        send_ipc_msg(ctx->pipe_fd, MSG_FPRINT_SWIPE_SHORT, "󰈷 Swipe too short, please try again");
        if (done) {
            restart_verify_if_needed(ctx);
        }
    } else if (strcmp(result, "verify-finger-not-centered") == 0) {
        send_ipc_msg(ctx->pipe_fd, MSG_FPRINT_NOT_CENTERED, "󰈷 Center finger on sensor, retry");
        if (done) {
            restart_verify_if_needed(ctx);
        }
    } else if (strcmp(result, "verify-remove-and-retry") == 0) {
        send_ipc_msg(ctx->pipe_fd, MSG_FPRINT_RETRY, "󰈷 Remove finger and retry swipe");
        if (done) {
            restart_verify_if_needed(ctx);
        }
    } else if (done) {
        restart_verify_if_needed(ctx);
    }
}

static void *fprint_loop_thread(void *arg) {
    FprintContext *ctx = (FprintContext *)arg;
    if (!ctx) return NULL;

    g_main_context_push_thread_default(ctx->main_ctx);
    g_main_loop_run(ctx->loop);
    g_main_context_pop_thread_default(ctx->main_ctx);
    return NULL;
}

FprintContext *auth_fprint_init(const char *username, int pipe_fd) {
    if (!username || pipe_fd < 0) return NULL;

    GError *err = NULL;
    GDBusConnection *conn = g_bus_get_sync(G_BUS_TYPE_SYSTEM, NULL, &err);
    if (!conn) {
        if (err) g_error_free(err);
        return NULL;
    }

    /* Query default device */
    GVariant *res = g_dbus_connection_call_sync(
        conn,
        "net.reactivated.Fprint",
        "/net/reactivated/Fprint/Manager",
        "net.reactivated.Fprint.Manager",
        "GetDefaultDevice",
        NULL,
        G_VARIANT_TYPE("(o)"),
        G_DBUS_CALL_FLAGS_NONE,
        3000,
        NULL,
        &err
    );

    if (!res) {
        if (err) g_error_free(err);
        g_object_unref(conn);
        return NULL;
    }

    const char *dev_path = NULL;
    g_variant_get(res, "(&o)", &dev_path);
    if (!dev_path || dev_path[0] == '\0') {
        g_variant_unref(res);
        g_object_unref(conn);
        return NULL;
    }

    char device_path[128];
    snprintf(device_path, sizeof(device_path), "%s", dev_path);
    g_variant_unref(res);

    /* Check if user has enrolled fingers */
    res = g_dbus_connection_call_sync(
        conn,
        "net.reactivated.Fprint",
        device_path,
        "net.reactivated.Fprint.Device",
        "ListEnrolledFingers",
        g_variant_new("(s)", username),
        G_VARIANT_TYPE("(as)"),
        G_DBUS_CALL_FLAGS_NONE,
        3000,
        NULL,
        &err
    );

    if (!res) {
        if (err) g_error_free(err);
        g_object_unref(conn);
        return NULL;
    }

    GVariantIter *iter = NULL;
    g_variant_get(res, "(as)", &iter);
    gsize finger_count = g_variant_iter_n_children(iter);
    g_variant_iter_free(iter);
    g_variant_unref(res);

    if (finger_count == 0) {
        /* User has no registered fingerprints */
        g_object_unref(conn);
        return NULL;
    }

    /* Claim device */
    res = g_dbus_connection_call_sync(
        conn,
        "net.reactivated.Fprint",
        device_path,
        "net.reactivated.Fprint.Device",
        "Claim",
        g_variant_new("(s)", username),
        NULL,
        G_DBUS_CALL_FLAGS_NONE,
        3000,
        NULL,
        &err
    );

    if (!res) {
        if (err) g_error_free(err);
        g_object_unref(conn);
        return NULL;
    }
    g_variant_unref(res);

    /* Allocate Context */
    FprintContext *ctx = calloc(1, sizeof(FprintContext));
    if (!ctx) {
        g_object_unref(conn);
        return NULL;
    }

    snprintf(ctx->username, sizeof(ctx->username), "%s", username);
    snprintf(ctx->device_path, sizeof(ctx->device_path), "%s", device_path);
    ctx->pipe_fd = pipe_fd;
    ctx->conn = conn;
    ctx->claimed = true;
    ctx->main_ctx = g_main_context_new();
    ctx->loop = g_main_loop_new(ctx->main_ctx, FALSE);

    /* Subscribe to VerifyStatus */
    ctx->sub_id = g_dbus_connection_signal_subscribe(
        ctx->conn,
        "net.reactivated.Fprint",
        "net.reactivated.Fprint.Device",
        "VerifyStatus",
        ctx->device_path,
        NULL,
        G_DBUS_SIGNAL_FLAGS_NONE,
        on_verify_status_signal,
        ctx,
        NULL
    );

    /* Start initial verification */
    restart_verify_if_needed(ctx);

    /* Launch GMainLoop thread */
    if (pthread_create(&ctx->thread, NULL, fprint_loop_thread, ctx) != 0) {
        auth_fprint_cleanup(ctx);
        return NULL;
    }

    send_ipc_msg(pipe_fd, MSG_FPRINT_ACTIVE, "󰈷 Swipe fingerprint or enter password");
    return ctx;
}

void auth_fprint_cleanup(FprintContext *ctx) {
    if (!ctx) return;
    ctx->stopped = true;

    if (ctx->conn && ctx->claimed) {
        GError *err = NULL;
        /* VerifyStop */
        GVariant *res = g_dbus_connection_call_sync(
            ctx->conn,
            "net.reactivated.Fprint",
            ctx->device_path,
            "net.reactivated.Fprint.Device",
            "VerifyStop",
            NULL,
            NULL,
            G_DBUS_CALL_FLAGS_NONE,
            1500,
            NULL,
            &err
        );
        if (res) g_variant_unref(res);
        if (err) { g_error_free(err); err = NULL; }

        /* Release */
        res = g_dbus_connection_call_sync(
            ctx->conn,
            "net.reactivated.Fprint",
            ctx->device_path,
            "net.reactivated.Fprint.Device",
            "Release",
            NULL,
            NULL,
            G_DBUS_CALL_FLAGS_NONE,
            1500,
            NULL,
            &err
        );
        if (res) g_variant_unref(res);
        if (err) { g_error_free(err); err = NULL; }
    }

    if (ctx->sub_id > 0 && ctx->conn) {
        g_dbus_connection_signal_unsubscribe(ctx->conn, ctx->sub_id);
        ctx->sub_id = 0;
    }

    if (ctx->loop) {
        g_main_loop_quit(ctx->loop);
        pthread_join(ctx->thread, NULL);
        g_main_loop_unref(ctx->loop);
        ctx->loop = NULL;
    }

    if (ctx->main_ctx) {
        g_main_context_unref(ctx->main_ctx);
        ctx->main_ctx = NULL;
    }

    if (ctx->conn) {
        g_object_unref(ctx->conn);
        ctx->conn = NULL;
    }

    free(ctx);
}
