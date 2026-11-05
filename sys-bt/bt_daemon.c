/*
 * bt_daemon.c: Zero-polling, event-driven on-demand Bluetooth power manager daemon
 */

#include "sys_bt.h"
#include <glib-unix.h>

typedef struct {
    GMainLoop *loop;
    GDBusConnection *conn;
    BtSystemState *state;
    int timeout_seconds;
    guint timer_source_id;
} DaemonContext;

static gboolean on_idle_timeout(gpointer user_data);

static void sync_daemon_state(DaemonContext *ctx) {
    bt_query_system_state(ctx->conn, ctx->state);

    gboolean powered = (ctx->state->has_adapter && ctx->state->adapter.powered && !ctx->state->rfkill_blocked);

    if (powered) {
        if (ctx->state->connected_count == 0) {
            /* No devices connected -> ensure timer is armed */
            if (ctx->timer_source_id == 0) {
                ctx->timer_source_id = g_timeout_add_seconds(ctx->timeout_seconds, on_idle_timeout, ctx);
                ctx->state->timer_armed = TRUE;
                ctx->state->deadline_epoch = (gint64)time(NULL) + ctx->timeout_seconds;
                g_print("[sys-bt daemon] No connected devices. Auto-powerdown timer armed (%d seconds).\n", ctx->timeout_seconds);
            }
        } else {
            /* Active connections -> cancel timer if armed */
            if (ctx->timer_source_id != 0) {
                g_source_remove(ctx->timer_source_id);
                ctx->timer_source_id = 0;
                ctx->state->timer_armed = FALSE;
                ctx->state->deadline_epoch = 0;
                g_print("[sys-bt daemon] Device connected (%d active). Auto-powerdown timer cancelled.\n", ctx->state->connected_count);
            }
        }
    } else {
        /* Radio is powered off -> timer must be disarmed */
        if (ctx->timer_source_id != 0) {
            g_source_remove(ctx->timer_source_id);
            ctx->timer_source_id = 0;
        }
        ctx->state->timer_armed = FALSE;
        ctx->state->deadline_epoch = 0;
    }

    ctx->state->daemon_active = TRUE;
    ctx->state->daemon_pid = getpid();
    ctx->state->timeout_seconds = ctx->timeout_seconds;
    bt_write_state_file(ctx->state);
}

static gboolean on_idle_timeout(gpointer user_data) {
    DaemonContext *ctx = (DaemonContext *)user_data;
    ctx->timer_source_id = 0;
    ctx->state->timer_armed = FALSE;
    ctx->state->deadline_epoch = 0;

    /* Re-verify state directly before powering down */
    bt_query_system_state(ctx->conn, ctx->state);

    if (ctx->state->connected_count == 0 && ctx->state->has_adapter && ctx->state->adapter.powered) {
        g_print("[sys-bt daemon] Inactivity timeout expired (%d seconds). Powering down Bluetooth radio...\n", ctx->timeout_seconds);

        /* 1. Turn off adapter via BlueZ D-Bus */
        bt_adapter_set_powered(ctx->conn, ctx->state->adapter.path, FALSE);

        /* 2. Soft-block rfkill to eliminate radio power draw */
        bt_rfkill_set_blocked(TRUE);

        /* 3. Emit notification */
        bt_notify("Bluetooth Powered Off", "Turned off radio to conserve battery", "bluetooth-disabled");

        ctx->state->adapter.powered = FALSE;
        ctx->state->rfkill_blocked = TRUE;
        bt_write_state_file(ctx->state);
    } else {
        g_print("[sys-bt daemon] Timeout expired but conditions not met (connected=%d, powered=%d). Skipping powerdown.\n",
                ctx->state->connected_count, ctx->state->has_adapter ? ctx->state->adapter.powered : 0);
    }

    return G_SOURCE_REMOVE;
}

static void on_device_properties_changed(GDBusConnection *conn,
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

    DaemonContext *ctx = (DaemonContext *)user_data;

    const gchar *iface;
    GVariant *changed_props;
    GVariant *invalidated_props;
    g_variant_get(parameters, "(&s@a{sv}@as)", &iface, &changed_props, &invalidated_props);

    if (g_strcmp0(iface, BLUEZ_IFACE_DEVICE) == 0) {
        GVariantIter iter;
        g_variant_iter_init(&iter, changed_props);
        const gchar *key;
        GVariant *val;
        gboolean connected_changed = FALSE;

        while (g_variant_iter_next(&iter, "{&sv}", &key, &val)) {
            if (g_strcmp0(key, "Connected") == 0) {
                gboolean is_conn = g_variant_get_boolean(val);
                g_print("[sys-bt daemon] Device %s Connected changed -> %s\n", object_path, is_conn ? "true" : "false");
                connected_changed = TRUE;
            }
            g_variant_unref(val);
        }

        if (connected_changed) {
            sync_daemon_state(ctx);
        }
    }

    g_variant_unref(changed_props);
    g_variant_unref(invalidated_props);
}

static void on_adapter_properties_changed(GDBusConnection *conn,
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

    DaemonContext *ctx = (DaemonContext *)user_data;

    const gchar *iface;
    GVariant *changed_props;
    GVariant *invalidated_props;
    g_variant_get(parameters, "(&s@a{sv}@as)", &iface, &changed_props, &invalidated_props);

    if (g_strcmp0(iface, BLUEZ_IFACE_ADAPTER) == 0) {
        GVariantIter iter;
        g_variant_iter_init(&iter, changed_props);
        const gchar *key;
        GVariant *val;
        gboolean power_changed = FALSE;

        while (g_variant_iter_next(&iter, "{&sv}", &key, &val)) {
            if (g_strcmp0(key, "Powered") == 0) {
                gboolean is_pow = g_variant_get_boolean(val);
                g_print("[sys-bt daemon] Adapter %s Powered changed -> %s\n", object_path, is_pow ? "true" : "false");
                power_changed = TRUE;
            }
            g_variant_unref(val);
        }

        if (power_changed) {
            sync_daemon_state(ctx);
        }
    }

    g_variant_unref(changed_props);
    g_variant_unref(invalidated_props);
}

static void on_interfaces_added(GDBusConnection *conn,
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
    (void)parameters;

    DaemonContext *ctx = (DaemonContext *)user_data;
    g_print("[sys-bt daemon] Interfaces added on %s\n", object_path);
    sync_daemon_state(ctx);
}

static void on_interfaces_removed(GDBusConnection *conn,
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
    (void)parameters;

    DaemonContext *ctx = (DaemonContext *)user_data;
    g_print("[sys-bt daemon] Interfaces removed on %s\n", object_path);
    sync_daemon_state(ctx);
}

static gboolean on_unix_signal(gpointer user_data) {
    DaemonContext *ctx = (DaemonContext *)user_data;
    g_print("\n[sys-bt daemon] Signal received, shutting down gracefully...\n");
    g_main_loop_quit(ctx->loop);
    return G_SOURCE_REMOVE;
}

int cmd_daemon(int timeout_seconds) {
    if (timeout_seconds <= 0) {
        timeout_seconds = SYS_BT_DEFAULT_TIMEOUT;
    }

    /* Check if already running */
    BtSystemState *tmp_state = bt_system_state_new();
    if (bt_read_state_file(tmp_state) && tmp_state->daemon_active) {
        g_printerr("[sys-bt] Daemon is already running (PID: %d)\n", (int)tmp_state->daemon_pid);
        bt_system_state_free(tmp_state);
        return 1;
    }
    bt_system_state_free(tmp_state);

    GError *error = NULL;
    GDBusConnection *conn = g_bus_get_sync(G_BUS_TYPE_SYSTEM, NULL, &error);
    if (!conn) {
        g_printerr("[sys-bt daemon] Failed to connect to system D-Bus: %s\n", error ? error->message : "unknown");
        if (error) g_error_free(error);
        return 1;
    }

    DaemonContext ctx;
    memset(&ctx, 0, sizeof(ctx));
    ctx.conn = conn;
    ctx.loop = g_main_loop_new(NULL, FALSE);
    ctx.state = bt_system_state_new();
    ctx.timeout_seconds = timeout_seconds;

    /* Subscribe to Device PropertiesChanged */
    guint sub_dev = g_dbus_connection_signal_subscribe(
        conn,
        BLUEZ_BUS_NAME,
        BLUEZ_IFACE_PROPERTIES,
        "PropertiesChanged",
        NULL,
        BLUEZ_IFACE_DEVICE,
        G_DBUS_SIGNAL_FLAGS_NONE,
        on_device_properties_changed,
        &ctx,
        NULL
    );

    /* Subscribe to Adapter PropertiesChanged */
    guint sub_adp = g_dbus_connection_signal_subscribe(
        conn,
        BLUEZ_BUS_NAME,
        BLUEZ_IFACE_PROPERTIES,
        "PropertiesChanged",
        NULL,
        BLUEZ_IFACE_ADAPTER,
        G_DBUS_SIGNAL_FLAGS_NONE,
        on_adapter_properties_changed,
        &ctx,
        NULL
    );

    /* Subscribe to ObjectManager InterfacesAdded / Removed */
    guint sub_added = g_dbus_connection_signal_subscribe(
        conn,
        BLUEZ_BUS_NAME,
        BLUEZ_IFACE_OBJ_MANAGER,
        "InterfacesAdded",
        NULL,
        NULL,
        G_DBUS_SIGNAL_FLAGS_NONE,
        on_interfaces_added,
        &ctx,
        NULL
    );

    guint sub_removed = g_dbus_connection_signal_subscribe(
        conn,
        BLUEZ_BUS_NAME,
        BLUEZ_IFACE_OBJ_MANAGER,
        "InterfacesRemoved",
        NULL,
        NULL,
        G_DBUS_SIGNAL_FLAGS_NONE,
        on_interfaces_removed,
        &ctx,
        NULL
    );

    /* Clean signal exit */
    guint sig_int = g_unix_signal_add(SIGINT, on_unix_signal, &ctx);
    guint sig_term = g_unix_signal_add(SIGTERM, on_unix_signal, &ctx);

    g_print("[sys-bt daemon] Started event-driven daemon (PID: %d, timeout: %ds)\n", (int)getpid(), timeout_seconds);

    /* Initial state sync */
    sync_daemon_state(&ctx);

    /* Run event loop (zero polling epoll) */
    g_main_loop_run(ctx.loop);

    /* Cleanup */
    if (ctx.timer_source_id != 0) {
        g_source_remove(ctx.timer_source_id);
    }
    g_source_remove(sig_int);
    g_source_remove(sig_term);
    g_dbus_connection_signal_unsubscribe(conn, sub_dev);
    g_dbus_connection_signal_unsubscribe(conn, sub_adp);
    g_dbus_connection_signal_unsubscribe(conn, sub_added);
    g_dbus_connection_signal_unsubscribe(conn, sub_removed);

    bt_remove_state_file();
    bt_system_state_free(ctx.state);
    g_main_loop_unref(ctx.loop);
    g_object_unref(conn);

    g_print("[sys-bt daemon] Stopped cleanly.\n");
    return 0;
}
